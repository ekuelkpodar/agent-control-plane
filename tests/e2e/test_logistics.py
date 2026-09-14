"""E2E: logistics flow via the public REST contract.

Registers an agent + mock tools (LocalFunctionToolExecutor), creates a task
with ONLY {goal, input} (router selects the agent), and runs the governed
pipeline: quote -> select -> book under the policy cost threshold.
"""

from tests.conftest import mk_agent, mk_task, mk_tool


def test_logistics_flow_router_selected(app_client, H):
    client, _ = app_client
    h = H()

    quote = mk_tool(client, h, "mock_get_quote", cost_per_call=0.01)
    select_ = mk_tool(client, h, "mock_select_carrier", cost_per_call=0.01)
    book = mk_tool(client, h, "mock_book_shipment", cost_per_call=0.05,
                   metadata={"financial": False, "side_effecting": True})
    agent = mk_agent(client, h, "logistics-agent",
                     [quote["id"], select_["id"], book["id"]],
                     capabilities=["logistics", "shipment", "booking", "freight"])

    # Demo contract: only {goal, input}; agent_id is OPTIONAL (router decides).
    task = mk_task(client, h, "book a shipment from NYC to Boston",
                   {"args": {"origin": "NYC", "dest": "Boston", "weight_kg": 120}})
    assert task["agent_id"] is None

    t = client.post(f"/api/v1/tasks/{task['id']}/execute", headers=h).json()
    assert t["status"] == "completed", t["error"]
    assert t["agent_id"] == agent["id"]
    steps = t["plan"]["steps"]
    assert [s["name"] for s in steps] == ["mock_get_quote", "mock_select_carrier", "mock_book_shipment"]

    # Policy: plan stayed under the approval cost threshold -> no approval needed.
    assert t["approvals"] == []
    assert t["cost_estimate"] < 5.0
    assert t["cost_incurred"] > 0

    # Cost attribution.
    summary = client.get(f"/api/v1/cost/summary?scope=task&scope_id={task['id']}", headers=h).json()
    assert summary["total"] > 0
    assert len(summary["by_tool"]) == 3

    # Audit chain verifies end-to-end.
    assert client.get("/api/v1/audit/verify", headers=h).json()["ok"] is True


def test_logistics_flow_with_explicit_agent(app_client, H):
    client, _ = app_client
    h = H()
    quote = mk_tool(client, h, "mock_get_quote", cost_per_call=0.01)
    select_ = mk_tool(client, h, "mock_select_carrier", cost_per_call=0.01)
    book = mk_tool(client, h, "mock_book_shipment", cost_per_call=0.05)
    agent = mk_agent(client, h, "logistics-agent",
                     [quote["id"], select_["id"], book["id"]],
                     capabilities=["logistics", "shipment", "booking"])

    task = mk_task(client, h, "book a shipment from NYC to Boston", agent_id=agent["id"])
    t = client.post(f"/api/v1/tasks/{task['id']}/execute", headers=h).json()
    assert t["status"] == "completed", t["error"]
    assert t["agent_id"] == agent["id"]
