"""FastAPI application factory: acp.api:app.

Serves ../dashboard static at /dashboard when the dashboard directory exists
(it is owned by a parallel agent; the API must not break when absent).
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from acp import __version__
from acp.api.middleware import AuthMiddleware, CorrelationMiddleware
from acp.api.routers import agents, approvals, audit, cost, evaluations, tasks, tools
from acp.core.config import Settings, settings
from acp.core.container import AppContainer, build_container
from acp.core.errors import (
    ApprovalRequired,
    BudgetExhausted,
    Conflict,
    InvalidTransition,
    NotFound,
    PolicyDenied,
    SecurityViolation,
)

log = logging.getLogger(__name__)


def create_app(app_settings: Settings | None = None) -> FastAPI:
    cfg = app_settings or settings
    container = build_container(cfg)

    app = FastAPI(
        title="Agent Control Plane",
        version=__version__,
        description=(
            "Governed management layer for AI agent fleets: registry, admission, "
            "planning, routing, policy/risk/approvals, durable execution, audit."
        ),
    )
    app.state.container = container

    app.add_middleware(CorrelationMiddleware)
    app.add_middleware(AuthMiddleware, api_key=cfg.api_key,
                       require_tenant_header=cfg.require_tenant_header)

    # ---- error mapping (fail-closed semantics preserved over HTTP) ----
    @app.exception_handler(NotFound)
    async def _not_found(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.exception_handler(SecurityViolation)
    async def _security(request, exc):
        # Any cross-tenant access attempt = SecurityViolationDetected event + deny.
        try:
            container: AppContainer = request.app.state.container
            tenant_id = request.headers.get("X-Tenant-ID", "unknown")
            with container.session() as session:
                container.audit_ledger.append(
                    session, tenant_id=tenant_id, event_type="SecurityViolationDetected",
                    actor={"type": "api", "principal": request.headers.get("X-Principal", "api")},
                    action=request.url.path, inputs={"detail": str(exc)}, result="denied")
                from acp.events import record_event as _record
                _record(session, container.event_bus, tenant_id=tenant_id,
                        event_type="SecurityViolationDetected",
                        payload={"detail": str(exc), "path": request.url.path})
                session.commit()
        except Exception as audit_exc:  # audit failure must not mask the denial
            log.warning("failed to audit security violation: %s", audit_exc)
        return JSONResponse({"detail": f"security violation: {exc}"}, status_code=403)

    @app.exception_handler(PolicyDenied)
    async def _denied(request, exc):
        return JSONResponse(
            {"decision": "deny", "reason": exc.reason, "reasons": exc.reasons},
            status_code=403)

    @app.exception_handler(BudgetExhausted)
    async def _budget(request, exc):
        return JSONResponse({"decision": "deny", "reason": str(exc)}, status_code=403)

    @app.exception_handler(InvalidTransition)
    async def _transition(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(Conflict)
    async def _conflict(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(ApprovalRequired)
    async def _approval(request, exc):
        return JSONResponse(
            {"approval_id": exc.approval_id, "status": "approval_required"},
            status_code=202)

    # ---- routers ----
    app.include_router(agents.router, prefix="/api/v1")
    app.include_router(tasks.router, prefix="/api/v1")
    app.include_router(tools.router, prefix="/api/v1")
    app.include_router(approvals.router, prefix="/api/v1")
    app.include_router(audit.router, prefix="/api/v1")
    app.include_router(cost.router, prefix="/api/v1")
    app.include_router(evaluations.router, prefix="/api/v1")

    # Root-level health alias (contract: GET /health). The versioned
    # /api/v1/health remains the canonical endpoint.
    @app.get("/health", include_in_schema=False)
    def _health_alias():
        from acp.api.routers.evaluations import health

        return health()

    # ---- dashboard static (optional; owned by parallel agent) ----
    dashboard_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "apps", "dashboard")
    dashboard_dir = os.path.abspath(dashboard_dir)
    if os.path.isdir(dashboard_dir):
        app.mount("/dashboard", StaticFiles(directory=dashboard_dir, html=True), name="dashboard")
        log.info("serving dashboard static from %s", dashboard_dir)
    else:
        log.info("dashboard static not present; /dashboard disabled")

    @app.on_event("startup")
    async def _startup():
        log.info("ACP api startup (version=%s, planner=%s)", __version__, cfg.planner)

    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("acp.api.app:app", host="0.0.0.0", port=8000)
