"""Cost: ledger, budgets, kill switch.

Budgets are enforced at the tool-invocation choke point. Hard deny at 100%
(fail closed) + CostThresholdExceeded event + kill switch (task frozen,
delegation revoked). Alerts at 50/80/95%.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from acp.core.errors import BudgetExhausted
from acp.core.utils import new_id
from acp.db.models import Budget, CostRecord


def record_cost(
    session: Session,
    *,
    tenant_id: str,
    amount: float,
    task_id: str | None = None,
    agent_id: str | None = None,
    tool_id: str | None = None,
    model: str | None = None,
    detail: dict | None = None,
) -> CostRecord:
    row = CostRecord(
        id=new_id(), tenant_id=tenant_id, task_id=task_id, agent_id=agent_id,
        tool_id=tool_id, model=model, amount=amount, detail=detail or {},
    )
    session.add(row)
    session.flush()
    return row


def total_cost(session: Session, tenant_id: str, *, task_id=None, agent_id=None, tool_id=None, model=None) -> float:
    q = select(func.coalesce(func.sum(CostRecord.amount), 0.0)).where(CostRecord.tenant_id == tenant_id)
    if task_id:
        q = q.where(CostRecord.task_id == task_id)
    if agent_id:
        q = q.where(CostRecord.agent_id == agent_id)
    if tool_id:
        q = q.where(CostRecord.tool_id == tool_id)
    if model:
        q = q.where(CostRecord.model == model)
    return float(session.execute(q).scalar_one())


def get_budget(session: Session, tenant_id: str, scope: str, scope_id: str) -> Budget | None:
    return session.execute(
        select(Budget).where(
            Budget.tenant_id == tenant_id, Budget.scope == scope, Budget.scope_id == scope_id
        ).order_by(Budget.created_at.desc())
    ).scalars().first()


def check_budget(
    session: Session,
    *,
    tenant_id: str,
    task_id: str | None,
    agent_id: str | None,
    additional: float,
    alert_thresholds: list[float] | None = None,
) -> dict:
    """Check all applicable budget envelopes (task -> agent -> tenant).

    Returns {"ok": True, "used_pct": ...} or raises BudgetExhausted at 100%.
    """
    envelopes = []
    if task_id:
        envelopes.append(("task", task_id, total_cost(session, tenant_id, task_id=task_id)))
    if agent_id:
        envelopes.append(("agent", agent_id, total_cost(session, tenant_id, agent_id=agent_id)))
    envelopes.append(("tenant", tenant_id, total_cost(session, tenant_id)))

    worst_pct = 0.0
    alerts: list[str] = []
    for scope, scope_id, used in envelopes:
        budget = get_budget(session, tenant_id, scope, scope_id)
        if not budget or budget.limit <= 0:
            continue
        projected = used + additional
        pct = 100.0 * projected / budget.limit
        worst_pct = max(worst_pct, pct)
        for t in (alert_thresholds or [50.0, 80.0, 95.0]):
            if used / budget.limit * 100 < t <= pct:
                alerts.append(f"{scope}:{scope_id} crossed {t:.0f}% of budget")
        if projected > budget.limit:
            raise BudgetExhausted(
                f"budget exhausted: {scope}:{scope_id} limit ${budget.limit:.2f}, "
                f"projected ${projected:.2f} (fail closed)"
            )
    return {"ok": True, "used_pct": round(worst_pct, 2), "alerts": alerts}
