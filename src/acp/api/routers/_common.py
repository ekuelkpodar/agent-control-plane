"""Shared router helpers: error mapping."""

from __future__ import annotations

from fastapi import HTTPException

from acp.core.errors import (
    ApprovalRequired,
    BudgetExhausted,
    Conflict,
    InvalidTransition,
    NotFound,
    PolicyDenied,
    SecurityViolation,
)


def http_error(exc: Exception) -> HTTPException:
    # Cross-tenant attempts must surface to the app-level exception handler,
    # which audits SecurityViolationDetected before responding. Never swallow.
    if isinstance(exc, SecurityViolation):
        raise exc
    if isinstance(exc, NotFound):
        return HTTPException(404, str(exc))
    if isinstance(exc, PolicyDenied):
        return HTTPException(403, {"decision": "deny", "reason": exc.reason, "reasons": exc.reasons})
    if isinstance(exc, BudgetExhausted):
        return HTTPException(403, {"decision": "deny", "reason": str(exc)})
    if isinstance(exc, InvalidTransition):
        return HTTPException(409, str(exc))
    if isinstance(exc, Conflict):
        return HTTPException(409, str(exc))
    if isinstance(exc, ApprovalRequired):
        return HTTPException(202, {"approval_id": exc.approval_id, "status": "approval_required"})
    raise exc
