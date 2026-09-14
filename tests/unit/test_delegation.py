"""Unit: delegation tokens — narrow-only, tenant-bound, short-lived."""


import pytest

from acp.core.errors import PolicyDenied
from acp.governance.delegation import DelegationIssuer


def _issuer():
    return DelegationIssuer("unit-test-secret")


def _issue(issuer, **kw):
    kw.setdefault("tenant_id", "t1")
    kw.setdefault("subject", "user-1")
    kw.setdefault("actor_agent_id", "agent-1")
    kw.setdefault("task_id", "task-1")
    kw.setdefault("scope_tools", ["tool-a", "tool-b"])
    kw.setdefault("audience", DelegationIssuer.AUDIENCE)
    return issuer.issue(**kw)


def test_issue_and_validate():
    issuer = _issuer()
    issued = _issue(issuer)
    claims = issuer.validate(issued["token"], tenant_id="t1")
    assert claims["sub"] == "user-1"
    assert claims["act"] == "agent-1"
    assert set(claims["scope_tools"]) == {"tool-a", "tool-b"}


def test_tenant_mismatch_fails_closed():
    issuer = _issuer()
    issued = _issue(issuer)
    with pytest.raises(PolicyDenied):
        issuer.validate(issued["token"], tenant_id="t2")


def test_revoked_token_rejected():
    issuer = _issuer()
    issued = _issue(issuer)
    with pytest.raises(PolicyDenied):
        issuer.validate(issued["token"], tenant_id="t1", revoked_jtis={issued["jti"]})


def test_expired_token_rejected():
    issuer = _issuer()
    issued = _issue(issuer, ttl_seconds=-1)
    with pytest.raises(PolicyDenied):
        issuer.validate(issued["token"], tenant_id="t1")


def test_narrow_may_only_narrow():
    issuer = _issuer()
    parent = _issue(issuer)["claims"]
    child = DelegationIssuer.narrow(parent, ["tool-a"])
    assert child["scope_tools"] == ["tool-a"]
    assert child["parent_jti"] == parent["jti"]
    with pytest.raises(PolicyDenied):
        DelegationIssuer.narrow(parent, ["tool-a", "tool-c"])  # widening blocked


def test_tampered_token_rejected():
    issuer = _issuer()
    issued = _issue(issuer)
    bad = issued["token"][:-4] + "xxxx"
    with pytest.raises(PolicyDenied):
        issuer.validate(bad, tenant_id="t1")
