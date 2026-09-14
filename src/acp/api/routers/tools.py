"""Tool registry + governed invocation."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from acp.api.deps import get_container, get_session, get_tenant
from acp.api.routers._common import http_error
from acp.api.schemas import ToolCreate, ToolInvoke
from acp.core.container import AppContainer
from acp.core.errors import ApprovalRequired
from acp.core.tenant import TenantContext
from acp.core.utils import new_id
from acp.db.models import Tool
from acp.orchestrator import service as orch

router = APIRouter(prefix="/tools", tags=["tools"])


def _to_dict(row: Tool) -> dict:
    return {
        "id": row.id, "tenant_id": row.tenant_id, "name": row.name,
        "description": row.description, "version": row.version,
        "risk_class": row.risk_class, "schema": row.schema, "auth": row.auth,
        "cost_per_call": row.cost_per_call, "owner": row.owner,
        "metadata": row.metadata_, "created_at": row.created_at.isoformat(),
    }


@router.post("", status_code=201)
def create_tool(body: ToolCreate, session: Session = Depends(get_session),
                tenant: TenantContext = Depends(get_tenant)):
    if body.risk_class not in ("low", "medium", "high", "critical"):
        from fastapi import HTTPException
        raise HTTPException(400, "risk_class must be low|medium|high|critical")
    row = Tool(
        id=new_id(), tenant_id=tenant.tenant_id, name=body.name,
        description=body.description, risk_class=body.risk_class,
        schema=body.tool_schema, auth=body.auth, cost_per_call=body.cost_per_call,
        owner=body.owner, metadata_=body.metadata,
    )
    session.add(row)
    session.commit()
    return _to_dict(row)


@router.get("")
def list_tools(session: Session = Depends(get_session),
               tenant: TenantContext = Depends(get_tenant)):
    return {"items": [_to_dict(t) for t in orch.list_tools(session, tenant.tenant_id)]}


@router.get("/{tool_id}")
def get_tool(tool_id: str, session: Session = Depends(get_session),
             tenant: TenantContext = Depends(get_tenant)):
    try:
        return _to_dict(orch.get_tool(session, tenant.tenant_id, tool_id))
    except Exception as exc:
        raise http_error(exc) from exc


@router.post("/{tool_id}/invoke")
def invoke_tool(tool_id: str, body: ToolInvoke,
                session: Session = Depends(get_session),
                tenant: TenantContext = Depends(get_tenant),
                container: AppContainer = Depends(get_container)):
    """Governed invocation: 200 {result, audit_seq} | 403 {decision, reason} |
    202 {approval_id} when human approval is required.

    agent_id is required when task_id is not given (no ambient authority:
    the caller must name the principal the call executes as).
    """
    agent_id = body.agent_id
    if body.task_id and not agent_id:
        try:
            task = orch.get_task(session, tenant.tenant_id, body.task_id)
            agent_id = task.agent_id
        except Exception as exc:
            raise http_error(exc) from exc
    if not agent_id:
        from fastapi import HTTPException
        raise HTTPException(400, "agent_id is required when task_id is not given")
    try:
        # Explicit composite authority (never ambient): the control plane mints a
        # narrow, short-lived delegation for THIS tenant + agent + tool (+ task).
        delegation = container.delegation_issuer.issue(
            tenant_id=tenant.tenant_id, subject=tenant.principal,
            actor_agent_id=agent_id,
            task_id=body.task_id or f"direct-{new_id()}",
            scope_tools=[tool_id], ttl_seconds=900,
            audience=container.delegation_issuer.AUDIENCE)
        out = orch.authorize_tool_call(
            session, container, tenant_id=tenant.tenant_id, agent_id=agent_id,
            tool_id=tool_id, args=body.args, principal=tenant.principal,
            task_id=body.task_id, delegation_token=delegation["token"])
        session.commit()
        return {"result": out["result"], "audit_seq": out["audit_seq"]}
    except ApprovalRequired as exc:
        session.commit()
        raise http_error(exc) from exc
    except Exception as exc:
        raise http_error(exc) from exc
