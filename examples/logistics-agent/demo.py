#!/usr/bin/env python3
"""End-to-end logistics demo for the Agent Control Plane.

Drives ONLY the public REST contract (base ``/api/v1``):
    POST/GET /agents, POST/GET /tools, POST /tasks, GET /tasks/{id},
    POST /tasks/{id}/execute, GET /approvals?status=requested,
    POST /approvals/{id}/approve|reject, GET /audit

Everything carrier-related below is a MOCK: the canned carrier data and the
``mock_*`` callables stand in for the real carrier APIs. The control plane
is never told the mocks are real: the server executes the demo carrier
adapters through the same governed tool-invocation choke point
(authorization, credential brokering, audit) as any production tool.

Environment:
    ACP_API_URL   base URL of the API, e.g. http://localhost:8000  (default)
    ACP_API_KEY   Bearer API key                                    (required)
    ACP_TENANT_ID tenant scope header                               (default: demo-logistics)

Two scenarios run:
  A. Best quote $2,100 (< $2,500 budget) -> approval required -> APPROVE -> booked.
  B. Best quote $2,688 (> $2,500 budget) -> approval required -> REJECT  -> denied.
Both hit the approval gate because carrier.book is a financial, irreversible
side effect (risk: critical; policy: require_approval).
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

API = os.environ.get("ACP_API_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.environ.get("ACP_API_KEY", "")
TENANT = os.environ.get("ACP_TENANT_ID", "demo-logistics")

if not API_KEY:
    sys.exit("ACP_API_KEY is required (export ACP_API_KEY=...)")

POLL_TIMEOUT_S = 120
POLL_INTERVAL_S = 2

# ----------------------------------------------------------------------------
# MOCK carrier data (clearly labeled). In a real deployment the execution
# plane would call the real carrier APIs; here the demo keeps canned data
# locally to illustrate what the tool executors would return.
# ----------------------------------------------------------------------------

MOCK_CARRIERS = [
    {"name": "SwiftFreight",   "rate_usd": 2100, "transit_days": 5, "reliability": 0.97},
    {"name": "BlueRoute",      "rate_usd": 2340, "transit_days": 3, "reliability": 0.99},
    {"name": "QuickHaul",      "rate_usd": 2600, "transit_days": 2, "reliability": 0.93},
]


def mock_carrier_quote(shipment: dict) -> list[dict]:
    """MOCK: stand-in for the carrier.quote tool executor."""
    # Realistic canned quotes: base rate adjusted by weight/distance factors.
    weight = shipment.get("weight_kg", 1000)
    distance = shipment.get("distance_km", 800)
    factor = 1.0 + 0.15 * (weight / 1000 - 1) + 0.10 * (distance / 800 - 1)
    return [
        {
            "carrier": c["name"],
            "total_usd": round(c["rate_usd"] * factor, 2),
            "transit_days": c["transit_days"],
            "reliability": c["reliability"],
        }
        for c in MOCK_CARRIERS
    ]


def mock_carrier_book(quote: dict, shipment: dict) -> dict:
    """MOCK: stand-in for the carrier.book tool executor (high-risk action)."""
    return {
        "booking_ref": f"MOCK-{quote['carrier'][:3].upper()}-"
                       f"{int(time.time()) % 100000:05d}",
        "carrier": quote["carrier"],
        "total_usd": quote["total_usd"],
        "transit_days": quote["transit_days"],
        "status": "confirmed",
    }


def best_quote(quotes: list[dict]) -> dict:
    return min(quotes, key=lambda q: (q["total_usd"], -q["reliability"]))


# ----------------------------------------------------------------------------
# HTTP helper (stdlib only — no dependencies)
# ----------------------------------------------------------------------------

def call(method: str, path: str, body: dict | None = None, role: str | None = None) -> dict:
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "X-Tenant-ID": TENANT,
        "Content-Type": "application/json",
    }
    if role:
        headers["X-Role"] = role  # RBAC: viewer (default) | approver | tenant_admin ...
    req = urllib.request.Request(
        f"{API}/api/v1{path}",
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:500]
        raise RuntimeError(f"{method} {path} -> HTTP {e.code}: {detail}") from e


def stage(n: int, title: str) -> None:
    print(f"\n{'=' * 70}\nSTAGE {n}: {title}\n{'=' * 70}")


def wait_for_status(task_id: str, *wanted: str) -> dict:
    deadline = time.time() + POLL_TIMEOUT_S
    while time.time() < deadline:
        task = call("GET", f"/tasks/{task_id}")
        status = task.get("status")
        if status in wanted:
            return task
        if status in ("failed", "denied", "completed"):
            return task  # terminal even if unexpected
        print(f"  ... task status: {status}")
        time.sleep(POLL_INTERVAL_S)
    raise TimeoutError(f"task {task_id} did not reach {wanted} within {POLL_TIMEOUT_S}s")


# ----------------------------------------------------------------------------
# Scenario setup (shared)
# ----------------------------------------------------------------------------

def ensure_agent() -> dict:
    stage(1, "Register logistics agent")
    agent = call("POST", "/agents", {
        "name": "logistics-agent",
        "description": "Freight quoting and carrier booking agent (demo).",
        "capabilities": ["freight_quoting", "carrier_booking"],
        "version": "0.1.0",
    })
    print(f"  agent: {agent['id']}  status={agent.get('status')}")
    return agent


def ensure_tools(agent_id: str) -> None:
    stage(2, "Register mock tools (carrier.quote: low risk, carrier.book: high risk)")
    quote_tool = call("POST", "/tools", {
        "name": "carrier.quote",
        "description": "MOCK tool: returns canned carrier quotes for a shipment.",
        "schema": {"json_schema": {
            "type": "object",
            "properties": {
                "weight_kg": {"type": "number"},
                "distance_km": {"type": "number"},
                "origin": {"type": "string"},
                "destination": {"type": "string"},
            },
            "required": ["weight_kg", "distance_km", "origin", "destination"],
        }},
        "risk_class": "low",
    })
    book_tool = call("POST", "/tools", {
        "name": "carrier.book",
        "description": "MOCK tool: books a shipment with a carrier (irreversible, financial).",
        "schema": {"json_schema": {
            "type": "object",
            "properties": {
                "carrier": {"type": "string"},
                "total_usd": {"type": "number"},
                "shipment_ref": {"type": "string"},
            },
            "required": ["carrier", "total_usd", "shipment_ref"],
        }},
        "risk_class": "high",
        # Truthful metadata: booking a shipment IS a financial, irreversible
        # side effect. The policy and risk engines key approval off this.
        "metadata": {"financial": True, "irreversible": True, "side_effecting": True},
    })
    print(f"  tool: carrier.quote  id={quote_tool['id']}  risk=low")
    print(f"  tool: carrier.book   id={book_tool['id']}  risk=high  metadata=financial,irreversible")
    # Grant the agent both tools so the planner can build a tool-calling plan.
    call("PUT", f"/agents/{agent_id}", {"tool_ids": [quote_tool["id"], book_tool["id"]]})
    print(f"  agent {agent_id} granted tools: carrier.quote, carrier.book")
    # Activate: only activated agents may invoke tools (governance rail choke point).
    agent = call("POST", f"/agents/{agent_id}/activate", {})
    print(f"  agent {agent_id} status={agent.get('status')}")


def run_scenario(label: str, agent_id: str, shipment: dict, budget_usd: float, decision: str) -> None:
    """Run one full task lifecycle. decision is 'approve' or 'reject'."""
    goal = (f"Find the best carrier for this shipment and book it "
            f"if the total cost is under ${budget_usd:,.0f}")

    stage(3, f"[{label}] Create task")
    task = call("POST", "/tasks", {
        "goal": goal,
        "agent_id": agent_id,  # pin the logistics agent so planning sees its tools
        "input": {
            "shipment": shipment,
            "budget_usd": budget_usd,
            # Tool-call args the planner forwards to carrier.quote / carrier.book.
            "args": {
                "weight_kg": shipment.get("weight_kg"),
                "distance_km": shipment.get("distance_km"),
                "origin": shipment.get("origin"),
                "destination": shipment.get("destination"),
                "shipment_ref": shipment.get("shipment_ref"),
            },
        },
    })
    task_id = task["id"]
    print(f"  task: {task_id}  status={task.get('status')}")

    stage(4, f"[{label}] Execute (governed pipeline: plan -> risk -> policy)")
    call("POST", f"/tasks/{task_id}/execute", {})
    task = wait_for_status(task_id, "awaiting_approval", "completed", "failed", "denied")
    print(f"  task status: {task.get('status')}")

    if task.get("status") == "awaiting_approval":
        stage(5, f"[{label}] Approval requested — inspect evidence")
        approvals = call("GET", "/approvals?status=requested")
        items = approvals.get("items", approvals.get("approvals", approvals))
        mine = [a for a in items if a.get("task_id") == task_id]
        if not mine:
            raise RuntimeError("expected approval for task, none found")
        ap = mine[0]
        print(f"  approval: {ap['id']}")
        print(f"  action:   {ap.get('action_summary')}")
        print(f"  risk:     {ap.get('risk_level')} (score={ap.get('risk_score')})")
        print("  reasons:")
        for r in ap.get("reasons", []):
            print(f"    - {r}")
        print(f"  policy:   {ap.get('policy_ref') or ap.get('policy_decision')}")

        # The demo consults the MOCK quote data to explain its decision,
        # exactly as an operator would consult the evidence payload.
        quotes = mock_carrier_quote(shipment)
        bq = best_quote(quotes)
        print(f"  evidence (mock quotes): best = {bq['carrier']} "
              f"${bq['total_usd']:,.2f} / {bq['transit_days']}d "
              f"(budget ${budget_usd:,.0f})")

        stage(6, f"[{label}] Human decision: {decision.upper()}")
        call("POST", f"/approvals/{ap['id']}/{decision}", {
            "decided_by": "demo-operator",
            "note": f"demo {label}: {'within' if decision == 'approve' else 'over'} budget"
        }, role="approver")
        # Resume the paused pipeline: execute again now that the approval is decided.
        call("POST", f"/tasks/{task_id}/execute", {})
        task = wait_for_status(task_id, "completed", "failed", "denied")

    stage(7, f"[{label}] Outcome + audit chain")
    print(f"  final task status: {task.get('status')}")
    if task.get("status") == "completed":
        # MOCK: illustrate what the booking tool would have returned.
        bq = best_quote(mock_carrier_quote(shipment))
        booking = mock_carrier_book(bq, shipment)
        print(f"  booking confirmed (MOCK): {booking['booking_ref']} "
              f"{booking['carrier']} ${booking['total_usd']:,.2f}")
    audit = call("GET", f"/audit?task_id={task_id}")
    events = audit.get("items", audit.get("events", audit))
    print(f"  audit events for task ({len(events)}):")
    for e in events:
        seq = e.get("seq", "?")
        etype = e.get("event_type", e.get("type", "?"))
        print(f"    [{seq}] {etype}")


def main() -> None:
    print(f"Agent Control Plane demo  api={API}  tenant={TENANT}")
    agent = ensure_agent()
    ensure_tools(agent["id"])

    # Scenario A: best quote $2,100 < $2,500 -> approval required -> APPROVE
    run_scenario(
        label="A",
        agent_id=agent["id"],
        shipment={"weight_kg": 1000, "distance_km": 800,
                  "origin": "Chicago, IL", "destination": "Dallas, TX",
                  "shipment_ref": "SHP-A-001"},
        budget_usd=2500,
        decision="approve",
    )

    # Scenario B: heavier shipment -> best quote $2,688 > $2,500
    #           -> approval required -> REJECT (deny path)
    run_scenario(
        label="B",
        agent_id=agent["id"],
        shipment={"weight_kg": 2200, "distance_km": 1600,
                  "origin": "Seattle, WA", "destination": "Miami, FL",
                  "shipment_ref": "SHP-B-002"},
        budget_usd=2500,
        decision="reject",
    )

    print("\nDemo complete: approval path (A) and deny path (B) both exercised.")

    stage(8, "Verify audit ledger (hash chain + Ed25519 signatures)")
    verify = call("GET", "/audit/verify")
    print(f"  ledger verifies: {verify.get('ok')}")
    if not verify.get("ok"):
        raise RuntimeError(f"audit ledger verification FAILED: {verify}")


if __name__ == "__main__":
    main()
