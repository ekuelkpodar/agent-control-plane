# Architecture Decision Records

Numbered, immutable-once-accepted. A superseded ADR stays in this file with
its status changed — history is not rewritten. See
`docs/research/technology-evaluation.md` for the evidence behind these.

## ADR-001 — Modular monolith, not microservices

**Status:** accepted · **Date:** 2026-09-14

**Context.** The MVP needs registry, tasks, policy, risk, approvals,
workflows, cost, audit, memory, evaluation. Splitting into services now
multiplies build tooling, CI, debugging, and cross-service auth for zero
MVP benefit; the research verdict is explicit: *"Do not microservice the
MVP."*

**Decision.** One Python process, organized into bounded packages with
strict public interfaces (`src/acp/`). Split only on proven seams: scale,
security boundary, or independent deployability.

**Consequences.** Fast iteration, single deployment unit for `docker
compose up`. Later extraction (e.g. policy sidecar in Go) must not require
rewrites — hence the interface-first rule in each package.

## ADR-002 — PostgreSQL is the system of record

**Status:** accepted · **Date:** 2026-09-14

**Context.** Approvals, budgets, delegation chains, and registries need
ACID consistency, relational queries, and an outbox for reliable event
publication. etcd (the K8s choice) is the wrong data model: ACP state is
relational, larger, and query-heavy.

**Decision.** PostgreSQL for all current-state data: registries, tasks,
approvals, policies, budgets, audit ledger. JSONB for flexible agent/tool
metadata. Row-level security for tenant isolation. Transactional outbox for
event publication.

**Consequences.** Operators need Postgres literacy (managed Postgres is
available on every cloud — cloud-neutral). Run-history *telemetry* (spans)
stays out of Postgres; high-volume trace storage is a separate concern.

## ADR-003 — REST + OpenAPI, with SSE for streams

**Status:** accepted · **Date:** 2026-09-14

**Context.** The control-plane API is the primary interface for humans,
agents, and dashboards. It must be universal (curl, codegen, browsers) and
governable (arbitrary GraphQL query depth against a governance system is a
liability).

**Decision.** REST with OpenAPI 3.1 and JSON as the primary API; SSE (and
WebSocket where bidirectional) for live streams: execution traces, approval
notifications. gRPC reserved for future internal service-to-service calls
after a monolith split.

**Consequences.** Entity-oriented design with standardized verbs maps cleanly
to K8s API conventions and to gRPC later. Dashboard needs are covered by
REST resources + SSE — no GraphQL resolver complexity.

## ADR-004 — Selective event sourcing

**Status:** accepted · **Date:** 2026-09-14

**Context.** Full event sourcing of registries ("replay 10M events to
answer 'is agent v3 enabled?'") is fashionable overengineering. But the
audit ledger and workflow execution history *are* evidence and must be
append-only streams.

**Decision.** Event-source only the audit ledger and workflow execution
history. Registries are current-state rows with version history, not event
streams.

**Consequences.** Simpler reads everywhere ("what is the current policy?")
with complete evidence where it matters ("who approved this, when, on what
basis?"). The `acp.audit` package owns the append-only writer; nobody else
may write to the ledger.

## ADR-005 — OPA/Rego PDP, with a minimal built-in evaluator for MVP dev

**Status:** accepted · **Date:** 2026-09-14

**Context.** A custom policy DSL becomes an untested, unaudited shadow
authorization system. OPA/Rego is CNCF-graduated, purpose-built for decoupled
JSON decisions, proven in K8s admission control (Gatekeeper) — the closest
precedent to ACP admission control. But requiring OPA for `docker compose
up` hurts DX.

**Decision.** A `PolicyEngine` interface in `acp.policy`. Production PDP:
OPA (embedded or sidecar), Rego policies versioned in Git, signed, tested
with `opa test`. MVP default: a minimal built-in rule evaluator so the
stack runs without OPA. The built-in evaluator is **explicitly marked
non-production** — it exists for local DX, not as a second standard.

**Consequences.** The interface boundary is the architecture; the engine is
a dependency. Cedar stays on the watchlist for formally-verified subsets
(V2), not as the primary PDP.

## ADR-006 — MVP durable runner → Temporal in V1

**Status:** accepted · **Date:** 2026-09-14

**Context.** Building a full workflow engine is the single largest
overengineering risk. Journal-replay-recovery is years of distributed-
systems edge cases. But requiring operators to run a Temporal cluster for
the MVP demo kills adoption.

**Decision.** MVP ships a minimal Postgres-backed durable runner *inside the
monolith*: explicit states, retries with backoff, idempotency keys,
heartbeats, pause/resume for approvals. V1 integrates Temporal behind a
`WorkflowBackend` interface (Hatchet as the Postgres-only fallback).
"durable enough," not a workflow engine.

**Consequences.** The durable runner's semantics are deliberately subset of
Temporal's so migration is an adapter, not a rewrite. Checkpoint *before*
every side-effecting step with the policy decision attached.

## ADR-007 — Fail-closed governance

**Status:** accepted · **Date:** 2026-09-14

**Context.** The adversary is inside the workload (prompt injection, tool
poisoning, compromised agents). "Fail open for availability" would let a
partitioned or compromised rail silently authorize actions.

**Decision.** Every failure defaults to the safe state: deny the action,
freeze the workflow, preserve evidence, escalate. Concretely: approval
timeout = deny; budget exhaustion = deny; governance rail unreachable =
deny high-risk, queue low-risk for re-adjudication; deny-by-default policy
model; watchdog breach = freeze (no "one last tool call").

**Consequences.** Availability is recovered via redundancy and checkpoints,
never by skipping authorization. Every fail-closed path gets a test —
fault injection against the governance rail is part of CI expectations.

## Template for new ADRs

```markdown
## ADR-NNN — Title

**Status:** proposed | accepted | superseded by ADR-MMM · **Date:** YYYY-MM-DD

**Context.** ...
**Decision.** ...
**Consequences.** ...
```
