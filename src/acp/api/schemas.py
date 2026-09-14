"""Pydantic request/response schemas for /api/v1."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------- agents
class AgentCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    description: str = ""
    capabilities: list[str] = Field(default_factory=list)
    # `model_config` is reserved by pydantic; the alias keeps the REST contract.
    model_config_: dict[str, Any] = Field(default_factory=dict, alias="model_config")
    tool_ids: list[str] = Field(default_factory=list)
    system_instructions: str = ""


class AgentUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = None
    description: str | None = None
    capabilities: list[str] | None = None
    model_config_: dict[str, Any] | None = Field(default=None, alias="model_config")
    tool_ids: list[str] | None = None
    system_instructions: str | None = None


class AgentActivate(BaseModel):
    version: int | None = None


# ---------------------------------------------------------------- tasks
class TaskCreate(BaseModel):
    goal: str
    input: dict[str, Any] | None = Field(default_factory=dict)
    agent_id: str | None = None  # OPTIONAL: router selects when omitted
    budget_limit: float | None = None


# ---------------------------------------------------------------- tools
class ToolCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    description: str = ""
    tool_schema: dict[str, Any] = Field(default_factory=dict, alias="schema")  # JSON schema
    risk_class: str = "low"  # low | medium | high | critical
    auth: dict[str, Any] = Field(default_factory=dict)
    cost_per_call: float = 0.0
    owner: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolInvoke(BaseModel):
    args: dict[str, Any] = Field(default_factory=dict)
    task_id: str | None = None
    agent_id: str | None = None  # required when task_id is not given


# ---------------------------------------------------------------- approvals
class ApprovalDecide(BaseModel):
    decided_by: str
    note: str | None = None


# ---------------------------------------------------------------- budgets / cost
class BudgetCreate(BaseModel):
    scope: str  # task | agent | tenant
    scope_id: str
    limit: float


# ---------------------------------------------------------------- evaluations
class EvaluationCreate(BaseModel):
    agent_id: str | None = None
    task_id: str | None = None
    metrics: list[str] = Field(default_factory=list)
