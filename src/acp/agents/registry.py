"""Agent registry: CRUD + explicit lifecycle state machine.

Capability change => new version (re-approval of grants). DELETE => deprecate.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from acp.core.errors import InvalidTransition, NotFound
from acp.core.utils import new_id, utcnow
from acp.db.models import Agent, AgentLifecycleEvent
from acp.state import AGENT_LIFECYCLE, transition

# POST /agents -> "created"; activate walks the happy path to "activated".
ACTIVATE_PATH = ["registered", "validated", "deployed", "tested", "activated"]


def create_agent(session: Session, *, tenant_id: str, name: str, description: str = "",
                 capabilities: list | None = None, model_config: dict | None = None,
                 tool_ids: list | None = None, system_instructions: str = "",
                 actor: str = "") -> Agent:
    row = Agent(
        id=new_id(), tenant_id=tenant_id, name=name, description=description, version=1,
        status="created", capabilities=capabilities or [], model_config=model_config or {},
        tool_ids=tool_ids or [], system_instructions=system_instructions,
    )
    session.add(row)
    _record(session, tenant_id, row.id, "created", "created", actor)
    session.flush()
    return row


def get_agent(session: Session, tenant_id: str, agent_id: str) -> Agent:
    row = session.execute(
        select(Agent).where(Agent.id == agent_id, Agent.tenant_id == tenant_id)
    ).scalars().first()
    if row is None:
        raise NotFound("agent not found")
    return row


def list_agents(session: Session, tenant_id: str) -> list[Agent]:
    return list(session.execute(
        select(Agent).where(Agent.tenant_id == tenant_id).order_by(Agent.created_at)
    ).scalars().all())


def transition_agent(session: Session, *, tenant_id: str, agent_id: str, to_status: str, actor: str = "") -> Agent:
    row = get_agent(session, tenant_id, agent_id)
    transition(AGENT_LIFECYCLE, row.status, to_status, what="agent lifecycle")
    _record(session, tenant_id, row.id, row.status, to_status, actor)
    row.status = to_status
    row.updated_at = utcnow()
    session.flush()
    return row


def activate(session: Session, *, tenant_id: str, agent_id: str, actor: str = "") -> Agent:
    """Walk CREATE..->ACTIVATE along the validated path."""
    row = get_agent(session, tenant_id, agent_id)
    for target in ACTIVATE_PATH:
        if row.status == target:
            continue
        try:
            transition(AGENT_LIFECYCLE, row.status, target, what="agent lifecycle")
        except InvalidTransition:
            # already beyond this step (e.g. re-activating an active agent)
            continue
        _record(session, tenant_id, row.id, row.status, target, actor)
        row.status = target
    row.updated_at = utcnow()
    session.flush()
    return row


def update_agent(session: Session, *, tenant_id: str, agent_id: str, actor: str = "",
                 **fields) -> Agent:
    """Capability/tool change => new version (grants must be re-approved)."""
    row = get_agent(session, tenant_id, agent_id)
    version_bump = False
    for key in ("capabilities", "tool_ids", "model_config"):
        if key in fields and fields[key] != getattr(row, key):
            version_bump = True
    for key, value in fields.items():
        if hasattr(row, key) and value is not None:
            setattr(row, key, value)
    if version_bump:
        row.version += 1
        # A changed version re-enters validation: it is no longer activated.
        if row.status in ("activated", "monitoring", "evaluating"):
            _record(session, tenant_id, row.id, row.status, "versioned", actor)
            row.status = "versioned"
    row.updated_at = utcnow()
    session.flush()
    return row


def deprecate(session: Session, *, tenant_id: str, agent_id: str, actor: str = "") -> None:
    row = get_agent(session, tenant_id, agent_id)
    if row.status != "deprecated":
        try:
            transition(AGENT_LIFECYCLE, row.status, "deprecated", what="agent lifecycle")
        except InvalidTransition:
            transition(AGENT_LIFECYCLE, row.status, "revoked", what="agent lifecycle")
            _record(session, tenant_id, row.id, row.status, "revoked", actor)
            row.status = "revoked"
            session.flush()
            return
        _record(session, tenant_id, row.id, row.status, "deprecated", actor)
        row.status = "deprecated"
        session.flush()


def _record(session: Session, tenant_id: str, agent_id: str, from_s: str, to_s: str, actor: str) -> None:
    session.add(AgentLifecycleEvent(
        id=new_id(), tenant_id=tenant_id, agent_id=agent_id,
        from_status=from_s, to_status=to_s, actor=actor,
    ))


def to_dict(row: Agent) -> dict:
    return {
        "id": row.id, "tenant_id": row.tenant_id, "name": row.name,
        "description": row.description, "version": row.version, "status": row.status,
        "capabilities": row.capabilities, "model_config": row.model_config,
        "tool_ids": row.tool_ids, "created_at": row.created_at.isoformat(),
    }
