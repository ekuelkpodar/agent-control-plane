"""Integration: governed tool invocation endpoint (200 / 403 / 202)."""

from tests.conftest import mk_agent, mk_tool


def _setup(client, H):
    h = H()
    low = mk_tool(client, h, "mock_echo", cost_per_call=0.01)
    high = mk_tool(client, h, "mock_format_disk", risk_class="critical", cost_per_call=0.01,
                   metadata={"destructive": True})
    agent = mk_agent(client, h, "ops-agent", [low["id"]], capabilities=["ops"])
    return h, low, high, agent


def test_invoke_allowed_returns_200(app_client, H):
    client, _ = app_client
    h, low, _, agent = _setup(client, H)
    r = client.post(f"/api/v1/tools/{low['id']}/invoke", headers=h,
                    json={"args": {"msg": "hi"}, "agent_id": agent["id"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["result"]["ok"] is True
    assert body["audit_seq"] > 0


def test_invoke_ungranted_tool_403(app_client, H):
    client, _ = app_client
    h, _, high, agent = _setup(client, H)  # agent was NOT granted the critical tool
    r = client.post(f"/api/v1/tools/{high['id']}/invoke", headers=h,
                    json={"args": {}, "agent_id": agent["id"]})
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["decision"] == "deny"


def test_invoke_critical_tool_202_approval(app_client, H):
    client, _ = app_client
    h = H()
    crit = mk_tool(client, h, "mock_format_disk", risk_class="critical", cost_per_call=0.01,
                   metadata={"destructive": True})
    agent = mk_agent(client, h, "ops-agent", [crit["id"]], capabilities=["ops"])
    r = client.post(f"/api/v1/tools/{crit['id']}/invoke", headers=h,
                    json={"args": {"target": "/data"}, "agent_id": agent["id"]})
    assert r.status_code == 202, r.text
    assert r.json()["detail"]["approval_id"]


def test_invoke_requires_agent_identity(app_client, H):
    client, _ = app_client
    h, low, _, _ = _setup(client, H)
    r = client.post(f"/api/v1/tools/{low['id']}/invoke", headers=h, json={"args": {}})
    assert r.status_code == 400  # no ambient authority: agent_id required
