"""Shared governance protocols (interfaces) — dependency-injection seams."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class PolicyDecision:
    decision: str  # allow | deny | require_approval | allow_with_constraints
    reasons: list[str] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)
    policy_version_hash: str = ""
    policy_refs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RiskAssessment:
    risk_score: float
    risk_level: str  # low | medium | high | critical
    requires_human_approval: bool
    reasons: list[str] = field(default_factory=list)
    score_breakdown: dict[str, float] = field(default_factory=dict)
    policy_refs: list[str] = field(default_factory=list)


class PolicyEngine(Protocol):
    def evaluate(self, ctx: dict[str, Any]) -> PolicyDecision: ...
    def version_hash(self) -> str: ...


class RiskEngine(Protocol):
    def assess(self, ctx: dict[str, Any]) -> RiskAssessment: ...
    def register_model_scorer(self, scorer: Callable[[dict[str, Any]], dict[str, Any]]) -> None: ...


class SecretBroker(Protocol):
    def issue(self, tenant_id: str, tool_id: str, ttl_seconds: int = 300) -> dict[str, Any]: ...
    def revoke(self, lease_id: str) -> None: ...
    def rotate(self, tool_id: str) -> None: ...


class EventBus(Protocol):
    def publish(self, event_type: str, payload: dict[str, Any]) -> None: ...


class ModelProvider(Protocol):
    name: str

    def capabilities(self) -> dict[str, Any]: ...
    def cost_per_1k_tokens(self) -> float: ...
    def generate(self, prompt: str, **kwargs: Any) -> str: ...


class MemoryStore(Protocol):
    def write(self, tenant_id: str, namespace: str, key: str, value: dict, provenance: dict,
              ttl_seconds: int | None = None) -> dict: ...
    def read(self, tenant_id: str, namespace: str, key: str) -> dict | None: ...
    def list(self, tenant_id: str, namespace: str) -> list[dict]: ...
    def delete(self, tenant_id: str, namespace: str, key: str) -> None: ...


class WorkflowBackend(Protocol):
    def run_task(self, task_id: str, steps: list[dict], executor: Callable[[dict], dict]) -> dict: ...
