"""Orchestrator: task lifecycle + the governed execute pipeline.

POST /tasks/{id}/execute runs, in order, each stage emitting events + audit
entries + OTel spans:
  1. Task admission (policy) -> denied stops.
  2. Planner -> plan -> TaskPlanned.
  3. Router -> agent+model -> TaskRouted.
  4. Plan admission (policy on plan).
  5. Risk engine scores plan+tools.
  6. Approval gate -> ApprovalRequested + pause at awaiting_approval.
     Resume: approve -> continue; reject/expire -> denied.
  7. Workflow runner; EVERY tool call through authorize_tool_call
     (identity + delegation + policy + risk + budget) -> brokered credential
     -> LocalFunctionToolExecutor; idempotency keys; checkpoint before
     side effects.
  8. Cost metered per step; budget 100% -> deny + kill switch (CostThresholdExceeded).
  9. TaskCompleted / TaskFailed with full audit chain.
"""

from __future__ import annotations

import logging
from typing import Any

from opentelemetry import trace
from sqlalchemy import select
from sqlalchemy.orm import Session

from acp.agents import registry as agent_registry
from acp.core.errors import (
    ApprovalRequired,
    BudgetExhausted,
    NotFound,
    PolicyDenied,
    SecurityViolation,
)
from acp.core.utils import new_id, utcnow
from acp.cost import check_budget, record_cost, total_cost
from acp.db.models import Approval as ApprovalRow
from acp.db.models import Delegation, Task, TaskStep, Tool
from acp.events import record_event
from acp.governance import approvals as approval_svc
from acp.governance.permissions import check_abac
from acp.models import build_provider
from acp.observability import correlation_ctx
from acp.state import TASK_LIFECYCLE, transition

log = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

TERMINAL = {"completed", "failed", "cancelled", "denied"}


# ---------------------------------------------------------------- helpers

def _tenant_policy(session: Session, tenant_id: str) -> dict:
    from acp.db.models import PolicyBundle

    row = session.execute(
        select(PolicyBundle)
        .where(PolicyBundle.tenant_id == tenant_id)
        .order_by(PolicyBundle.version.desc())
        .limit(1)
    ).scalars().first()
    return dict(row.content) if row else {}


def _audit(container, session: Session, *, tenant_id: str, task_id: str | None = None,
           event_type: str, actor: dict,
           action: str, inputs=None, policy=None, risk=None,
           delegation_chain: list | None = None, result: str = ""):
    return container.audit_ledger.append(
        session, tenant_id=tenant_id, task_id=task_id, event_type=event_type, actor=actor, action=action,
        inputs=inputs, policy=policy, risk=risk,
        delegation_chain=delegation_chain or [], result=result,
    )


def _emit(container, session: Session, *, tenant_id: str, event_type: str,
          task_id: str | None = None, agent_id: str | None = None, payload: dict | None = None):
    return record_event(
        session, container.event_bus, tenant_id=tenant_id, event_type=event_type,
        task_id=task_id, agent_id=agent_id,
        correlation_id=correlation_ctx.get(), payload=payload or {},
    )


def _actor(principal: str, agent_id: str | None = None) -> dict:
    return {"type": "api", "principal": principal, "agent_id": agent_id}


def _tool_dict(row: Tool) -> dict:
    return {
        "id": row.id, "tenant_id": row.tenant_id, "name": row.name,
        "description": row.description, "version": row.version,
        "risk_class": row.risk_class, "schema": row.schema, "auth": row.auth,
        "cost_per_call": row.cost_per_call, "owner": row.owner,
        "metadata": row.metadata_,
    }


def _agent_dict(row) -> dict:
    return {
        "id": row.id, "tenant_id": row.tenant_id, "name": row.name,
        "status": row.status, "capabilities": row.capabilities,
        "model_config": row.model_config, "tool_ids": row.tool_ids,
        "max_risk_level": row.max_risk_level, "version": row.version,
    }


def get_tool(session: Session, tenant_id: str, tool_id: str) -> Tool:
    row = session.execute(
        select(Tool).where(Tool.id == tool_id, Tool.tenant_id == tenant_id)
    ).scalars().first()
    if row is None:
        # Distinguish "not found" from "exists in another tenant" (security event).
        other = session.execute(select(Tool.id).where(Tool.id == tool_id)).scalar_one_or_none()
        if other is not None:
            raise SecurityViolation(f"cross-tenant tool access attempt: {tool_id}")
        raise NotFound("tool not found")
    return row


def list_tools(session: Session, tenant_id: str) -> list[Tool]:
    return list(session.execute(
        select(Tool).where(Tool.tenant_id == tenant_id).order_by(Tool.created_at)
    ).scalars().all())


