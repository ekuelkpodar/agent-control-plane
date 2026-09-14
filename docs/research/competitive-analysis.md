# Agent Control Plane — Competitive / Capability Analysis

**Date:** 2026-09-14 · **Stream:** Market / competitive / product strategy (1 of 3) · **Type:** Research only, no code.

**Claim labels:** `[ESTABLISHED FACT]` · `[INDUSTRY CONVENTION]` · `[ARCHITECTURAL RECOMMENDATION]` · `[HYPOTHESIS]` · `[OPINION]`

Method: for each system, what it *actually* solves (grounded in its real architecture/API, per official docs) and what it explicitly does NOT solve relative to a governed enterprise control plane. Marketing claims ignored.

---

## 1. Capability map: what each system solves vs. what it leaves to a control plane

| System | Actually solves | Does NOT solve (gaps an ACP must fill) |
|---|---|---|
| **OpenAI agent infra** (Agents SDK, Responses API, **Agents API beta 2026-09-10**) | Production single/multi-agent harness: run loop, tool dispatch, handoffs, guardrail hooks, session persistence, tracing spans, HITL pauses. Agents API adds managed session orchestration, context compaction, recovery. | No fleet registry/discovery; guardrails are developer callbacks, not org-wide policy; no scheduler (capability/cost routing); no agent identity issuance; tracing is observe-only. |
| **Anthropic Claude / Code SDK** (permission system; **computer/browser toolsets GA Aug 2026**) | Most complete *permission-gated harness*: least-privilege `allowedTools`/`disallowedTools`, hard deny surviving bypass mode, hook interception, subagent isolation, first-class computer/browser use. | Permissions are per-process config, not enterprise policy; no fleet scheduler/discovery; hooks run in-process (bypassable); computer-use guardrails "aren't absolute" per Anthropic. |
| **Google ADK** | Typed workflow orchestration, sessions/state/artifacts, MCP + A2A interop, Model Armor guardrail service, documented K8s (GKE) deployment path. | Framework, not control plane: no registry, no fleet policy, no cost/latency-aware routing; callbacks are per-agent code. |
| **Microsoft Agent Framework 1.0** (GA Apr 2026; **AutoGen + Semantic Kernel retired to maintenance**) | Unified .NET/Python stack: Agent Harness (planning, compaction, approvals), AgentWorkflow graphs with checkpointing + HITL, native OTel, MCP/A2A adapters. | No fleet registry with signed identities; no admission control on deployments; governance is Azure-coupled (Foundry guardrails, Purview); no agent-aware scheduler. |
| **LangChain** (1.0 alpha Sept 2026) | Fastest path to a governed-*ish single* agent: prebuilt ReAct, middleware (HITL approval, PII redaction), tight trace→eval→deploy loop via LangSmith. | Middleware is per-agent code, not fleet policy; no registry/discovery/identity; "Govern" = eval iteration, not runtime governance (no kill-switch, no budgets). |
| **LangGraph** | Durable, debuggable, resumable agent workflows: checkpointers, interrupts for HITL, time-travel. Closest agent-native workflow engine. | Library, not service (you operate it); tool calls aren't transactional (retry can double-execute); no policy/admission/identity/scheduling. |
| **CrewAI** | Opinionated multi-agent *team* modeling (roles, delegation, manager hierarchy) + event-driven flows; enterprise AMP offering. | Framework-level: no registry, fleet policy, identity, or scheduler; durability story thinner than LangGraph/Temporal. |
| **LlamaIndex** | Retrieval-grounded agents: agents over indexes/retrievers, query planning, object retrieval over tools. | Not a general agent runtime: no durable execution, no HITL primitives, no fleet management, no policy. |
| **OpenAI Swarm** (archived) | Proved handoffs are sufficient as the multi-agent coordination primitive; proved the framework can be trivially thin. | Everything: no persistence, auth, policy, observability, multi-tenancy. **Minimal counter-example** — every ACP component must justify itself *above* Swarm's two primitives. |
| **MCP** (open standard) | Tool/data interoperability: build once, any harness uses it; schema re-discovery. | No orchestration, no authorization policy (OAuth = identity, not *whether agent X may call tool Y*), no registry/trust (any server can claim any name), no observability. |
| **A2A** (Linux Foundation, v1.0) | Agent-to-agent interop: Agent Cards, task lifecycle, 150+ orgs. | Cards are self-asserted (no signed identity authority yet); no policy layer. |
| **Temporal** | Durable execution commoditized: event-sourced history, replay, retries, signals (HITL), exactly-once ops, long-running workflows. | Nothing agent-specific: no model routing, no tool negotiation, no agent identity/discovery, no policy on *what the agent may do* — it will durably execute a malicious plan as faithfully as a benign one. |
| **Kubernetes** (analogy source) | Control plane for containers: API choke point, declarative desired state, reconciliation loops, RBAC, admission, secrets. | Workloads are deterministic; K8s never had to solve non-determinism, semantic scheduling, or runtime per-action authorization (see §3). |
| **Enterprise orchestration** (Sierra, Moveworks/ServiceNow, Cognigy/NiCE) | Proves enterprises *pay* for governed outcomes (Sierra per-resolution pricing + trust layer: SOC 2, ISO 42001, HIPAA, audit trails); orchestrator + policy-validator split (Moveworks); cost/latency model routing as platform concern (Cognigy). | Closed single-vendor vertical SaaS for service/support — none offers a vendor-neutral control plane for *arbitrary* agents with portable policy. |
| **Observability/eval** (LangSmith, Arize AX/Phoenix, Langfuse, Braintrust, MLflow) | Trace capture, cost/latency attribution, offline + online evals, trajectory scoring, human review queues. | **Observe-only.** None governs: no admission control, no runtime policy enforcement, no identity, no kill-switch, no budget enforcement. Consume their signals; don't rebuild them. |
| **Security/governance** (HiddenLayer, Lakera/Check Point, CalypsoAI, PromptArmor) | Threat *detection* at prompt/tool boundary: injection, jailbreak, PII leakage, multi-step attack chains; HiddenLayer's agent-harness hooks are the closest to an enforcement point. | Detection ≠ governance: no agent deployment policy, no identity, no scheduling; policies are vendor-proprietary, not portable policy-as-code. Treat as enforcement *plugins*. |
| **Computer-use environments** (Anthropic GA toolsets; OpenAI ChatGPT Work) | Last-mile action layer: connectors → browser → screen fallback; emerging least-privilege escalation consensus. | An *actuator*, not a governor: every action needs an authorization decision made *above* it; screen-level access is the highest-risk actuator. |
| **Coding-agent architectures** (Devin/Cognition, OpenHands, SWE-agent) | Three reusable patterns: **sandbox-per-run** as default execution boundary; **risk-tiered confirmations** (OpenHands confirmation policy + risk analyzer); **event stream as source of truth** (OpenHands). | Single-domain, single-run scope; no fleet management, no cross-run policy, no identity federation. |

