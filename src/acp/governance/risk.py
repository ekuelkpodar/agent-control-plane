"""Risk engine: hybrid with ASYMMETRY.

Deterministic rules set the FLOOR. An optional model scorer may only RAISE
risk — never lower it, never clear requires_human_approval, never override a
rule-set trigger. Output: {risk_score, risk_level, requires_human_approval,
reasons[], score_breakdown}.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from acp.core.protocols import RiskAssessment

log = logging.getLogger(__name__)

RISK_CLASS_FLOOR = {"low": 5.0, "medium": 20.0, "high": 45.0, "critical": 70.0}
FINANCIAL_KEYWORDS = ("pay", "purchase", "refund", "transfer", "charge", "invoice", "payout", "withdraw")


class RiskEngine:
    def __init__(self, settings):
        self._settings = settings
        self._model_scorers: list[Callable[[dict[str, Any]], dict[str, Any]]] = []

    def register_model_scorer(self, scorer: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        """Register an ML/model hook. It may only ADD risk (score_delta >= 0)."""
        self._model_scorers.append(scorer)

    def _level(self, score: float) -> str:
        if score >= self._settings.critical_risk_score:
            return "critical"
        if score >= self._settings.high_risk_score:
            return "high"
        if score >= 25.0:
            return "medium"
        return "low"

    def assess(self, ctx: dict[str, Any]) -> RiskAssessment:
        """ctx: {tools:[{id,name,risk_class,metadata}], goal, estimated_cost,
        untrusted_content:bool, data_classification, action_kinds:[...]}"""
        breakdown: dict[str, float] = {}
        reasons: list[str] = []
        tools = ctx.get("tools") or []
        goal = str(ctx.get("goal") or "")
        cost = float(ctx.get("estimated_cost") or 0.0)

        score = 0.0
        # 1. Tool risk-class floor: max of tool floors.
        if tools:
            floor = max(RISK_CLASS_FLOOR.get(str(t.get("risk_class", "low")).lower(), 0.0) for t in tools)
            score = max(score, floor)
            breakdown["tool_risk_floor"] = floor
            reasons.append(f"tool risk floor {floor:.0f} from {[t.get('name') for t in tools]}")

        # 2. Deterministic factor rules (always true regardless of context).
        def add(points: float, key: str, reason: str):
            nonlocal score
            score += points
            breakdown[key] = breakdown.get(key, 0.0) + points
            reasons.append(reason)

        side_effecting = sum(1 for t in tools if (t.get("metadata") or {}).get("side_effecting"))
        if side_effecting:
            add(5.0 * side_effecting, "side_effecting_steps", f"{side_effecting} side-effecting tool(s)")
        destructive = any((t.get("metadata") or {}).get("destructive") for t in tools)
        if destructive:
            add(20.0, "destructive", "destructive action in plan")
        irreversible = any((t.get("metadata") or {}).get("irreversible") for t in tools)
        if irreversible:
            add(15.0, "irreversible", "irreversible action in plan")
        financial = any((t.get("metadata") or {}).get("financial") for t in tools) or any(
            k in goal.lower() for k in FINANCIAL_KEYWORDS
        )
        if financial:
            add(15.0, "financial", "financial transaction involved")
        if cost > 10.0:
            add(10.0, "high_cost", f"estimated cost ${cost:.2f} > $10")
        if ctx.get("untrusted_content"):
            add(10.0, "untrusted_content", "plan derived from untrusted content")
        classification = str(ctx.get("data_classification") or "internal").lower()
        if classification in ("confidential", "restricted"):
            add(10.0, "sensitive_data", f"data classification={classification}")
        if ctx.get("cross_boundary"):
            add(10.0, "cross_boundary", "cross data-boundary flow")

        score = min(100.0, score)
        level = self._level(score)
        requires = level in ("high", "critical") or score >= self._settings.risk_approval_threshold
        if requires and level in ("high", "critical"):
            reasons.append(f"risk level {level} requires human approval")

        # 3. Model hook: may ONLY raise. Enforce asymmetry explicitly.
        for scorer in self._model_scorers:
            try:
                out = scorer(ctx) or {}
            except Exception as exc:
                log.warning("model risk scorer failed (ignored, rules stand): %s", exc)
                continue
            delta = float(out.get("score_delta", 0.0))
            if delta < 0:
                log.warning(
                    "model risk scorer attempted to LOWER risk by %s — clamped to 0 (asymmetry enforced)",
                    delta,
                )
                delta = 0.0
            if delta:
                score = min(100.0, score + delta)
                breakdown["model_uplift"] = breakdown.get("model_uplift", 0.0) + delta
                reasons.extend(out.get("reasons") or ["model-based risk uplift"])
            # The model can never clear a rule-set approval requirement.
            level = self._level(score)
            requires = requires or level in ("high", "critical") or score >= self._settings.risk_approval_threshold

        return RiskAssessment(
            risk_score=round(score, 2),
            risk_level=level,
            requires_human_approval=requires,
            reasons=reasons,
            score_breakdown={k: round(v, 2) for k, v in breakdown.items()},
            policy_refs=["risk.deterministic_floor.v1"],
        )
