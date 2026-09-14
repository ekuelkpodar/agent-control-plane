# Agent Control Plane — Technology Evaluation

Research date: 2026-09-14. Every section: options → tradeoffs → recommendation.
Markers: **[Fact]**, **[Convention]**, **[Recommendation]**, **[Hypothesis]**, **[Opinion]**.

---

## 1. Backend language(s)

### Options
**Python** — the agent ecosystem's lingua franca (LangChain, LangGraph,
CrewAI, AutoGen, Pydantic AI, Strands all Python-first); richest ML/LLM
library surface; fastest hiring for AI teams.
**TypeScript** — best dashboard/full-stack story; Inngest/AgentKit-class
tooling TS-first; weaker agent-framework ecosystem than Python.
**Go** — excellent for control planes (Kubernetes itself is Go), low-latency
high-concurrency services; thin AI ecosystem; Hatchet is Go-native.
**Rust** — maximal performance/safety (Qdrant is Rust); slowest development
velocity; overkill for orchestration logic.

### Tradeoffs
- The ACP's hard problems are *policy evaluation, state machines, API
  design, and integrations* — not numerical compute. Language performance is
  rarely the binding constraint; ecosystem and velocity are.
- Polyglot from day one multiplies build tooling, CI, hiring surface, and
  cross-service debugging for zero MVP benefit.

