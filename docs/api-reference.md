# API Reference — Agent Control Plane (MVP)

> **Authoritative contract.** This document is the source of truth for the
> `/api/v1` REST surface. Behavior described here is covered by the test suite
> in `tests/`; where prose and code disagree, the code wins and this document
> must be updated.

Base URL: `http://localhost:8000/api/v1` · OpenAPI: `/openapi.json` · Docs UI: `/docs`
ASGI entrypoint: `acp.api:app` (i.e. `uvicorn acp.api:app`).

## 1. Authentication & tenancy

Every `/api/v1` request requires:

| Header | Required | Purpose |
|---|---|---|
| `Authorization: Bearer <ACP_API_KEY>` | yes | Service credential. Wrong/missing → `401`. |
| `X-Tenant-ID: <tenant>` | yes (unless `ACP_REQUIRE_TENANT_HEADER=false`) | Tenant scope. Missing → `400`. |
| `X-Principal: <name>` | no | Human/service principal recorded in audit actors. |
| `X-Role: <role>` | no | RBAC role for `*/invoke` and approval decisions (see §8). |
| `X-Correlation-ID: <id>` | no | Propagated through tasks, events, audit, and traces. |

**Tenant isolation is enforced on every query.** Any access to a resource that
exists in another tenant returns `403` and emits a `SecurityViolationDetected`
audit event (never a `404` that would leak existence — the violation is denied
and recorded). Row-level scoping is applied in the service layer on every read
and write; there is no ambient cross-tenant access path.

**No ambient agent authority.** Tool invocation never inherits ambient
permissions: the caller must name the executing agent (`agent_id`), and the
control plane mints a narrow, short-lived delegation (single tenant + agent +
tool [+ task], 15 min TTL) for that call. See §5.

## 2. Conventions

- IDs are UUID strings (`id` fields).
- Timestamps are ISO-8601 UTC (`created_at`, `updated_at`, `requested_at`, …).
- Errors:
  - `401 {"detail": ...}` — bad/missing API key.
  - `400 {"detail": ...}` — validation / missing tenant / missing `agent_id`.
  - `403` — denied. Policy denials: `{"detail": {"decision": "deny", "reason": …,
    "reasons": […]}}`. Security violations: `{"detail": "security violation: …"}`.
  - `404 {"detail": ...}` — not found **within your tenant**.
  - `409 {"detail": ...}` — invalid state transition (e.g. approving an expired approval).
  - `202` — approval required; body carries `{"approval_id": …}` (tool invoke) or
    the task in `awaiting_approval` (pipeline).
- Pagination on list endpoints: `?limit=` (default 50, max 500), `?offset=`.
- All money values are decimal units of account (no currency conversion in MVP).

## 3. Alignment pins (do not change without a contract amendment)

1. **Task statuses** are exactly:
   `created, admitted, planned, routed, awaiting_approval, executing, paused, completed, failed, cancelled, denied`.
2. **`GET /approvals` supports `?task_id=`** — per-task approval queries.
3. **`agent_id` is optional on task creation** — when omitted, the router selects
   the agent; the chosen agent is returned on the task (`task.agent_id`).
4. **`POST /tasks/{id}/cancel` is the kill switch** — freezes the task and
   revokes its delegation chain.
5. **Approval evidence** exposes `risk_score`, `risk_level`, `reasons[]`, plus a
   pinned policy-decision reference: `policy_decision` and
   `policy_version_hash`.

## 4. Endpoints

### 4.1 Health

`GET /api/v1/health` → `200 {"status": "ok", "version": "0.1.0"}` (no auth required).

### 4.2 Agents — registry & lifecycle

Agent lifecycle (explicit state machine):
`created → registered → validated → deployed → tested → activated → monitoring ⇄ evaluating → versioned → … → deprecated → revoked`

