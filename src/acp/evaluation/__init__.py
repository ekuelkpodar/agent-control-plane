"""Evaluation framework: metric registry + sample metrics.

Sample metrics: task_success, tool_call_accuracy, policy_violations, latency, cost.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from acp.core.utils import new_id
from acp.cost import total_cost
from acp.db.models import Evaluation, Event, Task, TaskStep

MetricFn = Callable[[Session, str, dict[str, Any]], Any]
_registry: dict[str, MetricFn] = {}


def metric(name: str):
    def deco(fn: MetricFn) -> MetricFn:
        _registry[name] = fn
        return fn
    return deco


def metric_names() -> list[str]:
    return sorted(_registry)


@metric("task_success")
def _task_success(session: Session, tenant_id: str, scope: dict) -> float:
    task = _get_task(session, tenant_id, scope)
    return 1.0 if task and task.status == "completed" else 0.0


@metric("tool_call_accuracy")
def _tool_call_accuracy(session: Session, tenant_id: str, scope: dict) -> float:
    steps = _get_steps(session, tenant_id, scope)
    if not steps:
        return 0.0
    ok = sum(1 for s in steps if isinstance(s.result, dict) and s.result.get("ok") is True)
    return round(ok / len(steps), 4)


@metric("policy_violations")
def _policy_violations(session: Session, tenant_id: str, scope: dict) -> int:
    q = select(Event).where(Event.tenant_id == tenant_id, Event.type == "PermissionDenied")
    if scope.get("task_id"):
        q = q.where(Event.task_id == scope["task_id"])
    return len(session.execute(q).scalars().all())


@metric("latency")
def _latency(session: Session, tenant_id: str, scope: dict) -> float | None:
    task = _get_task(session, tenant_id, scope)
    if not task:
        return None
    return round((task.updated_at - task.created_at).total_seconds(), 3)


@metric("cost")
def _cost(session: Session, tenant_id: str, scope: dict) -> float:
    return round(total_cost(session, tenant_id, task_id=scope.get("task_id"), agent_id=scope.get("agent_id")), 4)


def _get_task(session: Session, tenant_id: str, scope: dict) -> Task | None:
    if not scope.get("task_id"):
        return None
    return session.execute(
        select(Task).where(Task.id == scope["task_id"], Task.tenant_id == tenant_id)
    ).scalars().first()


def _get_steps(session: Session, tenant_id: str, scope: dict) -> list[TaskStep]:
    q = select(TaskStep).where(TaskStep.tenant_id == tenant_id)
    if scope.get("task_id"):
        q = q.where(TaskStep.task_id == scope["task_id"])
    return list(session.execute(q).scalars().all())


def run_evaluation(
    session: Session, tenant_id: str,
    agent_id: str | None, task_id: str | None, metrics: list[str],
) -> Evaluation:
    scope = {"agent_id": agent_id, "task_id": task_id}
    results: dict[str, Any] = {}
    for name in metrics:
        fn = _registry.get(name)
        if fn is None:
            results[name] = {"error": f"unknown metric {name!r}"}
            continue
        results[name] = fn(session, tenant_id, scope)
    ev = Evaluation(id=new_id(), tenant_id=tenant_id, agent_id=agent_id, task_id=task_id,
                    metrics=metrics, results=results, status="completed")
    session.add(ev)
    session.flush()
    return ev
