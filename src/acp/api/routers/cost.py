"""Cost + budgets endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from acp.api.deps import get_session, get_tenant
from acp.api.schemas import BudgetCreate
from acp.core.tenant import TenantContext
from acp.core.utils import new_id
from acp.cost import get_budget, total_cost
from acp.db.models import Budget, CostRecord

router = APIRouter(tags=["cost"])


@router.post("/budgets", status_code=201)
def create_budget(body: BudgetCreate, session: Session = Depends(get_session),
                  tenant: TenantContext = Depends(get_tenant)):
    if body.scope not in ("task", "agent", "tenant"):
        from fastapi import HTTPException
        raise HTTPException(400, "scope must be task|agent|tenant")
    row = Budget(id=new_id(), tenant_id=tenant.tenant_id, scope=body.scope,
                 scope_id=body.scope_id, limit=body.limit)
    session.add(row)
    session.commit()
    return {"id": row.id, "scope": row.scope, "scope_id": row.scope_id, "limit": row.limit}


@router.get("/cost/summary")
def cost_summary(scope: str = Query(...), scope_id: str = Query(...),
                 session: Session = Depends(get_session),
                 tenant: TenantContext = Depends(get_tenant)):
    if scope not in ("task", "agent", "tenant"):
        from fastapi import HTTPException
        raise HTTPException(400, "scope must be task|agent|tenant")
    kwargs = {}
    if scope == "task":
        kwargs["task_id"] = scope_id
    elif scope == "agent":
        kwargs["agent_id"] = scope_id
    total = total_cost(session, tenant.tenant_id, **kwargs)

    by_model_rows = session.execute(
        select(CostRecord.model, func.coalesce(func.sum(CostRecord.amount), 0.0))
        .where(CostRecord.tenant_id == tenant.tenant_id,
               *([CostRecord.task_id == scope_id] if scope == "task" else []),
               *([CostRecord.agent_id == scope_id] if scope == "agent" else []))
        .group_by(CostRecord.model)
    ).all()
    by_tool_rows = session.execute(
        select(CostRecord.tool_id, func.coalesce(func.sum(CostRecord.amount), 0.0))
        .where(CostRecord.tenant_id == tenant.tenant_id,
               *([CostRecord.task_id == scope_id] if scope == "task" else []),
               *([CostRecord.agent_id == scope_id] if scope == "agent" else []))
        .group_by(CostRecord.tool_id)
    ).all()

    budget = get_budget(session, tenant.tenant_id, scope, scope_id)
    out = {
        "total": round(total, 4),
        "by_model": {m or "n/a": round(float(s), 4) for m, s in by_model_rows},
        "by_tool": {t or "n/a": round(float(s), 4) for t, s in by_tool_rows},
    }
    if budget:
        out["budget_limit"] = budget.limit
        out["budget_used_pct"] = round(100.0 * total / budget.limit, 2) if budget.limit else 0.0
    return out
