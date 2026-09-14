"""FastAPI dependencies: container, DB session, tenant context."""

from __future__ import annotations

from fastapi import Depends, Request

from acp.core.container import AppContainer
from acp.core.tenant import TenantContext, current_tenant


def get_container(request: Request) -> AppContainer:
    return request.app.state.container


def get_tenant() -> TenantContext:
    return current_tenant()


def get_session(container: AppContainer = Depends(get_container)):
    session = container.session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
