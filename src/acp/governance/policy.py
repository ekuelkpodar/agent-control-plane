"""Policy engine: PolicyEngine interface, MinimalRuleEngine (MVP default,
explicitly NON-PRODUCTION), and OPA HTTP adapter (used only if ACP_OPA_URL set).

Fail-closed: no rule allowing => deny. Platform guardrails override tenant policy.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from acp.core.protocols import PolicyDecision
from acp.core.utils import sha256_hex

log = logging.getLogger(__name__)

GUARDRAILS_VERSION = "mvp-guardrails-0.1.0"

ALLOW = "allow"
DENY = "deny"
REQUIRE_APPROVAL = "require_approval"
ALLOW_WITH_CONSTRAINTS = "allow_with_constraints"


class MinimalRuleEngine:
    """MVP default PDP. Deterministic, explainable, TEST double for OPA.

    WARNING: non-production. Deploy OPA (ACP_OPA_URL) for real policy-as-code
    with versioned, signed Rego bundles.
    """

    def __init__(self, settings):
        self._settings = settings

    def version_hash(self) -> str:
        return sha256_hex(GUARDRAILS_VERSION)

    # ctx keys: kind (task_admission|plan_admission|tool_invoke|memory_write|learning),
    # tenant_id, agent{...}, tool{...}, plan{...}, args, cost_estimate, tenant_policy{...}
    def evaluate(self, ctx: dict[str, Any]) -> PolicyDecision:
        tenant_policy = ctx.get("tenant_policy") or {}
        kind = ctx.get("kind", "")

        # --- Platform guardrail 1: cross-tenant reach is always denied ---
        args = ctx.get("args") or {}
        if isinstance(args, dict):
            for k, v in args.items():
                if k in ("tenant_id", "tenant") and v != ctx.get("tenant_id"):
                    return PolicyDecision(
                        DENY,
                        [f"cross-tenant access attempt blocked (arg {k}={v!r})"],
                        policy_version_hash=self.version_hash(),
                        policy_refs=["platform.guardrail.cross_tenant"],
                    )

        # --- Platform guardrail 2: tool must be granted to the agent version ---
        if kind in ("tool_invoke", "plan_admission"):
            agent = ctx.get("agent") or {}
            tool_ids = set(agent.get("tool_ids") or [])
            tools = ctx.get("tools") or ([ctx.get("tool")] if ctx.get("tool") else [])
            for t in tools:
                if not t:
                    continue
                if t.get("id") not in tool_ids:
                    return PolicyDecision(
                        DENY,
                        [f"tool {t.get('id')!r} not granted to agent {agent.get('id')!r} (least privilege)"],
                        policy_version_hash=self.version_hash(),
                        policy_refs=["platform.guardrail.least_privilege"],
                    )

        # --- Tenant policy: explicit tool denylist / allowlist ---
        tools = ctx.get("tools") or ([ctx.get("tool")] if ctx.get("tool") else [])
        deny_tools = set(tenant_policy.get("deny_tool_ids") or [])
        allow_tools = tenant_policy.get("allow_tool_ids")  # None => no allowlist
        for t in tools:
            if not t:
                continue
            if t.get("id") in deny_tools or t.get("name") in deny_tools:
                return PolicyDecision(
                    DENY,
                    [f"tool {t.get('name')!r} denied by tenant policy"],
                    policy_version_hash=self.version_hash(),
                    policy_refs=["tenant.policy.tool_denylist"],
                )
            if allow_tools is not None and t.get("id") not in allow_tools and t.get("name") not in allow_tools:
                return PolicyDecision(
                    DENY,
                    [f"tool {t.get('name')!r} not in tenant allowlist"],
                    policy_version_hash=self.version_hash(),
                    policy_refs=["tenant.policy.tool_allowlist"],
                )

        # --- Platform guardrail 3: destructive / critical tools need approval ---
        reasons: list[str] = []
        constraints: dict[str, Any] = {}
        need_approval = False
        for t in tools:
            if not t:
                continue
            meta = t.get("metadata") or {}
            if t.get("risk_class") == "critical":
                need_approval = True
                reasons.append(f"tool {t.get('name')!r} is risk_class=critical")
            if meta.get("destructive"):
                need_approval = True
                reasons.append(f"tool {t.get('name')!r} is destructive")
            if meta.get("financial"):
                need_approval = True
                reasons.append(f"tool {t.get('name')!r} performs financial operations")

        # --- Cost threshold -> approval ---
        cost_estimate = float(ctx.get("cost_estimate") or 0.0)
        threshold = float(tenant_policy.get("require_approval_above_cost", self._settings.tenant_cost_approval_threshold))
        if cost_estimate > threshold:
            need_approval = True
            reasons.append(f"estimated cost ${cost_estimate:.2f} exceeds approval threshold ${threshold:.2f}")

        # --- Tenant max risk level ---
        max_risk = (tenant_policy.get("max_risk_level") or "critical").lower()
        risk_level = (ctx.get("risk_level") or "low").lower()
        order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        if order.get(risk_level, 0) > order.get(max_risk, 3):
            return PolicyDecision(
                DENY,
                [f"risk level {risk_level} exceeds tenant max {max_risk}"],
                policy_version_hash=self.version_hash(),
                policy_refs=["tenant.policy.max_risk"],
            )

        if need_approval:
            # Plan-approval coverage: a human's approval of the plan satisfies the
            # approval requirement for invoking the plan's own tools — the human
            # already approved exactly this action. Denials above still win
            # (fail closed); coverage never overrides a deny, and it only applies
            # to tool_invoke calls the orchestrator explicitly marks as covered
            # (direct tool invocation never carries a plan_approval).
            if kind == "tool_invoke":
                pa = ctx.get("plan_approval") or {}
                covered = set(pa.get("tool_ids") or [])
                if pa.get("status") == "approved" and tools and all(
                    t.get("id") in covered for t in tools if t
                ):
                    return PolicyDecision(
                        ALLOW,
                        [f"tool(s) covered by approved plan approval {pa.get('id')}"],
                        policy_version_hash=self.version_hash(),
                        policy_refs=["plan.approval.coverage"],
                    )
            return PolicyDecision(
                REQUIRE_APPROVAL, reasons,
                policy_version_hash=self.version_hash(),
                policy_refs=["platform.guardrail.high_risk_approval"],
            )

        if kind == "memory_write":
            trust = (ctx.get("provenance") or {}).get("source_trust", "unknown")
            if trust == "untrusted":
                constraints["quarantine"] = True
                return PolicyDecision(
                    ALLOW_WITH_CONSTRAINTS,
                    ["untrusted source: write quarantined from high-stakes retrieval"],
                    constraints,
                    policy_version_hash=self.version_hash(),
                    policy_refs=["platform.guardrail.memory_provenance"],
                )

        # Default: allow ONLY because explicit guardrails passed. (Deny-by-default
        # is preserved: any guardrail above returns deny/require_approval first,
        # and unknown kinds with no allow path fall through to deny below.)
        if kind in ("task_admission", "plan_admission", "tool_invoke", "memory_write", "learning", "tool_invoke_direct"):
            return PolicyDecision(ALLOW, ["all applicable guardrails passed"],
                                  policy_version_hash=self.version_hash())
        return PolicyDecision(
            DENY, [f"no policy explicitly allows kind={kind!r} (deny by default)"],
            policy_version_hash=self.version_hash(),
            policy_refs=["platform.guardrail.deny_by_default"],
        )


class OPAEngine:
    """OPA/Rego PDP via HTTP. Used only when ACP_OPA_URL is set.

    Fail-closed: OPA unreachable / malformed response => DENY.
    """

    def __init__(self, opa_url: str, timeout: float = 2.0):
        self._url = opa_url.rstrip("/") + "/v1/data/acp/authz"
        self._timeout = timeout
        self._fallback = None

    def set_fallback(self, engine: MinimalRuleEngine) -> None:
        self._fallback = engine

    def version_hash(self) -> str:
        return sha256_hex("opa:" + self._url)

    def evaluate(self, ctx: dict[str, Any]) -> PolicyDecision:
        try:
            resp = httpx.post(self._url, json={"input": ctx}, timeout=self._timeout)
            resp.raise_for_status()
            result = resp.json().get("result") or {}
        except Exception as exc:  # fail closed: rail unreachable => deny
            log.error("OPA unreachable (%s) — failing closed (deny)", exc)
            return PolicyDecision(
                DENY,
                ["policy engine unreachable; fail-closed deny"],
                policy_version_hash=self.version_hash(),
                policy_refs=["platform.fail_closed.opa_unreachable"],
            )
        decision = str(result.get("decision", DENY))
        if decision not in (ALLOW, DENY, REQUIRE_APPROVAL, ALLOW_WITH_CONSTRAINTS):
            log.error("OPA returned unknown decision %r — failing closed", decision)
            decision = DENY
        return PolicyDecision(
            decision=decision,
            reasons=list(result.get("reasons") or []),
            constraints=dict(result.get("constraints") or {}),
            policy_version_hash=self.version_hash(),
            policy_refs=list(result.get("policy_refs") or ["opa.bundle"]),
        )


def build_policy_engine(settings) -> MinimalRuleEngine | OPAEngine:
    minimal = MinimalRuleEngine(settings)
    if settings.opa_url:
        engine = OPAEngine(settings.opa_url)
        engine.set_fallback(minimal)
        log.info("Policy engine: OPA at %s (MinimalRuleEngine as documented fallback)", settings.opa_url)
        return engine
    log.warning(
        "Policy engine: MinimalRuleEngine (MVP default, NON-PRODUCTION). "
        "Set ACP_OPA_URL to use OPA/Rego."
    )
    return minimal
