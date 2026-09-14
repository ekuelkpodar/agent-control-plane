"""SQLAlchemy 2.0 declarative models.

Portability rule: sqlalchemy.JSON, String(36) ids, naive UTC DateTime,
no PG-only DDL in code. Postgres RLS is a deployment concern — the DDL is
documented in docs/api-reference.md and enforced in the app layer on every query.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from acp.core.utils import utcnow


class Base(DeclarativeBase):
    pass


def _id() -> Mapped[str]:
    return mapped_column(String(36), primary_key=True)


def _ts() -> Mapped[datetime]:
    return mapped_column(DateTime, default=utcnow, nullable=False)


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    created_at: Mapped[datetime] = _ts()


class Agent(Base):
    __tablename__ = "agents"
    id: Mapped[str] = _id()
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")
    capabilities: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    model_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    tool_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    system_instructions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    max_risk_level: Mapped[str] = mapped_column(String(16), nullable=False, default="high")
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class AgentLifecycleEvent(Base):
    __tablename__ = "agent_lifecycle_events"
    id: Mapped[str] = _id()
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    from_status: Mapped[str] = mapped_column(String(32), nullable=False)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    actor: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    at: Mapped[datetime] = _ts()


class Tool(Base):
    __tablename__ = "tools"
    id: Mapped[str] = _id()
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    risk_class: Mapped[str] = mapped_column(String(16), nullable=False, default="low")
    schema: Mapped[dict] = mapped_column("tool_schema", JSON, nullable=False, default=dict)
    auth: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    cost_per_call: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    owner: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = _ts()


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = _id()
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    input: Mapped[dict] = mapped_column("task_input", JSON, nullable=False, default=dict)
    agent_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created", index=True)
    plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    risk_assessment: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    cost_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_incurred: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    budget_limit: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class TaskStep(Base):
    __tablename__ = "task_steps"
    id: Mapped[str] = _id()
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    step_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    tool_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    args: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    checkpointed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[str] = _id()
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    action_summary: Mapped[str] = mapped_column(Text, nullable=False)
    action_detail: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, default="low")
    reasons: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="requested", index=True)
    requested_at: Mapped[datetime] = _ts()
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    decided_by: Mapped[str | None] = mapped_column(String(256), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditEntry(Base):
    """Append-only, hash-chained, Ed25519-signed ledger. Per-tenant chains."""

    __tablename__ = "audit_entries"
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    timestamp: Mapped[datetime] = _ts()
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    action: Mapped[str] = mapped_column(String(256), nullable=False)
    inputs_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    policy: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    risk: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    delegation_chain: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    result: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    signature: Mapped[str] = mapped_column(String(128), nullable=False)


class Event(Base):
    """Selectively event-sourced domain events (audit-adjacent; workflow history)."""

    __tablename__ = "events"
    id: Mapped[str] = _id()
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    agent_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = _ts()


class Outbox(Base):
    """Transactional outbox: written in the same DB tx as domain changes, relayed by the worker."""

    __tablename__ = "outbox"
    id: Mapped[str] = _id()
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = _ts()
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Delegation(Base):
    __tablename__ = "delegations"
    id: Mapped[str] = _id()
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    jti: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    subject: Mapped[str] = mapped_column(String(256), nullable=False)  # human user
    actor_agent_id: Mapped[str] = mapped_column(String(36), nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    scope_tools: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    audience: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = _ts()


class Budget(Base):
    __tablename__ = "budgets"
    id: Mapped[str] = _id()
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)  # task | agent | tenant
    scope_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    limit: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = _ts()


class CostRecord(Base):
    __tablename__ = "cost_records"
    id: Mapped[str] = _id()
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    agent_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    tool_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = _ts()


class PolicyBundle(Base):
    __tablename__ = "policy_bundles"
    id: Mapped[str] = _id()
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    bundle_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = _ts()


class MemoryEntry(Base):
    __tablename__ = "memory_entries"
    id: Mapped[str] = _id()
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    namespace: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(256), nullable=False)
    value: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    provenance: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    quarantined: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"
    id: Mapped[str] = _id()
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    uri: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    trust_level: Mapped[str] = mapped_column(String(16), nullable=False, default="untrusted")
    created_at: Mapped[datetime] = _ts()


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    id: Mapped[str] = _id()
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    provenance: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = _ts()


class Evaluation(Base):
    __tablename__ = "evaluations"
    id: Mapped[str] = _id()
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    agent_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    metrics: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    results: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="completed")
    created_at: Mapped[datetime] = _ts()


class LearningProposal(Base):
    """Propose-only learning: proposals need policy pass + human approval. No self-modification."""

    __tablename__ = "learning_proposals"
    id: Mapped[str] = _id()
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    proposal_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    policy_decision: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="proposed")
    created_at: Mapped[datetime] = _ts()
