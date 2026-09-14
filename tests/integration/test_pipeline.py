"""Integration: full governed pipeline incl. approval-resume and reject paths."""

from tests.conftest import mk_agent, mk_task, mk_tool


def _logistics_setup(client, H):
    h = H()
    tools = [mk_tool(client, h, n, cost_per_call=c) for n, c in
             [("mock_get_quote", 0.01), ("mock_select_carrier", 0.01), ("mock_book_shipment", 0.05)]]
    agent = mk_agent(client, h, "logistics-agent", [t["id"] for t in tools],
                     capabilities=["logistics", "shipment", "booking"])
    return h, agent, tools


def test_full_pipeline_happy_path(app_client, H):
    client, _ = app_client
    h, agent, _ = _logistics_setup(client, H)
    task = mk_task(client, h, "book a shipment from NYC to Boston",
                   {"args": {"origin": "NYC", "dest": "Boston"}})
    assert task["status"] == "created"
    assert task["agent_id"] is None  # router decides

    r = client.post(f"/api/v1/tasks/{task['id']}/execute", headers=h)
    assert r.status_code == 200, r.text
    t = r.json()
    assert t["status"] == "completed", t["error"]
    assert t["agent_id"] == agent["id"]  # router selected the capable agent
    assert len(t["plan"]["steps"]) == 3
    assert t["cost_incurred"] > 0
    assert t["risk_assessment"]["risk_level"] == "low"

    # audit chain verifies; events streamed
    assert client.get("/api/v1/audit/verify", headers=h).json()["ok"] is True
    ev = client.get(f"/api/v1/tasks/{task['id']}/events", headers=h).text
    for et in ("TaskCreated", "TaskPlanned", "TaskRouted", "TaskStarted",
               "ToolInvoked", "TaskCompleted"):
        assert et in ev, et


