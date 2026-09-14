"""Explicit state machines — transitions are enumerated and enforced.

Agent lifecycle: CREATE -> REGISTER -> VALIDATE -> DEPLOY -> TEST -> ACTIVATE
    -> MONITOR -> EVALUATE -> VERSION -> ROLLBACK -> DEPRECATE -> REVOKE
Task lifecycle: created -> admitted -> planned -> routed -> awaiting_approval
    -> executing -> paused -> completed | failed | cancelled | denied
Approval lifecycle: requested -> approved | rejected | expired
"""

from __future__ import annotations

from acp.core.errors import InvalidTransition

AGENT_LIFECYCLE: dict[str, set[str]] = {
    "created": {"registered", "revoked"},
    "registered": {"validated", "revoked"},
    "validated": {"deployed", "revoked"},
    "deployed": {"tested", "revoked"},
    "tested": {"activated", "revoked"},
    "activated": {"monitoring", "deprecated", "revoked"},
    "monitoring": {"evaluating", "deprecated", "revoked"},
    "evaluating": {"versioned", "monitoring", "deprecated", "revoked"},
    "versioned": {"rollback", "monitoring", "deprecated", "revoked"},
    "rollback": {"monitoring", "deprecated", "revoked"},
    "deprecated": {"revoked"},
    "revoked": set(),
}

TASK_LIFECYCLE: dict[str, set[str]] = {
    "created": {"admitted", "denied", "cancelled"},
    "admitted": {"planned", "denied", "cancelled", "failed"},
    "planned": {"routed", "denied", "cancelled", "failed"},
    "routed": {"awaiting_approval", "executing", "denied", "cancelled", "failed"},
    "awaiting_approval": {"executing", "denied", "cancelled", "failed"},
    "executing": {"paused", "completed", "failed", "cancelled", "denied"},
    "paused": {"executing", "cancelled", "failed", "denied"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
    "denied": set(),
}

APPROVAL_LIFECYCLE: dict[str, set[str]] = {
    "requested": {"approved", "rejected", "expired"},
    "approved": set(),
    "rejected": set(),
    "expired": set(),
}

STEP_STATUS: dict[str, set[str]] = {
    "pending": {"checkpointed", "running", "skipped"},
    "checkpointed": {"running", "skipped"},
    "running": {"succeeded", "failed", "awaiting_approval"},
    "awaiting_approval": {"running", "failed"},
    "succeeded": set(),
    "failed": set(),
    "skipped": set(),
}


def transition(machine: dict[str, set[str]], current: str, target: str, *, what: str = "state") -> str:
    allowed = machine.get(current, set())
    if target not in allowed:
        raise InvalidTransition(f"invalid {what} transition: {current!r} -> {target!r}")
    return target


def can_transition(machine: dict[str, set[str]], current: str, target: str) -> bool:
    return target in machine.get(current, set())
