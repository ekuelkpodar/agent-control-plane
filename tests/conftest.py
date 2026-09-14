"""Shared fixtures: isolated app + TestClient per test (fresh SQLite file DB)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

API_KEY = "test-key"


@pytest.fixture()
def app_client(tmp_path):
    from acp.api.app import create_app
    from acp.core.config import Settings
    from acp.db import reset_db_cache

    db = tmp_path / "test.db"
    cfg = Settings(database_url=f"sqlite:///{db}", api_key=API_KEY)
    reset_db_cache()
    app = create_app(cfg)
    client = TestClient(app, raise_server_exceptions=False)
    yield client, app
    client.close()


@pytest.fixture()
def H():
    def _headers(tenant: str = "tenant-a", key: str = API_KEY, role: str | None = None):
        h = {"Authorization": f"Bearer {key}", "X-Tenant-ID": tenant}
        if role:
            h["X-Role"] = role
        return h
    return _headers


def mk_tool(client, headers, name, risk_class="low", cost_per_call=0.01, metadata=None, description=""):
    r = client.post("/api/v1/tools", headers=headers, json={
        "name": name, "description": description or f"mock tool {name}",
        "risk_class": risk_class, "cost_per_call": cost_per_call,
        "metadata": metadata or {}})
    assert r.status_code == 201, r.text
    return r.json()


def mk_agent(client, headers, name, tool_ids, capabilities=None, model_config=None, activate=True):
    r = client.post("/api/v1/agents", headers=headers, json={
        "name": name, "capabilities": capabilities or [],
        "model_config": model_config or {"provider": "mock", "model": "mock-llm-1"},
        "tool_ids": tool_ids})
    assert r.status_code == 201, r.text
    agent = r.json()
    if activate:
        r = client.post(f"/api/v1/agents/{agent['id']}/activate", headers=headers, json={})
        assert r.status_code == 200, r.text
        agent = r.json()
    return agent


def mk_task(client, headers, goal, task_input=None, agent_id=None, budget_limit=None):
    body = {"goal": goal, "input": task_input or {}}
    if agent_id:
        body["agent_id"] = agent_id
    if budget_limit is not None:
        body["budget_limit"] = budget_limit
    r = client.post("/api/v1/tasks", headers=headers, json=body)
    assert r.status_code == 201, r.text
    return r.json()
