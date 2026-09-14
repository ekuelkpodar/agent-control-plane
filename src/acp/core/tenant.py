"""Tenant context: extracted from headers, carried explicitly (no ambient tenant)."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass

tenant_ctx: ContextVar[TenantContext | None] = ContextVar("tenant_ctx", default=None)


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    principal: str  # authenticated API principal (human user / service account id)
    api_key_id: str = "default"
    role: str = "viewer"  # RBAC role from X-Role; validated by AuthMiddleware


def current_tenant() -> TenantContext:
    ctx = tenant_ctx.get()
    if ctx is None:
        raise RuntimeError("no tenant context active")
    return ctx
