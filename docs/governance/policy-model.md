# Policy Model

Derived from `docs/research/security-analysis.md` §2. Four decision
outcomes, three policy layers, one default: **deny**.

## Decision outcomes

The policy engine (PDP) returns exactly one of:

| Decision | Meaning |
|---|---|
| `allow` | Action proceeds. |
| `deny` | Action blocked. First-class workflow state — the agent re-plans within its grants or requests elevation through proper channels, not an exception. |
| `require_approval` | Action pauses; resumes only on human approval (with an approval tier: self / peer / human / multi-person). |
| `allow_with_constraints` | Action proceeds under attached constraints, e.g. redacted output, budget cap, read-only mode, narrowed tool scope. |

Every evaluation emits a `PolicyEvaluated` audit event with the **policy
version hash, inputs digest, and decision** — "which policy decided" is a
content address, not a log line.

## Layering

1. **Platform guardrails** — shipped, signed, non-overridable by tenants.
   Examples: "no destructive prod actions without human approval," "no
   credential exfiltration," kill-switch authority. Guardrails win every
   conflict.
2. **Tenant policies** — tenant admins author, versioned, change-audited.
   Data-residency rules, approved model lists, spend caps, tool allowlists.
3. **Task-scoped constraints** — from the delegation token + risk engine:
   narrowed per task (tool set, max iterations, max spend, max blast
   radius). The planner declares what it needs; the engine grants the
   minimum.

**Deny-by-default:** if no policy explicitly allows, the decision is
`deny` (fail closed).

## PDP choice

OPA/Rego as the production PDP (embedded or sidecar), Rego bundles
versioned in Git, tested with `opa test`, signed at load. The MVP ships a
minimal built-in rule evaluator behind the same `PolicyEngine` interface
for local dev — explicitly non-production (see ADR-005). Cedar is tracked
for formally-verified authorization subsets (V2), not as the primary PDP.

## Permission engine

- **RBAC** for coarse human-manageable roles: `platform_admin`,
  `tenant_admin`, `agent_operator`, `approver`, `auditor`, `viewer`.
- **ABAC** for what RBAC can't express: agent identity + tool risk class +
  data classification + tenant + time window + risk score + delegation
  scope. Example: `allow(tool.invoke)` iff `agent.clearance ≥
  data.classification` ∧ `tool.risk ≤ agent.max_risk` ∧ `delegation.scope
  ∋ tool.id`.
- **ReBAC** deferred to V1.

Least-privilege mechanics:

- Tool grants are **per agent-version**, not per agent-type. Capability
  upgrades require re-approval (no privilege creep).
- Grants are **leases, not entitlements**: short-lived, continuously
  re-evaluated; revocation propagates within seconds via lease expiry +
  event fan-out.
- **No inheritance from the user:** effective permission set =
  intersection(user's delegable permissions, agent's granted permissions,
  task scope, policy decision). The agent can never exceed the *least* of
  these.

## Enforcement points (fail-closed choke points)

1. **Task admission** (task creation): may this agent pursue this goal in
   this tenant?
2. **Plan approval** (planner output): do the plan's tool set, cost
   estimate, and risk profile comply? High-risk plans ⇒ human approval
   before any execution.
3. **Tool-call authorization** (per invocation): allow/deny against the
   composite principal — the hot path; must be local/cached with async
   audit. A human's **plan approval covers the plan's own tool
   invocations**: the per-tool choke point does not demand a second
   approval for an action the human already approved (denials — least
   privilege, tenant denylists, risk clearance — still win, and direct
   invocation outside an approved plan still requires its own approval).
   Coverage is derived server-side from the approval's recorded plan,
   never from client input.
4. **Egress control** (before external call): DLP inspection, classification
   boundaries, default-deny proxy.
5. **Memory write** (before persistence): provenance tagging, quarantine
   of low-trust writes.
6. **Human approval gate** (where required): evidence-based, deliberation
   delays, multi-person thresholds — see `docs/governance/approval-ux.md`.