# ---------------------------------------------------------------- task CRUD

def create_task(session: Session, container, *, tenant_id: str, goal: str,
                task_input: dict | None = None, agent_id: str | None = None,
                budget_limit: float | None = None, principal: str = "api") -> Task:
    with tracer.start_as_current_span("acp.task.create", attributes={"acp.task.goal": goal[:200]}):
        if agent_id:
            # Tenant-scoped lookup; cross-tenant agent id -> SecurityViolation.
            try:
                agent_registry.get_agent(session, tenant_id, agent_id)
            except NotFound:
                from sqlalchemy import select as _select

                from acp.db.models import Agent as _Agent
                other = session.execute(_select(_Agent.id).where(_Agent.id == agent_id)).scalar_one_or_none()
                if other is not None:
                    raise SecurityViolation("cross-tenant agent reference blocked") from None
                raise
        task = Task(
            id=new_id(), tenant_id=tenant_id, goal=goal, input=task_input or {},
            agent_id=agent_id, status="created", budget_limit=budget_limit,
            correlation_id=correlation_ctx.get(),
        )
        session.add(task)
        if budget_limit is not None:
            # A task budget_limit is enforced, not decorative: materialize the
            # budget row the cost choke points check against.
            from acp.db.models import Budget as _Budget
            session.add(_Budget(id=new_id(), tenant_id=tenant_id, scope="task",
                                scope_id=task.id, limit=float(budget_limit)))
        session.flush()
        _audit(container, session, tenant_id=tenant_id, task_id=task.id, event_type="TaskCreated",
               actor=_actor(principal), action="task.create",
               inputs={"goal": goal, "agent_id": agent_id}, result="created")
        _emit(container, session, tenant_id=tenant_id, event_type="TaskCreated",
              task_id=task.id, agent_id=agent_id, payload={"goal": goal})
        session.flush()
        return task


def get_task(session: Session, tenant_id: str, task_id: str) -> Task:
    row = session.execute(
        select(Task).where(Task.id == task_id, Task.tenant_id == tenant_id)
    ).scalars().first()
    if row is None:
        other = session.execute(select(Task.id).where(Task.id == task_id)).scalar_one_or_none()
        if other is not None:
            raise SecurityViolation("cross-tenant task access attempt")
        raise NotFound("task not found")
    return row


def list_tasks(session: Session, tenant_id: str, status: str | None = None) -> list[Task]:
    q = select(Task).where(Task.tenant_id == tenant_id).order_by(Task.created_at.desc())
    if status:
        q = q.where(Task.status == status)
    return list(session.execute(q).scalars().all())


def task_to_dict(session: Session, task: Task) -> dict:
    approvals = session.execute(
        select(ApprovalRow).where(ApprovalRow.task_id == task.id).order_by(ApprovalRow.requested_at)
    ).scalars().all()
    return {
        "id": task.id, "tenant_id": task.tenant_id, "goal": task.goal, "input": task.input,
        "agent_id": task.agent_id, "status": task.status, "plan": task.plan,
        "risk_assessment": task.risk_assessment, "cost_estimate": task.cost_estimate,
        "cost_incurred": round(task.cost_incurred, 4), "budget_limit": task.budget_limit,
        "error": task.error, "correlation_id": task.correlation_id,
        "approvals": [approval_svc.to_dict(a) for a in approvals],
        "created_at": task.created_at.isoformat(), "updated_at": task.updated_at.isoformat(),
    }


def cancel_task(session: Session, container, *, tenant_id: str, task_id: str, principal: str) -> Task:
    """Kill switch: freeze the task, revoke its delegation chain."""
    with tracer.start_as_current_span("acp.task.cancel", attributes={"acp.task.id": task_id}):
        task = get_task(session, tenant_id, task_id)
        if task.status not in TERMINAL:
            transition(TASK_LIFECYCLE, task.status, "cancelled", what="task")
            task.status = "cancelled"
            # Revoke delegation chain (kill switch).
            rows = session.execute(
                select(Delegation).where(Delegation.task_id == task_id, Delegation.revoked.is_(False))
            ).scalars().all()
            for d in rows:
                d.revoked = True
                container.revoked_delegation_jtis.add(d.jti)
            _audit(container, session, tenant_id=tenant_id, event_type="TaskCancelled",
                   actor=_actor(principal, task.agent_id), action="task.cancel",
                   inputs={"task_id": task_id}, result="cancelled")
            _emit(container, session, tenant_id=tenant_id, event_type="TaskCancelled",
                  task_id=task_id, agent_id=task.agent_id, payload={"revoked_delegations": len(rows)})
            session.flush()
        return task


# ---------------------------------------------------------------- authorize_tool_call (choke point #3)

