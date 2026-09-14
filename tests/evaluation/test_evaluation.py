"""Evaluation suite: run the metric registry over a real pipeline task."""

from tests.conftest import mk_agent, mk_task, mk_tool


def test_evaluation_metrics_over_e2e_task(app_client, H):
    client, _ = app_client
    h = H()
    tools = [mk_tool(client, h, n, cost_per_call=c) for n, c in
             [("mock_get_quote", 0.01), ("mock_select_carrier", 0.01), ("mock_book_shipment", 0.05)]]
    agent = mk_agent(client, h, "logistics-agent", [t["id"] for t in tools],
                     capabilities=["logistics", "shipment", "booking"])
    task = mk_task(client, h, "book a shipment from NYC to Boston")
    t = client.post(f"/api/v1/tasks/{task['id']}/execute", headers=h).json()
    assert t["status"] == "completed"

    r = client.post("/api/v1/evaluations", headers=h, json={
        "agent_id": agent["id"], "task_id": task["id"],
        "metrics": ["task_success", "tool_call_accuracy", "policy_violations", "latency", "cost"]})
    assert r.status_code == 201, r.text
    ev = r.json()
    assert ev["results"]["task_success"] == 1.0
    assert ev["results"]["tool_call_accuracy"] == 1.0
    assert ev["results"]["policy_violations"] == 0
    assert ev["results"]["cost"] > 0

    r = client.get(f"/api/v1/evaluations/{ev['id']}", headers=h)
    assert r.status_code == 200
    assert r.json()["results"]["task_success"] == 1.0


def test_metrics_endpoint(app_client, H):
    client, _ = app_client
    h = H()
    r = client.get("/api/v1/metrics", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert "tasks_by_status" in body and "available_metrics" in body
