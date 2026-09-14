"""Task endpoints, incl. the governed execute pipeline and SSE event stream."""

from __future__ import annotations

import json
import time

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse  # type: ignore

from acp.api.deps import get_container, get_session, get_tenant
from acp.api.routers._common import http_error
from acp.api.schemas import TaskCreate
from acp.core.container import AppContainer
from acp.core.tenant import TenantContext
from acp.db.models import Event
from acp.orchestrator import service as orch

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", status_code=201)
def create_task(body: TaskCreate, session: Session = Depends(get_session),
                tenant: TenantContext = Depends(get_tenant),
                container: AppContainer = Depends(get_container)):
    try:
        task = orch.create_task(
            session, container, tenant_id=tenant.tenant_id, goal=body.goal,
            task_input=body.input, agent_id=body.agent_id,
            budget_limit=body.budget_limit, principal=tenant.principal)
        session.commit()
        return orch.task_to_dict(session, task)
    except Exception as exc:
        raise http_error(exc) from exc


@router.get("")
def list_tasks(status: str | None = Query(default=None),
               session: Session = Depends(get_session),
               tenant: TenantContext = Depends(get_tenant)):
    return {"items": [orch.task_to_dict(session, t)
                      for t in orch.list_tasks(session, tenant.tenant_id, status=status)]}


@router.get("/{task_id}")
def get_task(task_id: str, session: Session = Depends(get_session),
             tenant: TenantContext = Depends(get_tenant)):
    try:
        return orch.task_to_dict(session, orch.get_task(session, tenant.tenant_id, task_id))
    except Exception as exc:
        raise http_error(exc) from exc


@router.post("/{task_id}/execute")
def execute_task(task_id: str, session: Session = Depends(get_session),
                 tenant: TenantContext = Depends(get_tenant),
                 container: AppContainer = Depends(get_container)):
    """Run the governed pipeline to completion OR to the first approval pause.

    Returns the Task. If status == awaiting_approval, approve via
    POST /approvals/{id}/approve then call this endpoint again to resume.
    """
    try:
        task = orch.execute_task(session, container, tenant_id=tenant.tenant_id,
                                 task_id=task_id, principal=tenant.principal)
        session.commit()
        return orch.task_to_dict(session, task)
    except Exception as exc:
        raise http_error(exc) from exc


@router.post("/{task_id}/cancel")
def cancel_task(task_id: str, session: Session = Depends(get_session),
                tenant: TenantContext = Depends(get_tenant),
                container: AppContainer = Depends(get_container)):
    """Kill switch: freeze the task and revoke its delegation chain."""
    try:
        task = orch.cancel_task(session, container, tenant_id=tenant.tenant_id,
                                task_id=task_id, principal=tenant.principal)
        session.commit()
        return orch.task_to_dict(session, task)
    except Exception as exc:
        raise http_error(exc) from exc


@router.get("/{task_id}/events")
def task_events(task_id: str, wait: bool = Query(default=False),
                timeout: float = Query(default=20.0, le=60.0),
                session: Session = Depends(get_session),
                tenant: TenantContext = Depends(get_tenant),
                container: AppContainer = Depends(get_container)):
    try:
        orch.get_task(session, tenant.tenant_id, task_id)  # tenant-scoped 404/403
    except Exception as exc:
        raise http_error(exc) from exc

    def gen():
        seen: set[str] = set()
        deadline = time.time() + (timeout if wait else 0)
        while True:
            with container.session() as s:
                rows = s.execute(
                    select(Event).where(Event.task_id == task_id,
                                        Event.tenant_id == tenant.tenant_id)
                    .order_by(Event.created_at).limit(500)
                ).scalars().all()
            fresh = [e for e in rows if e.id not in seen]
            for e in fresh:
                seen.add(e.id)
                yield {"event": e.type, "id": e.id, "data": json.dumps({
                    "id": e.id, "type": e.type, "task_id": e.task_id,
                    "agent_id": e.agent_id, "payload": e.payload,
                    "created_at": e.created_at.isoformat()})}
            if not wait or time.time() >= deadline:
                break
            time.sleep(0.5)

    return EventSourceResponse(gen())
