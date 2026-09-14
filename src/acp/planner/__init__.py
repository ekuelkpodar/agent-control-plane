"""Planner: Planner protocol + DeterministicPlanner + RuleBasedPlanner +
LLMPlanner (interface only — real LLM planning is V1).

Plan schema: {steps:[{id,name,tool_id?,args,estimated_cost}], approvals_required, risk_hints}
"""

from __future__ import annotations

import logging
import re
from typing import Any

log = logging.getLogger(__name__)

BOOKING_RE = re.compile(r"book\s+(a\s+)?(shipment|flight|hotel|table|appointment|delivery)", re.IGNORECASE)


class Planner:
    def plan(self, *, goal: str, task_input: dict, agent: dict, tools: list[dict]) -> dict[str, Any]:
        raise NotImplementedError


class DeterministicPlanner(Planner):
    """Deterministic, explainable plan generation from registered tools.

    Strategy: match goal keywords against tool names; fall back to a single
    reasoning step (no tool) executed via the model provider.
    """

    def plan(self, *, goal: str, task_input: dict, agent: dict, tools: list[dict]) -> dict[str, Any]:
        goal_l = goal.lower()
        usable = [t for t in tools if t.get("id") in set(agent.get("tool_ids") or [])]
        steps: list[dict[str, Any]] = []

        # Booking-style flow: quote -> select -> book (logistics e2e shape).
        if BOOKING_RE.search(goal):
            ordered = []
            for want in ("quote", "select", "book"):
                hit = next((t for t in usable if want in t.get("name", "").lower()), None)
                if hit and hit not in ordered:
                    ordered.append(hit)
            for i, t in enumerate(ordered):
                steps.append(self._step(f"step-{i+1}", t, task_input, i, len(ordered)))
        else:
            # Generic: tools whose name tokens appear in the goal, in registry order.
            goal_tokens = set(re.findall(r"[a-z0-9]+", goal_l))
            for t in usable:
                name_tokens = set(re.findall(r"[a-z0-9_]+", t.get("name", "").lower().replace("_", " ")))
                name_tokens |= set(re.findall(r"[a-z0-9]+", t.get("name", "").lower()))
                if goal_tokens & name_tokens:
                    steps.append(self._step(f"step-{len(steps)+1}", t, task_input, len(steps), 0))

        if not steps:
            steps.append({
                "id": "step-1", "name": "reason", "tool_id": None,
                "args": {"goal": goal}, "estimated_cost": 0.002,
            })
        estimated = round(sum(s.get("estimated_cost", 0.0) for s in steps), 4)
        return {
            "steps": steps,
            "approvals_required": any(
                str((next((t for t in usable if t.get("id") == s.get("tool_id")), {}) or {}).get("risk_class", "low")).lower()
                in ("high", "critical") for s in steps if s.get("tool_id")
            ),
            "risk_hints": [],
            "estimated_cost": estimated,
            "strategy": "deterministic",
        }

    @staticmethod
    def _step(step_id: str, tool: dict, task_input: dict, idx: int, total: int) -> dict[str, Any]:
        args = dict(task_input.get("args") or {})
        # Wire step outputs forward by convention: later steps may reference
        # prior results via the executor's context (kept simple for MVP).
        return {
            "id": step_id,
            "name": tool.get("name", step_id),
            "tool_id": tool.get("id"),
            "args": args,
            "estimated_cost": round(float(tool.get("cost_per_call") or 0.0) + 0.002, 4),
        }


class RuleBasedPlanner(DeterministicPlanner):
    """DeterministicPlanner + rule-based risk hints and approval flags."""

    def plan(self, *, goal: str, task_input: dict, agent: dict, tools: list[dict]) -> dict[str, Any]:
        plan = super().plan(goal=goal, task_input=task_input, agent=agent, tools=tools)
        hints: list[str] = []
        by_id = {t.get("id"): t for t in tools}
        for s in plan["steps"]:
            t = by_id.get(s.get("tool_id") or "")
            if not t:
                continue
            rc = str(t.get("risk_class", "low")).lower()
            if rc in ("high", "critical"):
                hints.append(f"step {s['id']} uses {rc}-risk tool {t.get('name')}")
            if (t.get("metadata") or {}).get("destructive"):
                hints.append(f"step {s['id']} is destructive")
                plan["approvals_required"] = True
        plan["risk_hints"] = hints
        plan["strategy"] = "rule_based"
        return plan


class LLMPlanner(Planner):
    """Interface for LLM-backed planning (V1). No concrete real implementation
    ships in the MVP — planning via an LLM without the governance rail's
    plan-admission gate would violate policy-before-execution."""

    def plan(self, *, goal: str, task_input: dict, agent: dict, tools: list[dict]) -> dict[str, Any]:
        raise NotImplementedError("LLMPlanner is an interface for V1 (no uncontrolled LLM planning in MVP).")


def build_planner(name: str) -> Planner:
    if name == "rule_based":
        return RuleBasedPlanner()
    if name == "llm":
        return LLMPlanner()
    return DeterministicPlanner()