### **[Recommendation] Python for the MVP modular monolith.**
Rationale: (1) every agent framework the ACP must interoperate with is
Python-first, so adapters, reference runtime, and evaluation harnesses are
cheapest in Python; (2) OPA, Temporal, and OpenTelemetry all have first-class
Python SDKs; (3) the 2026 enterprise data shows buyers choose orchestration
for *flexibility across models/tools* (29% top purchase driver —
[VentureBeat](https://venturebeat.com/resources/agentic-orchestration-enterprise-ai-organizations-know-how-to-govern-agents-but-still-cant-meter-what-they-cost)),
which argues for ecosystem reach over runtime speed.
**Go or Rust later, and only** for proven hot paths (policy evaluation
sidecar, high-throughput event router). Enforce strict package boundaries in
the monolith so a package can be extracted without rewrite.

---

## 2. API style

### Options
**REST (+ OpenAPI)** — universal, browser-friendly, best tooling (curl,
Postman, codegen), matches Kubernetes' own API conventions.
**gRPC** — strongly typed, streaming, efficient; internal-services sweet spot.
**GraphQL** — client-driven queries for dashboards; resolver complexity and
governance of arbitrary queries are real costs.
**WebSockets / SSE** — needed regardless for live execution streams, approval
notifications, trace tailing.

### **[Recommendation] REST as the primary control-plane API (OpenAPI 3.1,
JSON), SSE/WebSocket for streams, gRPC reserved for future internal
service-to-service calls after the monolith splits.**
Rationale:
- Kubernetes' own design principles apply directly: declarative APIs,
  transparent control plane (no hidden internal APIs), cost of operations
  proportional to objects touched
  ([K8s principles](https://github.com/kubernetes/design-proposals-archive/blob/main/architecture/principles.md)).
- Google's API guidance notes the Kubernetes API itself is usable as both
  REST and protobuf; entity-oriented design with standardized verbs
  (create/retrieve/update/delete/list) captures most of REST's benefits and
  maps cleanly to gRPC later if needed
  ([Google Cloud](https://cloud.google.com/blog/products/api-management/understanding-grpc-openapi-and-rest-and-when-to-use-them)).
- **Not GraphQL for MVP**: arbitrary query depth against a governance system
  is a security/complexity liability; REST resources + SSE cover dashboard
  needs. Industry hybrid pattern (REST at edge, gRPC internal, events async)
  is the proven shape
  ([comparison](https://dev.to/benyusouf/microservices-communication-patterns-when-to-use-rest-grpc-or-message-queues-2dl4)).

---

## 3. Database & storage

### System of record — **[Recommendation] PostgreSQL.**
**[Convention]** Postgres is the default system of record for control planes:
ACID, JSONB for flexible agent/tool metadata, row-level security for
multi-tenancy, transactional outbox for event publication, mature
operational tooling, and every cloud offers it managed. The ACP's
consistency needs (approvals, budgets, delegation chains) are exactly what
relational ACID is for.

### Cache / ephemeral state — **[Recommendation] Redis.**
Rate limiting, idempotency keys, distributed locks/leases for task claiming,
session/approval tokens, pub/sub for live updates. Redis Streams can double
as the MVP event bus (see §4).

### Vector search — **[Recommendation] pgvector in Postgres for MVP; Qdrant
(or Weaviate for hybrid search) as the documented scale-out path; Milvus
only past ~100M vectors.**
**[Fact]** 2026 comparisons converge: pgvector suffices under ~10M vectors
when Postgres is already in the stack ("for 90% of RAG in 2026, pgvector
suffices"); Qdrant (Rust, single binary) is the best OSS default for
10M–1B; Weaviate leads native hybrid (vector+BM25) search; Milvus is the
only serious option past 100M+ but demands Kubernetes and real DevOps
([dev.to comparison](https://dev.to/krunalkanojiya/pinecone-vs-weaviate-vs-milvus-vs-qdrant-which-vector-db-in-2026-26dc);
[production guide](https://devops.gheware.com/blog/posts/vector-databases-kubernetes-production-guide-2026.html);
[OSS comparison](https://botmonster.com/ai/open-source-vector-databases-qdrant-milvus-weaviate/);
[engineering notes](https://github.com/bschouha19/vector-database-engineering/blob/HEAD/CLAUDE.md)).
**[Opinion]** A dedicated vector DB on day one is premature optimization for
an MVP whose memory story is lifecycle/tenancy management, not ANN recall
benchmarks.

### Graph — **[Recommendation] defer.** Model agent/tool/goal relationships in
Postgres (adjacency + recursive CTEs) for MVP; adopt a graph DB only when
traversal queries prove painful. GraphRAG is a V2 knowledge-layer concern.

### Object storage — **[Recommendation] S3-compatible (MinIO locally).**
Artifacts, trace payloads, evaluation datasets, prompt bundles. Never in
Postgres as blobs at scale.

---

## 4. Eventing / message bus

### Options
**Postgres (LISTEN/NOTIFY + outbox)** — zero new infra; limited throughput.
**Redis Streams** — lightweight, good enough for MVP event fan-out.
**NATS (JetStream)** — simple ops, low latency, persistence; excellent
mid-scale choice.
**Kafka** — maximum throughput and ecosystem; heaviest operationally.

### **[Recommendation] Transactional outbox in Postgres → Redis Streams (MVP),
with a `EventBus` interface; NATS JetStream as the documented step-up; Kafka
only on proven throughput need.**
Rationale: the ACP's event volume (task lifecycle, policy decisions,
approvals) is moderate — control-plane traffic, not clickstream. Kafka on day
one is the classic overengineering move. The outbox pattern gives reliable
publication without distributed transactions, and the interface keeps the
upgrade path clean.

---

## 5. Workflow / durable execution

### Options
**Temporal** — industry standard; deterministic replay, activities with
retries, signals for human-in-the-loop, polyglot SDKs; officially positions
itself for AI agents (LLM calls as activities, MCP clients in activities,
signals for HITL, workflow variables as durable memory)
([Temporal](https://temporal.io/blog/durable-execution-meets-ai-why-temporal-is-the-perfect-foundation-for-ai)).
**[Fact]** ~9.1T lifetime executions, ~1.86T from AI-native companies; raised
$300M at $5B (Feb 2026) — credible long-term vendor
([eval](https://github.com/atilladeniz/next-go-pg/issues/57)).
**Hatchet** — Go-native, MIT, Postgres-backed durability (no new datastore),
lighter ops; positioned as Temporal/DBOS alternative for AI pipelines
([same eval](https://github.com/atilladeniz/next-go-pg/issues/57)).
**Restate / DBOS** — journaled durable execution; DBOS checkpoints in
Postgres; Pydantic AI treats durable backends as pluggable (Temporal, DBOS,
Prefect, Restate) — the ecosystem already considers this buy-not-build.
**Inngest** — excellent DX, AgentKit for agents; TS-first, SaaS-happy-path.
**Build your own** — journal-replay-recovery is years of distributed-systems
edge cases (determinism constraints, versioning, replay-breaking changes).

### **[Recommendation] Two-track:**
1. **MVP:** a minimal Postgres-backed durable task runner *inside the
   monolith* (states, retries with backoff, idempotency keys, heartbeats,
   pause/resume for approvals) — enough for the demo workflows without
   requiring operators to run a Temporal cluster. This is "durable enough,"
   not a workflow engine.
2. **V1:** integrate **Temporal** behind a `WorkflowBackend` interface
   (Hatchet as fallback for Postgres-only shops). Temporal wins on maturity,
   ecosystem, and explicit AI-agent positioning; its operational weight is
   the reason it waits for V1, not MVP.
**[Opinion]** Building a bespoke full workflow engine is the single largest
overengineering risk in this project. The interface boundary is the
architecture; the engine is a dependency.

---

## 6. Policy engine

### Options
**OPA/Rego** — CNCF graduated, general-purpose, purpose-built for decoupled
policy decisions over JSON; `opa test` for policy CI; proven in Kubernetes
admission (Gatekeeper) — the closest precedent to ACP admission control
([Styra](https://www.styra.com/knowledge-center/opa-vs-cedar-agent-and-opal/);
[OPA in practice 2026](https://medium.com/@maulik.shyani_25021/implementing-least-privilege-dlp-controls-using-open-policy-agent-opa-snippets-f4fc629bd03a)).
**Cedar** — AWS's authorization language; formally verifiable, readable;
but a *language*, not an engine — needs Cedar Agent/OPAL or Amazon Verified
Permissions (AWS-only) for a complete solution
([Styra](https://www.styra.com/knowledge-center/opa-vs-cedar-aws-verified-permissions/)).
**Custom rules engine** — fastest MVP, but becomes a second policy language
to maintain; policy-as-code benefits (versioning, testing, audit) are lost.

### **[Recommendation] OPA (embedded via Go library/sidecar or OPA server) as
the PDP, Rego policies versioned in Git; a `PolicyEngine` interface with a
minimal built-in rule evaluator as the MVP default so the system runs without
OPA deployed.**
Rationale: OPA is the only option that is simultaneously a complete engine,
cloud-neutral, and proven in admission-control-shaped problems. Cedar is
worth tracking for formally-verified authorization subsets in V2, not as the
primary PDP. The built-in MVP evaluator must be explicitly marked
non-production — it exists for `docker compose up` DX, not as a second
standard.

---

## 7. Observability

### **[Recommendation] OpenTelemetry from day one; Prometheus + Grafana for
metrics/dashboards; structured JSON logs; W3C trace context + a
first-class `correlation_id`/`trace_id` on every task.**
Rationale:
- **[Convention]** OTel is the industry standard for traces/metrics/logs;
  every 2026 vector DB, workflow engine, and cloud supports it natively.
- The ACP needs *decision provenance* beyond standard telemetry: every trace
  should link task → plan → agent selection → policy evaluation → risk score
  → approval → tool calls → outcome. Implement as OTel spans with
  semantic attributes (`acp.task.id`, `acp.policy.decision`, …), following
  OTel's GenAI semantic conventions where applicable.
- Cost telemetry (tokens, tool calls) is emitted as metrics from the same
  pipeline — this is how the 2026 "can't meter agents" gap gets closed
  ([VentureBeat](https://venturebeat.com/resources/agentic-orchestration-enterprise-ai-organizations-know-how-to-govern-agents-but-still-cant-meter-what-they-cost)).

---

## 8. Authentication & identity

### **[Recommendation]**
- **Humans:** OIDC (enterprise IdP) → short-lived JWTs; OAuth2 for delegated
  user authority. Agents NEVER inherit ambient user authority — delegation is
  explicit, scoped, and attenuated (the composite-principal model).
- **Services/agents:** SPIFFE/SPIRE workload identity where available;
  otherwise short-lived mTLS/JWT service credentials with automatic rotation.
- **Secrets:** Vault or cloud secret manager integration; agents receive
  short-lived, scoped credentials brokered by the control plane — never raw
  vault access, never long-lived API keys.
- **Tenant isolation:** every identity carries tenant scope; enforcement at
  both API and data layers.

---

## 9. Model abstraction

### **[Recommendation] A `ModelProvider` adapter interface
(capabilities, cost/latency metadata, streaming) with OpenAI, Anthropic,
Google, Bedrock, OpenRouter, and Ollama adapters; routing consumes the
metadata.** Do not build a model gateway — route *through* existing
gateways where present. The router's job is selection on
capability×quality×latency×cost×risk×availability×policy, not proxying
tokens (data-plane principle).

---

## 10. Memory & knowledge infrastructure

### **[Recommendation]**
- **Short-term / working memory:** workflow variables / Postgres task state
  (durable execution gives this nearly free).
- **Semantic/episodic memory:** pgvector (MVP) → dedicated vector DB (V1+)
  per §3; always behind a `MemoryStore` interface with tenant namespacing,
  retention policies, and deletion support.
- **Knowledge/RAG:** keep the *retrieval interface* in the ACP; the document
  pipeline (ingestion, chunking, GraphRAG) is a V1 integration, not MVP.
- **[Opinion]** Vector DBs solve retrieval, not memory. Memory lifecycle
  (what to remember, forget, consolidate; tenant isolation; privacy) is the
  ACP's actual differentiated work.

---

## 11. Deployment targets

### **[Recommendation] Docker Compose for local dev (Postgres, Redis,
MinIO, OPA sidecar, OTel collector); Kubernetes manifests + Helm for
production; Terraform for cloud scaffolding in V1. First cloud target:
the one the operator already runs — the system is cloud-neutral by design
(Postgres/Redis/K8s are everywhere).**
Rationale: 2026 buyers fear lock-in above all; a control plane that only
runs on one cloud contradicts its own value proposition.

---

## 12. Decision log (one-line each)

| Decision | Choice | Why |
|---|---|---|
| Language | Python monolith | Ecosystem reach, velocity; extract hot paths later |
| API | REST+OpenAPI, SSE streams | Universal, K8s-conventional, governable |
| System of record | PostgreSQL | ACID for approvals/budgets/delegation; outbox |
| Cache/queue | Redis (+Streams) | Leases, idempotency, MVP bus |
| Vectors | pgvector → Qdrant/Weaviate | Right-size by scale; avoid day-one ops |
| Events | Outbox → bus interface | Reliable without distributed txns |
| Workflows | MVP built-in durable runner → Temporal V1 | DX now, maturity later, no rebuild ever |
| Policy | OPA/Rego (interface; minimal built-in for MVP) | Proven admission-control precedent |
| Observability | OpenTelemetry + Prometheus/Grafana | Standard; decision provenance via span attrs |
| Auth | OIDC/JWT + SPIFFE + Vault-class secrets | Zero-trust, attenuated delegation |
| Models | Adapter interface, no gateway | Route, don't proxy |
| Deploy | Compose → K8s/Helm → Terraform | Cloud-neutral, lock-in-averse |
