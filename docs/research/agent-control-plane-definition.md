# Agent Control Plane — Definition & Category Analysis

Research date: 2026-09-14. Status markers used throughout: **[Fact]**, **[Convention]**,
**[Recommendation]**, **[Hypothesis]**, **[Opinion]**.

## 1. Working definition

**[Recommendation]** An *Agent Control Plane* (ACP) is the governed, model- and
tool-independent management layer that registers, authorizes, schedules,
orchestrates, observes, evaluates, and audits fleets of autonomous AI agents —
separating *decisions about agency* (who may act, with what authority, at what
risk and cost, under which policy, with what human oversight) from the
*execution of agency itself* (the agent runtime, model calls, and tool
invocations).

In one sentence: the control plane determines **WHO / WHAT / WHEN / WHY / HOW /
WITH WHICH MODEL / WITH WHICH TOOLS / WITH WHICH PERMISSIONS / AT WHAT RISK /
AT WHAT COST / UNDER WHICH POLICY / WITH WHAT HUMAN OVERSIGHT** — and records
the answers immutably after the fact.

## 2. Is it a genuinely new category?

**[Fact]** By 2026 the term has escaped metaphor status and entered analyst
vocabulary. IDC published a February 2026 Market Perspective explicitly titled
around the "Agentic AI Control Plane," with IDC projecting up to 100M agents
running on Twilio alone by 2029 and describing a "governance firewall" role for
agentic communication. ([IDC/Twilio report](https://twilio.com/en-us/lp/idc-agenticai-marketperspective-2026);
[PDF](https://www.twilio.com/content/dam/twilio-com/global/en/other/landing-pages/h-l/idc-agentic-ai-market-perspective-2026/idc-agentic-ai-report-2026.pdf))

**[Fact]** VentureBeat's Q2 2026 enterprise research found a majority (51–53%)
of enterprises expect a **hybrid control plane** — provider-native plus external
orchestration — by end of 2026, while only ~6% would hand control to a
provider-managed service; vendor lock-in (35%) and security/permissioning limits
(37%) are the top fears of provider-resident control.
([orchestration study](https://venturebeat.com/ai/agentic-orchestration-enterprise-ai-organizations-have-a-deployment-problem-not-a-platform-problem-and-most-are-calling-chatbots-agents);
[cost/governance study](https://venturebeat.com/resources/agentic-orchestration-enterprise-ai-organizations-know-how-to-govern-agents-but-still-cant-meter-what-they-cost))

**[Fact]** All three major cloud providers announced **agent registries in
April 2026** — the most basic control-plane primitive — per SiliconANGLE's
Google Cloud Next 2026 coverage.
([source](https://siliconangle.com/2026/04/30/agentic-control-plane-battle-enterprise-ai-googlecloudnext/))

**[Hypothesis]** The category is real but *composite*: almost every ACP
sub-capability already exists somewhere (see §4). The genuinely new element is
the **composition** — a single authoritative layer that binds identity,
authority, delegation, plan-awareness, execution, and evidence for
*non-deterministic, stateful, tool-using principals*. This matches the arXiv
2026 five-plane runtime-governance paper's core claim: existing stacks govern
"request-time access against atomic principals," while production agents require
"plan-aware, stateful, attenuated, richly-output adjudication against composite
principals."
([arXiv 2606.12320](https://arxiv.org/html/2606.12320v1))

**[Opinion]** Treat "Agent Control Plane" as a new *category* but not a new
*primitive*. Positioning should stress the integration of governance with
execution, not invent jargon for things Kubernetes/Temporal/OPA already do.

## 3. How it differs from adjacent things

| Adjacent concept | What it solves | What the ACP adds that it doesn't |
|---|---|---|
| **AI agent framework** (LangChain, CrewAI, AutoGen, Semantic Kernel) | Developer ergonomics for building a single agent's reasoning loop | Lifecycle, multi-tenancy, policy, audit, cost, fleet management across agents |
| **Orchestration framework** (LangGraph, Temporal) | Durable, stateful execution of multi-step workflows | Governance of *autonomous* decisions: routing, risk, approvals, delegation chains |
| **LLM gateway** | Model routing, key management, rate limits, caching | Agent identity, tool authority, task semantics, human-in-the-loop |
| **MCP server** | Standardized tool/capability exposure to models | Policy over tool use, risk scoring, approval gates, cost attribution |
| **API gateway** | Request routing, authn/authz at the edge, throttling | Plan-aware adjudication, composite principals, execution evidence |
| **Workflow engine** | Deterministic durable execution (DAGs, sagas) | Non-deterministic planning, agent selection, evaluation, learning loops |
| **Observability platform** | Logs/metrics/traces of what happened | Decision provenance: *why* an agent was chosen, *which policy* fired, *who* approved |
| **AI platform** (Foundry, Vertex, Bedrock) | Hosted models, data, eval tooling, deployment | Vendor-neutral governance; the 2026 enterprise data says buyers explicitly fear provider-resident control (lock-in 35%, permissioning limits 37%) |
| **Agent runtime** | Executes the agent loop (the "kubelet" of agents) | Everything above the loop: registry, admission, routing, audit |

**[Convention]** AWS's Prescriptive Guidance for agentic AI in the enterprise
already structures the space into layers (applications → agents → cross-cutting
governance/observability/security/discoverability), which corroborates a
layered ACP reading.
([AWS guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/govern-architect-agentic-ai/enterprise-architecture.html))

**[Fact]** At least two independent open-source projects in 2026 already brand
themselves as agent control planes with the same separation of concerns:
- **Azure Agents Control Plane** (Microsoft): "centralized governance,
  observability, identity, and compliance — regardless of agent execution
  location," with Microsoft Entra agent identities and API-first MCP
  architecture.
  ([repo](https://github.com/microsoft/azure-agents-control-plane))
- **AgentOps-style "AgentOps Control Plane"** (saralabiswal): control plane
  owns execution state, cost, quality, trace exposure, outcome accounting;
  agents do domain reasoning; provider adapters behind one interface.
  ([repo](https://github.com/saralabiswal/agentops-control-plane))
- **mpalmer79/agent-control**: "enterprise operations platform" — registry,
  deployments, approvals, evaluations, cost, immutable audit; explicitly "not a
  chatbot, an AI wrapper, or a generic dashboard."
  ([repo](https://github.com/mpalmer79/agent-control))

**[Recommendation]** These corroborate the scope boundary: the ACP **owns
contracts and coordination, not execution**. The OSA-AI "Enterprise Agentic
Platform" paper phrases it best: the control plane "governs how [planes]
compose; it does not execute their work. This distinction is what keeps the
control plane small and authoritative rather than sprawling and unaccountable."
([PDF](https://github.com/osa-ai-org/enterprise-ai/raw/refs/heads/main/docs/Enterprise-Agentic-AI-Platform-Strategy.pdf))

## 4. Which parts already exist (critical review input)

**[Fact]** Component-by-component, the buy-vs-build ledger looks like this:

| Component | Mature existing solution | Verdict |
|---|---|---|
| Durable workflow execution | Temporal (industry standard, polyglot SDKs; ~9.1T lifetime executions, ~1.86T from AI-native companies per a 2026 evaluation) | **Integrate, don't rebuild** ([Temporal on AI](https://temporal.io/blog/durable-execution-meets-ai-why-temporal-is-the-perfect-foundation-for-ai); [eval](https://github.com/atilladeniz/next-go-pg/issues/57)) |
| Policy decision point | OPA/Rego (CNCF graduated), Gatekeeper precedent; Cedar as newer alternative | **Integrate** ([Styra: OPA vs Cedar](https://www.styra.com/knowledge-center/opa-vs-cedar-agent-and-opal/)) |
| Observability | OpenTelemetry (+ Prometheus/Grafana) | **Adopt, don't rebuild** |
| Container orchestration | Kubernetes | **Deploy onto; don't reimplement** |
| Secrets | Vault / cloud KMS / external secret stores | **Integrate** |
| Identity | OIDC/OAuth2, SPIFFE/SPIRE for workload identity | **Integrate** |
| Model access | Provider SDKs, OpenRouter-style gateways | **Adapter layer only** |
| Tool protocol | MCP (first-class but not exclusive) | **Integrate** |
| Vector search | pgvector → Qdrant/Weaviate/Milvus by scale | **Integrate** |

**[Recommendation]** The minimum differentiated layer — the part no existing
product owns end-to-end — is: **governed agency composition**: agent registry +
composite-principal identity/delegation + plan-aware policy/risk/admission +
agent+model routing + human approval state machine + decision-evidence audit +
cost attribution. Everything else is integration.

## 5. The strongest moat candidates

**[Opinion]**
1. **Delegation chains with capability attenuation** — cryptographically bound,
   strictly-attenuating authority chains (cf. the arXiv composite-principal
   model). Hard to retrofit onto frameworks; easy to get subtly wrong.
2. **Decision-evidence ledger** — append-only, tamper-evident record binding
   plan → policy evaluation → risk score → approval → execution → outcome.
   This is what auditors and regulated buyers pay for.
3. **Plan-aware policy evaluation** — evaluating the *plan*, not just the
   single action, against policy. No existing policy engine does this natively
   for agents.
4. **Routing intelligence** — the learned mapping of task → (agent, model,
   tools) by capability, cost, latency, risk, and historical outcome. Data
   network effect.

## 6. Open questions (carried into architecture)

1. Where exactly does the Governance Rail end and the Execution Plane begin
   when the executor must enforce policy locally (offline edge agents)?
   → See `architecture-analysis.md` §3.
2. Is the AGRL (goals/resources ledger) part of the ACP or above it?
   → **Recommendation**: above it. The ACP consumes goals; it does not own
   goal management. (See `architecture-analysis.md` §2.)
3. Event sourcing everywhere vs. selectively? → Selectively: audit ledger and
   workflow history are event-sourced; registries are current-state with
   version history. (See `technology-evaluation.md`.)

---

*Sources are linked inline above. Market figures: Mordor Intelligence sizes the
agentic AI development platform market at USD 14.62B (2026) → 66.38B (2031),
35.3% CAGR
([report](https://www.mordorintelligence.com/industry-reports/agentic-artificial-intelligence-development-platform-market)) —
directional context, not a design input.*
