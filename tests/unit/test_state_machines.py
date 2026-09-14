"""Unit: explicit state machines."""

import pytest

from acp.core.errors import InvalidTransition
from acp.state import (
    AGENT_LIFECYCLE,
    APPROVAL_LIFECYCLE,
    STEP_STATUS,
    TASK_LIFECYCLE,
    can_transition,
    transition,
)


def test_task_lifecycle_happy_path():
    s = "created"
    for nxt in ["admitted", "planned", "routed", "awaiting_approval", "executing", "completed"]:
        s = transition(TASK_LIFECYCLE, s, nxt, what="task")
    assert s == "completed"


def test_task_lifecycle_denied_from_created():
    assert transition(TASK_LIFECYCLE, "created", "denied", what="task") == "denied"


def test_task_terminal_states_have_no_outgoing():
    for terminal in ("completed", "failed", "cancelled", "denied"):
        assert TASK_LIFECYCLE[terminal] == set()
        with pytest.raises(InvalidTransition):
            transition(TASK_LIFECYCLE, terminal, "executing", what="task")


def test_task_invalid_transition_rejected():
    with pytest.raises(InvalidTransition):
        transition(TASK_LIFECYCLE, "created", "completed", what="task")


def test_agent_lifecycle_full_walk():
    s = "created"
    for nxt in ["registered", "validated", "deployed", "tested", "activated",
                "monitoring", "evaluating", "versioned", "rollback", "monitoring",
                "deprecated", "revoked"]:
        s = transition(AGENT_LIFECYCLE, s, nxt, what="agent")
    assert s == "revoked"


def test_agent_cannot_skip_validation():
    with pytest.raises(InvalidTransition):
        transition(AGENT_LIFECYCLE, "created", "activated", what="agent")


def test_approval_lifecycle():
    assert transition(APPROVAL_LIFECYCLE, "requested", "approved", what="approval") == "approved"
    with pytest.raises(InvalidTransition):
        transition(APPROVAL_LIFECYCLE, "approved", "rejected", what="approval")
    with pytest.raises(InvalidTransition):
        transition(APPROVAL_LIFECYCLE, "requested", "requested", what="approval")


def test_step_lifecycle_checkpoint_before_side_effect():
    s = transition(STEP_STATUS, "pending", "checkpointed", what="step")
    s = transition(STEP_STATUS, s, "running", what="step")
    s = transition(STEP_STATUS, s, "succeeded", what="step")
    assert s == "succeeded"
    with pytest.raises(InvalidTransition):
        transition(STEP_STATUS, "pending", "succeeded", what="step")


def test_can_transition():
    assert can_transition(TASK_LIFECYCLE, "created", "admitted")
    assert not can_transition(TASK_LIFECYCLE, "created", "executing")
