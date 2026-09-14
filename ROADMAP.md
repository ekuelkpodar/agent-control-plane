# Roadmap

Phases run from research → MVP → enterprise. Each phase lists features,
engineering complexity, dependencies, risks, and the expected outcome.
See `docs/research/` for the evidence behind these sequencing choices.

## Phase 0 — Research ✅ (done, 2026-09-14)

Market, competitive/product, architecture, technology, Kubernetes-comparison,
definition, and security/threat-model research streams. Outputs live in
`docs/research/`.

- **Outcome:** validated category, positioning ("the control plane for
  enterprise AI agents"), tech decisions, hard constraints, T1–T20 threat
  model.

## Phase 1 — Architecture ✅ (done, 2026-09-14)

Layering (AGRL → control plane → governance rail → execution → tools),
data/control-plane traffic rule, selective event sourcing, fail-closed
model, multi-tenancy shape. See [ARCHITECTURE.md](ARCHITECTURE.md).

- **Outcome:** the spine every later phase builds on; K8s-analogy mapping
  (~60% useful) documented in
  `docs/research/kubernetes-comparison.md`.

## Phase 2 — MVP (this repo)

**Features**
- Agent registry (versions, capabilities, verifiable identity, signed
  definitions).
- Tool registry (catalog, JSON schemas, risk classes, signed schemas).
- Task API + governed pipeline: admission → plan → risk → policy →
  approval → execute → audit.
- Rule-based planner behind a strategy interface; capability/cost/policy
  router (route, don't proxy).
- Policy engine: `allow`/`deny`/`require_approval`/`allow_with_constraints`;
  OPA/Rego PDP behind interface; minimal built-in evaluator for local dev
  (explicitly non-production).
- Deterministic risk engine with approval triggers; budget envelopes +
  hard deny at 100%; kill switch per task.
- Approval/HITL state machine; approval timeout = deny; evidence payloads.
- MVP durable runner (Postgres-backed: states, retries, backoff,
  idempotency keys, heartbeats, pause/resume).
- Append-only, hash-chained, signed audit ledger.
- Multi-tenancy: tenant scoping via `X-Tenant-ID`, RLS, per-tenant
  policies/budgets/audit chains.
- OTel instrumentation with decision-provenance attributes; dashboard.
- Local reference runtime + mock tool executor; logistics end-to-end demo.

**Engineering complexity:** Medium. One modular monolith, ~6 bounded
packages. Hardest parts: approval state machine + durable runner semantics,
correct fail-closed behavior under fault injection, and the policy-engine
interface design (must not leak OPA specifics into the core).

**Dependencies:** Postgres 16, Redis 7, OPA (optional), OTel collector.
No external SaaS required.

**Risks:** scope creep into workflow-engine territory (cut: Temporal
integration deferred); built-in policy evaluator being mistaken for
production (mitigate: naming, docs, startup warning).

**Expected outcome:** `docker compose up` → registered agent → governed
task → human approval → audit-verifiable run. Demoable logistics flow.

## Phase 3 — Multi-agent orchestration & knowledge

**Features**
- Multi-agent tasks: planner produces multi-step/multi-agent plans;
  handoff protocol (A2A-compatible) with authenticated inter-agent
  messages via the control-plane bus.
- Knowledge layer: RAG retrieval interface behind the ACP; document
  ingestion/chunking as V1 integration (pgvector first).
- Memory management: lifecycle, retention, tenant namespacing, deletion;
  provenance-tagged entries.
- Evaluation engine: trajectory scoring, eval gates on agent versions
  (behavioral versioning), canary-by-outcome rollouts.
- `WorkflowBackend` interface + Temporal adapter for heavy-duty durable
  execution (MVP runner remains the Postgres-only option).

**Complexity:** High. Multi-agent coordination semantics and behavioral
versioning are genuinely hard; Temporal integration is the easy part.

**Dependencies:** Temporal cluster (V1), vector store (pgvector first).

**Risks:** non-deterministic semantics break deploy-style rollout
intuitions; canary metrics need statistical care.

**Expected outcome:** fleet tasks with handoffs, governed by the same
policy rail; eval-gated agent version promotion.

## Phase 4 — Enterprise governance

**Features**
- OPA as production PDP (sidecar/embedded), Rego policy bundles versioned
  in Git, signed, with `opa test` CI.
- Delegation chains: user→agent delegation tokens (OAuth token-exchange
  pattern), downward-narrowing, full chain in audit.
- Per-tenant KMS envelope encryption; field-level encryption for
  PII/secret fields in audit + memory.
- Audit anchoring: periodic chain-head publication to an external
  transparency log (Sigstore Rekor-style).
- RBAC roles (platform_admin, tenant_admin, agent_operator, approver,
  auditor, viewer) + ABAC policy hooks; multi-person approval thresholds.
- Compliance evidence packs: EU AI Act recordkeeping (Arts. 12/19),
  SOC 2 Type II audit exports.
- Three deployment artifacts: managed SaaS, customer-VPC managed,
  air-gapped self-hosted.

**Complexity:** High. KMS envelope encryption + key lifecycle and air-gap
packaging are the long poles.

**Dependencies:** Vault/class secret manager, SPIFFE/SPIRE (production
identity issuance), Rekor-style anchor.

**Risks:** 16–20 week enterprise buying cycles (Levelpath) mean the wedge
(gateway + registry + policy) must sell before full governance ships;
plan packaging accordingly.

**Expected outcome:** FS-ready governance posture; auditor-readable
evidence packs; air-gap deploy works.

## Phase 5 — Scale & operations

**Features**
- Kubernetes manifests + Helm chart; Terraform cloud scaffolding; cloud-neutral.
- Event bus step-up: Redis Streams → NATS JetStream (interface preserved).
- Vector step-up: pgvector → Qdrant.
- Horizontal worker scaling; bulkheads between tenants; per-tenant quotas.
- Edge/offline PEPs: local policy enforcement points for disconnected
  agents (fail-closed by construction).
- SLOs for control-plane latency; admission-path caching (the hardest
  engineering constraint: runtime authorization latency).

**Complexity:** Medium-High. Latency optimization on the hot path
(local policy cache + async audit) is the critical path.

**Dependencies:** K8s clusters, NATS, Qdrant.

**Risks:** cache staleness vs. revocation freshness — revocation must
propagate within seconds (lease expiry + event fan-out).

**Expected outcome:** production-scale multi-tenant operation; hot-path
policy decisions in microseconds-to-milliseconds.

## Phase 6 — Autonomous optimization (gated)

**Features**
- Learning/feedback loops *inside* governance bounds: learning outputs are
  versioned change proposals (routing weights, prompt updates, policy
  suggestions) → policy evaluation → human approval → canary eval →
  promotion. **No self-modification**: the optimizer can never edit its own
  guardrails (constraint flow is one-way: control policy → intelligence).
- Advanced routing (learned), cross-tenant (org-level) governance,
  GraphRAG, agent/tool marketplace.

**Complexity:** Very high. Formal "risk algebra" (deterministic floor +
ML refinement composition, trust decay without boiling-frog creep) needs a
prototype first (open research question, see
`docs/research/security-analysis.md` §9).

**Dependencies:** V1 evidence from Phases 3–5; a real fleet with real
feedback data.

**Risks:** shipping learning before the governance chain is proven would
be the architectural equivalent of removing the admission controller.
Gate strictly on evidence.

**Expected outcome:** self-improving routing and policies that a regulator
can still audit.
