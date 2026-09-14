"""Evaluations + ops endpoints (health, metrics, traces)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from acp import __version__
from acp.api.deps import get_session, get_tenant
from acp.api.routers._common import http_error
from acp.api.schemas import EvaluationCreate
from acp.core.tenant import TenantContext
from acp.db.models import Approval, AuditEntry, Task, TaskStep
from acp.evaluation import metric_names, run_evaluation
from acp.observability import recent_spans

router = APIRouter(tags=["evaluations", "ops"])


@router.get("/health")
def health():
    return {"status": "ok", "version": __version__}


@router.post("/evaluations", status_code=201)
def create_evaluation(body: EvaluationCreate,
                      session: Session = Depends(get_session),
                      tenant: TenantContext = Depends(get_tenant)):
    try:
        ev = run_evaluation(session, tenant.tenant_id, body.agent_id, body.task_id, body.metrics)
        session.commit()
        return {"id": ev.id, "agent_id": ev.agent_id, "task_id": ev.task_id,
                "metrics": ev.metrics, "results": ev.results, "status": ev.status,
                "created_at": ev.created_at.isoformat()}
    except Exception as exc:
        raise http_error(exc) from exc


@router.get("/evaluations/{evaluation_id}")
def get_evaluation(evaluation_id: str, session: Session = Depends(get_session),
                   tenant: TenantContext = Depends(get_tenant)):
    from acp.db.models import Evaluation
    row = session.execute(
        select(Evaluation).where(Evaluation.id == evaluation_id,
                                 Evaluation.tenant_id == tenant.tenant_id)
    ).scalars().first()
    if row is None:
        from acp.core.errors import NotFound
        raise http_error(NotFound("evaluation not found"))
    return {"id": row.id, "agent_id": row.agent_id, "task_id": row.task_id,
            "metrics": row.metrics, "results": row.results, "status": row.status,
            "created_at": row.created_at.isoformat()}


@router.get("/metrics")
def metrics(session: Session = Depends(get_session),
            tenant: TenantContext = Depends(get_tenant)):
    t = tenant.tenant_id
    by_status = dict(session.execute(
        select(Task.status, func.count()).where(Task.tenant_id == t).group_by(Task.status)).all())
    total_cost = float(session.execute(
        select(func.coalesce(func.sum(Task.cost_incurred), 0.0)).where(Task.tenant_id == t)).scalar_one())
    tool_calls = session.execute(
        select(func.count()).select_from(TaskStep).where(TaskStep.tenant_id == t)).scalar_one()
    denials = session.execute(
        select(func.count()).select_from(AuditEntry).where(
            AuditEntry.tenant_id == t, AuditEntry.event_type == "PermissionDenied")).scalar_one()
    pending_approvals = session.execute(
        select(func.count()).select_from(Approval).where(
            Approval.tenant_id == t, Approval.status == "requested")).scalar_one()
    return {
        "tasks_by_status": by_status,
        "total_cost_incurred": round(total_cost, 4),
        "tool_step_executions": tool_calls,
        "policy_denials": denials,
        "pending_approvals": pending_approvals,
        "available_metrics": metric_names(),
    }


@router.get("/traces")
def traces(task_id: str | None = Query(default=None),
           limit: int = Query(default=100, le=500),
           tenant: TenantContext = Depends(get_tenant)):
    # Spans are tenant-scoped via the acp.tenant.id attribute set by the API.
    items = [s for s in recent_spans(task_id=task_id, limit=limit)
             if s["attributes"].get("acp.tenant.id", tenant.tenant_id) == tenant.tenant_id]
    return {"items": items}