Sources: [OpenAI release notes](http://openai.com/products/release-notes/) · [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/) · [Anthropic releasebot (Aug 2026)](https://releasebot.io/updates/anthropic/claude-developer-platform) · [Google Cloud ADK](https://docs.cloud.google.com/agent-builder/agent-development-kit/overview) · [Microsoft Agent Framework GA](https://devblogs.microsoft.com/agent-framework/microsoft-agent-framework-version-1-0/) · [AutoGen retirement](https://venturebeat.com/ai/microsoft-retires-autogen-and-debuts-agent-framework-to-unify-and-govern) · [LangChain 1.0 alpha](https://www.langchain.com/blog/langchain-langchain-1-0-alpha-releases) · [LangGraph HITL](https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/) · [CrewAI](https://github.com/crewAIInc/crewai) · [LlamaIndex agents](https://developers.llamaindex.ai/python/framework/module_guides/deploying/agents/) · [Swarm](https://github.com/openai/swarm) · [MCP threat model](https://github.com/he8um/mcp-skills) · [Temporal architecture](https://github.com/temporalio/temporal/blob/main/docs/architecture/README.md) · [HiddenLayer PR](https://www.prnewswire.com/news-releases/hiddenlayer-unveils-new-agentic-runtime-security-capabilities-for-securing-autonomous-ai-execution-302721517.html) · [HiddenLayer harness security](https://www.morningstar.com/news/pr-newswire/20260803da17762/hiddenlayer-unveils-agent-harness-security-to-protect-ai-powered-software-development-at-runtime) · [Arize 2026 eval-platform comparison](https://arize.com/blog/best-ai-observability-tools-for-autonomous-agents-in-2026/)

**The one-line verdict across all 18 systems** `[OPINION]`: harnesses are commoditized (five+ production run loops), protocols are commoditized (MCP for tools, A2A for interop), durability is commoditized (Temporal), telemetry is commoditized (OTel) — **the gap is fleet-level governance: no system offers neutral, fleet-wide, externally-enforced policy over a multi-vendor agent estate.**

---

## 2. Kubernetes comparison: where the analogy holds and where it breaks

| K8s concept | Agent mapping | Verdict |
|---|---|---|
| API Server → Control-plane API | **HOLDS.** The single choke point transfers directly: every deployment, tool registration, invocation, and policy decision goes through one authenticated API. Copy the shape: stateless API server, all state in etcd-like storage. | `[ARCHITECTURAL RECOMMENDATION]` |
| etcd → Agent state store | **HOLDS (with a twist).** You need strongly-consistent desired state (agent definitions, policies, registry) + an append-only event log (runs, tool calls, approvals). The twist: run history is high-volume telemetry (belongs in a trace store), control state belongs in etcd-like storage. Don't put spans in etcd. | `[ARCHITECTURAL RECOMMENDATION]` |
| RBAC → Agent permissions | **HOLDS in structure, BREAKS in granularity.** K8s RBAC answers "can subject S do verb V on resource R." Agents need that *plus*: "can agent A call tool T with args matching schema S on data classified C, spending budget B, in task context K?" Static RBAC is necessary but insufficient — add ABAC/OPA-style policy *and* runtime approval gates. | `[ARCHITECTURAL RECOMMENDATION]` |
| Admission Controller → Policy engine | **HOLDS — the most transferable idea.** Mutating admission (inject defaults: timeouts, budgets, tracing) + validating admission (deny specs with unapproved tools, missing owners, no data classification) maps 1:1. OPA Gatekeeper/Kyverno are reusable here. The gap: K8s admission is *deploy-time*; agents also need *run-time* per-action authorization, which K8s never needed because containers don't make autonomous decisions. | `[ARCHITECTURAL RECOMMENDATION]` |
| Secrets → Agent credentials | **HOLDS.** Same problem, same solution: never in the spec, encrypted at rest, injected at runtime, short-lived tokens, external secret operators (Vault). Agent twist: credential scoping *per task* (a refund agent shouldn't hold the production DB password). | `[INDUSTRY CONVENTION]` |
| Controller → Agent controller | **HOLDS in pattern, differs in what's reconciled.** K8s controllers reconcile *infrastructure* state (N pods running). Agent controllers reconcile *behavioral* state: is it stuck/looping/degrading per evals, budget burn, drift from approved behavior — with auto-quarantine/pause/rollback as actuators. Level-triggered reconciliation is the right pattern; the signals are new. | `[ARCHITECTURAL RECOMMENDATION]` |
| Observability → Agent observability | **HOLDS for plumbing, BREAKS for semantics.** OTel metrics/logs/traces transfer directly (the ecosystem already emits OTel). What breaks: K8s monitors *system* health; agent observability must monitor *decision* health (trajectory correctness, tool misuse, goal drift, cost per outcome). Consume LangSmith/Arize-style eval signals; don't rebuild dashboards. | `[ARCHITECTURAL RECOMMENDATION]` |
| Events → Agent events | **HOLDS.** K8s Events are the precedent for the agent-action audit log: every tool call, approval, handoff, policy decision as structured, attributable events — the compliance substrate. | `[INDUSTRY CONVENTION]` |

**Where it breaks — do not force the analogy:**

- **Pod → Agent runtime: STRAINS.** A Pod is a dumb, deterministic workload: same image + same spec = same behavior, restartable, interchangeable. An agent is non-deterministic and semantically stateful: the "same" agent with different history, memory, or model version behaves differently. Restarting an agent mid-task is a *recovery* problem (context reconstruction, idempotency of partial effects), not `kubectl delete pod`.
- **Deployment → Agent deployment/version: STRAINS.** K8s versions immutable images; rollouts are deterministic and rollback is trivial. Agent versions bundle prompts, model versions, tool sets, memory contents, and policy — and "rollback" doesn't undo actions already taken in the world (emails sent, money moved). Versioning must cover the *behavioral* contract (evals as acceptance tests per version); rollout needs canary-by-outcome, not canary-by-traffic.
- **Service → Tool/service: PARTIALLY HOLDS.** MCP is becoming the "Service" abstraction (standard discovery, schema contracts). What breaks: K8s Service routing is content-blind; agent tool routing needs semantic, policy-aware routing (which tool, with what args, under whose authority, at what cost). MCP gives the interface; the control plane supplies registry + policy + routing.
- **Scheduler → Agent router: BREAKS (the most important break).** kube-scheduler solves *bin-packing* (place this Pod on a node with spare CPU/RAM). An agent router solves a *different* optimization: choose agent/model/tool-chain by capability match, expected quality, latency SLO, cost budget, data residency, and risk tier — with the choice itself sometimes requiring a model call. **Do not build a "kube-scheduler for agents" — build a capability/cost/risk-aware router.** `[ARCHITECTURAL RECOMMENDATION]`
- **Cluster → Agent ecosystem: HOLDS loosely.** Useful as a trust-boundary concept, but agent estates are inherently *federated* (your agents, vendor agents via A2A, employee-used copilots). K8s federation is famously weak; the ACP needs federation as a first-class design (signed Agent Cards, cross-estate trust), not an afterthought.

**One-line summary:** `[OPINION]` **K8s got right:** single API choke point, declarative desired state, reconciliation loops, deploy-time admission, RBAC, secret hygiene, event audit. **K8s never had to solve:** non-deterministic workloads, semantic (not resource) scheduling, runtime per-action authorization, behavioral versioning, federated identity — **which is exactly the differentiated layer.**

---

## 3. Critical review: what exists, what to delegate, what's actually new

### 3a. Already commodities — do NOT rebuild

1. **Agent harness (the run loop).** OpenAI Agents SDK, Claude Agent SDK, LangGraph, Microsoft Agent Framework, Google ADK — increasingly as *managed* services (OpenAI Agents API beta Sept 2026). `[ESTABLISHED FACT]` → **Delegate.**
2. **Tool interoperability.** MCP: discovery, schemas, invocation; native in every major harness. `[ESTABLISHED FACT]` → **Delegate entirely.** Build registry/policy/audit *around* MCP, never a competing tool protocol.
3. **Agent-to-agent interop.** A2A (Linux Foundation v1.0): Agent Cards, task lifecycle, 150+ orgs. `[ESTABLISHED FACT]` → **Delegate + extend** (identity signing/verification).
4. **Durable execution.** Temporal (event-sourced, signals, exactly-once ops) or LangGraph checkpointing for lighter needs. `[ESTABLISHED FACT]` → **Delegate.** Never rebuild event sourcing, replay, timers, or retries.
5. **Tracing/telemetry plumbing.** OpenTelemetry + OpenInference semantic conventions. `[INDUSTRY CONVENTION]` → **Delegate.** Ingest standard spans; no agent-specific trace protocol.
6. **Trace storage, evals, dashboards.** LangSmith / Arize AX / Phoenix / Langfuse / Braintrust / MLflow. `[ESTABLISHED FACT]` → **Delegate** (buy or self-host OSS); consume their signals in controller loops.
7. **Threat detection at the prompt boundary.** HiddenLayer, Lakera Guard, PromptArmor-class injection/PII detection. `[ESTABLISHED FACT]` → **Delegate as enforcement plugins** behind a standard interface.
8. **Policy language & deploy-time admission.** OPA/Rego, Gatekeeper, Kyverno — proven at K8s scale. `[INDUSTRY CONVENTION]` → **Reuse.**
9. **Secrets, sandboxing, model gateway.** K8s Secrets + Vault, containers/microVMs, LiteLLM-class gateways. `[INDUSTRY CONVENTION]` → **Reuse.**
10. **Sandboxed execution substrate.** Devin VMs, OpenHands containers, OpenAI sandbox agents, vetto-style Landlock/seccomp. `[ESTABLISHED FACT]` → **Reuse** the substrate; the control plane decides *which* sandbox tier a task gets.

### 3b. The minimum differentiated layer — what is actually new

Nothing above governs a *fleet*. The new layer is small but load-bearing — five components, in priority order:

1. **Agent registry with verifiable identity.** A2A Agent Cards are self-asserted; the control plane adds issuance/signing of agent identities, card verification, ownership/attestation metadata, version lineage. The "image registry + signing" (Sigstore equivalent) for agents. `[ARCHITECTURAL RECOMMENDATION]`
2. **Unified policy engine: deploy-time admission + runtime authorization.** OPA-style policy-as-code for specs, *plus* a per-action authorization service the harnesses call out to (Claude's `canUseTool`, OpenAI guardrails, MAF middleware become *clients* of this, not the policy itself): allow/deny/escalate-to-human with budgets, data-classification checks, separation-of-duties, risk-tiered confirmations (OpenHands' confirmation-policy pattern, centralized). **This is the single biggest gap**: every framework implements permissions *in-process and per-agent*; none offers fleet-wide, auditable, externally-enforced policy. `[ARCHITECTURAL RECOMMENDATION]`
3. **Capability/cost/risk-aware router (the anti-scheduler).** Route tasks by capability match, quality history, latency SLO, cost budget, data residency, and risk tier — with routing decisions logged as auditable events. No neutral version exists (Cognigy's is walled-garden). `[ARCHITECTURAL RECOMMENDATION]`
4. **Behavioral controller loops.** K8s-style reconciliation over behavioral signals: stuck/loop detection (OpenHands proved the pattern), eval/trajectory drift (consume LangSmith/Arize signals), budget burn, auto-quarantine/pause/rollback, approval escalation on anomaly. `[ARCHITECTURAL RECOMMENDATION]`
5. **Immutable agent-action audit ledger.** Every deployment, policy decision, tool call, approval, handoff, and router decision as attributable, tamper-evident events — the compliance substrate. Build on the event-sourced pattern; keep separate from high-volume trace storage. `[ARCHITECTURAL RECOMMENDATION]`

**What this layer is NOT:** not another harness, not another tool protocol, not another trace dashboard, not another prompt filter. If a proposed component duplicates MCP/A2A/OTel/Temporal/OPA, cut it. `[OPINION]`

### 3c. Build-vs-delegate map

| Concern | Verdict | Delegate to |
|---|---|---|
| Agent run loop, tool dispatch, compaction | DELEGATE | OpenAI/Claude/LangGraph/MAF/ADK harnesses; managed Agents APIs |
| Tool interface + discovery | DELEGATE | MCP (all of it) |
| Agent-to-agent interop | DELEGATE + EXTEND | A2A; add identity signing/verification |
| Durable execution, retries, HITL signals | DELEGATE | Temporal (heavy) / LangGraph runtime (light) |
| Trace/metric/log plumbing | DELEGATE | OpenTelemetry + OpenInference |
| Trace storage, evals, trajectory scoring | DELEGATE (buy/OSS) | LangSmith / Arize / Langfuse / Braintrust / MLflow |
| Prompt-injection / PII detection | DELEGATE (plugin) | HiddenLayer / Lakera / PromptArmor-class |
| Deploy-time policy (spec admission) | REUSE | OPA / Gatekeeper / Kyverno |
| Secrets, sandboxing, model gateway | REUSE | K8s/Vault, containers/microVMs, LiteLLM-class gateway |
| **Agent identity + registry** | **BUILD** | *(the gap)* |
| **Fleet policy engine (admit + authorize)** | **BUILD** | *(the gap; harnesses become clients)* |
| **Capability/cost/risk router** | **BUILD** | *(the gap)* |
| **Behavioral controllers** | **BUILD** | *(the gap; consume eval/trace signals)* |
| **Action audit ledger** | **BUILD** | *(the gap)* |

### 3d. Honest caveats

- **Hyperscalers are converging from above.** OpenAI's Agents API (Sept 2026) sells session orchestration/recovery/compaction as a managed service; Microsoft ties governance to Foundry; Anthropic is asserting harness control (OpenClaw restriction). A neutral control plane must win on *multi-vendor neutrality* — the one thing none of them can credibly offer. `[OPINION]`
- **A2A identity is still immature.** Signed Agent Cards are in progress; building a registry on a moving spec means tracking it. `[ESTABLISHED FACT]`
- **Runtime authorization adds latency to every tool call.** The policy engine must be local/cached with async audit, or agents will route around it. **This is the hardest engineering constraint in the whole proposal.** `[ARCHITECTURAL RECOMMENDATION]`
- **Non-determinism limits "deployment" semantics.** Behavioral versioning via eval-gates is probabilistic; canary/rollback will be *statistical*, never K8s-deterministic. `[OPINION]`
- **Stale-info flags:** CrewAI AMP enterprise details are thin in public sources; CalypsoAI's current surface verified only via a 2026 roundup; several framework docs were crawled 1–6 months ago — re-verify before architecture sign-off. The OpenAI Agents API (days old) and Anthropic computer/browser toolsets (Aug 2026) are the fastest-moving pieces.
