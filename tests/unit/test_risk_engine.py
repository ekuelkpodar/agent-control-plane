"""Unit: risk engine — deterministic floor + model-hook asymmetry."""

from acp.core.config import Settings
from acp.governance.risk import RiskEngine


def _engine():
    return RiskEngine(Settings(database_url="sqlite:///:memory:"))


def test_tool_risk_floor_sets_minimum():
    e = _engine()
    r = e.assess({"tools": [{"name": "t", "risk_class": "critical",
                             "metadata": {"destructive": True}}]})
    assert r.risk_score >= 70.0
    assert r.risk_level == "critical"  # floor 70 + destructive 20 = 90 >= 75
    assert r.requires_human_approval is True
    assert "tool_risk_floor" in r.score_breakdown


def test_deterministic_factors_add_up():
    e = _engine()
    r = e.assess({"tools": [{"name": "t", "risk_class": "low",
                             "metadata": {"destructive": True, "side_effecting": True}}],
                  "goal": "pay the invoice"})
    assert r.score_breakdown["destructive"] == 20.0
    assert r.score_breakdown["financial"] == 15.0
    assert r.risk_score >= 40.0


def test_low_risk_plan_needs_no_approval():
    e = _engine()
    r = e.assess({"tools": [{"name": "t", "risk_class": "low", "metadata": {}}],
                  "estimated_cost": 0.05})
    assert r.risk_level == "low"
    assert r.requires_human_approval is False
    assert set(r.reasons)  # explainable


def test_model_hook_may_raise_but_never_lower():
    e = _engine()
    base = e.assess({"tools": [{"name": "t", "risk_class": "low", "metadata": {}}]})
    e.register_model_scorer(lambda ctx: {"score_delta": -50.0, "reasons": ["shady"]})
    after = e.assess({"tools": [{"name": "t", "risk_class": "low", "metadata": {}}]})
    assert after.risk_score == base.risk_score  # lowering clamped to 0
    assert "model_uplift" not in after.score_breakdown


def test_model_hook_raise_is_sticky_for_approval():
    e = _engine()
    e.register_model_scorer(lambda ctx: {"score_delta": 60.0, "reasons": ["anomaly"]})
    r = e.assess({"tools": [{"name": "t", "risk_class": "low", "metadata": {}}]})
    assert r.risk_score >= 60.0
    assert r.requires_human_approval is True
    assert "model_uplift" in r.score_breakdown


def test_output_schema():
    e = _engine()
    r = e.assess({"tools": []})
    assert isinstance(r.risk_score, float)
    assert r.risk_level in ("low", "medium", "high", "critical")
    assert isinstance(r.requires_human_approval, bool)
    assert isinstance(r.reasons, list)
    assert isinstance(r.score_breakdown, dict)
