"""Security tests: unauthorized invoke, privilege escalation, policy bypass,
tenant isolation, approval timeout, budget exhaustion, provenance tagging."""

from datetime import timedelta

from sqlalchemy import select

from acp.core.utils import new_id, utcnow
from acp.db.models import Approval, PolicyBundle
from tests.conftest import mk_agent, mk_task, mk_tool


def _basic(client, H, tenant="tenant-a"):
    h = H(tenant)
    tool = mk_tool(client, h, "mock_echo", cost_per_call=0.01)
    agent = mk_agent(client, h, "agent-1", [tool["id"]], capabilities=["general"])
    return h, tool, agent


# 1. unauthorized tool invoke -> 401 (no key), 403 handled at policy layer
def test_no_api_key_401(app_client, H):
    client, _ = app_client
    h, tool, agent = _basic(client, H)
    r = client.post(f"/api/v1/tools/{tool['id']}/invoke", headers={"X-Tenant-ID": "tenant-a"},
                    json={"args": {}, "agent_id": agent["id"]})
    assert r.status_code == 401
    r = client.get("/api/v1/agents", headers=H("tenant-a", key="wrong-key"))
    assert r.status_code == 401


# 2. privilege escalation: agent invokes tool outside its grants -> deny + 403
def test_privilege_escalation_blocked(app_client, H):
    client, app = app_client
    h, _, agent = _basic(client, H)
    other = mk_tool(client, h, "mock_admin_reset", risk_class="medium")
    r = client.post(f"/api/v1/tools/{other['id']}/invoke", headers=h,
                    json={"args": {}, "agent_id": agent["id"]})
    assert r.status_code == 403
    assert r.json()["detail"]["decision"] == "deny"
    denials = client.get("/api/v1/audit?event_type=PermissionDenied", headers=h).json()["items"]
    assert len(denials) >= 1


# 3. policy bypass attempt: tenant denylist denies even a granted tool
def test_policy_bypass_denied(app_client, H):
    client, app = app_client
    h, tool, agent = _basic(client, H)
    with app.state.container.session() as s:
        from acp.core.utils import canonical_json, sha256_hex
        content = {"deny_tool_ids": [tool["id"]]}
        s.add(PolicyBundle(id=new_id(), tenant_id="tenant-a", name="t", version=1,
                           content=content,
                           bundle_hash=sha256_hex(canonical_json(content))))
        s.commit()
    r = client.post(f"/api/v1/tools/{tool['id']}/invoke", headers=h,
                    json={"args": {}, "agent_id": agent["id"]})
    assert r.status_code == 403


# 4. tenant isolation: cross-tenant read -> 403 + SecurityViolationDetected
def test_tenant_isolation(app_client, H):
    client, app = app_client
    ha, _, _ = _basic(client, H, "tenant-a")
    hb = H("tenant-b")
    task = mk_task(client, ha, "book a shipment from NYC to Boston")
    r = client.get(f"/api/v1/tasks/{task['id']}", headers=hb)
    assert r.status_code == 403
    items = client.get("/api/v1/audit?event_type=SecurityViolationDetected", headers=hb).json()["items"]
    assert len(items) >= 1


# 5. approval timeout -> DENY (never auto-approve)
def test_approval_timeout_denies(app_client, H):
    client, app = app_client
    h = H()
    tool = mk_tool(client, h, "mock_echo", risk_class="high", cost_per_call=0.02,
                   metadata={"side_effecting": True})
    mk_agent(client, h, "ops-agent", [tool["id"]], capabilities=["archive", "purge"])
    task = mk_task(client, h, "echo the archive manifest for review")
    t = client.post(f"/api/v1/tasks/{task['id']}/execute", headers=h).json()
    assert t["status"] == "awaiting_approval"
    ap_id = t["approvals"][0]["id"]

    # expire the approval out-of-band, then try to approve and to resume
    with app.state.container.session() as s:
        ap = s.execute(select(Approval).where(Approval.id == ap_id)).scalars().one()
        ap.expires_at = utcnow() - timedelta(seconds=1)
        s.commit()
    r = client.post(f"/api/v1/approvals/{ap_id}/approve", headers=H(role="approver"),
                    json={"decided_by": "human-1"})
    assert r.status_code == 409  # expired: timeout == DENY

    r = client.post(f"/api/v1/tasks/{task['id']}/execute", headers=h)
    assert r.json()["status"] == "denied"


