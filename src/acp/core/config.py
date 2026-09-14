"""Runtime configuration (pydantic-settings, ACP_ prefix)."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ACP_", extra="ignore")

    # --- Database ---
    database_url: str = Field(default="sqlite:///./acp.db")
    auto_migrate: bool = Field(default=True)  # create_all on startup (dev); use Alembic in prod

    # --- Auth (MVP: shared API key + tenant header; OIDC/SPIFFE are V1) ---
    api_key: str = Field(default="dev-key-change-me")
    require_tenant_header: bool = Field(default=True)

    # --- Integrations ---
    opa_url: str | None = Field(default=None)  # e.g. http://localhost:8181 ; enables OPA adapter
    redis_url: str | None = Field(default=None)  # enables RedisStreamsEventBus; else in-process
    otlp_endpoint: str | None = Field(default=None)  # OTLP HTTP endpoint; else console exporter

    # --- Governance knobs ---
    approval_ttl_seconds: int = Field(default=900)  # approval expiry; timeout == DENY
    risk_approval_threshold: float = Field(default=70.0)  # score >= this => requires_human_approval
    high_risk_score: float = Field(default=50.0)
    critical_risk_score: float = Field(default=75.0)
    tenant_cost_approval_threshold: float = Field(default=5.0)  # plan est. cost above => approval
    budget_alert_thresholds: str = Field(default="50,80,95")

    # --- Workflow ---
    step_max_retries: int = Field(default=3)
    step_retry_base_seconds: float = Field(default=0.2)
    planner: str = Field(default="deterministic")  # deterministic | rule_based
    router_weights: str = Field(default="capability:0.30,cost:0.15,latency:0.10,risk:0.15,policy:0.15,availability:0.10,history:0.05")

    # --- Audit ledger signing (Ed25519) ---
    ledger_signing_key_b64: str | None = Field(default=None)  # base64 32-byte seed; generated ephemerally if absent (dev only)

    # --- Models (mock by default) ---
    default_model_provider: str = Field(default="mock")
    default_model: str = Field(default="mock-llm-1")

    version: str = Field(default="0.1.0")


settings = Settings()
