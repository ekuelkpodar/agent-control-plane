"""Tool registry + executors.

ToolExecutor protocol; LocalFunctionToolExecutor (in-process python callables,
dev/demo); MCPClient interface with a MockMCPClient for tests. Real MCP
integration is V1.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)


class ToolExecutor:
    def invoke(self, tool: dict[str, Any], args: dict[str, Any], *, credential: dict | None = None) -> dict[str, Any]:
        raise NotImplementedError


class LocalFunctionToolExecutor(ToolExecutor):
    """Executes registered python callables. The brokered credential is
    injected server-side here — it never enters agent-visible context."""

    def __init__(self):
        self._functions: dict[str, Callable[[dict, dict | None], dict]] = {}
        self._register_demo_functions()

    def register(self, tool_id: str, fn: Callable[[dict, dict | None], dict]) -> None:
        self._functions[tool_id] = fn

    def register_by_name(self, tool_name: str, fn: Callable[[dict, dict | None], dict]) -> None:
        self._functions[f"name:{tool_name}"] = fn

    def invoke(self, tool: dict[str, Any], args: dict[str, Any], *, credential: dict | None = None) -> dict[str, Any]:
        fn = self._functions.get(tool["id"]) or self._functions.get(f"name:{tool.get('name')}")
        if fn is None:
            raise RuntimeError(
                f"no local function registered for tool {tool.get('name')!r} "
                f"(id={tool.get('id')!r}); register one or use an MCP tool"
            )
        return fn(dict(args), credential)

    # ---- Mock/demo functions (clearly marked; deterministic) ----
    def _register_demo_functions(self) -> None:
        self._functions["name:mock_echo"] = lambda args, cred: {"ok": True, "echo": args}
        self._functions["name:mock_get_quote"] = lambda args, cred: {
            "ok": True,
            "quotes": [
                {"carrier": "acme-freight", "price": 120.0, "eta_days": 3},
                {"carrier": "swift-haul", "price": 95.0, "eta_days": 5},
            ],
            "request": args,
        }
        self._functions["name:mock_select_carrier"] = lambda args, cred: {
            "ok": True, "selected": args.get("carrier") or "swift-haul",
        }
        self._functions["name:mock_book_shipment"] = lambda args, cred: {
            "ok": True, "booking_ref": "BK-12345", "carrier": args.get("carrier"), "cost": args.get("price"),
        }
        # Demo carrier adapters for examples/logistics-agent (MOCK — deterministic
        # canned data standing in for real carrier APIs, which are V1
        # integrations). The booking adapter is intentionally simple: it books
        # the best canned quote unless the caller names a carrier explicitly.
        self._functions["name:carrier.quote"] = _demo_carrier_quote
        self._functions["name:carrier.book"] = _demo_carrier_book


_DEMO_CARRIERS = [
    {"name": "SwiftFreight", "rate_usd": 2100.0, "transit_days": 5, "reliability": 0.97},
    {"name": "BlueRoute", "rate_usd": 2340.0, "transit_days": 3, "reliability": 0.99},
    {"name": "QuickHaul", "rate_usd": 2600.0, "transit_days": 2, "reliability": 0.93},
]


def _demo_quotes(args: dict) -> list[dict]:
    """Deterministic canned quotes. Mirrors the demo client's mock math."""
    weight = float(args.get("weight_kg") or 1000)
    distance = float(args.get("distance_km") or 800)
    factor = 1.0 + 0.15 * (weight / 1000 - 1) + 0.10 * (distance / 800 - 1)
    return [
        {
            "carrier": c["name"],
            "total_usd": round(c["rate_usd"] * factor, 2),
            "transit_days": c["transit_days"],
            "reliability": c["reliability"],
        }
        for c in _DEMO_CARRIERS
    ]


def _demo_carrier_quote(args: dict, cred: dict | None) -> dict:
    return {"ok": True, "mock": True, "quotes": _demo_quotes(args), "request": args}


def _demo_carrier_book(args: dict, cred: dict | None) -> dict:
    quotes = _demo_quotes(args)
    best = min(quotes, key=lambda q: (q["total_usd"], -q["reliability"]))
    carrier = args.get("carrier") or best["carrier"]
    total = args.get("total_usd") or best["total_usd"]
    ref = f"BK-{carrier[:3].upper()}-DEMO"
    return {
        "ok": True,
        "mock": True,
        "booking_ref": ref,
        "carrier": carrier,
        "total_usd": total,
        "transit_days": next(q["transit_days"] for q in quotes if q["carrier"] == carrier),
        "status": "confirmed",
    }


class MCPClient:
    """Interface for MCP tool servers (V1)."""

    def list_tools(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def call_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class MockMCPClient(MCPClient):
    """Deterministic mock MCP client for tests. NOT a real MCP server."""

    def __init__(self, tools: list[dict[str, Any]] | None = None):
        self._tools = tools or []

    def list_tools(self) -> list[dict[str, Any]]:
        return self._tools

    def call_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "mock_mcp_tool": name, "args": args}