def authorize_tool_call(
    session: Session, container, *, tenant_id: str, agent_id: str, tool_id: str,
    args: dict, principal: str, task_id: str | None = None,
    delegation_token: str | None = None, data_classification: str = "internal",
    plan_approval: dict | None = None,
) -> dict[str, Any]:
    """The per-tool-call governance choke point.

    Order: identity -> grant -> delegation -> policy -> ABAC -> risk -> budget
    -> broker credential -> execute. Any failure denies (fail closed) and is
    audited. Returns {"result": ..., "audit_seq": ..., "lease_id": ...}.

    plan_approval ({"id", "status", "tool_ids"}): supplied ONLY by the workflow
    executor for steps of a human-approved plan, so the policy engine can see
    the approval requirement was already satisfied. Denials still win; direct
    tool invocation never passes one.
    """
    agent_row = agent_registry.get_agent(session, tenant_id, agent_id)
    tool_row = get_tool(session, tenant_id, tool_id)
    agent = _agent_dict(agent_row)
    tool = _tool_dict(tool_row)
    actor = _actor(principal, agent_id)
    tenant_policy = _tenant_policy(session, tenant_id)

    def _deny(event_type: str, reason: str, reasons: list[str], policy=None, risk=None):
        _audit(container, session, tenant_id=tenant_id, task_id=task_id, event_type=event_type, actor=actor,
               action="tool.invoke", inputs={"tool_id": tool_id, "args": args, "task_id": task_id},
               policy=policy, risk=risk, result="denied")
        _emit(container, session, tenant_id=tenant_id, event_type=event_type,
              task_id=task_id, agent_id=agent_id,
              payload={"tool_id": tool_id, "reason": reason})
        session.flush()
        # Denial records must survive even if the outer request later rolls back:
        # a deny decision is always durable (fail-closed auditability).
        session.commit()

    # 1. identity: agent must be in an executable state.
    if agent["status"] not in ("activated", "monitoring", "evaluating"):
        _deny("PermissionDenied", f"agent status {agent['status']} cannot invoke tools",
              [f"agent status {agent['status']} cannot invoke tools"])
        raise PolicyDenied(f"agent {agent_id} is not activated (status={agent['status']})")

    # 2. grant: tool must be granted to this agent VERSION (least privilege).
    if tool_id not in set(agent.get("tool_ids") or []):
        _deny("PermissionDenied", "tool not granted to agent",
              [f"tool {tool['name']!r} not in agent {agent['name']!r} tool_ids"])
        raise PolicyDenied(f"tool {tool['name']!r} not granted to agent (privilege escalation blocked)")

    # 3. delegation: valid token, tool within scope.
    delegation_chain: list = []
    if delegation_token:
        claims = container.delegation_issuer.validate(
            delegation_token, tenant_id=tenant_id,
            revoked_jtis=container.revoked_delegation_jtis,
        )
        if tool_id not in set(claims.get("scope_tools") or []):
            _deny("PermissionDenied", "tool outside delegation scope",
                  ["tool not within delegation scope"])
            raise PolicyDenied("delegation token does not cover this tool")
        delegation_chain = [{"jti": claims.get("jti"), "sub": claims.get("sub"),
                             "act": claims.get("act"), "parent_jti": claims.get("parent_jti")}]

    # 4. policy (PDP).
    policy_ctx = {
        "kind": "tool_invoke", "tenant_id": tenant_id, "agent": agent, "tool": tool,
        "tools": [tool], "args": args, "tenant_policy": tenant_policy,
        "data_classification": data_classification,
        "plan_approval": plan_approval,  # None unless executing an approved plan
    }
    decision = container.policy_engine.evaluate(policy_ctx)
    policy_ref = {"decision": decision.decision, "version_hash": decision.policy_version_hash,
                  "reasons": decision.reasons}
    _audit(container, session, tenant_id=tenant_id, task_id=task_id, event_type="PolicyEvaluated", actor=actor,
           action="tool.invoke", inputs={"tool_id": tool_id, "args": args},
           policy=policy_ref, result=decision.decision)
    if decision.decision == "deny":
        _deny("PermissionDenied", "; ".join(decision.reasons), decision.reasons, policy=policy_ref)
        raise PolicyDenied(f"policy denied tool invoke: {'; '.join(decision.reasons)}", decision.reasons)
    if decision.decision == "require_approval":
        approval = approval_svc.create_approval(
            session, tenant_id=tenant_id, task_id=task_id,
            action_summary=f"invoke tool {tool['name']}",
            action_detail={"tool_id": tool_id, "args": args, "agent_id": agent_id,
                           "policy_decision": decision.decision,
                           "policy_version_hash": decision.policy_version_hash,
                           "policy_reasons": decision.reasons},
            risk_score=0.0, risk_level="medium", reasons=decision.reasons,
            ttl_seconds=container.settings.approval_ttl_seconds,
        )
        _emit(container, session, tenant_id=tenant_id, event_type="ApprovalRequested",
              task_id=task_id, agent_id=agent_id,
              payload={"approval_id": approval.id, "tool_id": tool_id})
        session.flush()
        raise ApprovalRequired(approval.id)

    # 5. ABAC.
    ok, abac_reasons = check_abac(
        agent=agent, tool=tool,
        delegation_scope_tools=(delegation_chain and [tool_id]) or ([tool_id] if delegation_token else []),
        data_classification=data_classification,
    )
    if not ok:
        _deny("PermissionDenied", "; ".join(abac_reasons), abac_reasons, policy=policy_ref)
        raise PolicyDenied(f"ABAC denied: {'; '.join(abac_reasons)}", abac_reasons)

    # 6. risk (deterministic floor; model hook may only raise).
    risk = container.risk_engine.assess({
        "tools": [tool], "goal": "", "estimated_cost": float(tool.get("cost_per_call") or 0.0),
    })
    risk_ref = {"score": risk.risk_score, "level": risk.risk_level}
    _audit(container, session, tenant_id=tenant_id, task_id=task_id, event_type="RiskAssessed", actor=actor,
           action="tool.invoke", inputs={"tool_id": tool_id}, risk=risk_ref, result=risk.risk_level)

    # 7. budget at the choke point.
    estimated = float(tool.get("cost_per_call") or 0.0) + 0.002
    try:
        check_budget(session, tenant_id=tenant_id, task_id=task_id, agent_id=agent_id,
                     additional=estimated,
                     alert_thresholds=[float(x) for x in container.settings.budget_alert_thresholds.split(",")])
    except BudgetExhausted as exc:
        _deny("PermissionDenied", str(exc), [str(exc)], policy=policy_ref, risk=risk_ref)
        _emit(container, session, tenant_id=tenant_id, event_type="CostThresholdExceeded",
              task_id=task_id, agent_id=agent_id, payload={"reason": str(exc)})
        raise

    # 8. broker credential (server-side injection; never agent-visible).
    lease = container.secret_broker.issue(tenant_id, tool_id, tool_name=tool.get("name", ""))

    # 9. execute.
    with tracer.start_as_current_span("acp.tool.invoke", attributes={
        "acp.task.id": task_id or "", "acp.tool.id": tool_id,
        "acp.policy.decision": decision.decision, "acp.risk.level": risk.risk_level,
    }):
        try:
            result = container.tool_executor.invoke(tool, args, credential=lease)
        except Exception as exc:
            _audit(container, session, tenant_id=tenant_id, task_id=task_id, event_type="ToolFailed", actor=actor,
                   action="tool.invoke", inputs={"tool_id": tool_id, "args": args},
                   policy=policy_ref, risk=risk_ref, result="failed")
            _emit(container, session, tenant_id=tenant_id, event_type="ToolFailed",
                  task_id=task_id, agent_id=agent_id,
                  payload={"tool_id": tool_id, "error": str(exc)})
            session.flush()
            raise
        finally:
            container.secret_broker.revoke(lease["lease_id"])

    # 10. meter cost.
    record_cost(session, tenant_id=tenant_id, amount=estimated, task_id=task_id,
                agent_id=agent_id, tool_id=tool_id, model=None,
                detail={"tool": tool["name"]})
    audit_row = _audit(
        container, session, tenant_id=tenant_id, task_id=task_id, event_type="ToolInvoked", actor=actor,
        action="tool.invoke", inputs={"tool_id": tool_id, "args": args, "task_id": task_id},
        policy=policy_ref, risk=risk_ref, delegation_chain=delegation_chain, result="ok",
    )
    _emit(container, session, tenant_id=tenant_id, event_type="ToolInvoked",
          task_id=task_id, agent_id=agent_id,
          payload={"tool_id": tool_id, "audit_seq": audit_row.seq})
    session.flush()
    return {"result": result, "audit_seq": audit_row.seq, "lease_id": lease["lease_id"]}

