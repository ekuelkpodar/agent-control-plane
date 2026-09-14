"""Router: Router protocol + WeightedRouter.

Scores candidates on capability / cost / latency / risk / policy /
availability / history. Returns a ranked list with score breakdowns.
"""

from __future__ import annotations

import logging
import re

log = logging.getLogger(__name__)

RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class Router:
    def rank(self, *, goal: str, plan: dict, candidates: list[dict],
             tools: list[dict], policy_engine, tenant_policy: dict) -> list[dict]:
        raise NotImplementedError


class WeightedRouter(Router):
    def __init__(self, weights: dict[str, float] | None = None):
        self._weights = weights or {
            "capability": 0.30, "cost": 0.15, "latency": 0.10, "risk": 0.15,
            "policy": 0.15, "availability": 0.10, "history": 0.05,
        }

    def rank(self, *, goal: str, plan: dict, candidates: list[dict],
             tools: list[dict], policy_engine, tenant_policy: dict) -> list[dict]:
        plan_tool_ids = {s.get("tool_id") for s in plan.get("steps", []) if s.get("tool_id")}
        goal_tokens = set(re.findall(r"[a-z0-9]+", goal.lower()))
        tool_by_id = {t.get("id"): t for t in tools}
        ranked = []
        for agent in candidates:
            scores: dict[str, float] = {}
            granted = set(agent.get("tool_ids") or [])
            # capability: tool coverage + capability keyword overlap
            coverage = (len(plan_tool_ids & granted) / len(plan_tool_ids)) if plan_tool_ids else 1.0
            caps = set()
            for c in agent.get("capabilities") or []:
                caps |= set(re.findall(r"[a-z0-9]+", str(c).lower()))
            overlap = len(goal_tokens & caps) / max(len(goal_tokens), 1)
            scores["capability"] = round(0.7 * coverage + 0.3 * overlap, 4)
            # cost: cheaper model config wins
            model_cost = float((agent.get("model_config") or {}).get("cost_per_1k", 0.01))
            scores["cost"] = round(1.0 / (1.0 + model_cost * 100), 4)
            # latency
            latency = float((agent.get("model_config") or {}).get("latency_ms_p50", 800.0))
            scores["latency"] = round(1.0 / (1.0 + latency / 1000.0), 4)
            # risk: agent max risk vs plan tool risk
            plan_risk = max([RISK_ORDER.get(str((tool_by_id.get(tid) or {}).get("risk_class", "low")).lower(), 0)
                             for tid in plan_tool_ids] or [0])
            agent_max = RISK_ORDER.get(str(agent.get("max_risk_level", "high")).lower(), 2)
            scores["risk"] = 1.0 if agent_max >= plan_risk else 0.0
            # policy: admission for this agent+plan
            decision = policy_engine.evaluate({
                "kind": "task_admission", "tenant_id": agent.get("tenant_id"),
                "agent": agent, "tools": [tool_by_id.get(tid) for tid in plan_tool_ids if tool_by_id.get(tid)],
                "tenant_policy": tenant_policy,
            })
            scores["policy"] = {"allow": 1.0, "allow_with_constraints": 0.8,
                                "require_approval": 0.4, "deny": 0.0}[decision.decision]
            # availability
            scores["availability"] = 1.0 if agent.get("status") == "activated" else 0.3
            # history
            scores["history"] = float(agent.get("history_score", 0.5))
            total = round(sum(scores[k] * self._weights.get(k, 0.0) for k in scores), 4)
            ranked.append({
                "agent_id": agent.get("id"), "score": total,
                "breakdown": scores, "policy_decision": decision.decision,
            })
        ranked.sort(key=lambda r: r["score"], reverse=True)
        return ranked

    def select(self, **kwargs) -> dict | None:
        ranked = self.rank(**kwargs)
        eligible = [r for r in ranked if r["policy_decision"] != "deny" and r["breakdown"]["capability"] > 0]
        return eligible[0] if eligible else None