| Method & path | Description |
|---|---|
| `POST /api/v1/agents` | Register an agent. Body: `{name, capabilities[], model_config{}, tool_ids[]}`. → `201` agent (`status: "created"`). |
| `GET /api/v1/agents` | List agents (tenant-scoped). |
| `GET /api/v1/agents/{id}` | Agent detail incl. `status`, `capabilities`, `tool_ids`, `version`. |
| `PUT /api/v1/agents/{id}` | Update (mutable fields). Tool-grant changes are versioned. |
| `DELETE /api/v1/agents/{id}` | Soft-delete. |
| `POST /api/v1/agents/{id}/activate` | Walk the lifecycle to `activated` (validates each transition). Body: `{}`. → `200` agent. Only `activated`/`monitoring`/`evaluating` agents may invoke tools. |

`tool_ids` is the agent's **least-privilege grant set**: a tool not in it can
never be invoked by that agent (privilege-escalation attempts are denied and
audited as `PermissionDenied`).

### 4.3 Tasks — governed pipeline

Task lifecycle (explicit state machine):
`created → admitted → planned → routed → [awaiting_approval] → executing → completed`
with terminal `failed`, `cancelled`, `denied` (and `paused` reserved for future
suspend/resume). Terminal states have no outgoing transitions.

**Pipeline stages** (`POST /tasks/{id}/execute` runs synchronously, inline):

1. **Admission** — policy `task_admission` on `{goal, input}`. Deny → `denied`.
2. **Plan** — planner (`deterministic` default; `rule_based` via `ACP_PLANNER`)
   decomposes the goal into ordered steps over granted tools. Reasoning-only
   steps have `tool_id: null` and are model-metered.
3. **Route** — weighted router scores activated agents (capability match, tool
   coverage, cost, policy eligibility). Explicit `agent_id` is honored but still
   policy-checked; omitted `agent_id` → router selects.
4. **Plan admission + risk** — policy `plan_admission` on the plan, then the
   hybrid risk engine (deterministic factors; model hook may only *raise* risk).
5. **Approval gate** — pauses to `awaiting_approval` when policy says
   `require_approval`, risk requires human approval, or the plan flags it.
6. **Execute** — durable runner: checkpoint-before-side-effect per step, retries
   with backoff for transient failures, idempotent replay of succeeded steps,
   heartbeats. **Every step goes through the tool-call choke point** (§5).

| Method & path | Description |
|---|---|
| `POST /api/v1/tasks` | Create a task. Body: `{goal, input?, agent_id? (optional), budget_limit?}`. → `201` task (`status: "created"`). If `budget_limit` is set, a task-scoped budget is materialized and enforced (see §7). |
| `GET /api/v1/tasks` | List tasks (tenant-scoped, newest first). |
| `GET /api/v1/tasks/{id}` | Task detail: `status`, `plan{steps[]}`, `risk_assessment{}` (score/level/reasons/breakdown), `cost_estimate`, `cost_incurred`, `budget_limit`, `error`, `approvals[]`, `agent_id`. |
| `POST /api/v1/tasks/{id}/execute` | Run/resume the pipeline. Returns the task: `completed`, `awaiting_approval` (with `approvals[]`), `failed` (`error` set), or `denied`. Safe to retry: succeeded steps are never re-executed; approvals already decided are not re-requested. |
| `POST /api/v1/tasks/{id}/cancel` | **Kill switch.** `cancelled` + delegation chain revoked. A cancelled task will not execute. |
| `GET /api/v1/tasks/{id}/events` | Event history for the task (selective event sourcing: audit + workflow history only). Query `?wait=true&timeout=` for long-poll; streams as SSE (`text/event-stream`). |

**Task object (abridged):**
```json
{
  "id": "bfd9fe8e-…", "tenant_id": "tenant-a", "goal": "book a shipment from NYC to Boston",
  "agent_id": "…", "status": "completed",
  "plan": {"steps": [{"step_id": "step-1", "name": "mock_get_quote", "tool_id": "…", "args": {}}],
           "estimated_cost": 0.076, "approvals_required": false},
  "risk_assessment": {"risk_score": 5.0, "risk_level": "low",
                      "requires_human_approval": false, "reasons": ["…"]},
  "cost_estimate": 0.076, "cost_incurred": 0.076, "budget_limit": null,
  "error": null, "approvals": []
}
```

