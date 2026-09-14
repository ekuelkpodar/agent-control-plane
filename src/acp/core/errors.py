"""Domain errors. HTTP mapping lives in the API layer."""

from __future__ import annotations


class ACPError(Exception):
    """Base ACP error."""


class NotFound(ACPError):
    pass


class Conflict(ACPError):
    pass


class InvalidTransition(ACPError):
    pass


class PolicyDenied(ACPError):
    """Fail-closed denial from the governance rail."""

    def __init__(self, reason: str, reasons: list[str] | None = None):
        super().__init__(reason)
        self.reason = reason
        self.reasons = reasons or [reason]


class ApprovalRequired(ACPError):
    def __init__(self, approval_id: str):
        super().__init__(f"human approval required: {approval_id}")
        self.approval_id = approval_id


class BudgetExhausted(ACPError):
    pass


class SecurityViolation(ACPError):
    """Cross-tenant access attempt or other security boundary breach."""
