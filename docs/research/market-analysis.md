# Agent Control Plane — Market Analysis

**Date:** 2026-09-14 · **Stream:** Market / competitive / product strategy (1 of 3) · **Type:** Research only, no code.

**Claim labels used throughout:**
- `[ESTABLISHED FACT]` — verifiable from the cited source
- `[INDUSTRY CONVENTION]` — widely repeated pattern, not a formal standard
- `[ARCHITECTURAL RECOMMENDATION]` — what this research recommends, with justification
- `[HYPOTHESIS]` — plausible but unverified
- `[OPINION]` — judgment call

Every important external claim carries a source link. Staleness and confidence notes are in the appendix.

---

## 1. Definition: what an Agent Control Plane is

**Short answer:** "Agent Control Plane" is now established industry vocabulary — but not a formal standard. IBM, Microsoft, Salesforce, GitHub, and Gartner all use the exact term to describe a governed control layer for agent fleets. No RFC/ISO/OCI-style specification exists yet; the Kubernetes control-plane/data-plane split is the dominant shared metaphor.

Who uses the exact term (verified 2026-09-14):

- **IBM** published a dedicated explainer, "What is an Agent Control Plane?", defining it as *"the system that deploys, operates, monitors and governs AI agents across an organization"* — with individual agents running in the "data plane" and the control plane above as a centralized control center. IBM's Institute for Business Value study: **96% of enterprises are already using AI agents in some capacity.**
  ([IBM](https://www.ibm.com/think/topics/agent-control-plane?lnk=thinkhpagents4us))
- **Microsoft** launched **Agent 365** (Nov 18, 2025, early access) explicitly as a *"control plane to help organizations deploy and manage AI agents at scale,"* regardless of where agents were built or acquired. Five capabilities: **Registry** (all agents including shadow agents, with agent IDs), **Access control**, **Visualization** (agent↔people↔data graph), **Interoperability**, and more; integrates with Defender, Entra, Purview, M365 admin center.
  ([InfoWorld](https://www.infoworld.com/article/4093378/microsoft-rolls-out-agent-365-control-plane-for-ai-agents.html), [VentureBeat](https://venturebeat.com/orchestration/claudes-next-enterprise-battle-is-not-models-its-the-agent-control-plane))
- **Salesforce** expanded **Agent Fabric** as *"a trusted agent control plane for your rapidly evolving multi-vendor AI landscape"* (~May 2026), with automated discovery, authoring, centralized LLM governance, and monitoring dashboards.
  ([Salesforce](https://www.salesforce.com/news/stories/agent-fabric-control-plane-announcement/?bc=OTH))
- **GitHub** made **"Enterprise AI Controls" and "agent control plane" generally available** (Feb 26, 2026): consolidated AI administration, audit logs with `actor_is_agent` identifiers, `agent_session.task` events, and an enterprise-wide MCP allowlist via a centralized MCP registry URL.
  ([GitHub](https://github.blog/changelog/2026-02-26-enterprise-ai-controls-agent-control-plane-now-generally-available/))
- **Gartner** hosts a sponsored guide titled *"An agentic control plane"* and uses the term in enterprise readiness assessments (agent observability, semantic governance via ABAC policy engines, drift management, supervisor/worker orchestration, human fallback).
  ([Gartner](https://www.gartner.com/technology/media-products/newsletters/UST/1-2NA054CI/guide.pdf))

**Grounded technical definition (synthesized):**

> An **Agent Control Plane** is a centralized, vendor-neutral management layer that **discovers, registers, governs, orchestrates, and observes** fleets of AI agents running across an enterprise. It holds the **desired state** of the agent estate (which agents exist, what they may do, which tools/data they may touch, under which policies and identities), **reconciles** actual state against desired state (provisioning, permissioning, versioning, kill-switching), and **enforces policy at runtime** (per-action authorization, cost/risk routing, audit) — while the agents themselves execute in the **data plane**. It is to agents what Kubernetes is to containers: not the runtime that executes work, but the control system that makes the fleet operable, observable, and governable.

`[ESTABLISHED FACT]` The term is in active use by IBM, Microsoft, Salesforce, GitHub, and Gartner.
`[INDUSTRY CONVENTION]` The control-plane/data-plane split is the shared metaphor; no published open standard defines required ACP interfaces.
`[OPINION]` The strongest product definition borrows Kubernetes's reconciliation loop: desired-state declarations + controllers driving agents toward it + an admission gate that vetoes non-compliant actions before execution.

---

## 2. Why now: the drivers creating the need

### 2a. Adoption is past the pilot stage — the installed base exists

- **IDC** (Future Enterprise Resiliency and Spending Survey, Wave 4, July 2026): **95% of enterprises worldwide now run at least one company-funded agent-enabled workflow in production**, averaging **~11** across functions (heaviest: IT ops/software dev 71%, customer service 43%, supply chain/procurement 36%). Average monthly spend: **$117,558** (~$1.4M/year) on agent inference and orchestration. IDC projects **2.5 billion active agents by 2030** (~80× 2025), completing **459 trillion actions/year** vs 48 billion today.
  ([IDC](https://www.idc.com/resource-center/blog/the-agent-economy-is-scaling-faster-than-it-can-be-metered/))
- **Gartner:** **33% of enterprise software applications will include agentic AI by 2028** (up from <1% in 2024); **≥15% of day-to-day work decisions made autonomously through agentic AI by 2028** (up from 0% in 2024).
  ([Gartner](https://www.gartner.com/en/articles/3-bold-and-actionable-predictions-for-the-future-of-genai))
- **Gartner:** Fortune 500 enterprises projected to deploy an average of **~150,000 "digital workers" per company by 2028** (described as a ballpark figure).
  ([Computerworld](https://www.computerworld.com/article/4165686/gartner-sees-untamed-growth-in-agentic-ai.html))
- **Gartner:** by 2028, **80% of all tangible ROI from agentic AI will come from specialized, domain-specific agents**; **70% of AI applications expected to use multi-agent systems by 2028**.
  ([Gartner](https://www.gartner.com/en/articles/agentic-ai-roi))
- **Gartner:** **Guardian agents** — AI systems that monitor/manage/secure other AI systems — will capture **10–15% of the agentic AI market by 2030**. Analyst quote: *"Agentic AI will lead to unwanted outcomes if it is not controlled with the right guardrails."*
  ([dayofdubai/Gartner](https://dayofdubai.com/news/gartner-guardian-agents-to-capture-up-to-15-of-agentic-ai-market-by-2030))
- Counterweight: Gartner (June 2025) predicted **>40% of agentic AI projects will be canceled by end of 2027** due to escalating costs and unclear business value, warning of "agent washing" — only ~130 of thousands of agentic-AI vendors are "real."
  ([Reuters](https://www.reuters.com/business/over-40-agentic-ai-projects-will-be-scrapped-by-2027-gartner-says-2025-06-25/?ref=blog.speedcloud.sh))

`[ESTABLISHED FACT]` All statistics above are sourced. Note the tension: massive projected scale *and* a projected high failure rate — which is precisely the governance argument (the projects that survive to scale are the ones that can be governed).

### 2b. Agent sprawl / shadow AI: the fragmentation is already here

- **Reco, State of Agent Security 2026:** **80% of employee AI tools** (browser extensions, MCP servers) run with **no IT oversight**. Of 500 MCP servers on npm analyzed: **50% enable shell execution, 82% local file read/write, 73% outbound network calls** — "toxic combinations" enabling exfiltration via prompt injection.
  ([SC World](https://www.scworld.com/news/shadow-ai-surges-as-80-of-employee-ai-tools-evade-it-oversight))
- **PagerDuty Shadow AI Survey 2026** (1,250 professionals, companies ≥$500M): **66% used AI tools at work despite believing it was against policy**; >1/3 put customer data into public models.
  ([PagerDuty](https://www.pagerduty.com/newsroom/shadow-ai-workplace-survey-2026/))
- **Nutanix Enterprise Cloud Index 2026:** **79% of IT leaders** have encountered unauthorized AI deployments by employees in non-IT functions.
  ([Nutanix](https://www.nutanix.com/theforecastbynutanix/business/shadow-it-surges-as-employees-deploy-unsanctioned-ai-tools-and-agents))
- Microsoft's Agent 365 explicitly includes a **registry of "shadow agents"** — vendor acknowledgment that discovery of unknown agents is a core control-plane job.
  ([InfoWorld](https://www.infoworld.com/article/4093378/microsoft-rolls-out-agent-365-control-plane-for-ai-agents.html))

`[ESTABLISHED FACT]` Shadow AI is measured and large (66–80% ungoverned-adoption figures across independent surveys); the control plane's **discovery + registry** function directly answers this.
`[OPINION]` "Discovery" is the most defensible wedge feature: enterprises can't govern what they can't see, and every vendor's control-plane narrative starts with the registry.

### 2c. Governance / regulatory drivers

- **EU AI Act — transparency obligations (Article 50) apply since August 2, 2026:** providers must inform users when interacting with AI; machine-readable marking of AI-generated content; deployers must disclose deepfakes and AI-generated public-interest content.
  ([European Commission](https://digital-strategy.ec.europa.eu/en/news/commission-publishes-guidelines-transparency-obligations-providers-and-deployers-certain-ai-systems))
- **EU AI Act — enforcement phase began August 2, 2026:** the EU AI Office can investigate GPAI providers (request documentation, evaluate models, require corrective measures), with fines up to **€15M or 3% of worldwide annual turnover**. High-risk system requirements demand: lifecycle risk management, **automatic recordkeeping/logging**, human oversight, and quality management systems.
  ([JD Supra](https://www.jdsupra.com/legalnews/eu-ai-act-enforcement-phase-begins-5071689/), [IAPP](https://iapp.org/media/pdf/resource_center/eu_ai_act_compliance_matrix_at_a_glance.pdf))
- **SOC 2 for agents:** no agent-specific SOC 2 criteria were found — existing Trust Services Criteria are being *interpreted* for agent systems by auditors. The practical driver: agent actions need auditable logs and change control to pass ordinary SOC 2 Type II audits.
  `[HYPOTHESIS]` A dedicated "SOC 2 for AI agents" framework is likely to emerge; it does not appear to exist as of Sept 2026 based on this research.

`[ESTABLISHED FACT]` EU AI Act enforcement is now live and includes per-decision logging, human oversight, and transparency obligations that map directly onto control-plane capabilities (identity, disclosure, audit trail).
`[OPINION]` The regulatory tailwind is real but uneven: the EU AI Act creates hard requirements; the US has no federal equivalent, so US enterprise buyers will frame this as risk/audit-readiness rather than compliance per se.

---

## 3. Market size: projections 2025–2030

Note: "AI agents market" definitions vary by firm (some count platforms + services; some count only agent software). Treat as directional, not reconcilable. All figures USD.

| Source | Publication | 2025 base | 2030 projection | CAGR |
|---|---|---|---|---|
| **Grand View Research** | Sept 2026 | — | **$50.31B** | 45.8% |
| **MarkNtel Advisors** | Sept 2026 | **$5.32B** | **$42.7B** | 41.5% |
| **MarketsandMarkets** | Jan 2026 | — | **$48.3B** | 43.3% |
| **Gartner** (software disruption, not market size) | Oct 2025 | — | **$234B** of enterprise software spend diverted to AI alternatives; >$450B agentic AI-driven revenue by 2028 | n/a |
| **Gartner** (guardian agents) | 2026 | — | **10–15% of agentic AI market** | n/a |
| **IDC** FutureScape 2026 | Oct 2025 | — | 45% of orgs orchestrate agents at scale by 2030 | n/a |

Sources: [PR Newswire (Grand View)](https://www.prnewswire.co.uk/news-releases/ai-agents-market-size-to-hit-50-31-billion-by-2030-at-cagr-45-8---grand-view-research-inc-302447061.html) · [PR Newswire (MarkNtel)](https://www.prnewswire.co.uk/news-releases/ai-agent-market-forecast-to-reach-42-7-billion-by-2030-north-america-is-leading-with-40-market-share--markntel-advisors-302547620.html) · [GlobeNewswire (MarketsandMarkets)](https://rss.globenewswire.com/news-release/2026/01/05/3213141/0/en/AI-Agents-Market-to-Grow-43-3-Annually-Through-2030.html) · [SDxCentral/Gartner](https://www.sdxcentral.com/news/gartner-reckons-ai-agents-will-swipe-234b-from-software-vendors-by-2030/)

`[ESTABLISHED FACT]` Three independent firms converge on roughly **$42–50B for the AI-agents market by 2030 at ~41–46% CAGR** — an unusually tight consensus for this space.
`[OPINION]` The more strategically useful number for an ACP pitch is Gartner's **$234B software-spend diversion** and the **10–15% guardian-agent slice**: the control plane isn't selling into the $45B agent market, it's selling into the *governance tax* on the hundreds of billions of spend being reshaped around agents.
`[HYPOTHESIS]` No analyst firm yet tracks an "agent control plane / agent governance platform" sub-category with its own dollar figure; whoever defines that category gets to set its TAM narrative. Gartner's "guardian agents" is the closest existing frame.

---

## 4. Category differentiation: what each adjacent category is, is NOT, and how it differs from an ACP

| Category | Layer | Manages | Does NOT manage | ACP relationship |
|---|---|---|---|---|
| Agent framework (LangGraph, CrewAI, ADK, Claude Agent SDK) | Build-time | One agent's logic (reasoning loop, tools, memory) | Fleet, policy, identity, cross-agent audit | ACP governs what frameworks produce — framework-agnostic |
| Orchestration framework | Execution logic | Task flow/routing (what happens next) | Authority, compliance (whether it's allowed) | Pluggable inside ACP; orchestration via interfaces |
| LLM gateway (LiteLLM, Portkey, OpenRouter) | Model access | Token routing/cost across providers | Agent intent, tool permissions, business policy | Execution-plane component the ACP can sit in front of |
| MCP server | Tool interface | Capability exposure (standardized agent↔tool plumbing) | Whether access is allowed, by whom, with what budget | ACP allowlists/registers MCP servers; MCP standardizes the interface |
| API gateway | Network L7 | API traffic policy | Agent semantics (intent, identity, multi-step task) | Complementary; integrate, don't rebuild |
| Workflow engine (Temporal) | Execution | Durable deterministic runs (replay, retries, exactly-once) | Non-deterministic agent judgment, authorization | Execution-plane backbone for deterministic sub-flows |
| Observability platform (LangSmith, Arize) | Insight | Traces/evals — **read-only** | Enforcement, prevention, identity, budgets | Data feed into ACP's control loop; "observability with a kill switch" |
| AI platform (Azure Foundry, Vertex, Bedrock) | Vendor suite | Agents inside one cloud/identity boundary | Cross-vendor neutrality | ACP is the neutral overlay; platforms are execution substrates |
| Agent runtime / K8s | Infrastructure | Compute for agent code | Agent-level policy | ACP deploys onto runtimes; K8s-native design (CRDs, operators, admission webhooks) |

**The differentiation rule of thumb** `[OPINION]`: frameworks build agents, LLM gateways route tokens, MCP standardizes tool access, Temporal guarantees durable execution, LangSmith observes (read-only), AI platforms are vendor-scoped — **none governs a cross-vendor agent fleet; that's the ACP's empty slot.**

Key boundary judgments:

- **IBM draws the line explicitly:** the ACP and MCP *"operate at different layers."* ([IBM](https://www.ibm.com/think/topics/agent-control-plane?lnk=thinkhpagents4us))
- **Observability is read-only.** It shows what agents did; it does not prevent them from doing it. The ACP consumes traces/evals (for drift detection, behavioral evaluation) and *acts*: quarantine a misbehaving agent, revoke a tool grant, trigger human review.
- `[ARCHITECTURAL RECOMMENDATION]` Keep orchestration pluggable: the ACP should orchestrate via interfaces, not own the workflow engine. `[INDUSTRY CONVENTION]` Do not rebuild an API gateway, an IdP, a SIEM, or an LLM gateway inside the ACP; integrate with what the enterprise already runs.

---

## 5. Architectural boundaries: what belongs where

### 5a. The two precedents

**Kubernetes (control plane vs data plane).** `[ESTABLISHED FACT]` A K8s cluster splits into: control plane (API server, etcd, scheduler, controller-manager — holds desired state, makes global decisions, reconciles actual→desired) and data plane (kubelets, container runtime — executes workloads). The mechanism is the **reconciliation loop**: declare desired state → controllers continuously drive the world toward it.

**Enterprise policy/execution separation.** `[INDUSTRY CONVENTION]` Mature enterprises separate *policy decision* from *policy enforcement*: IAM authored centrally but enforced at every service; OPA-style policy agents evaluate, applications enforce.

### 5b. Recommended five-plane architecture

| Plane/Layer | Belongs here | Does NOT belong here |
|---|---|---|
| **CONTROL** | Agent registry (incl. shadow-agent discovery); desired-state declarations (agents, versions, owners, allowed tools/data); scheduler/router; **admission gate** (pre-execution allow/deny/escalate per action); lifecycle controllers (deploy, upgrade, rollback, quarantine, kill-switch); fleet health & reconciliation; cost/risk-based routing policy evaluation point | LLM calls themselves; tool execution; model weights; long-term memory stores; the enterprise's IdP |
| **EXECUTION** | Agent workers/runtimes (containers, serverless, pods); framework harnesses; durable workflow engine (Temporal) for deterministic sub-flows; local policy **enforcement points** (sidecar/gate); tool-call dispatch via MCP clients; trace emission | Policy authoring; identity issuance; cross-agent goal reasoning |
| **GOVERNANCE / SECURITY** | Policy authoring & versioning; agent identity issuance (agent IDs, SPIFFE-style workload identity); secrets/credentials brokerage (agents never hold raw creds); MCP server allowlist/registry; **immutable audit trail** (EU AI Act Arts. 12/19 recordkeeping); compliance evidence packs; human-approval workflows; behavioral evaluation & drift detection | Task routing; model selection for cost; agent-to-agent collaboration logic |
| **INTELLIGENCE / GOAL-MGMT** | Agent reasoning/planning; goal hierarchies, prioritization, conflict detection (AGMS); shared event-sourced state substrate (AGRL — single ledger); memory systems; learning/adaptation loops; multi-agent coordination | Enforcement; identity; billing; deployment mechanics |
| **EXTERNAL INFRA** | Foundation models (via LLM gateway); K8s/cluster infra; enterprise IdP; SIEM; ITSM; data warehouses; network/API gateways; existing observability | Anything agent-specific |

`[ARCHITECTURAL RECOMMENDATION]` Keep governance a **separate logical plane** from control, not merged into it — it is a different trust domain with a different change cadence: policies and audit requirements change on legal/compliance timescales and need independent versioning, sign-off, and retention, while control-plane routing changes on operational timescales.

`[OPINION]` The most important architectural decision in the whole design: **constraint flow is one-way — control-plane policy bounds are non-negotiable inputs to goal-management; the optimizer must never edit its own guardrails.** Conflating the intelligence layer with the control plane lets the optimizer rewrite its own constraints — the exact failure mode governance exists to prevent.

### 5c. Critical interfaces (where the planes touch)

1. **Admission interface (Control → Execution):** every consequential agent action passes an allow/deny/escalate check *before* executing — the ACP's equivalent of K8s admission webhooks. Must be local/fast (cached policy) with central override.
2. **Registry interface (Governance → Control):** agent identity issuance and MCP/tool allowlists authored in governance, consumed by control's admission decisions.
3. **Telemetry interface (Execution → Control → Governance):** traces flow up; control detects drift/anomalies and can quarantine; governance persists the immutable audit record.
4. **Constraint interface (Control → Intelligence):** goal-management may propose any plan, but policy bounds are non-negotiable inputs, not suggestions.
5. **Human interface (Governance → people):** approval queues, audit exports, and the fleet-wide kill switch — operable by humans without agent mediation.

### 5d. What to explicitly keep OUT of the ACP (scope discipline)

- **Do not build:** a foundation model, an LLM gateway from scratch (integrate LiteLLM/Portkey), an IdP, a SIEM, a workflow engine from scratch (embed Temporal), an API gateway.
- **Do not own:** the agent's internal reasoning (frameworks do that); the enterprise's data (reference it, don't copy it).

`[OPINION]` The ACP's defensible scope is: **identity + registry + admission + audit + lifecycle** for agents. Everything else is integration. Scope creep into model serving or agent authoring is how this becomes a second-rate AI platform instead of a first-rate control plane.

---

## Appendix: staleness & confidence notes

- Market-size figures from PR announcements (Grand View, MarkNtel, Sept 2026) reflect reports published days before this research — current. MarketsandMarkets is from Jan 2026 — recent.
- Gartner predictions cited (33% apps by 2028, 40% cancellations by 2027) originate from 2024–2025 publications and are repeated in 2026 Gartner materials; underlying surveys are small-sample — treat as directional.
- Shadow-AI statistics come from vendor-sponsored surveys (Reco, PagerDuty, Nutanix, ArmorCode, Akamai) — expect upward bias in absolute numbers, but the *direction* is consistent across five independent sources.
- The "150,000 digital workers per Fortune 500 by 2028" is explicitly a ballpark figure — high uncertainty.
- No agent-specific SOC 2 criteria found as of 2026-09-14; verify with an auditor before relying on this.
- Term status: "Agent Control Plane" is established vendor/analyst vocabulary, NOT a formal standard. No open specification for required ACP interfaces was found.
