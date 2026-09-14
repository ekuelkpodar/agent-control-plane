# Agent Control Plane — Product Strategy

**Date:** 2026-09-14 · **Stream:** Market / competitive / product strategy (1 of 3) · **Type:** Research only, no code.

**Claim labels:** `[ESTABLISHED FACT]` · `[INDUSTRY CONVENTION]` · `[ARCHITECTURAL RECOMMENDATION]` · `[HYPOTHESIS]` · `[OPINION]`

**Working definition:** An *Agent Control Plane* is a governed control layer for fleets of autonomous AI agents — the system that registers agents, enforces policy on what they may do (permissions, approvals, spend), observes what they did (audit trail, lineage, cost), routes their tool/model calls, and manages their lifecycle across heterogeneous agent stacks. Enterprises already run multiple agent platforms (avg 3.1 per org), so the control layer must sit *above* them, not inside one of them.

---

## 1. Target customers

### 1.1 Segments

| Segment | Profile | Fit for ACP |
|---|---|---|
| **Global 2000 / regulated majors** (10,000+ employees; platform engineering orgs 50–500+) | 85% run 2+ agent orchestration platforms simultaneously, avg 3.1 per enterprise ([VentureBeat Intelligence, July 2026](https://venturebeat.com/orchestration/companies-already-run-3-agent-platforms-salesforces-new-enterprise-ai-harness-wants-govern-all-of-them)) | `[HYPOTHESIS]` Strongest ICP: they already have the sprawl problem, and governance is a CISO-mandated line item |
| **Large mid-market** (2,000–10,000 employees) | 57.3% of surveyed teams run agents in production ([LangChain State of Agent Engineering](https://sqmagazine.co.uk/ai-agents-statistics/)) | `[HYPOTHESIS]` Fastest to close; lower ACV, fewer procurement layers — good second wave |
| **SMB / startup** | Ad-hoc AI use, no platform team; 31% "wait and see" on agentic AI ([Gartner](https://www.gartner.com/en/newsroom/press-releases/2025-06-25-gartner-predicts-over-40-percent-of-agentic-ai-projects-will-be-canceled-by-end-of-2027)) | `[OPINION]` Weak fit: they need a single agent platform, not a control plane above several |
| **Government / public sector** | Large, slow procurement; sovereignty mandates rising ([Computer Weekly](https://www.computerweekly.com/feature/Sovereign-cloud-and-AI-services-tipped-for-take-off-in-2026)) | `[HYPOTHESIS]` Strong demand for sovereign/on-prem control planes, but 12–24 month cycles — land later via partners |

### 1.2 Ideal Customer Profile (ICP)

`[ARCHITECTURAL RECOMMENDATION]` The ICP is a **regulated large enterprise (bank, insurer, global logistics, telco) with:**

- 5,000+ employees and an existing platform engineering / MLOps function (owns Kubernetes, Terraform, Kafka-scale infrastructure);
- **2+ agent frameworks already in production** (the measured average of 3.1 platforms means the fragmentation pain is real, not theoretical);
- a CISO office that has already flagged AI-agent risk (Anthropic's 2026 enterprise data: 80% of orgs report measurable economic returns from agents, but integration (46%) and data access/quality (42%) are the top blockers — value exists, control is missing ([Anthropic](https://claude.com/blog/how-enterprises-are-building-ai-agents-in-2026)));
- AI budget concentrated with the CIO/CTO; multi-stakeholder buying cycle (most common AI purchase cycle **16–20 weeks**, 58% cite security review as the top delay; 58% involve 7+ people ([Levelpath](https://www.businesswire.com/news/home/20260709895815/en/AI-Tops-Enterprise-Buying-Priorities-Yet-Takes-the-Longest-to-Buy-Levelpath-Research-Finds))).

**Buyer map:**

- **Economic buyer: CIO/CTO** — 61% of CIOs prefer investing in known vendors already in their stack ([Salesforce CIO Trends 2026](https://www.salesforce.com/au/news/stories/cio-trends-2026/)). Argument for partnering/channeling through incumbent vendors rather than pure direct motion early.
- **Co-buyer / veto: CISO** — data security & privacy is CIOs' #1 AI fear; only 23% are confident they have AI data governance ([Salesforce](https://www.salesforce.com/au/news/stories/cio-trends-2026/)). The CISO is the budget key for the *governance* wedge.
- **Champion / daily user: VP Platform Engineering, Head of AI/ML infrastructure** — they own the fragmentation and spend problems. "Control plane" is their native vocabulary.
- **Line-of-business sponsors** (service ops, claims, fraud) fund the use-case side; agentic AI investment decisions are becoming "more business led and value driven" ([IDC](https://my.idc.com/getdoc.jsp?containerId=US54373626)).

### 1.3 Market context

- `[ESTABLISHED FACT]` Gartner: AI agent market $8.03B (2025) → **$11.78B (2026)**, 46.6% CAGR; agentic AI spend **$201.9B in 2026** (+141% YoY), exceeding chatbot/assistant spend by 2027 ([Belitsoft/Gartner](https://www.barchart.com/story/news/1204699/belitsoft-releases-ai-agent-development-forecast-2026-40-of-enterprise-applications-to-include-task-specific-agents-by-year-end)).
- `[ESTABLISHED FACT]` Gartner: **40% of enterprise apps will include task-specific AI agents by end of 2026** (from <5% in 2025) ([UC Today](https://www.uctoday.com/unified-communications/gartner-predicts-40-of-enterprise-apps-will-feature-ai-agents-by-2026/)).
- `[ESTABLISHED FACT]` Enterprise genAI spend reached **$37B in 2025** (from $11.5B in 2024) per Menlo Ventures; Salesforce Agentforce ARR ≈ **$800M (+169% YoY)** ([sqmagazine](https://sqmagazine.co.uk/ai-agents-statistics/)).
- `[OPINION]` The ACP should not compete with the *use-case* leaders (Sierra, Decagon, Agentforce). It should position as the layer that *governs and operates* all of them — the use-case vendors create the demand for the control plane, the same way SaaS sprawl created demand for Okta.

---

## 2. Enterprise use cases — concrete, and which are most mature

**Maturity signal:** 88% of orgs use AI in ≥1 function, but only 23% are *scaling* an agentic system ([McKinsey](https://sqmagazine.co.uk/ai-agents-statistics/)). The gap is the ACP's opening: use cases are proven, scale-up is blocked on control.

| Use case | Production example | Maturity |
|---|---|---|
| **Customer service / contact center** | Salesforce Agentforce ARR ~$800M (+169% YoY); PolyAI containment 50–87%; CIOs rank customer service #1 for agentic AI ([Rasa](https://rasa.com/blog/best-ai-agents-for-enterprise), [Salesforce](https://www.salesforce.com/au/news/stories/cio-trends-2026/)) | `[ESTABLISHED FACT]` Most mature |
| **Software engineering / DevOps** | AI coding-agent market $9.8–11B annualized ([EnterpriseDNA](https://enterprisedna.co/resources/news/gartner-enterprise-ai-coding-agents-10-billion-market-2026/)); Doctolib: 40% faster shipping ([Anthropic](https://claude.com/blog/how-enterprises-are-building-ai-agents-in-2026)) | `[ESTABLISHED FACT]` Most mature alongside support |
| **IT operations / NetOps** | 80% of network automation vendors adding agentic capabilities by end-2027, but >65% of enterprise networking activities remain manual ([Itential](https://www.itential.com/resource/analyst-report/gartner-market-guide-for-network-automation-platforms/)) | `[INDUSTRY CONVENTION]` Maturing fast |
| **Financial ops: fraud / payments / AML** | Macquarie Bank: 40% fewer false positives ([Google Cloud](https://blog.google/innovation-and-ai/infrastructure-and-cloud/google-cloud/ai-business-trends-report-2026/)); payment-authorization agents deciding in <200ms ([PYMNTS](https://www.pymnts.com/news/artificial-intelligence/2026/banks-shift-ai-from-chatbots-autonomous-money-movement/)) | `[INDUSTRY CONVENTION]` Production but high-governance |
| **Logistics / supply chain execution** | Overroute ($5.5M, Sept 2026) agents across **J.B. Hunt's** network ([FreightWaves](https://www.freightwaves.com/news/overroute-raises-5-5m-to-expand-ai-freight-execution-platform)); Cargofy Series A $11M, >$10M ARR, 2,000 customers, one dispatcher managing 10× fleet ([tech.eu](https://tech.eu/2026/06/18/cargofy-lands-6m-to-scale-ai-workers-for-logistics/)) | `[ESTABLISHED FACT]` Real production revenue, early stage |
| **Security operations (SOC)** | Agents taking over alert triage; eSentire: threat analysis 5 hrs → 7 min ([Anthropic](https://claude.com/blog/how-enterprises-are-building-ai-agents-in-2026)) | `[INDUSTRY CONVENTION]` Fast-moving, high willingness to pay |
| **Data analysis / reporting** | Highest-impact non-coding use case (60%); L'Oréal: 99.9% conversational analytics accuracy across 44,000 users ([Anthropic](https://claude.com/blog/how-enterprises-are-building-ai-agents-in-2026)) | `[INDUSTRY CONVENTION]` Mature as assist, maturing as autonomous |
| **Procurement** | Only 15% would *never* let an AI agent complete a purchase; 20% would allow <$10K with controls ([Levelpath](https://www.businesswire.com/news/home/20260709895815/en/AI-Tops-Enterprise-Buying-Priorities-Yet-Takes-the-Longest-to-Buy-Levelpath-Research-Finds)) | `[HYPOTHESIS]` Emerging — trust threshold is the product |

**Maturity ranking (most → least):** customer service ≈ software engineering > data analysis/reporting > IT operations > security operations > financial ops > logistics execution > procurement.

---

## 3. Initial vertical — evaluation & recommendation

Scored on: (a) agentic AI spend & momentum, (b) pain intensity (sprawl + risk), (c) governance/regulatory pull, (d) buying capacity & cycle reality.

| Vertical | Evidence | Verdict |
|---|---|---|
| **Financial services (banks, insurers, payments)** | IDC: FS firms spend **>$67B on AI by 2028** ([Morningstar](https://www.morningstar.com/news/pr-newswire/20251216cl48797/bankings-ai-reckoning-13-expert-predictions-for-2026)); Nvidia: FS investing in agentic systems for payment routing, fraud, service ops ([PYMNTS](https://www.pymnts.com/news/artificial-intelligence/2026/banks-shift-ai-from-chatbots-autonomous-money-movement/)); banks must now "authenticate not only people but also the AI agents acting in their name"; Experian launched an "Agent Operating System" with *embedded governance by design* for FS ([Experian](https://markets.financialcontent.com/ibtimes/article/bizwire-2026-6-2-experian-brings-trusted-agentic-ai-to-financial-services-with-the-launch-of-agent-operating-system)) | **RECOMMEND** |
| **Insurance** | Shares FS regulatory DNA; claims is a frontier use case ([Microsoft](https://www.microsoft.com/en-us/industry/blog/financial-services/2025/12/18/ai-transformation-in-financial-services-5-predictors-for-success-in-2026/)) | Strong #2 — folds into the FS motion |
| **Logistics / supply chain** | Real production economics (J.B. Hunt/Overroute; Cargofy 10× dispatcher productivity, >$10M ARR); but IT budgets are thinner, buying is fragmented, compliance pull is weaker ([Y Combinator](https://www.ycombinator.com/companies/industry/logistics)) | Strong #3 — best design-partner territory, weaker ACV economics |
| **Customer service (horizontal)** | #1 CIO-ranked use case, but crowded: Sierra, Decagon, Cognigy/NICE, Agentforce ([Rasa](https://rasa.com/blog/best-ai-agents-for-enterprise)) | Crowded — the ACP's *wedge*, not the vertical |
| **Healthcare** | Large savings narrative, 37% expected transformation ([SupplyChain247](https://www.supplychain247.com/article/agentic-ai-mass-market-2026-ieee-survey)); but HIPAA liability culture + EU AI Act high-risk classification slow autonomous-agent approval | High need, slow buying — phase 2 |
| **Government** | Sovereignty tailwinds real ([Computer Weekly](https://www.computerweekly.com/feature/Sovereign-cloud-and-AI-services-tipped-for-take-off-in-2026)); procurement cycles 12–24 months | Partner-led, phase 3 |
| **Cybersecurity** | Agentic SOC is real, but security vendors are *acquiring* this layer (PANW + Portkey) — they'd buy an ACP, not buy from it | Exit-channel vertical, not an entry vertical |
| **Manufacturing** | Danfoss-style transactional automation is real; OT/IT divide slows adoption | Niche opportunities; not the lead |
| **IT operations** | Strong vendor momentum; but better attacked as a *horizontal wedge inside the FS vertical* than a standalone vertical | Wedge, not vertical |

### Recommendation: **Financial services first (banks + insurers), with IT operations as the in-vertical wedge**

1. **Spend.** The single largest quantified agentic-AI budget pool among regulated verticals: >$67B FS AI spend by 2028 (IDC), with 2026 spend increases targeted at *agentic* systems (Nvidia). `[ESTABLISHED FACT]`
2. **Pain.** Money-moving agents are already live (payment authorization <200ms) — the CISO's nightmare. The "authenticate the agent" problem is *uniquely* FS. `[INDUSTRY CONVENTION]`
3. **Regulatory pull.** Model risk management (SR 11-7, EBA/ECB guidance, EU AI Act enforcement from Aug 2026) already forces banks to document, audit, and human-oversight AI decisions — a governance product slots into *existing compliance budgets*. `[INDUSTRY CONVENTION]`
4. **Buying capacity.** Banks already buy infra control planes (Kafka via Confluent, IaC via Terraform Enterprise, API gateways) with $100K+ enterprise deals. The procurement muscle exists. `[ESTABLISHED FACT — see §4]`
5. `[OPINION]` Logistics (Ekue's own domain expertise) is the best *second* vertical: strongest "agents do physical-world work" story and his credibility, but lower per-account spend and a fragmented buyer landscape. Healthcare is the best *third*.

**Caveat:** FS sales cycles are the longest (16–20 weeks) and incumbents are entrenched; the entry wedge should be *one* governed workflow (e.g., fraud-ops agent fleet or customer-service agent governance) inside a platform-engineering team, then expand to the enterprise agent registry. `[HYPOTHESIS]`

---

## 4. Business model — open source vs SaaS vs enterprise licensing vs managed

### 4.1 How infrastructure comparables actually monetized

| Company | Posture | Model | Anchor |
|---|---|---|---|
| **Temporal** | Core OSS, 43M installs | OSS + managed cloud, usage-based per-action | $550M at **$12.55B** (Sept 2026); 4,300+ customers incl. OpenAI, NVIDIA, JPMorgan Chase ([Reuters](https://www.reuters.com/business/temporals-valuation-spikes-126-billion-lightspeed-led-funding-round-2026-09-14/)) |
| **HashiCorp (Terraform)** | Moved to BSL after cloud re-hosting; community forked **OpenTofu** | Per-resource/month SaaS + contract-priced self-managed Enterprise with air-gap support | ([The New Stack](https://thenewstack.io/forks-clouds-and-the-new-economics-of-open-source-licensing/)) |
| **Confluent (Kafka)** | Community license + proprietary enterprise features | Consumption-based cloud + enterprise subscription (self-hosted); OEM/embedded program | Cloud = growth engine; self-hosted sustains regulated accounts |
| **Kong (API gateway)** | OSS gateway (Apache 2.0) | Tiered enterprise tiers on connectivity + governance (RBAC, audit, policy); SaaS + self-managed | Classic land-with-OSS / expand-with-governance playbook |
| **LangChain** | OSS frameworks (118K+ stars) | **Managed platform (LangSmith)** for observability/eval — OSS drives adoption, the *control/observability* layer is the paid product | $125M at $1.25B (Oct 2025) ([TechCrunch](https://techcrunch.com/2025/10/21/open-source-agentic-startup-langchain-hits-1-25b-valuation/)) |
| **Databricks** | Spark OSS heritage | Lakehouse + Unity AI Gateway (multi-AI governance + cost controls) on consumption (DBUs) | $5B raise at **$190B** ([PYMNTS](https://www.pymnts.com/news/investment-tracker/2026/databricks-raises-5-billion-to-expand-enterprise-ai-agent-platform/)) |

**The pattern** `[INDUSTRY CONVENTION]`: the winning infra playbook is **open/adoptable core → paid control plane** — the thing enterprises pay for is not the runtime, it's the *governance, observability, and policy layer*. An ACP *is* that layer for agents — it starts from the paid side of the analogy.

### 4.2 Model assessment

| Model | Pros | Cons | Fit |
|---|---|---|---|
| Pure open source | Adoption, trust, standards play | No revenue engine; forks strip monetization (OpenTofu lesson) | ❌ Not standalone |
| SaaS-only | Fast land, usage-based expansion | Regulated FS/government can't put agent metadata in a vendor cloud | ⚠️ Necessary but insufficient |
| Enterprise licensing (self-hosted) | Matches how banks already buy infra; enables air-gap; largest ACVs | Slow land, heavy professional services | ✅ Core revenue engine for regulated ICP |
| Managed control plane (hybrid: vendor-managed in customer VPC) | Cloud economics + data residency; Boomi already sells agent runtime "fully behind your firewall" ([Boomi](https://boomi.com/platform/agent-control-plane/)) | Operationally heavy for a young company | ✅ The differentiator — ship from day one |

### 4.3 Recommended model & packaging `[OPINION]`

**Open core (Apache-2.0) + managed cloud + self-hosted enterprise:**

- **Open core:** agent registry, policy engine (OPA-style), audit event schema, MCP/A2A adapters — open to win the standard and the community. Keep multi-tenant SaaS management, advanced policy analytics, cost optimization, and sovereign deployment tooling proprietary.
- **Licensing caution:** avoid BSL on the core — the HashiCorp→OpenTofu saga shows BSL invites a fork precisely when the product matters. Apache-2.0 for the core; commercial license for enterprise modules (the Confluent split).
- **Plausible packaging:**
  - *Team (cloud, self-serve):* usage-based — per governed agent-run / per 1M policy evaluations, plus per-seat for operators. Entry ~$500–2K/mo (mirrors Temporal Cloud's floor).
  - *Enterprise (self-hosted or customer-VPC managed):* annual platform fee **$100K–$300K** base (Sierra-scale deals ~$150K+/yr; Terraform Enterprise enterprise contracts in this band) + consumption on governed actions.
  - *Sovereign / air-gapped:* premium uplift, contract only.
- `[ARCHITECTURAL RECOMMENDATION]` **Price the *control plane*, not the agents**: charge for governed agent-runs, policy evaluations, and audit retention — metrics that grow as the customer's agent fleet grows. This mirrors Temporal's per-action pricing and aligns vendor revenue with customer success, avoiding the "AI bill shock" backlash.

---

## 5. Competitive landscape (business lens)

There is no single "agent control plane" category yet — Gartner estimates only ~130 of the thousands of "agentic AI" vendors are real (the rest is "agent washing"). Competitors approach from six directions:

**Hyperscalers (the 800-lb risk):** AWS Bedrock AgentCore + Agent Registry (preview), Microsoft Azure Foundry Agent Service, Google (Gemini/A2A), OpenAI Frontier ("HR for AI coworkers") + Lockdown Mode. `[ESTABLISHED FACT]` Their incentive is consumption on *their* cloud — every hyperscaler control plane is cloud-scoped; none is credibly neutral. That gap is the startup's wedge. Analyst warning: parallel AWS/Azure/Google registries recreate *registry sprawl* across clouds.

**Enterprise platform incumbents (shipping "control plane" language):** Salesforce "Trusted Enterprise AI Harness" + "AI Control Plane" (GA early 2027), Databricks Unity AI Gateway, Boomi "Agent Control Plane" (observability, governance, AI gateway, lifecycle, runtime behind firewall), GitHub enterprise agent control plane (GA Feb 2026). `[OPINION]` These validate the category *and* crowd it. None is framework-neutral: each governs agents *inside its own stack*. The neutral, multi-platform control plane is still unclaimed — Boomi and Salesforce are closest.

**Agent framework / infra vendors:** Temporal ($550M at $12.55B, Sept 2026 — the execution substrate *under* agents), LangChain ($125M at $1.25B), CrewAI. Potential acquirers *or* acquirers of the layer.

**AI gateway / cost-control layer (the adjacent beachhead):** Portkey — **acquired by Palo Alto Networks** into Prisma AIRS as the "mission-critical control plane" (Nikesh Arora: "You cannot build an agentic enterprise without a **centralised control plane** to secure it"); Sapiom $35M Series A (model router cutting a customer's Anthropic bill ~10×); Portal26 $15M ("Agentic Token Controls"). `[INDUSTRY CONVENTION]` The gateway is the proven *wedge feature*: it sits in the request path (like Kong did), so routing → cost control → policy → full control plane is a natural expansion path.

**Governance / security startups:** AIR ($50M seed, agent supply-chain security), Zafran ("secure control plane for AI agents"), Vorlon (agent flight recorder), Rimini Govern for AI (managed GRC for agent fleets). `[OPINION]` These are *point* solutions (supply chain, audit, GRC services). An ACP would subsume or partner with them; the supply-chain angle (AIR) is the most differentiated and hardest to replicate.

**Analyst / buyer infrastructure:** GAI Insights 2026 Buyers' Guide evaluates 32 vendors across "agent ops and infrastructure" — the category is being formalized in procurement; IDC tracks 13 business functions in agentic AI measurement.

**Funding signal:** `[ESTABLISHED FACT]` AI companies accounted for **86% of US venture deal value in H1 2026**; control/governance-adjacent rounds are accelerating (Temporal $550M, Databricks $5B, AIR $50M seed, Sapiom $35M). `[HYPOTHESIS]` Capital is rewarding the *control* layer, not just the agent builders.

**Net assessment:** `[OPINION]` The space is *crowded at the edges, empty at the center*. Every incumbent's "control plane" is scoped to its own stack. The defensible position is the **neutral, multi-platform, multi-cloud control plane** — the "Switzerland" play — sold first as a gateway + registry + policy wedge into platform-engineering teams.

---

## 6. Deployment models — what regulated enterprises actually require

Per Scality's 2026 survey: **fully on-premises** (regulated, air-gapped), **private cloud** (enterprise-boundary multi-tenant), **sovereign AI** (jurisdictional control) — and "most production environments combine two of them."

| Model | Who requires it | Notes |
|---|---|---|
| **Managed public cloud** | Mid-market, tech, non-regulated | Default for speed; buyers demand portability clauses |
| **Customer-VPC / private cloud** | Banks, insurers, healthcare — the FS ICP | SpaceFlow deploys "in the customer's cloud or on-prem… without moving sensitive data"; the FS sweet spot |
| **Self-hosted / air-gapped** | Defense, top-tier banks, EU critical infra | Boomi sells agent runtime "fully behind your firewall"; TFE's air-gap support is the enterprise-tier differentiator |
| **Sovereign cloud** | Government, EU/UK regulated | Forrester: half of G20 to mandate domestically tuned models for public services |

`[ARCHITECTURAL RECOMMENDATION]`:

- **The 53% rule:** 53% of enterprises expect their primary agent control plane to be **hybrid** (provider-native + external orchestration) by end-2026 ([VentureBeat](https://venturebeat.com/orchestration/companies-already-run-3-agent-platforms-salesforces-new-enterprise-ai-harness-wants-govern-all-them)). Design for hybrid from day one: a single policy/audit fabric spanning cloud-managed and customer-deployed runtimes.
- **Ship three deployment artifacts from the start:** (1) managed SaaS, (2) customer-VPC deployment, (3) air-gapped self-hosted. Regulated buyers treat self-hosted as table stakes.
- **Sovereignty as a design principle:** EU AI Act enforcement is live (fines since Aug 2, 2026) — data-residency and audit-log retention are procurement checkboxes.
- `[HYPOTHESIS]` The fastest revenue path is the **managed-in-customer-VPC** model: it removes the CISO's data-residency objection while keeping the vendor's operational leverage.

---

## 7. Positioning — candidate evaluation & recommendation

**Buyer psychology:**

- **Economic buyer (CIO/CTO):** buys *platforms*, not point tools; 61% prefer known vendors; needs cross-functional alignment ([Salesforce](https://www.salesforce.com/au/news/stories/cio-trends-2026/)).
- **Co-buyer (CISO):** buys *risk reduction*; 58% of AI purchases delayed by security review ([Levelpath](https://www.businesswire.com/news/home/20260709895815/en/AI-Tops-Enterprise-Buying-Priorities-Yet-Takes-the-Longest-to-Buy-Levelpath-Research-Finds)).
- **Champion (platform engineering):** buys *operational leverage*; speaks Kubernetes/Terraform/Kafka — "control plane" is native vocabulary.
- **Analyst framing:** InfoWorld declares "we are in a **control-plane race**" ([InfoWorld](https://www.infoworld.com/article/4132451/finding-the-key-to-the-ai-agent-control-plane.html)).

**Candidate scorecard:**

| Candidate | Who it speaks to | Strengths | Weaknesses | Verdict |
|---|---|---|---|---|
| **"The control plane for enterprise AI agents"** | CIO + platform eng | Most successful enterprise-infra metaphor of the last decade; implies neutrality and cross-stack necessity; PANW's CEO independently used "centralised control plane" | Technical — needs a one-line business translation for the board | **RECOMMEND — primary** |
| **"AI Control Plane"** | Same, plus press/analyst shorthand | Category validation | Name collision: Salesforce already announced an "AI Control Plane"; GitHub uses "agent control plane" too | Use as *descriptor*, not the brand |
| **"Autonomous Workforce Platform"** | CEO/CHRO | Outcome-oriented; matches "digital workers" language | `[OPINION]` Invites labor-displacement politics and HR-owns-it confusion; what *use-case* vendors claim — an infra product wearing a workforce costume gets mis-bought | ❌ |
| **"Agent Infrastructure Platform"** | Developers, platform eng | Accurate; Temporal/LangChain-adjacent | Developer framing = smaller budgets; undersells the governance story that unlocks CISO budget | ⚠️ Good technical descriptor; weak commercially |
| **"Agent Governance Platform"** | CISO, compliance | Names the budget line; regulatory tailwinds live | Fear-based and narrow: implies a compliance tax, not an enabler; Palo Alto Networks is colonizing this exact framing via Portkey/Prisma AIRS | ⚠️ Use as a *module/pillar*, not the company |
| **"AI Operations Platform"** | ITOps | Familiar to NetOps/AIOps buyer | Collides with the existing **AIOps** category; positions the product as ops tooling, not the strategic layer | ❌ |

**Recommendation** `[OPINION]` — **Primary: "The control plane for enterprise AI agents."**

- It borrows the most trusted metaphor in enterprise infrastructure, claims neutrality across the 3.1 platforms the average enterprise already runs, and naturally contains the governance story as one pillar rather than the whole identity.
- **Messaging architecture:** Company = control plane; pillars = *Register* (agent registry/discovery), *Govern* (policy, approvals, audit), *Route* (AI gateway, cost control), *Operate* (lifecycle, observability, SLAs). The CISO hears "Govern," the CIO hears "control plane," platform engineering hears the K8s analogy.
- **Avoid** workforce framing (wrong buyer, wrong politics) and avoid leading with "governance" (cedes the enabler narrative and walks into Palo Alto Networks' kill zone).
- **Naming note:** Salesforce's "AI Control Plane" announcement (Sept 2026) means the *term* is now contested. Own the longer, more specific form — "the control plane for enterprise AI agents" — and let analysts shorten it. Consider trademark counsel on the exact mark.

---

## 8. Risks — top product/market risks

**R1. Hyperscalers build it in (highest impact).** `[ESTABLISHED FACT]` AWS (AgentCore + Agent Registry), Microsoft (Foundry Agent Service), Google (Gemini/A2A), OpenAI (Frontier + Lockdown Mode) are all shipping control-plane-adjacent features, each scoped to its own cloud.
`[HYPOTHESIS]` The mitigant is structural: hyperscalers monetize *consumption on their cloud*, so none will credibly build a neutral, multi-cloud control plane — and enterprises know it. The startup's moat is **neutrality + on-prem**, the position that let Confluent, Datadog, and Snowflake survive the cloud era. But this only holds if the product is genuinely portable; any cloud dependency in the architecture destroys the thesis.

**R2. The category may not exist as a standalone purchase.** `[ESTABLISHED FACT]` Gartner: >40% of agentic AI projects will be canceled by end-2027; only ~130 vendors are "real."
`[HYPOTHESIS]` If most pilots die, the "control plane" market is the *survivors'* market — smaller but real. Mitigant: sell the wedge that pays for itself *during* the pilot phase (gateway cost control — Sapiom's 10× bill cut is the proof point), so the product earns its keep before the fleet scales.

**R3. Open-source commoditization.** `[ESTABLISHED FACT]` Primitives are commoditizing fast: MCP went from ~3 implementations (Oct 2024) to ~7,000 (Nov 2025); LiteLLM-style routing, LangGraph orchestration, registry schemas are all open.
`[INDUSTRY CONVENTION]` The HashiCorp lesson: monetization must live in the *operational/governance* layer (policy, audit, multi-tenancy, cost analytics), not the protocol. Keep the core open to own the standard; keep the control plane commercial. BSL on the core invites an OpenTofu-style fork.

**R4. Security giants colonize the governance framing.** `[ESTABLISHED FACT]` Palo Alto Networks acquired Portkey and frames it as the "mission-critical control plane"; Zafran, AIR ($50M), Vorlon are funded; CyberArk ($25B) and Chronosphere ($3.35B) show the M&A appetite.
`[OPINION]` If the ACP leads with "governance/security," it fights PANW/CrowdStrike/Zscaler on their home turf. The control-plane/infrastructure framing (§7) is the way around, with security as a pillar, not the headline.

**R5. Token/model cost deflation compresses gateway pricing power.** `[HYPOTHESIS]` If model costs fall 10×, "cost optimization" weakens as a value prop — but governance, audit, and policy value *rises* as agents get cheaper to run (more agents → more sprawl → more need for control). Price on governed actions/policy evaluations, not on tokens saved.

**R6. Regulatory capture by standards, not products.** `[HYPOTHESIS]` EU AI Act enforcement could drive buyers toward standards-compliance tooling or auditor-led solutions rather than a product category. Mitigant: ship pre-mapped compliance evidence (the thing Rimini Govern sells as a service) as a product feature.

**R7. Execution risk: the product is genuinely hard.** `[INDUSTRY CONVENTION]` A multi-framework, multi-cloud, policy-enforcing control plane with air-gap support is a 3–5 year engineering program. The graveyard of "single pane of glass" startups is large. Mitigant: ruthless wedge sequencing — gateway + registry first (months), policy/audit second, full lifecycle later.

---

## Appendix A — Key sources (primary, in order of importance)

**Analyst / market sizing**
- Gartner: 40% of enterprise apps with task-specific agents by end-2026 — https://www.uctoday.com/unified-communications/gartner-predicts-40-of-enterprise-apps-will-feature-ai-agents-by-2026/
- Gartner: >40% of agentic AI projects canceled by end-2027 — https://www.gartner.com/en/newsroom/press-releases/2025-06-25-gartner-predicts-over-40-percent-of-agentic-ai-projects-will-be-canceled-by-end-of-2027
- AI agent statistics roundup (McKinsey, Menlo, KPMG, LangChain figures) — https://sqmagazine.co.uk/ai-agents-statistics/
- IDC Global Agentic AI Use Case Survey (Jan 2026, 13 functions) — https://my.idc.com/getdoc.jsp?containerId=US54551526

**Enterprise adoption / buyer behavior**
- VentureBeat Intelligence: 85% run 2+ agent platforms, avg 3.1; 53% expect hybrid control plane (July 2026) — https://venturebeat.com/orchestration/companies-already-run-3-agent-platforms-salesforces-new-enterprise-ai-harness-wants-govern-all-them
- Salesforce CIO Trends 2026 — https://www.salesforce.com/au/news/stories/cio-trends-2026/
- Levelpath: AI buying cycles 16–20 weeks, security review #1 delay (June 2026) — https://www.businesswire.com/news/home/20260709895815/en/AI-Tops-Enterprise-Buying-Priorities-Yet-Takes-the-Longest-to-Buy-Levelpath-Research-Finds
- Anthropic: enterprise agent adoption 2026 — https://claude.com/blog/how-enterprises-are-building-ai-agents-in-2026
- Google Cloud Business Trends 2026 (Danfoss, Macquarie, A2A) — https://blog.google/innovation-and-ai/infrastructure-and-cloud/google-cloud/ai-business-trends-report-2026/

**Competitors / funding**
- Salesforce Trusted Enterprise AI Harness + AI Control Plane — https://venturebeat.com/orchestration/companies-already-run-3-agent-platforms-salesforces-new-enterprise-ai-harness-wants-govern-all-them
- Boomi Agent Control Plane — https://boomi.com/platform/agent-control-plane/
- GitHub enterprise agent control plane (GA, Feb 2026) — https://github.blog/changelog/2026-02-26-enterprise-ai-controls-agent-control-plane-now-generally-available/
- Temporal $550M at $12.55B (Sept 14, 2026) — https://www.reuters.com/business/temporals-valuation-spikes-126-billion-lightspeed-led-funding-round-2026-09-14/
- Databricks $5B at $190B, Unity AI Gateway — https://www.pymnts.com/news/investment-tracker/2026/databricks-raises-5-billion-to-expand-enterprise-ai-agent-platform/
- Palo Alto Networks acquiring Portkey — https://www.prnewswire.com/news-releases/palo-alto-networks-to-acquire-portkey-to-secure-the-rise-of-ai-agents-302759436.html
- AIR $50M seed (agent supply-chain security) — https://www.pymnts.com/news/investment-tracker/2026/ai-agent-security-startup-air-raises-50-million-to-guard-enterprise-supply-chains/
- LangChain $125M at $1.25B — https://techcrunch.com/2025/10/21/open-source-agentic-startup-langchain-hits-1-25b-valuation/

**Caveats:** pricing figures for Sierra/Agentforce come from a vendor comparison blog (indicative only); vendor ARR claims are vendor-reported; Gartner's 40%-cancellation prediction dates to June 2025 and predates the 2026 production wave.