# ---------------------------------------------------------------- execute pipeline

def _set_status(session: Session, task: Task, target: str) -> None:
    transition(TASK_LIFECYCLE, task.status, target, what="task")
    task.status = target
    task.heartbeat_at = utcnow()
    session.flush()


def execute_task(session: Session, container, *, tenant_id: str, task_id: str,
                 principal: str = "api") -> Task:
    """Run the governed pipeline to completion OR to the first approval pause.

    Resume path: call again after approving; an approved, unexpired approval
    continues the workflow from the first pending step. Reject/expire -> denied.
    """
    task = get_task(session, tenant_id, task_id)
    if task.status in TERMINAL:
        return task
    settings = container.settings
    actor = _actor(principal, task.agent_id)
    tenant_policy = _tenant_policy(session, tenant_id)

    # Expiry sweep first: approval timeout == DENY.
    expired = approval_svc.sweep_expired(session, tenant_id)
    for ap in expired:
        if ap.task_id == task_id and task.status == "awaiting_approval":
            _deny_task(session, container, task, actor, "approval expired (timeout == DENY)")
            _emit(container, session, tenant_id=tenant_id, event_type="ApprovalExpired",
                  task_id=task_id, payload={"approval_id": ap.id})
            session.flush()
            return task

    # ---- Resume path: awaiting_approval with a decided approval ----
    if task.status == "awaiting_approval":
        ap = session.execute(
            select(ApprovalRow).where(ApprovalRow.task_id == task_id)
            .order_by(ApprovalRow.requested_at.desc()).limit(1)
        ).scalars().first()
        if ap is None or ap.status == "requested":
            return task  # still waiting
        if ap.status == "approved":
            _emit(container, session, tenant_id=tenant_id, event_type="ApprovalGranted",
                  task_id=task_id, payload={"approval_id": ap.id, "decided_by": ap.decided_by})
            _audit(container, session, tenant_id=tenant_id, event_type="ApprovalGranted",
                   actor={"type": "human", "principal": ap.decided_by}, action="approval.decide",
                   inputs={"approval_id": ap.id}, result="approved")
            # The human approved this exact plan: its tool invocations must not
            # demand a second approval at the per-tool choke point. Coverage is
            # derived server-side from the approval's own action_detail (the
            # approved artifact), never from client input.
            approved_plan = (ap.action_detail or {}).get("plan") or {}
            plan_approval = {
                "id": ap.id,
                "status": "approved",
                "tool_ids": [s.get("tool_id") for s in approved_plan.get("steps", [])
                             if s.get("tool_id")],
            }
            return _run_workflow(session, container, task, principal,
                                 plan_approval=plan_approval)
        # rejected or expired
        _deny_task(session, container, task, actor, f"approval {ap.status}")
        _emit(container, session, tenant_id=tenant_id,
              event_type="ApprovalRejected" if ap.status == "rejected" else "ApprovalExpired",
              task_id=task_id, payload={"approval_id": ap.id})
        session.flush()
        return task

    if task.status not in ("created",):
        # execute is only entered from created (fresh) or awaiting_approval (resume)
        return task

    with tracer.start_as_current_span("acp.task.execute", attributes={
        "acp.task.id": task_id, "acp.tenant.id": tenant_id,
    }):
        # ---- 1. Task admission ----
        with tracer.start_as_current_span("acp.stage.admission"):
            candidates = [_agent_dict(a) for a in agent_registry.list_agents(session, tenant_id)]
            if task.agent_id:
                candidates = [c for c in candidates if c["id"] == task.agent_id]
            admission = container.policy_engine.evaluate({
                "kind": "task_admission", "tenant_id": tenant_id,
                "agent": candidates[0] if candidates else {},
                "goal": task.goal, "tenant_policy": tenant_policy,
            })
            _audit(container, session, tenant_id=tenant_id, task_id=task.id,
                   event_type="PolicyEvaluated",
                   actor=actor, action="task.admission", inputs={"goal": task.goal},
                   policy={"decision": admission.decision,
                           "version_hash": admission.policy_version_hash,
                           "reasons": admission.reasons}, result=admission.decision)
            if admission.decision == "deny":
                _deny_task(session, container, task, actor,
                            f"admission denied: {'; '.join(admission.reasons)}")
                session.flush()
                return task
            _set_status(session, task, "admitted")

        # ---- 2. Planner ----
        with tracer.start_as_current_span("acp.stage.plan"):
            if task.agent_id:
                agent_row = agent_registry.get_agent(session, tenant_id, task.agent_id)
            else:
                agent_row = None
            tools = [_tool_dict(t) for t in list_tools(session, tenant_id)]
            # Plan with a provisional agent (router refines); use first activated or any.
            provisional = _agent_dict(agent_row) if agent_row else (
                next((c for c in candidates if c["status"] in ("activated", "monitoring")), None)
                or (candidates[0] if candidates else {"tool_ids": [], "model_config": {}})
            )
            plan = container.planner.plan(
                goal=task.goal, task_input=task.input, agent=provisional, tools=tools)
            task.plan = plan
            task.cost_estimate = float(plan.get("estimated_cost") or 0.0)
            _set_status(session, task, "planned")
            _audit(container, session, tenant_id=tenant_id, task_id=task.id, event_type="TaskPlanned",
                   actor=actor, action="task.plan", inputs={"goal": task.goal},
                   result=f"{len(plan['steps'])} steps")
            _emit(container, session, tenant_id=tenant_id, event_type="TaskPlanned",
                  task_id=task_id, payload={"steps": len(plan["steps"]),
                                            "estimated_cost": task.cost_estimate})
            session.flush()

        # ---- 3. Router ----
        with tracer.start_as_current_span("acp.stage.route"):
            if task.agent_id:
                agent_row = agent_registry.get_agent(session, tenant_id, task.agent_id)
                ranked = container.router.rank(
                    goal=task.goal, plan=plan, candidates=[_agent_dict(agent_row)],
                    tools=tools, policy_engine=container.policy_engine,
                    tenant_policy=tenant_policy)
                if not ranked or ranked[0]["policy_decision"] == "deny":
                    _deny_task(session, container, task, actor, "router: requested agent denied by policy")
                    session.flush()
                    return task
                chosen = _agent_dict(agent_row)
                route_info = ranked[0]
            else:
                chosen_rank = container.router.select(
                    goal=task.goal, plan=plan, candidates=candidates,
                    tools=tools, policy_engine=container.policy_engine,
                    tenant_policy=tenant_policy)
                if chosen_rank is None:
                    _deny_task(session, container, task, actor,
                                "router: no eligible agent (policy/capability)")
                    session.flush()
                    return task
                agent_row = agent_registry.get_agent(session, tenant_id, chosen_rank["agent_id"])
                chosen = _agent_dict(agent_row)
                route_info = chosen_rank
            task.agent_id = chosen["id"]
            actor = _actor(principal, chosen["id"])
            _set_status(session, task, "routed")
            _audit(container, session, tenant_id=tenant_id, task_id=task.id, event_type="TaskRouted",
                   actor=actor, action="task.route",
                   inputs={"goal": task.goal, "plan_steps": len(plan["steps"])},
                   policy={"decision": route_info["policy_decision"]},
                   result=f"agent={chosen['id']} score={route_info['score']}")
            _emit(container, session, tenant_id=tenant_id, event_type="TaskRouted",
                  task_id=task_id, agent_id=chosen["id"],
                  payload={"score": route_info["score"], "breakdown": route_info["breakdown"]})
            session.flush()

        # ---- 4. Plan admission (policy on the plan) ----
        # ---- 5. Risk engine ----
        with tracer.start_as_current_span("acp.stage.plan_admission"):
            plan_tools = [_tool_dict(get_tool(session, tenant_id, s["tool_id"]))
                          for s in plan["steps"] if s.get("tool_id")]
            plan_decision = container.policy_engine.evaluate({
                "kind": "plan_admission", "tenant_id": tenant_id, "agent": chosen,
                "tools": plan_tools, "plan": plan,
                "cost_estimate": task.cost_estimate, "tenant_policy": tenant_policy,
            })
            risk = container.risk_engine.assess({
                "tools": plan_tools, "goal": task.goal,
                "estimated_cost": task.cost_estimate,
                "untrusted_content": bool((task.input or {}).get("untrusted_content")),
                "data_classification": (task.input or {}).get("data_classification", "internal"),
            })
            task.risk_assessment = {
                "risk_score": risk.risk_score, "risk_level": risk.risk_level,
                "requires_human_approval": risk.requires_human_approval,
                "reasons": risk.reasons, "score_breakdown": risk.score_breakdown,
            }
            _audit(container, session, tenant_id=tenant_id, task_id=task.id,
                   event_type="PolicyEvaluated",
                   actor=actor, action="plan.admission", inputs={"plan": plan},
                   policy={"decision": plan_decision.decision,
                           "version_hash": plan_decision.policy_version_hash,
                           "reasons": plan_decision.reasons},
                   risk={"score": risk.risk_score, "level": risk.risk_level},
                   result=plan_decision.decision)
            _audit(container, session, tenant_id=tenant_id, task_id=task.id, event_type="RiskAssessed",
                   actor=actor, action="plan.risk", inputs={"plan": plan},
                   risk={"score": risk.risk_score, "level": risk.risk_level},
                   result=risk.risk_level)
            _emit(container, session, tenant_id=tenant_id, event_type="RiskAssessed",
                  task_id=task_id, agent_id=chosen["id"],
                  payload={"risk_score": risk.risk_score, "risk_level": risk.risk_level,
                           "requires_human_approval": risk.requires_human_approval})
            if plan_decision.decision == "deny":
                _deny_task(session, container, task, actor,
                            f"plan denied: {'; '.join(plan_decision.reasons)}")
                session.flush()
                return task
            session.flush()

        # ---- 6. Approval gate ----
        needs_approval = (
            plan_decision.decision == "require_approval"
            or risk.requires_human_approval
            or bool(plan.get("approvals_required"))
        )
        if needs_approval:
            with tracer.start_as_current_span("acp.stage.approval_gate"):
                reasons = list(plan_decision.reasons) + list(risk.reasons)
                approval = approval_svc.create_approval(
                    session, tenant_id=tenant_id, task_id=task_id,
                    action_summary=f"execute plan: {task.goal[:120]}",
                    action_detail={
                        "plan": plan,
                        "policy_decision": plan_decision.decision,
                        "policy_reasons": plan_decision.reasons,
                        "policy_version_hash": plan_decision.policy_version_hash,
                        "agent_id": chosen["id"],
                    },
                    risk_score=risk.risk_score, risk_level=risk.risk_level,
                    reasons=reasons, ttl_seconds=settings.approval_ttl_seconds,
                )
                _set_status(session, task, "awaiting_approval")
                _audit(container, session, tenant_id=tenant_id, task_id=task.id,
                       event_type="ApprovalRequested",
                       actor=actor, action="plan.approval",
                       inputs={"plan": plan},
                       policy={"decision": plan_decision.decision,
                               "version_hash": plan_decision.policy_version_hash},
                       risk={"score": risk.risk_score, "level": risk.risk_level},
                       result=f"approval={approval.id}")
                _emit(container, session, tenant_id=tenant_id, event_type="ApprovalRequested",
                      task_id=task_id, agent_id=chosen["id"],
                      payload={"approval_id": approval.id,
                               "risk_score": risk.risk_score, "risk_level": risk.risk_level,
                               "reasons": reasons,
                               "expires_at": approval.expires_at.isoformat()})
                session.flush()
                return task  # paused: resume via approve + execute

        # ---- 7-9. Workflow execution ----
        return _run_workflow(session, container, task, principal)