def test_approval_resume_path(app_client, H):
    client, _ = app_client
    h = H()
    tool = mk_tool(client, h, "mock_echo", risk_class="high", cost_per_call=0.02,
                   metadata={"side_effecting": True})
    mk_agent(client, h, "ops-agent", [tool["id"]], capabilities=["archive", "purge"])
    task = mk_task(client, h, "echo the archive manifest for review")

    r = client.post(f"/api/v1/tasks/{task['id']}/execute", headers=h)
    t = r.json()
    assert t["status"] == "awaiting_approval", t
    assert len(t["approvals"]) == 1
    ap = t["approvals"][0]
    assert ap["status"] == "requested"
    assert ap["risk_level"] in ("high", "critical")
    assert ap["risk_score"] > 0 and ap["reasons"]

    # approve -> execute resumes -> completes
    r = client.post(f"/api/v1/approvals/{ap['id']}/approve", headers=H(role="approver"),
                    json={"decided_by": "human-1", "note": "ok"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"

    r = client.post(f"/api/v1/tasks/{task['id']}/execute", headers=h)
    t = r.json()
    assert t["status"] == "completed", t["error"]

    # evidence: approval decision is in the audit ledger
    items = client.get("/api/v1/audit?event_type=ApprovalGranted", headers=h).json()["items"]
    assert any(i["task_id"] == task["id"] for i in items)


def test_approval_reject_denies_task(app_client, H):
    client, _ = app_client
    h = H()
    tool = mk_tool(client, h, "mock_echo", risk_class="high", cost_per_call=0.02,
                   metadata={"side_effecting": True})
    mk_agent(client, h, "ops-agent", [tool["id"]], capabilities=["archive", "purge"])
    task = mk_task(client, h, "echo the archive manifest for review")
    t = client.post(f"/api/v1/tasks/{task['id']}/execute", headers=h).json()
    assert t["status"] == "awaiting_approval"
    ap = t["approvals"][0]

    r = client.post(f"/api/v1/approvals/{ap['id']}/reject", headers=H(role="approver"),
                    json={"decided_by": "human-1", "note": "too risky"})
    assert r.status_code == 200

    r = client.post(f"/api/v1/tasks/{task['id']}/execute", headers=h)
    assert r.json()["status"] == "denied"


def test_approval_rbac_viewer_cannot_decide(app_client, H):
    """RBAC: the default viewer role may not approve; denial is audited."""
    client, _ = app_client
    h = H()
    tool = mk_tool(client, h, "mock_echo", risk_class="high", cost_per_call=0.02,
                   metadata={"side_effecting": True})
    mk_agent(client, h, "ops-agent", [tool["id"]], capabilities=["archive", "purge"])
    task = mk_task(client, h, "echo the archive manifest for review")
    t = client.post(f"/api/v1/tasks/{task['id']}/execute", headers=h).json()
    ap = t["approvals"][0]
    r = client.post(f"/api/v1/approvals/{ap['id']}/approve", headers=h,
                    json={"decided_by": "mallory"})
    assert r.status_code == 403
    denials = client.get("/api/v1/audit?event_type=PermissionDenied", headers=h).json()["items"]
    assert len(denials) >= 1


def test_approvals_task_id_filter(app_client, H):
    client, _ = app_client
    h = H()
    tool = mk_tool(client, h, "mock_echo", risk_class="high", cost_per_call=0.02,
                   metadata={"side_effecting": True})
    mk_agent(client, h, "ops-agent", [tool["id"]], capabilities=["archive", "purge"])
    t1 = mk_task(client, h, "echo the archive manifest for review")
    client.post(f"/api/v1/tasks/{t1['id']}/execute", headers=h)

    all_items = client.get("/api/v1/approvals", headers=h).json()["items"]
    mine = client.get(f"/api/v1/approvals?task_id={t1['id']}", headers=h).json()["items"]
    assert len(all_items) >= 1
    assert len(mine) == 1 and mine[0]["task_id"] == t1["id"]
    # approval evidence fields
    ap = mine[0]
    assert ap["risk_score"] > 0 and ap["risk_level"] and ap["reasons"]
    assert ap["expires_at"] and ap["requested_at"]


def test_cancel_kill_switch(app_client, H):
    client, _ = app_client
    h, _, _ = _logistics_setup(client, H)
    task = mk_task(client, h, "book a shipment from NYC to Boston")
    r = client.post(f"/api/v1/tasks/{task['id']}/cancel", headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"
    # cancelled tasks do not execute
    r = client.post(f"/api/v1/tasks/{task['id']}/execute", headers=h)
    assert r.json()["status"] == "cancelled"


def _financial_booking_setup(client, H):
    """Agent with a genuinely financial tool: carrier.book is booked as a
    financial, irreversible side effect, like a real shipment booking."""
    h = H()
    quote = mk_tool(client, h, "carrier.quote", cost_per_call=0.01)
    book = mk_tool(client, h, "carrier.book", risk_class="high", cost_per_call=0.01,
                   metadata={"financial": True, "irreversible": True, "side_effecting": True})
    agent = mk_agent(client, h, "logistics-agent", [quote["id"], book["id"]],
                     capabilities=["freight_quoting", "carrier_booking"])
    return h, agent


def test_approval_covers_financial_tool_invoke(app_client, H):
    """Flagship: approving the plan must not demand a second approval when the
    approved financial tool is invoked. One human approval -> booking runs."""
    client, _ = app_client
    h, agent = _financial_booking_setup(client, H)
    task = mk_task(client, h, "Find the best carrier for this shipment and book it",
                   {"args": {"weight_kg": 1000, "distance_km": 800,
                             "origin": "Chicago, IL", "destination": "Dallas, TX"}},
                   agent_id=agent["id"])

    r = client.post(f"/api/v1/tasks/{task['id']}/execute", headers=h)
    t = r.json()
    assert t["status"] == "awaiting_approval", t
    assert len(t["approvals"]) == 1
    ap = t["approvals"][0]
    assert ap["risk_level"] == "critical"

    r = client.post(f"/api/v1/approvals/{ap['id']}/approve", headers=H(role="approver"),
                    json={"decided_by": "human-1", "note": "within budget"})
    assert r.status_code == 200, r.text

    r = client.post(f"/api/v1/tasks/{task['id']}/execute", headers=h)
    t = r.json()
    assert t["status"] == "completed", t["error"]

    # exactly ONE approval was ever requested for this task: the plan gate.
    # the per-tool choke point must not re-ask for the approved booking.
    # (SSE repeats the type in the event line and the JSON payload.)
    ev = client.get(f"/api/v1/tasks/{task['id']}/events", headers=h).text
    assert ev.count("event: ApprovalRequested") == 1, ev
    assert "ApprovalGranted" in ev and "TaskCompleted" in ev
    # the booking tool actually ran through the governed choke point
    assert "ToolInvoked" in ev


def test_direct_invoke_financial_tool_still_requires_approval(app_client, H):
    """Plan-approval coverage must NOT leak into direct tool invocation:
    invoking the financial tool outside an approved plan still needs approval."""
    client, _ = app_client
    h, agent = _financial_booking_setup(client, H)
    book_id = [tid for tid in agent["tool_ids"]][1]
    r = client.post(f"/api/v1/tools/{book_id}/invoke", headers=h,
                    json={"args": {"carrier": "SwiftFreight"}, "agent_id": agent["id"]})
    assert r.status_code == 202, r.text
    assert r.json()["detail"]["approval_id"]
