"""Unit: policy engine — fail-closed, guardrails, deny-by-default."""

from acp.core.config import Settings
from acp.governance.policy import MinimalRuleEngine, OPAEngine


def _engine():
    return MinimalRuleEngine(Settings(database_url="sqlite:///:memory:"))


def _agent(tool_ids):
    return {"id": "a1", "tool_ids": tool_ids, "name": "a"}


def _tool(tid, name="t", risk_class="low", metadata=None):
    return {"id": tid, "name": name, "risk_class": risk_class, "metadata": metadata or {}}


def test_deny_by_default_unknown_kind():
    d = _engine().evaluate({"kind": "teleport", "tenant_id": "t1"})
    assert d.decision == "deny"


def test_allow_when_guardrails_pass():
    d = _engine().evaluate({
        "kind": "tool_invoke", "tenant_id": "t1",
        "agent": _agent(["tool-1"]), "tool": _tool("tool-1"), "tools": [_tool("tool-1")],
    })
    assert d.decision == "allow"


def test_ungranted_tool_denied_least_privilege():
    d = _engine().evaluate({
        "kind": "tool_invoke", "tenant_id": "t1",
        "agent": _agent(["tool-1"]), "tool": _tool("tool-2", "evil"), "tools": [_tool("tool-2", "evil")],
    })
    assert d.decision == "deny"
    assert any("least privilege" in r or "not granted" in r for r in d.reasons)


def test_critical_tool_requires_approval():
    d = _engine().evaluate({
        "kind": "tool_invoke", "tenant_id": "t1",
        "agent": _agent(["tool-1"]),
        "tool": _tool("tool-1", risk_class="critical"), "tools": [_tool("tool-1", risk_class="critical")],
    })
    assert d.decision == "require_approval"


def test_destructive_tool_requires_approval():
    d = _engine().evaluate({
        "kind": "plan_admission", "tenant_id": "t1",
        "agent": _agent(["tool-1"]),
        "tools": [_tool("tool-1", metadata={"destructive": True})],
    })
    assert d.decision == "require_approval"


def test_cost_above_threshold_requires_approval():
    d = _engine().evaluate({
        "kind": "plan_admission", "tenant_id": "t1",
        "agent": _agent(["tool-1"]), "tools": [_tool("tool-1")],
        "cost_estimate": 99.0, "tenant_policy": {"require_approval_above_cost": 5.0},
    })
    assert d.decision == "require_approval"


def test_cross_tenant_arg_always_denied():
    d = _engine().evaluate({
        "kind": "tool_invoke", "tenant_id": "t1",
        "agent": _agent(["tool-1"]), "tool": _tool("tool-1"), "tools": [_tool("tool-1")],
        "args": {"tenant_id": "t2"},
    })
    assert d.decision == "deny"


def test_tenant_denylist_denied():
    d = _engine().evaluate({
        "kind": "tool_invoke", "tenant_id": "t1",
        "agent": _agent(["tool-1"]), "tool": _tool("tool-1", "t"), "tools": [_tool("tool-1", "t")],
        "tenant_policy": {"deny_tool_ids": ["tool-1"]},
    })
    assert d.decision == "deny"


def test_tenant_allowlist_denied_when_absent():
    d = _engine().evaluate({
        "kind": "tool_invoke", "tenant_id": "t1",
        "agent": _agent(["tool-1", "tool-2"]),
        "tool": _tool("tool-2", "t2"), "tools": [_tool("tool-2", "t2")],
        "tenant_policy": {"allow_tool_ids": ["tool-1"]},
    })
    assert d.decision == "deny"


def test_memory_write_untrusted_is_constrained():
    d = _engine().evaluate({
        "kind": "memory_write", "tenant_id": "t1",
        "provenance": {"source_trust": "untrusted"},
    })
    assert d.decision == "allow_with_constraints"
    assert d.constraints.get("quarantine") is True


def test_version_hash_stable():
    e = _engine()
    assert e.version_hash() == e.version_hash() and len(e.version_hash()) == 64


def test_opa_unreachable_fails_closed():
    opa = OPAEngine("http://127.0.0.1:1", timeout=0.2)
    d = opa.evaluate({"kind": "tool_invoke", "tenant_id": "t1"})
    assert d.decision == "deny"
    assert any("fail-closed" in r for r in d.reasons)