### 4.4 Tools — registry & governed invocation

| Method & path | Description |
|---|---|
| `POST /api/v1/tools` | Register a tool. Body: `{name, description?, risk_class(low|medium|high|critical), cost_per_call, schema?, auth?, metadata?}`. → `201`. |
| `GET /api/v1/tools` | List tools (tenant-scoped). |
| `GET /api/v1/tools/{id}` | Tool detail. |
| `POST /api/v1/tools/{id}/invoke` | **Governed invocation choke point.** Body: `{args{}, agent_id (required unless task_id given), task_id?}`. → `200 {result, audit_seq}` · `403 {decision:"deny",…}` · `202 {approval_id}` when a human decision is required. |

**Invocation pipeline (fail-closed at every step):**
identity (agent activated) → grant (tool ∈ agent `tool_ids`) → delegation
(token valid, tool in scope) → policy (PDP) → ABAC → risk → budget →
credential brokering (server-side injection; the agent never sees the secret) →
execute → meter cost. Any failure denies and is audited; **denial records are
committed even if the outer request rolls back**.

The endpoint mints a one-time scoped delegation for the call
(`subject` = caller principal, `act` = agent, `scope_tools` = [tool], 15 min).
`agent_id` is required when `task_id` is absent — there is no ambient authority.

### 4.5 Approvals — human-in-the-loop

Lifecycle: `requested → approved | rejected | expired`. **Timeout == DENY**:
expiry is swept on every read and decision; an expired approval can never be
approved (`409`) and its task is denied.

| Method & path | Description |
|---|---|
| `GET /api/v1/approvals?task_id=` | List approvals (tenant-scoped); optional per-task filter. |
| `POST /api/v1/approvals/{id}/approve` | Body: `{decided_by, note?}`. → `200` approval (`status: "approved"`). Requires an approval-capable role (see §8). |
| `POST /api/v1/approvals/{id}/reject` | Body: `{decided_by, note?}`. → `200` (`status: "rejected"`); the task is denied on next execute. |

**Approval object (evidence):**
```json
{
  "id": "…", "task_id": "…", "action_summary": "execute plan: book a shipment…",
  "risk_score": 50.0, "risk_level": "high",
  "reasons": ["tool risk floor 45 …", "side-effecting tool +5"],
  "policy_decision": "require_approval",
  "policy_version_hash": "9f2c…(64 hex)",
  "status": "requested", "requested_at": "…", "expires_at": "…",
  "decided_by": null, "decided_at": null
}
```

### 4.6 Audit — append-only hash-chained ledger

Per-tenant Ed25519-signed hash chain. Entries store **digests** of inputs, never
raw secrets/PII (redact-before-write). Ephemeral signing key unless
`ACP_LEDGER_SIGNING_KEY_b64` is set — signatures do not verify across restarts
with the ephemeral key (dev-only; documented at startup).

| Method & path | Description |
|---|---|
| `GET /api/v1/audit?event_type=&task_id=&limit=&offset=` | Query entries (tenant-scoped, seq order). |
| `GET /api/v1/audit/{seq}` | Single entry by sequence number. |
| `GET /api/v1/audit/verify` | Recompute the chain. → `200 {"ok": true, "checked": N, "first_break": null}` or the first break (`link-broken` / `content-altered` with seq). |

### 4.7 Cost & budgets

| Method & path | Description |
|---|---|
| `POST /api/v1/budgets` | Create a budget. Body: `{scope: "task"|"agent"|"tenant", scope_id, limit, period?}`. → `201`. |
| `GET /api/v1/cost/summary?scope=&scope_id=` | → `200 {total, by_model{}, by_tool{}}`. |

Budgets are enforced at the tool-call choke point (estimated cost + actuals):
exhaustion raises `BudgetExhausted` → task fails, delegation chain revoked
(kill switch), `CostThresholdExceeded` emitted. Alerts fire at the configured
thresholds (`ACP_BUDGET_ALERT_THRESHOLDS`, default `0.8,0.95`).

### 4.8 Evaluations

