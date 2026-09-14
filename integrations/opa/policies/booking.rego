# Sample OPA/Rego policy bundle for the Agent Control Plane.
#
# Mirrors the MinimalRuleEngine platform guardrails so behavior is consistent
# whether ACP_OPA_URL is set or not. Deploy with:
#   opa run --server integrations/opa/policies/
# The ACP OPA adapter POSTs {"input": {...}} to /v1/data/acp/authz and expects
# {"result": {"decision": "allow"|"deny"|"require_approval"|"allow_with_constraints",
#             "reasons": [...], "constraints": {...}, "policy_refs": [...]}}.
package acp.authz

import rego.v1

default decision := "deny"
default reasons := ["no policy explicitly allows this action (deny by default)"]

# ---------------------------------------------------------------- helpers
is_tool_kind if {
	input.kind in {"tool_invoke", "plan_admission", "tool_invoke_direct"}
}

tools contains t if {
	some t in object.get(input, "tools", [])
	t != null
}

# ------------------------------------------------- platform guardrails
# G1: cross-tenant reach is always denied.
deny_cross_tenant if {
	some k, v in object.get(input, "args", {})
	k in {"tenant_id", "tenant"}
	v != input.tenant_id
}

# G2: tool must be granted to the agent version (least privilege).
deny_ungranted_tool if {
	is_tool_kind
	some t in tools
	not t.id in object.get(input.agent, "tool_ids", [])
}

# G3: critical-risk or destructive tools require human approval.
needs_approval if {
	some t in tools
	lower(object.get(t, "risk_class", "low")) == "critical"
}

needs_approval if {
	some t in tools
	object.get(object.get(t, "metadata", {}), "destructive", false) == true
}

needs_approval if {
	some t in tools
	object.get(object.get(t, "metadata", {}), "financial", false) == true
}

# G4: estimated cost above the tenant threshold requires approval.
needs_approval if {
	cost := to_number(object.get(input, "cost_estimate", 0))
	threshold := to_number(object.get(object.get(input, "tenant_policy", {}),
		"require_approval_above_cost", 5))
	cost > threshold
}

# ------------------------------------------------- tenant policy layer
deny_tenant_denylist if {
	some t in tools
	t.id in object.get(object.get(input, "tenant_policy", {}), "deny_tool_ids", [])
}

# G5: a tool covered by an approved plan approval does not need a second
# approval at the per-tool choke point — the human already approved this plan.
# Denials above still win; direct invocation never carries a plan_approval.
covered_by_plan_approval if {
	input.kind == "tool_invoke"
	pa := object.get(input, "plan_approval", {})
	pa.status == "approved"
	count({t | some t in tools; not t.id in object.get(pa, "tool_ids", [])}) == 0
	count(tools) > 0
}

# ------------------------------------------------- decision composition
# Platform guardrails override tenant policy; deny wins over approval.
result := {"decision": "deny",
	"reasons": ["cross-tenant access attempt blocked"],
	"policy_refs": ["platform.guardrail.cross_tenant"]} if {
	deny_cross_tenant
} else := {"decision": "deny",
	"reasons": ["tool not granted to agent (least privilege)"],
	"policy_refs": ["platform.guardrail.least_privilege"]} if {
	deny_ungranted_tool
} else := {"decision": "deny",
	"reasons": ["tool denied by tenant policy"],
	"policy_refs": ["tenant.policy.tool_denylist"]} if {
	deny_tenant_denylist
} else := {"decision": "allow",
	"reasons": ["covered by approved plan approval"],
	"policy_refs": ["plan.approval.coverage"]} if {
	covered_by_plan_approval
} else := {"decision": "require_approval",
	"reasons": ["high-risk action requires human approval"],
	"policy_refs": ["platform.guardrail.high_risk_approval"]} if {
	needs_approval
} else := {"decision": "allow",
	"reasons": ["all applicable guardrails passed"],
	"policy_refs": ["platform.guardrail.allow"]} if {
	input.kind in {"task_admission", "plan_admission", "tool_invoke",
		"tool_invoke_direct", "memory_write", "learning"}
} else := {"decision": "deny",
	"reasons": ["no policy explicitly allows this action (deny by default)"],
	"policy_refs": ["platform.guardrail.deny_by_default"]}
