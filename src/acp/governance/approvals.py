"""Approvals: human-in-the-loop state machine (requested -> approved|rejected|expired).

Approval timeout == DENY (never auto-approve). Expiry is enforced on every
read/decision via sweep_expired(); wrongly assuming an approval is still
valid fails closed.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from acp.core.errors import InvalidTransition, NotFound
from acp.core.utils import new_id, utcnow
from acp.db.models import Approval
from acp.state import APPROVAL_LIFECYCLE, transition


def create_approval(
    session: Session,
    *,
    tenant_id: str,
    task_id: str | None,
    action_summary: str,
    action_detail: dict,
    risk_score: float,
    risk_level: str,
    reasons: list[str],
    ttl_seconds: int,
) -> Approval:
    from datetime import timedelta

    row = Approval(
        id=new_id(), tenant_id=tenant_id, task_id=task_id, action_summary=action_summary,
        action_detail=action_detail, risk_score=risk_score, risk_level=risk_level,
        reasons=reasons, status="requested",
        expires_at=utcnow() + timedelta(seconds=ttl_seconds),
    )
    session.add(row)
    session.flush()
    return row


def get_approval(session: Session, tenant_id: str, approval_id: str) -> Approval:
    row = session.execute(
        select(Approval).where(Approval.id == approval_id, Approval.tenant_id == tenant_id)
    ).scalars().first()
    if row is None:
        raise NotFound("approval not found")
    return row


def sweep_expired(session: Session, tenant_id: str) -> list[Approval]:
    """Mark expired approvals; returns them so callers can deny the tasks (fail closed)."""
    rows = session.execute(
        select(Approval).where(
            Approval.tenant_id == tenant_id,
            Approval.status == "requested",
            Approval.expires_at <= utcnow(),
        )
    ).scalars().all()
    for row in rows:
        transition(APPROVAL_LIFECYCLE, row.status, "expired", what="approval")
        row.status = "expired"
    if rows:
        session.flush()
    return list(rows)


def decide(session: Session, *, tenant_id: str, approval_id: str, approve: bool,
           decided_by: str, note: str | None = None) -> Approval:
    sweep_expired(session, tenant_id)  # expiry is checked first: timeout == DENY
    row = get_approval(session, tenant_id, approval_id)
    if row.status == "expired":
        raise InvalidTransition("approval expired: timeout == DENY (never auto-approve)")
    if row.status != "requested":
        raise InvalidTransition(f"approval already {row.status}")
    target = "approved" if approve else "rejected"
    transition(APPROVAL_LIFECYCLE, row.status, target, what="approval")
    row.status = target
    row.decided_by = decided_by
    row.decided_at = utcnow()
    row.note = note
    session.flush()
    return row


def to_dict(row: Approval) -> dict:
    detail = row.action_detail or {}
    return {
        "id": row.id, "task_id": row.task_id, "action_summary": row.action_summary,
        "risk_score": row.risk_score, "risk_level": row.risk_level, "reasons": row.reasons,
        # Policy-decision evidence: what the PDP decided and which policy
        # version decided it (pinned reference for auditors).
        "policy_decision": detail.get("policy_decision"),
        "policy_version_hash": detail.get("policy_version_hash"),
        "status": row.status, "requested_at": row.requested_at.isoformat(),
        "expires_at": row.expires_at.isoformat(),
        "decided_by": row.decided_by,
        "decided_at": row.decided_at.isoformat() if row.decided_at else None,
    }
