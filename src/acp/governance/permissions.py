"""Permissions: RBAC + ABAC hybrid with least privilege.

Effective authority = intersection(
    user's delegable permissions,
    agent's granted permissions (per agent VERSION),
    task scope,
    policy decision,
).
Agents NEVER inherit ambient user authority.
"""

from __future__ import annotations

from typing import Any

# Coarse, human-manageable roles (K8s-RBAC analogy).
ROLES = ("platform_admin", "tenant_admin", "agent_operator", "approver", "auditor", "viewer")

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "platform_admin": {"*"},
    "tenant_admin": {
        "agents.*", "tasks.*", "tools.*", "approvals.*", "budgets.*",
        "policies.manage", "audit.read", "evaluations.*", "memory.*", "knowledge.*",
    },
    "agent_operator": {"agents.read", "agents.create", "tasks.*", "tools.read", "tools.invoke", "approvals.read", "memory.*"},
    "approver": {"approvals.read", "approvals.decide", "tasks.read", "audit.read"},
    "auditor": {"audit.read", "tasks.read", "agents.read", "evaluations.read"},
    "viewer": {"agents.read", "tasks.read", "tools.read"},
}

RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
DATA_LEVELS = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}


def role_allows(role: str, permission: str) -> bool:
    perms = ROLE_PERMISSIONS.get(role, set())
    if "*" in perms:
        return True
    if permission in perms:
        return True
    prefix = permission.split(".")[0] + ".*"
    return prefix in perms


def check_abac(
    *,
    agent: dict[str, Any],
    tool: dict[str, Any],
    delegation_scope_tools: list[str],
    data_classification: str = "internal",
    risk_level: str = "low",
) -> tuple[bool, list[str]]:
    """ABAC checks the RBAC layer cannot express. Returns (ok, reasons)."""
    reasons: list[str] = []
    # Agent clearance vs data classification.
    clearance = DATA_LEVELS.get(str(agent.get("clearance", "internal")).lower(), 1)
    needed = DATA_LEVELS.get(data_classification.lower(), 1)
    if clearance < needed:
        reasons.append(f"agent clearance insufficient for {data_classification} data")
    # Tool risk within agent's max risk.
    if RISK_ORDER.get(str(tool.get("risk_class", "low")).lower(), 0) > RISK_ORDER.get(
        str(agent.get("max_risk_level", "high")).lower(), 2
    ):
        reasons.append("tool risk_class exceeds agent max_risk_level")
    # Delegation scope containment.
    if tool.get("id") not in (delegation_scope_tools or []):
        reasons.append("tool not within delegation scope")
    return (len(reasons) == 0, reasons)


def effective_authority(
    *,
    user_delegable_tools: set[str],
    agent_granted_tools: set[str],
    task_scope_tools: set[str],
    policy_allowed_tools: set[str] | None,
) -> set[str]:
    """Intersection of all four authority sources. Narrow-only by construction."""
    sets = [user_delegable_tools, agent_granted_tools, task_scope_tools]
    if policy_allowed_tools is not None:
        sets.append(policy_allowed_tools)
    result = set.intersection(*sets) if sets else set()
    return result