| Method & path | Description |
|---|---|
| `POST /api/v1/evaluations` | Run metrics over a task. Body: `{agent_id, task_id, metrics[]}`. → `201 {results{}}`. |
| `GET /api/v1/evaluations/{id}` | Stored evaluation. |
| `GET /api/v1/metrics` | Aggregate counters (`tasks_by_status`, …) + `available_metrics`. |

Available metrics: `task_success`, `tool_call_accuracy`, `policy_violations`,
`latency`, `cost`. The `learning` package is **propose-only**: it drafts
promotion proposals from evaluations; nothing is auto-applied.

### 4.9 Traces & streaming

| Method & path | Description |
|---|---|
| `GET /api/v1/traces?task_id=&limit=` | OTel span metadata captured per task (`acp.stage.*`, `acp.tool.invoke` with `acp.task.id`, `acp.agent.id`, `acp.policy.decision`). |
| `GET /api/v1/tasks/{id}/events` | SSE stream of task events (see §4.3). |

## 5. Policy choke points

Six choke points, every one fail-closed (PDP unreachable or error ⇒ deny):

| # | Choke point | Policy kind | Where |
|---|---|---|---|
| 1 | Task admission | `task_admission` | `POST /tasks/{id}/execute` stage 1 |
| 2 | Plan admission | `plan_admission` | stage 4 (plan + cost + risk) |
| 3 | Tool call | `tool_invoke` | every step; `POST /tools/{id}/invoke` |
| 4 | Egress interface | `egress` | tool executions with network egress declared in tool `metadata` |
| 5 | Memory provenance | `memory_write` / `memory_read` | untrusted sources are quarantined and excluded from retrieval |
| 6 | Learning / promotion | `promotion` | learning proposals; MVP is propose-only |

**Deny-by-default:** unknown policy kinds, missing tenant policy, or an
unreachable OPA endpoint all evaluate to `deny`. The bundled
`MinimalRuleEngine` is a non-production fallback (loudly logged); set
`ACP_OPA_URL` to use OPA/Rego (sample policy: `integrations/opa/policies/booking.rego`).

Guardrails that always deny: cross-tenant arguments (`args.tenant_id` ≠ caller
tenant), tenant `deny_tool_ids`, tools outside the tenant `allow_tool_ids`,
tools outside the agent grant set, tools outside the delegation scope.

## 6. Risk model

Hybrid: deterministic scoring + optional model hook. The model hook may only
**raise** risk (uplift is added; negative deltas are clamped to 0) — it can
never lower a score or clear `requires_human_approval`.

Deterministic factors: per-tool risk-class floor
(low 5 / medium 20 / high 45 / critical 70), `destructive` +20, `financial` +15,
`side_effecting` +5, PII/data-classification uplift, untrusted-content uplift,
cost-ratio uplift. Levels: `low < 25 ≤ medium < 50 ≤ high < 75 ≤ critical`;
`requires_human_approval` at high+.

## 7. Budgets & kill switches

- **Task budget**: `budget_limit` on task creation materializes a task-scoped
  budget row; it is checked before every tool call (estimate) and on completion.
- **Kill switches**: `POST /tasks/{id}/cancel` (revokes the delegation chain);
  budget exhaustion (freezes spend, revokes delegations, fails the task).
- **Approval timeout == deny.** **Policy/governance failure == deny.**

## 8. RBAC / ABAC

Roles (via `X-Role`, default `viewer`; unknown roles → `403`):
`platform_admin` (all), `tenant_admin`, `agent_operator`, `approver`,
`auditor`, `viewer` (read-only). Approval decisions require
`approvals.decide` (`approver`, `tenant_admin`, `platform_admin`); other roles
get `403` and the attempt is audited as `PermissionDenied`.
ABAC additionally checks: agent `max_risk_level` vs tool `risk_class`, agent
`clearance` vs data classification, and delegation scope intersection
(user-delegable ∩ agent-granted ∩ task-scoped ∩ policy-allowed).

## 9. Events (selective event sourcing)

