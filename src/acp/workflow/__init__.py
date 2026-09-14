"""Workflow: WorkflowBackend protocol + PostgresDurableRunner.

MVP durable runner: steps with retries + exponential backoff, idempotency
keys (replay-safe), heartbeats, pause/resume for approvals, checkpoints
before side effects. Temporal is the V1 backend behind this same interface.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from acp.core.utils import new_id, sha256_hex, utcnow
from acp.db.models import Task, TaskStep
from acp.state import STEP_STATUS, transition

log = logging.getLogger(__name__)


def idempotency_key(task_id: str, step_id: str, args: dict) -> str:
    from acp.core.utils import canonical_json

    return sha256_hex(f"{task_id}:{step_id}:{canonical_json(args)}")[:64]


class PostgresDurableRunner:
    """Durable-enough step runner inside the monolith."""

    def __init__(self, settings):
        self._max_retries = settings.step_max_retries
        self._retry_base = settings.step_retry_base_seconds

    def prepare_steps(self, session: Session, *, tenant_id: str, task_id: str, steps: list[dict]) -> list[TaskStep]:
        rows = []
        for s in steps:
            key = idempotency_key(task_id, s["id"], s.get("args") or {})
            existing = session.execute(
                select(TaskStep).where(TaskStep.idempotency_key == key, TaskStep.tenant_id == tenant_id)
            ).scalars().first()
            if existing:
                rows.append(existing)
                continue
            row = TaskStep(
                id=new_id(), tenant_id=tenant_id, task_id=task_id, step_id=s["id"],
                name=s.get("name", s["id"]), tool_id=s.get("tool_id"),
                args=s.get("args") or {}, status="pending", idempotency_key=key,
            )
            session.add(row)
            rows.append(row)
        session.flush()
        return rows

    def run(
        self,
        session: Session,
        *,
        tenant_id: str,
        task: Task,
        step_rows: list[TaskStep],
        executor: Callable[[TaskStep], dict[str, Any]],
        on_step_event: Callable[[str, TaskStep, dict], None] | None = None,
    ) -> dict[str, Any]:
        """Execute pending steps. Returns {"completed": bool, "paused": bool, ...}.

        executor(step_row) performs ONE authorized tool call and returns the result.
        May raise to signal step failure (retried) or a control exception
        (ApprovalNeeded / BudgetExhausted propagate immediately).
        """
        from acp.core.errors import ApprovalRequired, BudgetExhausted, PolicyDenied

        results: list[dict] = []
        for row in step_rows:
            if row.status == "succeeded":
                results.append({"step_id": row.step_id, "reused": True, "result": row.result})
                continue  # idempotent replay: never re-execute a succeeded step
            if row.status in ("failed",):
                continue
            task.heartbeat_at = utcnow()
            # Checkpoint BEFORE the side effect.
            if row.status == "pending":
                transition(STEP_STATUS, row.status, "checkpointed", what="step")
                row.status = "checkpointed"
                row.checkpointed_at = utcnow()
                session.flush()
            transition(STEP_STATUS, row.status, "running", what="step")
            row.status = "running"
            session.flush()

            attempt = 0
            while True:
                row.attempts += 1
                try:
                    result = executor(row)
                except (ApprovalRequired, BudgetExhausted, PolicyDenied):
                    # Control signals: never retried. A denied tool call fails
                    # the task (fail closed); approvals/budget pause or kill.
                    raise
                except Exception as exc:
                    attempt += 1
                    if attempt > self._max_retries:
                        transition(STEP_STATUS, row.status, "failed", what="step")
                        row.status = "failed"
                        row.result = {"ok": False, "error": str(exc)}
                        session.flush()
                        if on_step_event:
                            on_step_event("ToolFailed", row, {"error": str(exc), "attempts": row.attempts})
                        return {"completed": False, "failed_step": row.step_id, "error": str(exc)}
                    backoff = self._retry_base * (2 ** (attempt - 1))
                    log.info("step %s failed (attempt %d), retrying in %.2fs: %s", row.step_id, attempt, backoff, exc)
                    time.sleep(backoff)
                    continue
                transition(STEP_STATUS, row.status, "succeeded", what="step")
                row.status = "succeeded"
                row.result = result
                session.flush()
                results.append({"step_id": row.step_id, "result": result})
                if on_step_event:
                    on_step_event("ToolInvoked", row, {"result_digest": sha256_hex(str(result))[:16]})
                break
        return {"completed": True, "results": results}
