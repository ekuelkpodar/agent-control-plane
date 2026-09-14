"""Event bus: interface + InProcessEventBus (MVP default) + RedisStreamsEventBus.

Publication is reliable via the transactional outbox table (written in the
same DB transaction as the domain change). The worker relays outbox rows to
the bus; InProcessEventBus also dispatches synchronously to local subscribers.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from acp.core.utils import new_id, utcnow
from acp.db.models import Event, Outbox

log = logging.getLogger(__name__)


class EventBus:
    def publish(self, event_type: str, payload: dict[str, Any]) -> None: ...
    def subscribe(self, event_type: str, handler: Callable[[dict[str, Any]], None]) -> None: ...


class InProcessEventBus(EventBus):
    def __init__(self):
        self._handlers: dict[str, list[Callable]] = {}

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        for handler in self._handlers.get(event_type, []):
            try:
                handler(payload)
            except Exception as exc:  # never let a subscriber break the pipeline
                log.warning("event subscriber failed for %s: %s", event_type, exc)
        for handler in self._handlers.get("*", []):
            try:
                handler({"type": event_type, **payload})
            except Exception as exc:
                log.warning("event subscriber failed for %s: %s", event_type, exc)

    def subscribe(self, event_type: str, handler: Callable[[dict[str, Any]], None]) -> None:
        self._handlers.setdefault(event_type, []).append(handler)


class RedisStreamsEventBus(EventBus):
    """Adapter for Redis Streams (used when ACP_REDIS_URL is set)."""

    def __init__(self, redis_url: str, stream: str = "acp-events"):
        import redis

        self._redis = redis.Redis.from_url(redis_url, decode_responses=True)
        self._stream = stream
        self._local = InProcessEventBus()

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        import json

        self._redis.xadd(self._stream, {"type": event_type, "payload": json.dumps(payload, default=str)})
        self._local.publish(event_type, payload)

    def subscribe(self, event_type: str, handler) -> None:
        self._local.subscribe(event_type, handler)


def record_event(
    session: Session,
    bus: EventBus,
    *,
    tenant_id: str,
    event_type: str,
    task_id: str | None = None,
    agent_id: str | None = None,
    correlation_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> Event:
    """Write the domain event (selective event sourcing) + outbox row, then publish."""
    event = Event(
        id=new_id(), tenant_id=tenant_id, type=event_type, task_id=task_id,
        agent_id=agent_id, correlation_id=correlation_id, payload=payload or {},
    )
    session.add(event)
    session.add(Outbox(id=new_id(), tenant_id=tenant_id, type=event_type, payload={
        "event_id": event.id, "tenant_id": tenant_id, "type": event_type,
        "task_id": task_id, "agent_id": agent_id,
        "correlation_id": correlation_id, "payload": payload or {},
    }))
    session.flush()
    bus.publish(event_type, {
        "event_id": event.id, "tenant_id": tenant_id, "type": event_type,
        "task_id": task_id, "agent_id": agent_id,
        "correlation_id": correlation_id, "payload": payload or {},
    })
    return event


def relay_outbox(session: Session, bus: EventBus, batch: int = 100) -> int:
    """Worker: publish unpublished outbox rows exactly-once (mark published)."""
    rows = session.execute(
        select(Outbox).where(Outbox.published_at.is_(None)).order_by(Outbox.created_at).limit(batch)
    ).scalars().all()
    for row in rows:
        try:
            bus.publish(row.type, row.payload)
        except Exception as exc:
            log.warning("outbox relay failed for %s: %s", row.id, exc)
            continue
        session.execute(update(Outbox).where(Outbox.id == row.id).values(published_at=utcnow()))
    session.commit()
    return len(rows)
