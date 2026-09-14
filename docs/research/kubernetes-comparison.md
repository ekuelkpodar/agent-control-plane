# Agent Control Plane — Kubernetes Comparison

Research date: 2026-09-14. Markers: **[Fact]**, **[Convention]**,
**[Recommendation]**, **[Hypothesis]**, **[Opinion]**.

Kubernetes reference: the control plane = kube-apiserver (API front end),
etcd (consistent state store), kube-scheduler (placement), kube-controller-
manager (reconciliation loops), cloud-controller-manager (provider
integration); nodes run kubelet + container runtime + kube-proxy.
([K8s components](https://kubernetes.io/docs/concepts/overview/components/?ref=seongjin.me))

## 1. The mapping

| Kubernetes | Agent Control Plane | Fit | Notes |
|---|---|---|---|
| Cluster | Agent ecosystem / tenant scope | ●○○ Loose | A K8s cluster is a failure/upgrade domain with a single etcd; an ACP "ecosystem" spans providers, clouds, SaaS — no single state store or blast radius. Useful only as "the thing being managed." |
| Pod | Agent runtime (one agent execution) | ●●○ Partial | A pod is deterministic and replaceable; an agent run is stateful, non-deterministic, and has *authority*. Restart ≠ resume for agents without durable execution. |
| Deployment | Agent deployment / version rollout | ●●● Strong | Desired-state versioning, promotion, rollback, canary of agent definitions maps almost 1:1. Steal this pattern wholesale. |
| Service | Tool / MCP server endpoint | ●●○ Partial | K8s Services are stable network endpoints; ACP tools need *risk classification, schema, auth, cost, and policy* — a richer catalog object than an endpoint. |
| Scheduler | Agent router | ●●○ Partial | Both do placement under constraints. But K8s schedules on *resources* (CPU/RAM/affinity); the ACP routes on *capabilities, quality, latency, cost, risk, policy, data residency, historical performance*. The objective function is fundamentally different. |
| Controller | Agent/task controllers (reconciliation loops) | ●●● Strong | The reconciliation pattern — watch desired state, act to converge, report status — transfers directly to agent lifecycle, approval expiry, budget enforcement. |
| API Server | Control-plane API | ●●● Strong | Single front door, declarative resources, admission chain, RBAC, audit. The closest true analogue. Follow K8s API conventions (verbs, status subresources, watch semantics). |
| RBAC | Agent permission engine | ●●○ Partial | K8s RBAC binds *static* subjects to verbs on resources. Agents need *dynamic, attenuated, delegating* authority (composite principals, capability intersection, expiry). RBAC is necessary but insufficient — ABAC + delegation chains required. |
| Admission Controller | Policy engine (PDP) | ●●● Strong | ValidatingAdmissionWebhook is the direct precedent: intercept a proposed state change, evaluate policy, allow/deny/mutate. The ACP generalizes this from "object writes" to "planned agent actions." |
| Secrets | Agent credential broker | ●●○ Partial | K8s mounts secrets into pods; the ACP must *never* give agents ambient credentials — it brokers short-lived, scoped, attenuated tokens per action. Same problem, stricter answer. |
| Events | Agent/task events | ●●● Strong | Append-only event stream as the coordination substrate; same role as K8s events, but ACP events carry decision provenance (which policy, which risk score, who approved). |
| Observability | Agent observability | ●●○ Partial | Metrics/traces/logs transfer; but ACP traces must explain *decisions* (why this agent, why this model), not just latency. |
| etcd | PostgreSQL (system of record) | ●●○ Partial | etcd is a CP key-value store for small, hot cluster state. ACP state (registries, approvals, audit) is relational, larger, and query-heavy — Postgres, not etcd. Don't copy the technology, copy the *role*: single strongly-consistent source of truth. |
| kubelet | Agent runtime agent | ●○○ Loose | The kubelet is a dumb reconciler ("run this pod spec"). An agent runtime is *intelligent and semi-autonomous* — it plans, calls tools, and must be governed. The trust relationship inverts: kubelet is trusted infrastructure; the agent runtime is a governed, partially-untrusted principal. |
| CRDs / Operators | Agent/tool/policy definitions | ●●● Strong | Declarative custom resources + operator-style controllers is exactly the right extensibility model for agent/tool/policy types. |

## 2. Where the analogy breaks down — the five fundamental differences

**[Opinion]** These are the reasons "Kubernetes for agents" is a useful
*intuition pump* but a dangerous *blueprint*:

1. **Deterministic vs. non-deterministic workloads.** Kubernetes reconciles
   *declarative desired state* for deterministic containers: "3 replicas of
   image X" converges. An agent's "desired state" is a *goal in natural
   language*; the path is non-deterministic and the outcome is probabilistic.
   Reconciliation loops still work for lifecycle management, but they cannot
   converge an agent's reasoning — only govern its boundaries.

2. **Authority is the product, not the plumbing.** In Kubernetes, identity and
   RBAC protect the *infrastructure*. In an ACP, identity, delegation, and
   attenuated authority *are the core value proposition* — the thing
   enterprises buy. The arXiv five-plane paper's central claim is that
   existing stacks authorize "atomic principals" at request time, while
   agents require adjudication against *composite, delegating, attenuating
   principals* with plan awareness.
   ([arXiv 2606.12320](https://arxiv.org/html/2606.12320v1))

3. **Cost is a first-class failure mode.** A runaway pod wastes CPU; a
   runaway agent burns money (tokens, API calls, SaaS actions) and takes
   *irreversible external actions* (send the email, book the shipment, move
   the funds). Kubernetes has no analogue of the cost manager + kill switch;
   27% of 2026 enterprises had no real-time runaway stop
   ([VentureBeat](https://venturebeat.com/ai/agentic-orchestration-enterprise-ai-organizations-have-a-deployment-problem-not-a-platform-problem-and-most-are-calling-chatbots-agents)).

4. **The adversary is inside the workload.** Kubernetes' threat model is
   mostly about *who can touch the cluster*. The ACP's threat model includes
   *the workload itself*: prompt injection, tool poisoning, compromised or
   misaligned agents, data exfiltration through legitimate tools. Admission
   control must evaluate *intent and plan*, not just identity and resource
   shape.

5. **No single substrate.** A K8s cluster owns its nodes. An ACP governs
   agents executing across provider APIs, SaaS tools, browsers, edge devices,
   and other clouds — substrates it does not own and cannot fully observe.
   Enforcement must therefore be *layered and fail-closed* (control-plane
   admission + runtime PEPs + tool proxies), never assumed from ownership.

## 3. What to steal from Kubernetes (concrete)

**[Recommendation]**
- **Declarative API with spec/status separation**, standard verbs, and watch
  semantics for agent/task/policy resources.
- **Admission-chain pattern** (validating/mutating webhooks) generalized to
  plan evaluation: policy → risk → approval as chained admission stages.
- **Controller/reconciliation pattern** for lifecycle (agent versions,
  approval expiry, budget enforcement, health).
- **CRD/operator-style extensibility** for new agent, tool, and policy kinds.
- **Design principles**: declarative APIs, transparent control plane (no
  hidden internal APIs), operation cost proportional to objects touched,
  status reconstructable by observation, avoid cluster-wide atomic invariants
  ([K8s principles](https://github.com/kubernetes/design-proposals-archive/blob/main/architecture/principles.md)).
- **Deployment/rollout semantics** (canary, rollback) for agent versions.

## 4. What NOT to copy

**[Recommendation]**
- **etcd as the state store** — wrong data model; use Postgres.
- **The scheduler's objective function** — bin-packing resources ≠ routing
  under capability/cost/risk/policy.
- **Pod-as-cattle disposability** — agent executions are stateful and
  evidence-bearing; "just restart it" destroys audit continuity. Durable
  execution with resume-from-checkpoint replaces restart semantics.
- **Trust in the node agent** — kubelet is trusted; the agent runtime is a
  governed principal with attenuated credentials and local PEPs.

## 5. Verdict on the analogy

**[Hypothesis]** "Kubernetes for AI agents" is ~60% useful: it correctly
predicts the *shape* of the solution (declarative API, admission control,
reconciliation, registry, audit) and is the fastest way to explain the ACP
to infrastructure buyers. It fails exactly where agents differ from
containers: non-determinism, delegated authority as the product, cost as a
failure mode, adversarial workloads, and unowned substrates. Use it for
positioning and API design; do not let it dictate the trust model, the state
store, or the scheduler.
