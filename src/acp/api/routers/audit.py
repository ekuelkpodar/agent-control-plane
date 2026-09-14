"""Audit ledger endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from acp.api.deps import get_container, get_session, get_tenant
from acp.core.container import AppContainer
from acp.core.tenant import TenantContext
from acp.db.models import AuditEntry

router = APIRouter(prefix="/audit", tags=["audit"])


def _to_dict(e: AuditEntry) -> dict:
    return {
        "seq": e.seq, "tenant_id": e.tenant_id, "task_id": e.task_id,
        "timestamp": e.timestamp.isoformat(), "event_type": e.event_type,
        "actor": e.actor, "action": e.action, "inputs_digest": e.inputs_digest,
        "policy": e.policy, "risk": e.risk, "delegation_chain": e.delegation_chain,
        "result": e.result, "prev_hash": e.prev_hash, "entry_hash": e.entry_hash,
        "signature": e.signature,
    }


@router.get("")
def list_audit(event_type: str | None = Query(default=None),
               task_id: str | None = Query(default=None),
               limit: int = Query(default=100, le=1000),
               session: Session = Depends(get_session),
               tenant: TenantContext = Depends(get_tenant)):
    q = select(AuditEntry).where(AuditEntry.tenant_id == tenant.tenant_id)
    if event_type:
        q = q.where(AuditEntry.event_type == event_type)
    if task_id:
        q = q.where(AuditEntry.task_id == task_id)
    rows = session.execute(q.order_by(AuditEntry.seq.desc()).limit(limit)).scalars().all()
    return {"items": [_to_dict(e) for e in rows]}


@router.get("/verify")
def verify_chain(session: Session = Depends(get_session),
                 tenant: TenantContext = Depends(get_tenant),
                 container: AppContainer = Depends(get_container)):
    """Recompute the tenant's hash chain + Ed25519 signatures."""
    return container.audit_ledger.verify(session, tenant.tenant_id)


@router.get("/{seq}")
def get_entry(seq: int, session: Session = Depends(get_session),
              tenant: TenantContext = Depends(get_tenant)):
    row = session.execute(
        select(AuditEntry).where(AuditEntry.seq == seq, AuditEntry.tenant_id == tenant.tenant_id)
    ).scalars().first()
    if row is None:
        from acp.api.routers._common import http_error as _he
        from acp.core.errors import NotFound
        raise _he(NotFound("audit entry not found"))
    return _to_dict(row)