Only audit/workflow history is event-sourced. Event types include:
`TaskCreated, TaskPlanned, TaskRouted, RiskAssessed, PolicyEvaluated,
ApprovalRequested, ApprovalGranted, ApprovalRejected, TaskStarted,
DelegationIssued, ToolInvoked, ToolFailed, TaskCompleted, TaskFailed,
CostThresholdExceeded, PermissionDenied, SecurityViolationDetected`.
Transport: in-process bus by default; Redis Streams via `ACP_REDIS_URL`;
transactional outbox relayed by `acp-worker`.

## 10. Configuration (env)

| Var | Default | Purpose |
|---|---|---|
| `ACP_API_KEY` | `dev-key-change-me` | Bearer credential (**change in production**). |
| `ACP_DATABASE_URL` | `sqlite:///./acp.db` | SQLAlchemy URL (Postgres recommended prod). |
| `ACP_REDIS_URL` | — | Enables Redis Streams event bus. |
| `ACP_OPA_URL` | — | OPA base URL; unset ⇒ `MinimalRuleEngine` (non-production). |
| `ACP_LEDGER_SIGNING_KEY_b64` | ephemeral | Ed25519 seed for the audit ledger (set in production). |
| `ACP_JWT_SECRET` | `dev-jwt-secret-change-me` | Delegation token HMAC secret. |
| `ACP_APPROVAL_TTL_SECONDS` | `3600` | Approval expiry (timeout == deny). |
| `ACP_PLANNER` | `deterministic` | `deterministic` \| `rule_based` (LLM planner is interface-only). |
| `ACP_DEFAULT_MODEL_PROVIDER` | `mock` | `mock` \| `openai` \| `anthropic` (latter two are stubs). |
| `ACP_BUDGET_ALERT_THRESHOLDS` | `0.8,0.95` | Spend-ratio alerts. |
| `ACP_OTLP_ENDPOINT` | — | OTLP HTTP traces endpoint; unset ⇒ console exporter. |
| `ACP_SECRET_BACKEND` | `env` | `env` (dev-only, loud warning) \| `vault` (stub). |

## 11. Data model (core tables)

`agents` (versioned registry: `tool_ids` grants, `capabilities`, `model_config`,
`max_risk_level`, lifecycle `status`) · `tools` (`risk_class`, `cost_per_call`,
`schema`, `auth`) · `tasks` (`status`, `plan`, `risk_assessment`,
`cost_estimate/incurred`, `budget_limit`) · `task_steps` (checkpointed durable
steps) · `approvals` (state machine + risk/policy evidence) · `audit_entries`
(hash chain) · `events` + `outbox` (selective event sourcing) · `delegations`
(revocable JWT JTIs) · `budgets`, `cost_ledger` · `policy_bundles` (versioned,
hash-pinned) · `memory_entries` (provenance + quarantine) · `knowledge_docs` ·
`evaluations`, `learning_proposals` (propose-only).

Every table carries `tenant_id`; every query is tenant-scoped.

## 12. Quickstart

```bash
python -m venv /tmp/venv-acp-backend && /tmp/venv-acp-backend/bin/pip install -e ".[test]"
ACP_DATABASE_URL="sqlite:////tmp/acp.db" /tmp/venv-acp-backend/bin/uvicorn acp.api:app --port 8000

H=(-H "Authorization: Bearer dev-key-change-me" -H "X-Tenant-ID: tenant-a")
curl "${H[@]}" -X POST localhost:8000/api/v1/tools -d '{"name":"mock_get_quote","risk_class":"low","cost_per_call":0.01}' -H 'Content-Type: application/json'
# … register tools, register agent, POST /tasks {"goal":"book a shipment from NYC to Boston"},
# POST /tasks/{id}/execute, GET /audit/verify
```

Run the suite: `/tmp/venv-acp-backend/bin/python -m pytest tests/ -q`
Lint: `/tmp/venv-acp-backend/bin/python -m ruff check src/ tests/`
Migrate (Postgres): `/tmp/venv-acp-backend/bin/alembic upgrade head`
Worker: `/tmp/venv-acp-backend/bin/acp-worker` (or `python -m acp.worker`)