def _deny_task(session: Session, container, task: Task, actor: dict, reason: str) -> None:
    if task.status not in TERMINAL:
        transition(TASK_LIFECYCLE, task.status, "denied", what="task")
        task.status = "denied"
        task.error = reason
    _audit(container, session, tenant_id=task.tenant_id, task_id=task.id,
           event_type="PermissionDenied",
           actor=actor, action="task.deny", inputs={"task_id": task.id},
           result="denied")
    _emit(container, session, tenant_id=task.tenant_id, event_type="PermissionDenied",
          task_id=task.id, agent_id=task.agent_id, payload={"reason": reason})


def _run_workflow(session: Session, container, task: Task, principal: str,
                  plan_approval: dict | None = None) -> Task:
    tenant_id = task.tenant_id
    actor = _actor(principal, task.agent_id)
    agent_row = agent_registry.get_agent(session, tenant_id, task.agent_id)
    agent = _agent_dict(agent_row)
    plan = task.plan or {"steps": []}

    with tracer.start_as_current_span("acp.stage.execute", attributes={
        "acp.task.id": task.id, "acp.agent.id": agent["id"],
        "acp.policy.decision": "allow",
    }):
        if task.status != "executing":
            _set_status(session, task, "executing")
        _emit(container, session, tenant_id=tenant_id, event_type="TaskStarted",
              task_id=task.id, agent_id=agent["id"], payload={"plan_steps": len(plan["steps"])})
        _audit(container, session, tenant_id=tenant_id, task_id=task.id, event_type="TaskStarted",
               actor=actor, action="task.execute", inputs={"task_id": task.id}, result="executing")
        session.flush()

        # Delegation token for this run: narrow-only, short-lived, tenant-bound.
        plan_tool_ids = [s["tool_id"] for s in plan["steps"] if s.get("tool_id")]
        delegation = container.delegation_issuer.issue(
            tenant_id=tenant_id, subject=principal, actor_agent_id=agent["id"],
            task_id=task.id, scope_tools=plan_tool_ids, audience="acp-tool-gateway",
            ttl_seconds=600,
        )
        from datetime import timedelta
        drow = Delegation(
            id=new_id(), tenant_id=tenant_id, jti=delegation["jti"], subject=principal,
            actor_agent_id=agent["id"], task_id=task.id, scope_tools=plan_tool_ids,
            audience="acp-tool-gateway",
            expires_at=utcnow() + timedelta(seconds=600),
        )
        session.add(drow)
        _emit(container, session, tenant_id=tenant_id, event_type="DelegationIssued",
              task_id=task.id, agent_id=agent["id"],
              payload={"jti": delegation["jti"], "scope_tools": plan_tool_ids})
        session.flush()

        step_rows = container.workflow_runner.prepare_steps(
            session, tenant_id=tenant_id, task_id=task.id, steps=plan["steps"])

        model_cfg = agent.get("model_config") or {}
        provider = build_provider(
            model_cfg.get("provider", container.settings.default_model_provider),
            model_cfg.get("model", container.settings.default_model))

        def _executor(step_row: TaskStep) -> dict[str, Any]:
            if step_row.tool_id:
                out = authorize_tool_call(
                    session, container, tenant_id=tenant_id, agent_id=agent["id"],
                    tool_id=step_row.tool_id, args=step_row.args, principal=principal,
                    task_id=task.id, delegation_token=delegation["token"],
                    plan_approval=plan_approval)
                return out["result"]
            # Reasoning step (no tool): model call, metered.
            text = provider.generate(f"goal: {task.goal}\nstep: {step_row.name}\nargs: {step_row.args}")
            record_cost(session, tenant_id=tenant_id, amount=0.002, task_id=task.id,
                        agent_id=agent["id"], model=provider.name,
                        detail={"kind": "reasoning", "step": step_row.step_id})
            return {"ok": True, "model": provider.name, "output": text}

        def _on_step(event_type: str, step_row: TaskStep, payload: dict):
            _emit(container, session, tenant_id=tenant_id, event_type=event_type,
                  task_id=task.id, agent_id=agent["id"],
                  payload={"step_id": step_row.step_id, **payload})

        try:
            outcome = container.workflow_runner.run(
                session, tenant_id=tenant_id, task=task, step_rows=step_rows,
                executor=_executor, on_step_event=_on_step)
        except ApprovalRequired as exc:
            # A step-level approval was raised mid-run: pause the workflow.
            _set_status(session, task, "awaiting_approval")
            _emit(container, session, tenant_id=tenant_id, event_type="ApprovalRequested",
                  task_id=task.id, agent_id=agent["id"],
                  payload={"approval_id": exc.approval_id, "mid_run": True})
            session.flush()
            return task
        except PolicyDenied as exc:
            # Fail closed: a denied tool call fails the task outright.
            _set_status(session, task, "failed")
            task.error = f"tool call denied: {exc}"
            _emit(container, session, tenant_id=tenant_id, event_type="TaskFailed",
                  task_id=task.id, agent_id=agent["id"],
                  payload={"error": task.error})
            _audit(container, session, tenant_id=tenant_id, task_id=task.id,
                   event_type="TaskFailed", actor=actor, action="task.execute",
                   inputs={"task_id": task.id}, result="denied")
            session.flush()
            return task
        except BudgetExhausted as exc:
            # Kill switch: freeze spend, revoke delegation, fail the task.
            _emit(container, session, tenant_id=tenant_id, event_type="CostThresholdExceeded",
                  task_id=task.id, agent_id=agent["id"], payload={"reason": str(exc)})
            _audit(container, session, tenant_id=tenant_id, task_id=task.id,
                   event_type="CostThresholdExceeded",
                   actor=actor, action="task.execute", inputs={"task_id": task.id},
                   result="budget_exhausted")
            for row in session.execute(
                select(Delegation).where(Delegation.task_id == task.id, Delegation.revoked.is_(False))
            ).scalars().all():
                row.revoked = True
                container.revoked_delegation_jtis.add(row.jti)
            transition(TASK_LIFECYCLE, task.status, "failed", what="task")
            task.status = "failed"
            task.error = f"budget exhausted (kill switch): {exc}"
            session.flush()
            return task

        if not outcome.get("completed"):
            transition(TASK_LIFECYCLE, task.status, "failed", what="task")
            task.status = "failed"
            task.error = outcome.get("error", "step failed")
            _audit(container, session, tenant_id=tenant_id, task_id=task.id, event_type="TaskFailed",
                   actor=actor, action="task.execute", inputs={"task_id": task.id},
                   result="failed")
            _emit(container, session, tenant_id=tenant_id, event_type="TaskFailed",
                  task_id=task.id, agent_id=agent["id"],
                  payload={"error": task.error, "failed_step": outcome.get("failed_step")})
            session.flush()
            return task

        task.cost_incurred = round(total_cost(session, tenant_id, task_id=task.id), 4)
        transition(TASK_LIFECYCLE, task.status, "completed", what="task")
        task.status = "completed"
        _audit(container, session, tenant_id=tenant_id, task_id=task.id, event_type="TaskCompleted",
               actor=actor, action="task.execute", inputs={"task_id": task.id},
               result="completed")
        _emit(container, session, tenant_id=tenant_id, event_type="TaskCompleted",
              task_id=task.id, agent_id=agent["id"],
              payload={"cost_incurred": task.cost_incurred,
                       "steps": len(outcome.get("results", []))})
        session.flush()
        return task
