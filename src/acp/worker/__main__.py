"""ACP worker: outbox relay (+ future durable step execution).

MVP note: task execution runs INLINE in the API process (POST /tasks/{id}/execute
is synchronous and documented as such). This worker relays the transactional
outbox to the event bus so events are published reliably even for work the API
enqueues. Run: python -m acp.worker
"""

from __future__ import annotations

import logging
import time

from acp.core.config import settings
from acp.core.container import build_container
from acp.db import get_session_factory
from acp.events import relay_outbox

log = logging.getLogger(__name__)


def main() -> None:
    container = build_container(settings)
    session_factory = get_session_factory(settings.database_url)
    log.info("acp-worker started (outbox relay)")
    while True:
        try:
            with session_factory() as session:
                n = relay_outbox(session, container.event_bus)
                if n:
                    log.info("relayed %d outbox events", n)
        except Exception as exc:
            log.warning("outbox relay error: %s", exc)
        time.sleep(2.0)


if __name__ == "__main__":
    main()
