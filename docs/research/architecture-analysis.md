# Agent Control Plane — Architecture Analysis

Research date: 2026-09-14. Status markers: **[Fact]**, **[Convention]**,
**[Recommendation]**, **[Hypothesis]**, **[Opinion]**.

## 1. The required spine — researched, challenged, improved

Required layering:

```
BUSINESS APPLICATIONS
        │
BUSINESS OBJECTIVES / GOALS
        │
AGRL / GOAL & RESOURCE MANAGEMENT
        │
AGENT CONTROL PLANE
        │
GOVERNANCE / SECURITY RAIL
        │
AGENT RUNTIME / EXECUTION PLANE
        │
TOOLS / APIs / MCP / DATABASES / CLOUD / COMPUTE
```

### 1.1 What survives scrutiny

**[Recommendation]** The spine is sound with three refinements:

1. **The Governance Rail must span control and execution, not sit between
   them.** Policy *decisions* happen in the control plane (admission,
   plan evaluation, risk scoring), but policy *enforcement* must also exist in
   the execution plane (local PEPs in the agent runtime, tool proxy
   interception) for offline/edge agents and defense-in-depth. A rail that only
   exists "between" layers is a single point of bypass. The arXiv 2026
   five-plane governance paper makes exactly this structural point: adjudicate
   once against full context, then *realize* the decision across infrastructure
   planes with coordinated enforcement.
   ([arXiv 2606.12320](https://arxiv.org/html/2606.12320v1))

2. **Observability and audit are cross-cutting, not a layer.** Every layer
   emits to shared telemetry and the audit ledger; drawing them as a box
   invites the "observability module" anti-pattern. This matches AWS's
   prescriptive guidance, where observability/security/discoverability *span*
   layers.
   ([AWS](https://docs.aws.amazon.com/prescriptive-guidance/latest/govern-architect-agentic-ai/enterprise-architecture.html))

3. **AGRL sits above the control plane and must remain separable.** Goals and
   resource ledgers are a business/intelligence concern; the ACP consumes
   *tasks derived from goals* via an API. Fusing them recreates the
   "sprawling and unaccountable" monolith the OSA-AI paper warns against: the
   control plane "owns the contracts that every other plane consumes… it
   deliberately does not run the other planes."
   ([OSA-AI](https://github.com/osa-ai-org/enterprise-ai/raw/refs/heads/main/docs/Enterprise-Agentic-AI-Platform-Strategy.pdf))

### 1.2 Improved layering

```
┌─────────────────────────────────────────────────────────────┐
│ BUSINESS APPLICATIONS (chat UIs, ops consoles, SaaS)        │
├─────────────────────────────────────────────────────────────┤
│ GOALS & RESOURCES LAYER (AGRL: goals, resources, ledger)    │  ← separable
├─────────────────────────────────────────────────────────────┤
│ AGENT CONTROL PLANE (decides: who/what/how/why, at what     │
│  risk+cost, under which policy, with what oversight)         │
│   registry · orchestrator · planner · router · tool registry │
│   memory/knowledge mgmt · workflow mgmt · evaluation · cost  │
├─────────────────────────────────────────────────────────────┤
│ GOVERNANCE RAIL (spans control + execution)                 │
│   PDP: policy engine · risk engine · permission engine      │
│   PEPs: admission webhook · runtime interceptor · tool proxy │
│   approvals/HITL · audit ledger · identity/delegation        │
├─────────────────────────────────────────────────────────────┤
│ EXECUTION PLANE (does the work)                             │
│   agent runtimes (agent loop, model calls) · workflow       │
│   workers · sandboxes · browsers · code exec                │
├─────────────────────────────────────────────────────────────┤
│ TOOL & INFRASTRUCTURE PLANE                                 │
│   MCP servers · APIs · DBs · SaaS · cloud · K8s · SSH       │
└─────────────────────────────────────────────────────────────┘
   ↕ cross-cutting: observability (OpenTelemetry), audit evidence, secrets
```

## 2. What belongs in each layer — the strong boundaries

### 2.1 Goals & Resources layer (AGRL) — NOT the control plane's job
**Belongs:** goal CRUD and lifecycle, goal decomposition policy, resource
inventory and budgets, utility/priority models, feedback ingestion.
**Does NOT belong:** anything that executes, routes, or authorizes.
**Boundary contract:** AGRL emits *task intents* (goal ref, constraints,
budget caps) to the control plane's Task API. The ACP never mutates goals.

### 2.2 Agent Control Plane — decides, coordinates, records
**Belongs:** agent registry (identity, versions, capabilities, health),
task API and lifecycle, planner (strategy selection), agent+model router,
tool registry (catalog, risk classification), workflow definitions,
evaluation framework, cost accounting, memory/knowledge *management*
(lifecycle, retention, tenancy — not the vector index itself).
**Does NOT belong:** model inference, tool execution, prompt execution,
secrets storage, raw vector storage, actual policy enforcement at the
metal (that's the rail's PEPs), business goal semantics.
**Key invariant:** the control plane is *off the hot path of execution* where
possible — it makes admission/routing decisions and observes via events; the
execution plane carries them out. (Same principle as Kubernetes: the API
server doesn't run containers.)

### 2.3 Governance Rail — adjudicates once, enforces everywhere
**Belongs:** policy engine (PDP), risk engine, permission engine (RBAC/ABAC,
delegation chains, capability attenuation), human-approval workflows,
append-only audit ledger, identity issuance (agent/service identities,
workload identity via SPIFFE), DLP/prompt-injection guardrails at
boundaries.
**Does NOT belong:** business logic, routing optimization, model selection.
**Boundary:** the rail exposes exactly one question to the rest of the
system — *"is this planned action permitted, and under what conditions?"* —
returning allow / deny / require-approval / conditional. Enforcement points:
control-plane admission (before dispatch), runtime interceptor (before tool
call), tool proxy (before external call).

### 2.4 Execution Plane — does the work, durably
**Belongs:** agent runtimes (the agentic loop), workflow workers
(Temporal-compatible activities), sandboxed code/browser execution,
checkpointing and retry mechanics, local PEP enforcement, execution
telemetry emission.
**Does NOT belong:** registry lookups for authority (it receives *scoped,
attenuated credentials* — never ambient authority), policy authoring,
cross-task coordination.
**Key invariant (fail-closed):** if the governance rail is unreachable, the
execution plane **denies high-risk actions by default** and queues low-risk
ones for re-adjudication. This is the single most important safety property
of the architecture.

### 2.5 Tool & Infrastructure Plane — external systems
**Belongs:** everything the enterprise already owns: MCP servers, SaaS APIs,
databases, K8s clusters, cloud accounts, SSH hosts.
**ACP's only job here:** catalogued, versioned, risk-classified *references*
in the tool registry + credential brokering (short-lived, scoped tokens —
never long-lived keys handed to agents). The ACP never reimplements a tool.

## 3. Data-plane vs control-plane traffic — where the analogy holds

**[Convention]** Borrowed from Kubernetes/networking: *control-plane traffic*
(registrations, task submissions, policy evaluations, approvals, status
updates) is low-volume, strongly consistent, and auditable; *data-plane
traffic* (model tokens, tool payloads, file transfers) is high-volume and
flows runtime↔tool directly, with the control plane seeing only metadata and
policy checkpoints — never proxying bulk data. Violating this (routing all
tool traffic through the ACP) is the fastest route to a bottleneck and a
single point of failure.

## 4. State, events, and consistency

**[Recommendation]**
- **System of record:** relational (PostgreSQL). Registries, tasks, approvals,
  policies are current-state rows with version history.
- **Event sourcing — selective, not everywhere:** the *audit ledger* and
  *workflow execution history* are append-only event streams (they are the
  evidence). Registries are NOT event-sourced; replaying 10M events to answer
  "is agent v3 enabled?" is fashionable overengineering.
- **Event backbone:** a transactional outbox in Postgres → message bus. This
  gives exactly-once *intent* publication without distributed transactions.
- **State machines explicit:** task, workflow execution, approval, and agent
  lifecycle states are enumerated state machines with documented transitions
  (CREATE→REGISTER→VALIDATE→DEPLOY→TEST→ACTIVATE→MONITOR→EVALUATE→VERSION→
  ROLLBACK→DEPRECATE→REVOKE).

### Core domain events (v1)
`AgentRegistered AgentUpdated AgentDeprecated TaskCreated TaskPlanned
TaskRouted TaskStarted TaskCompleted TaskFailed ToolInvoked ToolFailed
PolicyEvaluated PermissionDenied RiskAssessed ApprovalRequested
ApprovalGranted ApprovalRejected ApprovalExpired WorkflowStarted
WorkflowPaused WorkflowResumed WorkflowCompleted AgentEscalated
EvaluationCompleted CostThresholdExceeded SecurityViolationDetected
DelegationIssued DelegationRevoked`

## 5. Failure model (architectural consequences)

**[Recommendation]** Design for these explicitly; each maps to a mechanism:

| Failure | Architectural answer |
|---|---|
| Model failure / hallucination | Evaluation gates, output validators, planner fallback strategies, confidence-gated escalation |
| Tool/API failure, timeouts | Durable workflow retries with backoff (Temporal semantics), idempotency keys on all tool calls |
| Runaway loops / cost attacks | Cost manager with real-time budgets + kill switch; 27% of enterprises in 2026 had *no* real-time runaway stop ([VentureBeat](https://venturebeat.com/ai/agentic-orchestration-enterprise-ai-organizations-have-a-deployment-problem-not-a-platform-problem-and-most-are-calling-chatbots-agents)) — this is a differentiator |
| Prompt injection / tool poisoning | Input/output guardrails at runtime boundary, tool response sandboxing, provenance tagging of untrusted content |
| Compromised agent / credential theft | Short-lived attenuated credentials, capability intersection along delegation chain, instant revocation propagation |
| Policy denial / permission denial | First-class workflow states (pause, escalate, replan), not exceptions |
| Conflicting agents | Task-level locking/leases via the orchestrator; goal-conflict surfaced to AGRL |
| Crash mid-execution | Durable execution: resume from last checkpoint, never repay completed LLM steps |
| Governance rail unreachable | **Fail closed** for high-risk; queue-and-retry for low-risk |

## 6. Multi-tenancy shape

**[Recommendation]** Organization → Tenant → {users, agents, tools, policies,
knowledge, workflows, budgets, audit}. Enforcement: row-level tenant scoping
in Postgres (RLS or application-enforced tenant_id on every query),
per-tenant policy bundles, per-tenant credential vaults, per-tenant cost
budgets, data-residency routing constraints in the router. Vector/memory
namespaces per tenant.

## 7. Overengineering risks (aggressive cut list)

**[Opinion]**
1. **Do not build a workflow engine.** Integrate Temporal semantics
   (or Hatchet/Restate-class) behind a `WorkflowBackend` interface.
2. **Do not build a policy language.** Embed OPA/Rego (or Cedar) as the PDP.
3. **Do not build an agent framework.** The ACP *hosts references to* agents
   built in LangGraph/Strands/whatever; the MVP ships one thin reference
   runtime only.
4. **Do not build a vector database.** pgvector first; dedicated engine later.
5. **Do not build a message bus.** Outbox + Redis Streams/NATS for MVP;
   Kafka only when throughput proves it.
6. **Do not microservice the MVP.** Modular monolith; split on proven
   seams (scale, security boundary, independent deployability).
7. **Do not event-source the registries.** Current-state + audit events.
8. **Do not build your own model gateway.** Adapter interface; existing
   gateways (OpenRouter-class) are valid backends.

## 8. MVP layering (maps to `technology-evaluation.md` and build phasing)

**MVP (modular monolith):** Agent Registry → Task API → Planner (rule-based
+ LLM strategies behind interface) → Router (capability/cost/policy scoring)
→ Tool Registry → Policy Engine (embedded OPA or minimal Rego-compatible
rules behind interface) → Risk Engine (deterministic scorer, hybrid-ready)
→ Approval/HITL state machine → Workflow execution (built-in Postgres-backed
durable runner for MVP; Temporal-compatible interface) → OpenTelemetry
observability → append-only audit ledger.

**V1:** Temporal as the workflow backend, multi-agent orchestration,
knowledge layer (RAG/GraphRAG), evaluation engine, cost budgets + kill
switch, multi-tenancy hardening, dashboard.
**V2:** Learning/feedback loops inside governance bounds, advanced routing
(learned), GraphRAG, cross-tenant (org-level) governance, edge/offline PEPs.
**V3:** Autonomous optimization, fleet-scale self-management, marketplace of
agents/tools — only after V1 evidence exists.