def test_task_budget_limit_enforced_at_creation(app_client, H):
    """budget_limit on task creation is enforced, not decorative."""
    client, _ = app_client
    h = H()
    tools = [mk_tool(client, h, n, cost_per_call=c) for n, c in
             [("mock_get_quote", 0.05), ("mock_select_carrier", 0.05), ("mock_book_shipment", 0.05)]]
    mk_agent(client, h, "logistics-agent", [t["id"] for t in tools],
             capabilities=["logistics", "shipment", "booking"])
    task = mk_task(client, h, "book a shipment from NYC to Boston", budget_limit=0.001)
    r = client.post(f"/api/v1/tasks/{task['id']}/execute", headers=h)
    t = r.json()
    assert t["status"] == "failed"
    assert "budget" in (t["error"] or "").lower()


def test_approval_evidence_includes_policy_reference(app_client, H):
    client, _ = app_client
    h = H()
    tool = mk_tool(client, h, "mock_echo", risk_class="high", cost_per_call=0.02,
                   metadata={"side_effecting": True})
    mk_agent(client, h, "ops-agent", [tool["id"]], capabilities=["archive", "purge"])
    task = mk_task(client, h, "echo the archive manifest for review")
    t = client.post(f"/api/v1/tasks/{task['id']}/execute", headers=h).json()
    assert t["status"] == "awaiting_approval"
    ap = t["approvals"][0]
    assert ap["risk_score"] > 0 and ap["risk_level"] and ap["reasons"]
    assert ap["policy_decision"] in ("require_approval", "allow")
    assert ap["policy_version_hash"] and len(ap["policy_version_hash"]) == 64


# 6. budget exhaustion -> deny + kill switch + CostThresholdExceeded
def test_budget_exhaustion_denies(app_client, H):
    client, _ = app_client
    h = H()
    tools = [mk_tool(client, h, n, cost_per_call=c) for n, c in
             [("mock_get_quote", 0.05), ("mock_select_carrier", 0.05), ("mock_book_shipment", 0.05)]]
    mk_agent(client, h, "logistics-agent", [t["id"] for t in tools],
             capabilities=["logistics", "shipment", "booking"])
    task = mk_task(client, h, "book a shipment from NYC to Boston")
    r = client.post("/api/v1/budgets", headers=h,
                    json={"scope": "task", "scope_id": task["id"], "limit": 0.001})
    assert r.status_code == 201
    r = client.post(f"/api/v1/tasks/{task['id']}/execute", headers=h)
    t = r.json()
    assert t["status"] == "failed", t["status"]
    assert "budget" in (t["error"] or "").lower()
    ev = client.get(f"/api/v1/tasks/{task['id']}/events", headers=h).text
    assert "CostThresholdExceeded" in ev


# 7. untrusted-content provenance tagging (memory + policy)
def test_untrusted_content_provenance(app_client, H):
    client, app = app_client
    store = app.state.container.memory_store
    with app.state.container.session() as s:
        row = store.write(s, "tenant-a", "notes", "k1", {"fact": "x"},
                          {"writer": "reader-agent", "source_trust": "untrusted", "task_id": "t"})
        assert row["quarantined"] is True
        assert store.list(s, "tenant-a", "notes") == []
        s.commit()
    # policy layer: untrusted memory writes are constrained
    d = app.state.container.policy_engine.evaluate({
        "kind": "memory_write", "tenant_id": "tenant-a",
        "provenance": {"source_trust": "untrusted"}})
    assert d.decision == "allow_with_constraints"
    assert d.constraints.get("quarantine") is True
