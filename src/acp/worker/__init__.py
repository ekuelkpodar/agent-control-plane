"""ACP worker: outbox relay (+ future durable step execution).

MVP note: task execution runs INLINE in the API process (POST /tasks/{id}/execute
is synchronous and documented as such). This worker relays the transactional
outbox to the event bus so events are published reliably even for work the API
enqueues. Run: python -m acp.worker  or  acp-worker
"""

from acp.worker.__main__ import main

__all__ = ["main"]
