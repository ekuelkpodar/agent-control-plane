"""Unit: secret brokering + cost budgets + permissions + memory + planner/router."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from acp.core.errors import BudgetExhausted
from acp.core.utils import new_id
from acp.cost import check_budget, record_cost, total_cost
from acp.db.models import Base, Budget
from acp.governance.permissions import check_abac, effective_authority, role_allows
from acp.governance.secrets import EnvSecretBroker, VaultSecretBroker
from acp.memory import PostgresMemoryStore
from acp.planner import DeterministicPlanner, RuleBasedPlanner
from acp.router import WeightedRouter


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


# ---- secrets ----
def test_env_broker_issue_revoke():
    b = EnvSecretBroker()
    lease = b.issue("t1", "tool-1", ttl_seconds=60)
    assert b.lease_valid(lease["lease_id"])
    b.revoke(lease["lease_id"])
    assert not b.lease_valid(lease["lease_id"])


def test_vault_stub_raises():
    with pytest.raises(NotImplementedError):
        VaultSecretBroker()


# ---- cost ----
def test_budget_enforcement(session):
    session.add(Budget(id=new_id(), tenant_id="t1", scope="task", scope_id="task-1", limit=1.0))
    session.commit()
    record_cost(session, tenant_id="t1", task_id="task-1", amount=0.9)
    session.commit()
    assert total_cost(session, "t1", task_id="task-1") == pytest.approx(0.9)
    ok = check_budget(session, tenant_id="t1", task_id="task-1", agent_id=None, additional=0.05)
    assert ok["ok"] and ok["alerts"]  # crossed 95%
    with pytest.raises(BudgetExhausted):
        check_budget(session, tenant_id="t1", task_id="task-1", agent_id=None, additional=0.2)


def test_no_budget_no_block(session):
    ok = check_budget(session, tenant_id="t1", task_id="x", agent_id=None, additional=999.0)
    assert ok["ok"]


# ---- permissions ----
def test_effective_authority_is_intersection():
    eff = effective_authority(
        user_delegable_tools={"a", "b", "c"},
        agent_granted_tools={"a", "b"},
        task_scope_tools={"a", "b", "c", "d"},
        policy_allowed_tools={"a", "c"},
    )
    assert eff == {"a"}


def test_roles():
    assert role_allows("approver", "approvals.decide")
    assert not role_allows("viewer", "approvals.decide")
    assert role_allows("platform_admin", "anything.at.all")


def test_abac_blocks_overprivileged_tool():
    ok, reasons = check_abac(
        agent={"max_risk_level": "low", "clearance": "internal"},
        tool={"id": "t", "risk_class": "critical"},
        delegation_scope_tools=["t"],
    )
    assert not ok and reasons


def test_abac_allows_matching():
    ok, reasons = check_abac(
        agent={"max_risk_level": "high", "clearance": "internal"},
        tool={"id": "t", "risk_class": "low"},
        delegation_scope_tools=["t"],
    )
    assert ok, reasons


# ---- memory ----
def test_memory_write_read_tenant_isolated(session):
    m = PostgresMemoryStore()
    m.write(session, "t1", "ns", "k", {"v": 1}, {"writer": "a", "source_trust": "trusted"})
    assert m.read(session, "t1", "ns", "k")["value"] == {"v": 1}
    assert m.read(session, "t2", "ns", "k") is None  # tenant isolation


def test_memory_untrusted_quarantined(session):
    m = PostgresMemoryStore()
    row = m.write(session, "t1", "ns", "k", {"v": 1},
                  {"writer": "a", "source_trust": "untrusted", "task_id": "x"})
    assert row["quarantined"] is True
    assert m.list(session, "t1", "ns") == []  # excluded from normal retrieval
    assert len(m.list(session, "t1", "ns", include_quarantined=True)) == 1


def test_memory_ttl(session):
    m = PostgresMemoryStore()
    m.write(session, "t1", "ns", "k", {"v": 1}, {"writer": "a"}, ttl_seconds=-1)
    assert m.read(session, "t1", "ns", "k") is None


# ---- planner ----
def _tools():
    return [
        {"id": "q", "name": "mock_get_quote", "cost_per_call": 0.01},
        {"id": "s", "name": "mock_select_carrier", "cost_per_call": 0.01},
        {"id": "b", "name": "mock_book_shipment", "cost_per_call": 0.05},
    ]


def test_deterministic_planner_booking_flow():
    p = DeterministicPlanner()
    plan = p.plan(goal="book a shipment from NYC to Boston", task_input={},
                  agent={"tool_ids": ["q", "s", "b"]}, tools=_tools())
    assert [s["name"] for s in plan["steps"]] == ["mock_get_quote", "mock_select_carrier", "mock_book_shipment"]
    assert plan["estimated_cost"] > 0


def test_deterministic_planner_fallback_reasoning_step():
    p = DeterministicPlanner()
    plan = p.plan(goal="ponder the meaning of logs", task_input={},
                  agent={"tool_ids": ["q"]}, tools=_tools())
    assert plan["steps"][0]["tool_id"] is None


def test_rule_based_planner_flags_high_risk():
    p = RuleBasedPlanner()
    tools = [{"id": "d", "name": "mock_purge", "risk_class": "high", "cost_per_call": 0.01,
              "metadata": {"destructive": True}}]
    plan = p.plan(goal="purge stale records", task_input={},
                  agent={"tool_ids": ["d"]}, tools=tools)
    assert plan["approvals_required"] is True
    assert plan["risk_hints"]


# ---- router ----
def test_weighted_router_prefers_capable_agent():
    from acp.core.config import Settings
    from acp.governance.policy import MinimalRuleEngine

    policy = MinimalRuleEngine(Settings(database_url="sqlite:///:memory:"))
    r = WeightedRouter()
    plan = {"steps": [{"tool_id": "q"}, {"tool_id": "b"}]}
    tools = [{"id": "q", "name": "q", "risk_class": "low", "metadata": {}},
             {"id": "b", "name": "b", "risk_class": "low", "metadata": {}}]
    cands = [
        {"id": "a1", "tenant_id": "t1", "status": "activated", "capabilities": ["x"],
         "model_config": {}, "tool_ids": ["q"], "max_risk_level": "high"},
        {"id": "a2", "tenant_id": "t1", "status": "activated", "capabilities": ["x"],
         "model_config": {}, "tool_ids": ["q", "b"], "max_risk_level": "high"},
    ]
    ranked = r.rank(goal="book shipment", plan=plan, candidates=cands, tools=tools,
                    policy_engine=policy, tenant_policy={})
    assert ranked[0]["agent_id"] == "a2"
    assert ranked[0]["score"] > ranked[1]["score"]
