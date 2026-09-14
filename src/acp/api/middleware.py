"""Middleware: correlation IDs + MVP auth (Bearer ACP_API_KEY + X-Tenant-ID).

MVP auth: Authorization: Bearer <ACP_API_KEY>, X-Tenant-ID header.
OIDC/SPIFFE are V1 (documented in docs/api-reference.md).
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from acp.core.tenant import TenantContext, tenant_ctx
from acp.observability import correlation_ctx, new_correlation_id

PUBLIC_PATHS = {"/health", "/api/v1/health", "/openapi.json", "/docs", "/redoc"}


class CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        cid = request.headers.get("X-Correlation-ID") or new_correlation_id()
        correlation_ctx.set(cid)
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = cid
        return response


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, api_key: str, require_tenant_header: bool = True):
        super().__init__(app)
        self._api_key = api_key
        self._require_tenant = require_tenant_header
        if api_key == "dev-key-change-me":
            import logging
            logging.getLogger(__name__).warning(
                "AUTH: using default dev API key — set ACP_API_KEY in production."
            )

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in PUBLIC_PATHS or path.startswith("/dashboard"):
            return await call_next(request)
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or auth[len("Bearer "):] != self._api_key:
            return JSONResponse({"detail": "unauthorized: invalid or missing API key"}, status_code=401)
        tenant_id = request.headers.get("X-Tenant-ID", "")
        if self._require_tenant and not tenant_id:
            return JSONResponse({"detail": "missing X-Tenant-ID header"}, status_code=400)
        from acp.governance.permissions import ROLES
        role = request.headers.get("X-Role", "viewer")
        if role not in ROLES:
            return JSONResponse({"detail": f"unknown role: {role}"}, status_code=403)
        tenant_ctx.set(TenantContext(
            tenant_id=tenant_id or "default",
            principal=request.headers.get("X-Principal", "api"),
            api_key_id="default",
            role=role,
        ))
        try:
            return await call_next(request)
        finally:
            tenant_ctx.set(None)
