"""Approvals (HITL) endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from acp.api.deps import get_container, get_session, get_tenant
from acp.api.routers._common import http_error
from acp.api.schemas import ApprovalDecide
from acp.core.container import AppContainer
from acp.core.errors import PolicyDenied
from acp.core.tenant import TenantContext
from acp.db.models import Approval
from acp.governance import approvals as approval_svc
from acp.governance.permissions import role_allows

router = APIRouter(prefix="/approvals", tags=["approvals"])


def _require_decide(tenant: TenantContext, container: AppContainer, session: Session) -> None:
    """RBAC: only approval-capable roles may decide. Denials are audited."""
    if not role_allows(tenant.role, "approvals.decide"):
        container.audit_ledger.append(
            session, tenant_id=tenant.tenant_id, event_type="PermissionDenied",
            actor={"type": "api", "principal": tenant.principal, "role": tenant.role},
            action="approval.decide", inputs={"role": tenant.role}, result="denied")
        session.commit()
        raise PolicyDenied(f"role {tenant.role!r} may not decide approvals")


@router.get("")
def list_approvals(status: str | None = Query(default=None),
                   task_id: str | None = Query(default=None),
                   session: Session = Depends(get_session),
                   tenant: TenantContext = Depends(get_tenant)):
    """List approvals. Filters: ?status=requested (default view for approvers),
    ?task_id=<id> (per-task approvals)."""
    approval_svc.sweep_expired(session, tenant.tenant_id)  # timeout == DENY surfaces here
    q = select(Approval).where(Approval.tenant_id == tenant.tenant_id)
    if status:
        q = q.where(Approval.status == status)
    if task_id:
        q = q.where(Approval.task_id == task_id)
    rows = session.execute(q.order_by(Approval.requested_at.desc())).scalars().all()
    session.commit()
    return {"items": [approval_svc.to_dict(a) for a in rows]}


@router.post("/{approval_id}/approve")
def approve(approval_id: str, body: ApprovalDecide,
            session: Session = Depends(get_session),
            tenant: TenantContext = Depends(get_tenant),
            container: AppContainer = Depends(get_container)):
    _require_decide(tenant, container, session)
    try:
        row = approval_svc.decide(session, tenant_id=tenant.tenant_id,
                                  approval_id=approval_id, approve=True,
                                  decided_by=body.decided_by, note=body.note)
        container.audit_ledger.append(
            session, tenant_id=tenant.tenant_id, task_id=row.task_id, event_type="ApprovalGranted",
            actor={"type": "human", "principal": body.decided_by},
            action="approval.decide", inputs={"approval_id": approval_id},
            result="approved")
        session.commit()
        return approval_svc.to_dict(row)
    except Exception as exc:
        raise http_error(exc) from exc


@router.post("/{approval_id}/reject")
def reject(approval_id: str, body: ApprovalDecide,
           session: Session = Depends(get_session),
           tenant: TenantContext = Depends(get_tenant),
           container: AppContainer = Depends(get_container)):
    _require_decide(tenant, container, session)
    try:
        row = approval_svc.decide(session, tenant_id=tenant.tenant_id,
                                  approval_id=approval_id, approve=False,
                                  decided_by=body.decided_by, note=body.note)
        container.audit_ledger.append(
            session, tenant_id=tenant.tenant_id, task_id=row.task_id, event_type="ApprovalRejected",
            actor={"type": "human", "principal": body.decided_by},
            action="approval.decide", inputs={"approval_id": approval_id},
            result="rejected")
        session.commit()
        return approval_svc.to_dict(row)
    except Exception as exc:
        raise http_error(exc) from exc
