# Security Architecture, Threat Model, Multi-Tenancy & Governance

**Research stream 3 of 3 — Agent Control Plane (ACP) deep research**
**Date:** 2026-09-14 · **Status:** Research findings, not implementation
**Scope:** Security architecture, agent-specific defenses, policy/permission/risk design, formal threat model, multi-tenancy, failure model (fail-closed), audit ledger, governance constraints for the build.

## Claim legend

Every substantive claim is tagged:

- **[FACT]** — verifiable from a cited primary source.
- **[CONVENTION]** — widely practiced industry pattern, not a formal standard.
- **[REC]** — architectural recommendation derived from this research for the ACP build.
- **[HYP]** — hypothesis: plausible but not yet validated; needs prototyping or more evidence.
- **[OP]** — opinion of the researcher where evidence is mixed.

---

## 1. Security architecture

### 1.1 Design stance: zero trust, agent-first

**[FACT]** Zero-trust principles — never trust, always verify; assume breach; verify explicitly with least-privilege access — are the dominant enterprise security posture, and identity-based (not network-location-based) access is its core mechanism. SPIFFE/SPIRE exists precisely because IP-based security fails in dynamic environments and shared secrets don't scale. [\[RedHat\]](https://www.RedHat.com/en/topics/security/spiffe-and-spire) [\[AWS\]](https://aws.amazon.com/blogs/containers/implement-spiffe-spire-authorization-on-amazon-eks/)

**[REC]** The ACP must be designed zero-trust from day one, with one critical extension over classic zero trust: **agents are a new class of security principal, not just "workloads."** A workload identity answers "which software is calling"; an agent identity must additionally answer "on whose behalf, with what delegated authority, under which policy, toward which goal." The control plane issues and brokers *scoped, short-lived, purpose-bound* credentials to agents; agents never hold standing credentials.

This directly implements the master prompt's hard constraint: **agents must NEVER inherit unlimited authority from the human user.**

### 1.2 Identity architecture

Four distinct principal types, each with its own identity system. Conflating them is the root cause of "identity and privilege abuse" in the OWASP agentic top 10. [\[OWASP/Tenable\]](https://www.tenable.com/blog/cybersecurity-snapshot-owasp-agentic-ai-top-10-mitre-dangerous-software-weaknesses-12-12-2025)

| Principal | Identity mechanism [REC] | Notes |
|---|---|---|
| Human user | OIDC (enterprise IdP: Okta/Entra/Google) → short-lived access token | Standard. Human authenticates once; everything downstream is delegation. |
| Agent instance | SPIFFE ID, e.g. `spiffe://acp/tenant/{t}/agent/{name}/{version}` + JWT-SVID or X.509-SVID | [FACT] SPIFFE IDs are URIs embedded in SVIDs (X.509 or JWT); SPIRE attests workload + node before issuance and rotates automatically. [\[RedHat\]](https://www.RedHat.com/en/topics/security/spiffe-and-spire) Gives every agent run a cryptographic identity without long-lived secrets ("secret zero" solved). |
| Delegated authority (user→agent) | Constrained delegation token: OAuth 2.1 token exchange pattern (RFC 8693-style `act`/`may_act` claims), scoped to task, tools, time, and tenant | The agent's *authority* is not its identity. Authority = identity + policy decision + delegation token. Tokens are audience-bound (RFC 8707 resource indicators) and single-purpose. |
| Tool / downstream service | The tool's own auth, reached only via brokered credentials the agent never sees (see §1.4) | MCP servers are OAuth Resource Servers per the MCP spec. [\[Auth0\]](https://auth0.com/blog/mcp-specs-update-all-about-auth/) |

**Caveats on SPIFFE/SPIRE [FACT]:** Palo Alto Unit 42 (Sept 2026) demonstrated that if an attacker gains root on a node, they can harvest SVIDs of workloads on that node via selector spoofing; mitigations are node hardening, no privileged containers, minimal weak selectors. [\[Unit42\]](https://unit42.paloaltonetworks.com/kubernetes-spiffe-spire-identity-spoofing/) **[REC]** For the ACP: run agent sandboxes as unprivileged, use strong attestation selectors, and treat node compromise as in-scope in the threat model (§4). SPIRE is recommended for production deployments, but the MVP can use a simpler internal CA + JWT issuer behind the same `AgentIdentity` interface — identity *issuance* is an adapter, identity *semantics* (SPIFFE ID format, SVID-shaped tokens) are core.

### 1.3 Authentication & transport

- **[REC]** mTLS between all control-plane components (API, workers, policy engine, state store), with SPIFFE X.509-SVIDs as client certificates where SPIRE is deployed. This is [CONVENTION] in service meshes and what SPIFFE/SPIRE is designed for. [\[AWS\]](https://aws.amazon.com/blogs/containers/implement-spiffe-spire-authorization-on-amazon-eks/)
- **[REC]** Public API surface (agent/task/approval APIs) uses OAuth 2.1 / OIDC with PKCE; MCP-facing endpoints follow the MCP authorization spec (MCP servers as OAuth Resource Servers, protected-resource metadata at `/.well-known/oauth-protected-resource`). [FACT] This is the spec direction since June 2025, with issuer verification mandated and Dynamic Client Registration deprecated in favor of Client ID Metadata Documents. [\[Auth0\]](https://auth0.com/blog/mcp-specs-update-all-about-auth/) [\[SecurityOnline\]](http://securityonline.info/mcp-protocol-stateless-update/)
- **[REC]** Inter-agent communication must be authenticated and integrity-protected (OWASP lists "insecure inter-agent communication" in the 2026 top 10: spoofed/intercepted messages can misdirect whole agent clusters). [\[OWASP/Tenable\]](https://www.tenable.com/blog/cybersecurity-snapshot-owasp-agentic-ai-top-10-mitre-dangerous-software-weaknesses-12-12-2025) Every inter-agent message carries sender SVID, tenant scope, and a nonce/sequence; the control plane is the message bus, not peer-to-peer.

### 1.4 Delegation & credential isolation (the anti-"confused deputy" core)

This is the single most important security mechanism in the ACP. The failure it prevents is the **confused deputy**: an agent tricked (via prompt injection) into using its authority against the user's interests.

**[REC] Five rules:**

1. **No ambient authority.** An agent process holds zero standing credentials — no API keys, no user tokens, no DB passwords in its environment. All authority arrives per-action, just-in-time, from the control plane.
2. **Constrained delegation.** When a user asks an agent to act, the control plane mints a delegation token encoding: `subject=user`, `actor=agent-id`, `scope={tools, actions, resources}`, `tenant`, `expiry≤task window`, `audience=specific tool`. This mirrors the OAuth token-exchange delegation pattern and the MCP Enterprise-Managed Authorization (EMA) model, which replaced per-user OAuth consent loops with IdP-mediated delegation (stable June 2026). [\[TechTimes\]](https://www.techtimes.com/articles/318708/20260619/mcp-enterprise-authorization-goes-stable-zero-touch-sso-okta-anthropic-vs-code.htm)
3. **Credential brokering, not credential passing.** [CONVENTION] HashiCorp Boundary + Vault pattern: the broker injects credentials at session/use time; the requester never sees them. [\[HashiCorp\]](https://developer.hashicorp.com/vault/tutorials/cross-products/community-vault-cred-brokering-quickstart) **[REC]** The ACP's tool-gateway holds the actual tool credentials; the agent asks the gateway to *invoke* the tool, and the gateway attaches the credential server-side. The agent's context window never contains a secret. (A leaked prompt/trace then leaks no credentials.)
4. **Dynamic, short-lived secrets.** Where the agent runtime itself needs a secret (e.g., a DB handle for a code-execution sandbox), mint just-in-time credentials with 5-minute leases and immediate revocation — the Vault dynamic-secrets pattern, demonstrated working with SPIFFE-authenticated workloads. [\[vault-spiffe\]](https://github.com/darthvaderrc/vault-spiffe)
5. **Downward-only, narrowing delegation.** A delegated token can only *narrow* scope, never widen it; delegation chains are recorded in the audit ledger so every action traces to a human principal.

### 1.5 Secrets management

- **[REC]** Core abstraction: a `SecretBroker` interface (issue, lease, revoke, rotate). Production adapter: HashiCorp Vault (dynamic secrets, SPIFFE auth method). Local/dev adapter: encrypted file-backed broker (never plaintext `.env` in the repo; provide `.env.example` only).
- **[FACT]** Vault supports SPIFFE X.509-SVID as an auth method and issues dynamic DB credentials with leases — this is a proven integration path, not a hypothesis. [\[vault-spiffe\]](https://github.com/darthvaderrc/vault-spiffe)
- **[CONVENTION]** Never commit secrets; scan in CI (gitleaks/trufflehog equivalents); separate KMS-encrypted data keys per tenant (§5).

### 1.6 Encryption

- **[REC]** TLS 1.2+ everywhere (1.3 preferred); mTLS internally (§1.3).
- **[REC]** Encryption at rest with per-tenant data keys (envelope encryption via KMS adapter). Per-tenant keys matter for the "right to be forgotten" and tenant offboarding: deleting a tenant's key cryptographically shreds its data even in shared storage — a standard SaaS practice. [\[AWS MSK tenancy\]](https://aws.amazon.com/blogs/big-data/stream-multi-tenant-data-with-amazon-msk/)
- **[REC]** Field-level encryption for the audit ledger's sensitive fields and for memory entries containing PII/secrets (decrypt only inside policy-approved contexts).
- **[HYP]** Confidential computing (TEEs — Intel TDX, AMD SEV-SNP, NVIDIA H100 CC, Google Confidential Space with remote attestation) as an *optional* deployment tier for regulated tenants who need "data in use" protection and attested agent runtimes. [FACT] The technology is GA on major clouds and attestation-based key release is a proven pattern. [\[Google Confidential Space\]](https://docs.cloud.google.com/docs/security/confidential-space) [\[NVIDIA\]](https://developer.nvidia.com/blog/confidential-computing-on-h100-gpus-for-secure-and-trustworthy-ai/?ncid=so-link-394138) **[OP]** Don't build the MVP around TEEs; make the execution-plane sandbox interface attestation-capable so TEEs can be slotted in later.

### 1.7 Network, egress & execution sandboxing

Agents with network access and code execution are the highest-risk combination (OWASP "unexpected code execution": natural-language control of actions opens avenues to run malicious code on the host). [\[OWASP/Tenable\]](https://www.tenable.com/blog/cybersecurity-snapshot-owasp-agentic-ai-top-10-mitre-dangerous-software-weaknesses-12-12-2025)

**[REC] Execution plane sandboxing tiers:**
- **Default:** unprivileged containers, no host mounts, seccomp/AppArmor profiles, read-only rootfs.
- **Code execution:** gVisor/Firecracker-class microVM isolation per task (blast-radius = one task). No persistent identity inside the sandbox; credentials arrive via broker only.
- **Egress control:** default-deny egress proxy with per-tool allowlists (domain/IP + port). The agent cannot reach the open internet unless a policy explicitly allows a browsing tool, and then only through the filtering proxy (which also feeds the DLP layer, §1.8). DNS exfiltration filtering at the proxy.
- **Kubernetes network policies** (or security-group equivalents) segment control plane / execution plane / data plane; agent sandboxes cannot reach the control-plane API except through the authenticated task channel.

### 1.8 DLP / data boundaries

- **[REC]** Classify data (public / internal / confidential / restricted) at ingestion; tag memory, knowledge, and tool schemas with classification. The policy engine denies or redacts cross-boundary flows (e.g., restricted data → external SaaS tool, or → model provider without tenant consent).
- **[REC]** Egress inspection on agent outputs: pattern/PII redaction, and blocking of known-secret shapes (keys, tokens) before tool calls and before model calls (prevents training-data contamination via third-party providers).
- **[CONVENTION]** This is the "prompt firewall / AI gateway DLP" pattern now common in enterprise LLM gateways — recommended as an enforcement point in the governance rail, not inside each agent.

### 1.9 Supply-chain security

OWASP 2026 lists "agentic supply chain vulnerabilities": compromised third-party components, libraries, or datasets poisoning the agent runtime. [\[OWASP/Tenable\]](https://www.tenable.com/blog/cybersecurity-snapshot-owasp-agentic-ai-top-10-mitre-dangerous-software-weaknesses-12-12-2025)

**[REC]**
- Pin and sign everything: agent definitions, tool schemas, MCP server binaries, policy bundles. Verify signatures at load time (Sigstore-style signing; SLSA provenance for built artifacts).
- MCP/tool registry entries carry provenance: publisher identity, version, checksum, vulnerability-scan status. The router refuses unsigned or revoked tools (fail closed).
- Treat datasets/prompts/memory snapshots as supply-chain artifacts too: version them, hash them, and record their provenance in the audit ledger (defends against memory poisoning via tainted imports).

### 1.10 Core platform vs integration adapters

| Belongs in CORE (must exist even in MVP) | Belongs in ADAPTERS (swappable integrations) |
|---|---|
| Identity *semantics*: SPIFFE-ID format, SVID-shaped tokens, delegation-token claims schema | Identity *issuance*: SPIRE, internal CA, enterprise IdP (OIDC) |
| Policy *decision point* interface + policy-before-execution enforcement | Policy *engine*: OPA/Rego (recommended), Cedar, custom |
| Credential *brokering* interface (issue/lease/revoke, never expose) | Secret *store*: Vault, cloud KMS/Secrets Manager, dev file broker |
| Audit event *schema* + hash-chained append-only writer | Audit *sink*: Postgres, WORM object storage, SIEM forwarder |
| Egress *policy* model (allowlist per tool/tenant) | Egress *proxy* implementation |
| Tool *registry schema* incl. risk classification + signature verification | Specific tools / MCP servers |
| Tenant isolation *model* (ids, RLS, key separation) | Specific IdP, KMS, region topology |
| Sandboxing *interface* (tiers, attestation hooks) | gVisor/Firecracker/TEE runtimes |

**[OP]** The moat is not any single integration — it's the coherent identity→policy→delegation→audit chain. Every adapter must be replaceable without changing that chain's semantics.

## 2. Policy, permission & risk design

### 2.1 Policy engine: policy-as-code

**[REC] Use OPA/Rego as the policy engine (embedded or sidecar), not a bespoke DSL for the MVP.** Rationale:

- **[FACT]** OPA/Rego is the industry-standard policy-as-code engine (CNCF graduated), used for Kubernetes admission control (Gatekeeper), microservice authorization, and CI policy — i.e., exactly the "admission controller for agent actions" role the master prompt envisions.
- Policies become versioned, reviewable, testable artifacts (`policy allow/deny/require_approval { ... }`), which the audit ledger can reference by hash — "which policy decided" becomes a content address, not a log line.
- Decision latency: OPA evaluates in microseconds-to-milliseconds for typical policies; embed as a library for the hot path (tool-call authorization), sidecar for management-plane policy distribution.
- **[OP]** Don't build a custom policy language. The failure mode of custom DSLs is an untested, unaudited shadow authorization system. Rego's learning curve is real but cheaper than a novel engine's risk.

**Policy model [REC]:** four decision outcomes — `allow`, `deny`, `require_approval` (with approval tier: self/peer/human/multi-person), `allow_with_constraints` (e.g., redacted, budget-capped, read-only). Every evaluation emits a `PolicyEvaluated` event with policy version hash, inputs digest, and decision — this is what makes "policy before execution" auditable.

**Policy layering [REC]:**
1. **Platform guardrails** (shipped, signed, non-overridable by tenants): e.g., "no destructive prod actions without human approval," "no credential exfiltration," "kill-switch authority."
2. **Tenant policies** (tenant admins, versioned, change-audited): data-residency rules, approved model lists, spend caps, tool allowlists.
3. **Task-scoped constraints** (from delegation token + risk engine): narrowed per task.

Deny-by-default: if no policy explicitly allows, the decision is `deny` (fail closed, §6). Platform guardrails override tenant policies on conflict.

### 2.2 Permission engine: RBAC + ABAC hybrid, least privilege

**[REC]** Neither pure RBAC nor pure ABAC is sufficient:

- **RBAC** for coarse, human-manageable roles: `platform_admin`, `tenant_admin`, `agent_operator`, `approver`, `auditor`, `viewer`. [CONVENTION] This matches how enterprises already think (Kubernetes RBAC analogy in the master prompt).
- **ABAC** for the decisions RBAC can't express: agent identity + tool risk class + data classification + tenant + time window + risk score + delegation scope. Example: `allow(tool.invoke) IF agent.clearance ≥ data.classification AND tool.risk ≤ agent.max_risk AND delegation.scope CONTAINS tool.id`.
- **ReBAC** (relationship-based, e.g., "agent owned by team X can read knowledge owned by team X") as a later V1 addition; skip in MVP.

**Least-privilege mechanics [REC]:**
- Tool permissions are per-agent-version grants, not per-agent-type: upgrading an agent's capabilities requires re-approval (prevents privilege creep via "helpful" capability additions).
- **Temporary credentials only** (§1.4): grants are leases, not entitlements; the permission engine continuously re-evaluates (revocation propagates within seconds via lease expiry + event fan-out).
- **No inheritance from the user:** the agent's effective permission set = intersection(user's delegable permissions, agent's granted permissions, task scope, policy decision). The agent can never exceed the *least* of these. This is the formal answer to the master prompt's "agents NEVER automatically inherit unlimited authority."

### 2.3 Risk engine: hybrid deterministic + model-based

**[REC] Hybrid, exactly as the master prompt suggests — but with a strict division of labor:**

- **Deterministic rules (the floor):** risk *factors* that are always true regardless of context — destructive action, external side effect, financial transaction, irreversible operation, privilege escalation, cross-tenant data movement. These map to risk-score contributions and hard triggers (e.g., any financial transaction > threshold ⇒ `require_approval`). Deterministic, explainable, testable.
- **Model-based scoring (the refinement):** an ML/statistical scorer adjusts within guardrails for context the rules can't see — anomaly vs. the agent's historical behavior, data-sensitivity inference, novel tool-combination risk. The model can *raise* risk (triggering approval) but can never *lower* risk below the deterministic floor, and can never approve what a rule denies. **[OP]** This asymmetry is the key safety property: ML proposes caution, rules impose it.
- **Output:** `{risk_score, risk_level, requires_human_approval, reasons[]}` per the master prompt's schema, plus `policy_refs[]` and `score_breakdown` (which factors contributed — needed for audit and for the approval UX).
- **[HYP]** Risk scores should decay with successful, uneventful executions of the same action pattern (building justified trust) but reset on any anomaly, tool change, or policy change. Needs careful design to avoid "boiling frog" privilege creep; the deterministic floor prevents silent decay into danger.

### 2.4 Policy-before-execution: enforcement points

**[REC]** Policy evaluation must be a *choke point*, not advice. Enforcement points (each fail-closed):

1. **Task admission** (task creation): is this agent allowed to pursue this goal in this tenant?
2. **Plan approval** (planner output): does the plan's tool set, cost estimate, and risk profile comply? High-risk plans ⇒ human approval before any execution.
3. **Tool invocation** (every tool call): the hot path — identity + delegation + policy + risk, then broker credential and invoke. Cache decisions only within tight TTLs and invalidate on policy/grant change.
4. **Data egress** (tool outputs, model calls, inter-agent messages): classification check + DLP.
5. **Memory/knowledge write:** provenance check (who/what wrote this, is the source trusted?).
6. **Learning/promotion** (feedback loop): any model/policy/prompt change proposed by the learning loop re-enters as a *change request* subject to policy + human approval (§8).

**[FACT]** This mirrors the Kubernetes admission-controller pattern (validating/mutating webhooks that can deny a pod before it runs) — the analogy the master prompt asks to test holds *here*: policy engine : admission controller is a sound mapping. What breaks down is that agent "admission" must happen per-action at runtime, not just at deploy time, because agent behavior is non-deterministic.

## 3. Agent-specific defenses

Context: OWASP's *Top 10 for Agentic Applications 2026* (released Dec 2026... Dec 2025, developed with 100+ industry experts) names the canonical threat set: agent goal hijack, tool misuse/exploitation, identity & privilege abuse, agentic supply-chain vulnerabilities, unexpected code execution, memory/context poisoning, insecure inter-agent communication, cascading failures, human-agent trust exploitation, rogue agents. [\[OWASP\]](https://genai.owasp.org/2025/12/09/owasp-genai-security-project-releases-top-10-risks-and-mitigations-for-agentic-ai-security/) [\[Tenable\]](https://www.tenable.com/blog/cybersecurity-snapshot-owasp-agentic-ai-top-10-mitre-dangerous-software-weaknesses-12-12-2025) The defenses below map to each.

### 3.1 Direct prompt injection

**[FACT]** Direct injection ("ignore previous instructions") remains effective, and purely model-level defenses are unreliable: the CaMeL paper (Debenedetti et al., 2025) found that GPT-4o-mini — which ships OpenAI's instruction-hierarchy defense — was still vulnerable to 276 attacks in the AgentDojo benchmark, while the same model under CaMeL's architectural isolation resisted all of them. [\[CaMeL\]](https://arxiv.org/pdf/2503.18813v2)

**[REC] Defense in depth, ordered by strength:**
1. **Architectural isolation (strongest):** separate trusted planning from untrusted data — CaMeL-style explicit control/data-flow separation with formal policies over tool calls, so untrusted content *cannot* alter control flow regardless of what the model "believes." [\[CaMeL\]](https://arxiv.org/pdf/2503.18813v2)
2. **Privilege separation (dual-agent):** a *reader* agent (can see untrusted content; has no tools, no memory write) summarizes for an *executor* agent (has tools; never sees raw external content). [CONVENTION] widely recommended pattern.
3. **Instruction hierarchy + spotlighting/datamarking** as *defense-in-depth only*: mark untrusted content (e.g., delimiters, data-marking transforms from Hines et al. 2024) and declare system > user > tool-output > external-content precedence — but never rely on them alone, per the empirical results above. [\[awesome-ipi-defense\]](https://github.com/Rem1L/awesome-ipi-defense)
4. **Input/output filtering:** heuristic + classifier-based detection on the way in (D1/D2 in the community taxonomy) and egress filtering on the way out (block tool calls or exfiltration-shaped outputs the task didn't authorize).

**[OP]** The ACP's stance should be: *the model is never the security boundary.* Every security property must hold even if the model is fully compromised — enforced by the control plane around it. This is the single sentence the whole architecture should be judged against.

### 3.2 Indirect prompt injection (the hardest problem)

**[FACT]** Indirect injection — malicious instructions hidden in retrieved documents, web pages, tool outputs, calendar invites, i.e., content the user never sees — is the most dangerous class for RAG/agents because it bypasses user scrutiny entirely. The research community's 2026 direction includes temporal-causal diagnostics, instruction-authentication middleware, and KV-cache separation of trusted/untrusted context. [\[awesome-ipi-defense\]](https://github.com/Rem1L/awesome-ipi-defense)

**[REC] Layered controls, mapped to the ACP:**
- **Provenance tagging:** every piece of external content entering the system carries `{source, trust_level, retrieved_at, hash}`. The planner and policy engine see provenance; the model sees content. Tool outputs derived from untrusted sources inherit the lowest trust of their inputs (taint tracking, lightweight version).
- **Quarantine pattern:** untrusted content is processed by a minimally-privileged reader (no tools); only structured, validated extracts cross into the privileged context. [CONVENTION]
- **Tool-call policy binding:** tool invocations proposed on the basis of untrusted content require explicit policy evaluation with the *content's* trust level as an input — high-impact actions from low-trust content ⇒ human approval (this is where §2.4's enforcement point #3 earns its keep).
- **Spotlighting/datamarking** on untrusted spans so accidental instruction-following is reduced (weak alone, useful in combination). [\[MDPI Spotlight-Guard\]](https://www.mdpi.com/2076-3417/16/15/7662/pdf)
- **[HYP]** Cryptographic content authentication for high-value sources (signed feeds, verified publishers) so the policy engine can distinguish "untrusted web" from "trusted-but-external." Needs ecosystem support; design the provenance field to carry it.

### 3.3 Tool poisoning & compromised MCP servers

**[FACT]** The NSA's May 2026 analysis of MCP found: authorization in MCP is *optional* (not every implementation uses it); servers rely on OAuth-style bearer tokens without protocol-level token lifecycle management (refresh/revocation/reuse unspecified); idempotency is not enforced. A previously-benign approved MCP service can later access sensitive resources without triggering review. [\[NSA\]](https://www.nsa.gov/Portals/75/documents/Cybersecurity/CSI_MCP_SECURITY.pdf?ver=bmgiSbNQLP6Z_GiWtRt6bg%3D%3D) (URL as published by NSA.)

**[FACT]** The spec has hardened substantially: MCP servers are OAuth Resource Servers (June 2025), clients must verify issuer and bind credentials per-authorization-server (mitigating mix-up attacks), Dynamic Client Registration is deprecated for Client ID Metadata Documents, and Enterprise-Managed Authorization reached stable in June 2026. [\[Auth0\]](https://auth0.com/blog/mcp-specs-update-all-about-auth/) [\[TechTimes\]](https://www.techtimes.com/articles/318708/20260619/mcp-enterprise-authorization-goes-stable-zero-touch-sso-okta-anthropic-vs-code.htm)

**[REC] ACP tool-registry security rules:**
1. **Authenticate every MCP server** the ACP talks to (no anonymous tool servers in enterprise tiers); require OAuth 2.1, issuer verification, audience-bound tokens.
2. **Treat all tool outputs as untrusted input** (§3.2) — even from authenticated servers (server compromise ≠ auth failure).
3. **Tool vetting at registration:** signature verification, publisher identity, version pinning, schema allowlisting (the agent can only call declared tools with validated arguments — no free-form tool invention), risk classification per tool, and *tool description sanitization* (descriptions are a known injection vector — render them as data, and diff them on update; a changed description re-triggers review).
4. **Per-tenant tool allowlists** and **runtime behavior monitoring** (a tool that suddenly returns anomalous payloads or requests new scopes gets quarantined).
5. **Idempotency keys** on all side-effecting tool calls (compensates for the MCP spec gap the NSA identified).

### 3.4 Excessive agency prevention

**[REC]** Agency must be *granted*, not assumed (master prompt principle). Mechanisms:
- **Capability budgets:** each task grants a bounded set of tools, a max iteration count, a max spend, and a max blast radius (which systems, which data classes). The planner must declare what it needs; the policy engine grants the minimum.
- **Progressive authorization:** read-only reconnaissance is cheap to authorize; the first *write/external/destructive* action in a task re-enters policy evaluation and (per risk) human approval.
- **No self-escalation:** an agent cannot grant itself new tools, extend its own lease, or approve its own actions — approval authority always sits outside the agent being approved (separation of duties, [CONVENTION] from financial controls).

### 3.5 Memory & context poisoning

OWASP 2026: attackers can corrupt long-term memory to influence future behavior. [\[OWASP/Tenable\]](https://www.tenable.com/blog/cybersecurity-snapshot-owasp-agentic-ai-top-10-mitre-dangerous-software-weaknesses-12-12-2025)

**[REC]**
- **Write provenance:** every memory entry records `{writer_agent_id, source_trust, task_id, timestamp, hash}`; entries derived from untrusted content are tagged and quarantined from high-stakes retrieval.
- **Tenant-scoped memory** with no cross-tenant retrieval, ever (§5).
- **Signed snapshots:** memory checkpoints are hash-chained (same construction as the audit ledger, §7) so tampering is detectable; restore = verify-then-load.
- **Anomaly detection on writes:** sudden bulk writes, writes contradicting established facts, or writes from compromised-task contexts trigger quarantine + review.
- **Retention & deletion:** lifecycle policies (TTL, tenant deletion ⇒ cryptographic erasure via key destruction) — also a GDPR-style compliance requirement.

### 3.6 Insecure inter-agent communication

**[REC]** All inter-agent messages flow through the control-plane bus (no direct agent-to-agent network paths): authenticated sender (SVID), tenant scope check, schema validation, content provenance preserved, and every message hash-logged to the audit ledger. This kills spoofing, interception-driven misdirection, and gives a single point for policy enforcement. [FACT] OWASP flags unverified inter-agent messaging as a top-10 risk precisely because it enables cluster-wide misdirection. [\[OWASP/Tenable\]](https://www.tenable.com/blog/cybersecurity-snapshot-owasp-agentic-ai-top-10-mitre-dangerous-software-weaknesses-12-12-2025)

### 3.7 Cascading failures

**[REC]** Bulkheads and circuit breakers between agents: per-agent error budgets, backoff with jitter, dependency timeouts, and a "poison pill" protocol — if an agent's outputs fail validation N times, the orchestrator quarantines it and re-plans without it rather than propagating its outputs downstream. Workflow-level: compensation/rollback for multi-step tasks (the workflow engine's job, coordinated with the audit ledger for exactly-once accounting).

### 3.8 Human-agent trust exploitation

OWASP 2026: agents generate polished, confident explanations that mislead operators into approving dangerous actions. [\[OWASP/Tenable\]](https://www.tenable.com/blog/cybersecurity-snapshot-owasp-agentic-ai-top-10-mitre-dangerous-software-weaknesses-12-12-2025)

**[REC] Approval UX requirements (governance rail):**
- Approvals show **raw evidence**, not the agent's summary: the exact tool call, arguments, target, irreversible-effects warning, risk-score breakdown, and policy citations.
- **Mandatory deliberation delay** for high-risk approvals (no one-click approve on $25k payments).
- **Multi-person approval** above thresholds; **role-based approver eligibility** (can't approve your own agent's request).
- Approval decisions are themselves audit events with the approver's identity — accountability closes the loop.

### 3.9 Rogue agents & runaway loops

**[REC]**
- **Watchdogs:** max wall-clock time, max iterations, max tokens, max spend per task/agent/tenant — hard stops, not warnings.
- **Behavioral tripwires:** loop detection (repeated identical tool calls), goal-drift detection (plan divergence beyond threshold ⇒ re-plan or escalate), and a control-plane **kill switch** per agent/task/tenant that revokes credentials and freezes sandboxes within seconds.
- **Fail closed on watchdog breach:** a timed-out agent doesn't get to finish "one last tool call."

### 3.10 Cost attacks

**[REC]** Treat cost as a security boundary, not just FinOps: per-task/agent/tenant/model budget envelopes enforced at the tool-invocation choke point (§2.4 #3); real-time metering with alerts at 50/80/95%; hard deny at 100% (fail closed). An attacker (or a bug) that tries to burn $100k in tokens hits the same wall as a policy denial — and it's audit-logged as a security event (`CostThresholdExceeded`), not just a billing line.

### 3.11 Model manipulation & supply chain

Covered in §1.9 (signed/pinned artifacts) plus: **model allowlisting** per tenant (only approved model IDs routable), **output verification** for high-stakes tasks (second-model or deterministic checker), and **prompt/version pinning** — system prompts are versioned artifacts; an unapproved prompt change is a security event, not a config tweak.

## 4. Formal threat model

Likelihood/Impact are qualitative **architectural judgments [OP]** for a typical enterprise deployment (calibrated against OWASP 2026 prevalence notes and the NSA MCP analysis). Re-rate per deployment during implementation.

| # | Threat | Likelihood | Impact | Mitigation (primary) | Detection | Recovery |
|---|---|---|---|---|---|---|
| T1 | **Malicious user** — legitimate tenant user weaponizes agents (data theft, harassment, fraud) | High | High | Tenant-scoped least privilege; tool allowlists; DLP egress; content policies; no cross-tenant reach | Audit ledger anomaly rules; approval-tier triggers; user behavior baselines | Revoke user + agent grants; quarantine tasks; forensic export of tenant audit chain |
| T2 | **Compromised agent** — attacker hijacks an agent's context/plan (via injection or stolen delegation token) | High | High | No ambient authority (§1.4); short-lived scoped tokens; per-action policy evaluation; sandboxing | Goal-drift detection; tool-call anomaly vs. plan; risk-score spikes | Kill switch; revoke delegation chain; re-plan from last verified checkpoint |
| T3 | **Malicious tool / tool poisoning** — tool schema/description smuggles instructions or exfiltrates args | Medium | High | Registry vetting + signatures; schema allowlisting; description sanitization + diff-on-update; args never contain secrets (brokering) | Tool-output validation; payload anomaly detection; honeypot canary args | Quarantine tool registry-wide; revoke its grants; rotate any exposed credentials |
| T4 | **Compromised MCP server** — trusted server turns hostile or is breached | Medium | High | Authenticated MCP (OAuth 2.1, issuer verification); treat outputs as untrusted (§3.3); per-tenant allowlists; idempotency keys | Behavior-change monitoring; scope-request anomalies; attestation failures | Quarantine server; fail over to alternate tool; replay-safe re-execution from checkpoint |
| T5 | **Direct prompt injection** | High | Medium | Architectural isolation (CaMeL-style); privilege separation; input/output filtering (§3.1) | Injection-pattern detectors; dual-LLM disagreement | Discard tainted context; re-issue task with quarantined reader |
| T6 | **Indirect prompt injection** (via RAG, web, tool outputs, memory) | High | High | Provenance tagging + taint tracking; quarantine pattern; trust-weighted tool authorization (§3.2) | Provenance anomaly (low-trust content driving high-impact actions); canary markers | Purge tainted context/memory entries; human review of affected tasks |
| T7 | **Data exfiltration** — via tool args, model calls, DNS, multi-modal outputs | Medium | Critical | DLP egress inspection; classification-tagged flows; default-deny egress proxy; brokered credentials (§1.7–1.8) | Egress anomaly; classification-violation alerts; token-flow accounting | Revoke grants; key rotation; breach notification workflow; ledger forensics |
| T8 | **Credential theft** — from agent context, traces, memory, or logs | Medium | Critical | Agents never see raw secrets (§1.4); dynamic short-lived creds; field-level encryption; PII/secret redaction pre-write | Secret-shape scanning in traces/logs; unexpected credential-use alerts | Immediate revocation + rotation; lease-expiry bounds blast radius to minutes |
| T9 | **Privilege escalation** — agent widens its own authority | Medium | Critical | Downward-only delegation; no self-grant; per-action re-evaluation; platform guardrails non-overridable (§2.2) | Grant-change audit alerts; scope-widening attempt = security event | Revoke to last-known-good grants; human re-authorization required |
| T10 | **Tool poisoning** (supply-chain variant: poisoned tool *distribution*) | Low–Med | High | Signed registry; SLSA provenance; version pinning; publisher identity (§1.9) | Signature-verification failures; checksum drift on update | Roll back to last signed version; registry-wide quarantine |
| T11 | **Model manipulation** — backdoored/poisoned model or prompt | Low | High | Model allowlisting; prompt versioning; output verification for high-stakes tasks (§3.11) | Eval regressions; output-distribution drift | Swap to alternate approved model; invalidate affected task outputs |
| T12 | **Supply-chain attack** (libraries, base images, datasets, policies) | Medium | High | Signed artifacts; SBOM; image scanning; policy-bundle signatures; provenance in ledger (§1.9) | CI signature/scan gates; runtime attestation mismatch | Pin to last-good; rebuild from signed sources; rotate affected keys |
| T13 | **Runaway agent** — infinite/degenerate loops, goal thrash | Medium | Medium | Watchdogs: iteration/time/token/spend caps; loop detection; kill switch (§3.9) | Tripwire alerts; cost-velocity anomalies | Kill + checkpoint; human decides resume vs. abort |
| T14 | **Denial of service** — resource exhaustion (own agents or external) | Medium | Medium | Per-tenant quotas; rate limits; bulkheads; sandbox resource caps | Saturation metrics; queue-depth alerts | Shed load per policy; scale execution plane; tenant throttling |
| T15 | **Cost attack** — token/compute burn (malicious or bug) | Medium | High | Budget envelopes at invocation choke point; hard deny at 100% (§3.10) | 50/80/95% alerts; velocity anomalies | Freeze spend; human re-authorization; attribute cost in ledger |
| T16 | **Cross-tenant data leakage** — via shared models, memory, logs, or side channels | Low–Med | Critical | Tenant IDs in every row (RLS); per-tenant keys; tenant-scoped memory; no shared mutable caches across tenants (§5) | Cross-tenant access-attempt alerts (should be *impossible*, so any attempt = critical) | Key destruction for affected tenant data; forensic audit; notification |
| T17 | **Memory/context poisoning** (persistent influence) | Medium | High | Write provenance; signed hash-chained memory; quarantine of low-trust writes (§3.5) | Write-anomaly detection; fact-contradiction checks | Roll back to signed snapshot; purge tainted entries |
| T18 | **Insecure inter-agent communication** — spoofing/interception | Medium | High | Control-plane message bus; SVID-authenticated senders; schema validation (§3.6) | Signature/sequence failures | Rekey bus credentials; replay from ledger |
| T19 | **Human-agent trust exploitation** — misleading approvals | Medium | High | Evidence-based approval UX; deliberation delays; multi-person thresholds (§3.8) | Approval-velocity anomalies; approver-behavior baselines | Revoke wrongly-approved actions where reversible; compensation workflows |
| T20 | **Rogue agent** — persistent misalignment / self-directed action | Low | Critical | Kill switch; behavioral tripwires; no self-modification (§8); platform guardrails | Drift + anomaly ensembles; canary tasks | Full revocation; forensic ledger export; human post-mortem before any redeploy |

**Cross-cutting notes:**
- Detection everywhere feeds the same SIEM/audit pipeline (§7); a threat the ledger can't see is a threat you can't recover from.
- Recovery assumes **checkpoints + replay**: durable workflow state (§6) is what makes "revoke and re-plan" possible instead of "revoke and lose everything."
- Likelihood "Low" for T16/T20 reflects *design intent* (these should be architecturally near-impossible); the mitigations are what make them low.

## 5. Multi-tenancy

### 5.1 Hierarchy & isolation model

**[REC]** Adopt the AWS SaaS Factory vocabulary — **silo / pool / bridge** — and apply it per-layer (the "bridge" insight is that real systems mix models per service). [\[AWS whitepaper\]](https://docs.aws.amazon.com/pdfs/whitepapers/latest/saas-tenant-isolation-strategies/saas-tenant-isolation-strategies.pdf) [\[AWS Security Blog\]](https://aws.amazon.com/blogs/security/security-practices-in-aws-multi-tenant-saas-environments/)

```
Organization
 └── Tenant  ← the security & billing boundary
      ├── Users (OIDC federated, tenant-scoped roles)
      ├── Agents (registry entries + runtime identities, tenant-scoped)
      ├── Tools (allowlist subset of global catalog + tenant-private tools)
      ├── Policies (tenant bundle layered under platform guardrails)
      ├── Knowledge & Memory (namespaced, encrypted with tenant key)
      ├── Workflows & Executions (tenant-scoped, quota-bounded)
      ├── Budgets (spend envelopes)
      └── Audit Logs (per-tenant hash chain; tenant-readable, platform-immutable)
```

**[REC] Recommended per-layer placement (bridge model):**

| Layer | Model | Rationale |
|---|---|---|
| Control-plane API / orchestrator / policy engine | **Pool** (shared, tenant-aware) | Efficient; isolation via tenant claims in identity + RLS. This is the "one control plane, many tenants" thesis. |
| Execution sandboxes | **Pool with hard partitions** (per-task microVMs, per-tenant network segments) | Shared substrate, but blast radius is per-task; tenant affinity scheduling for noisy-neighbor control. |
| Relational data | **Pool with Row-Level Security** (tenant_id on every row, RLS enforced in DB, not just app code) [\[AWS RLS\]](https://aws.amazon.com/blogs/database/multi-tenant-data-isolation-with-postgresql-row-level-security/) | Cost-efficient; [FACT] RLS is the proven enforcement mechanism — "hoping the WHERE clause is right" is the documented anti-pattern. |
| Memory / vector store | **Pool with per-tenant namespaces + per-tenant encryption keys** | Logical separation + cryptographic separation; key deletion = erasure. |
| Audit ledger | **Pool storage, per-tenant chains** (each tenant's chain is independently verifiable) | Tenants can verify their own history without seeing others'. |
| Secrets / keys | **Silo** (per-tenant Vault namespace / KMS keys) | Strongest isolation where it matters most; enables crypto-shredding offboarding. |
| High-tier tenants | **Optional full silo** (dedicated execution nodes, dedicated DB schema/instance) | Tiering strategy: basic → pool, enterprise → silo for regulated data. [CONVENTION] per AWS tiering guidance. |

### 5.2 Tenant isolation mechanics

- **Identity:** tenant ID is a first-class claim in every token (user JWT, agent SVID, delegation token). Services reject tokens with missing/mismatched tenant claims — fail closed.
- **Authorization:** every policy evaluation takes `tenant` as input; tenant policies can't widen platform guardrails.
- **Resource fairness:** per-tenant quotas (concurrent tasks, tokens/min, tool calls/min, storage); noisy-neighbor protection via scheduling weights and rate limiters. Cross-tenant DoS is T14.
- **Data plane:** RLS + tenant-key encryption + no shared mutable caches. Temporary credentials are tenant-bound (a credential minted for tenant A is unusable for tenant B's resources — enforced by audience/scope, §1.4).
- **Control-plane metadata:** even internal telemetry (traces, metrics) carries tenant labels with access-controlled querying — an operator for tenant A cannot query tenant B's traces.

### 5.3 Tenant-specific configuration surface

Per the master prompt, each tenant independently configures: agents, tools (allowlist), policies, models (allowlist), knowledge sources, memory retention, workflows, budgets, approval thresholds, and data-residency region. **[REC]** All of it versioned, change-audited, and exportable (tenant data-portability + offboarding).

### 5.4 Data residency & sovereignty

- **[REC]** The **router** is residency-aware: tasks carrying residency constraints (e.g., "EU data stays in EU") only schedule to execution nodes and model endpoints in permitted regions; the policy engine denies otherwise (fail closed).
- **[REC]** Region-pinned storage for tenant data at rest; cross-region replication only where the tenant's policy allows.
- **[FACT]** Regulatory pressure is real and current: NIST's GenAI Profile (NIST AI 600-1, July 2024) gives the risk-management vocabulary enterprises now expect, and it pairs with ISO 42001/ISO 27001-style management systems. [\[NIST\]](http://nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence) Align the ACP's governance artifacts (risk register, control mapping) to AI RMF functions (Govern, Map, Measure, Manage) so enterprise buyers can slot it into existing GRC.
- **[OP]** Don't build a legal engine; build residency as *policy inputs + router constraints + audit evidence*. Lawyers define the rules, the platform enforces and proves them.

## 6. Failure model & fail-closed design

**Master rule [REC]:** every failure defaults to the *safe* state — deny the action, freeze the workflow, preserve evidence, and escalate. "Fail open for availability" is never acceptable for high-risk operations; availability is recovered via redundancy and checkpoints, not by skipping authorization.

| Failure class | Detection | Fail-closed behavior | Recovery |
|---|---|---|---|
| Model failure (errors, degraded output) | Timeouts, error rates, eval-score drop | Task pauses; no tool calls on unverified model output | Retry with backoff → fail over to alternate approved model → escalate |
| Hallucination (confident wrong plan/fact) | Output verification; checker model; schema validation | Block side-effecting actions on unverified content | Re-plan with grounding (RAG) or escalate to human |
| Tool / API failure | Error codes, timeouts, health checks | Mark tool degraded; circuit-break | Retry with idempotency key → alternate tool → compensation workflow |
| Timeout (tool, model, approval) | Watchdogs | Approval timeout = **deny** (never auto-approve); tool timeout = abort + compensate | Re-issue or escalate; never silently continue |
| Network failure / partition | Heartbeats, mesh telemetry | Freeze in-flight tasks at checkpoints; deny new high-risk actions | Resume from durable checkpoints on recovery (workflow engine) |
| Agent failure (crash, corruption) | Supervisor heartbeats | Revoke its leases; quarantine its outputs | Restart from checkpoint with fresh identity; re-verify plan |
| Workflow failure | State-machine invariant violations | Halt workflow; preserve state + ledger | Human or policy-driven resume/retry/compensate |
| Policy / permission denial | Decision = deny (normal, not exceptional) | Action blocked; agent informed with reason | Agent re-plans within granted authority or requests approval/elevation via proper channel |
| Memory corruption / stale knowledge | Hash-chain verification failure; freshness timestamps; contradiction checks | Quarantine affected memory; exclude from retrieval | Restore from signed snapshot; re-ingest; audit who wrote the bad data |
| Conflicting agents | Plan-conflict detection; resource contention | Serialize via control plane; higher-priority or human decides | Merge/re-plan; record conflict + resolution in ledger (learnable history per AGMS concept) |
| Runaway loops | Iteration caps, loop signatures, cost velocity | Kill switch; freeze task | Human triage: resume with tighter bounds or abort |
| Excessive cost | Budget envelopes, velocity alerts | Hard deny at 100% (fail closed) | Human re-authorization with raised envelope; post-mortem |
| Prompt injection (successful) | Detectors, canaries, behavior anomaly | Revoke task's authority; purge tainted context | Re-issue with quarantine pattern; rotate any exposed credentials |
| Compromised credentials | Use-anomaly, revocation events | Immediate revocation (leases bound blast radius) | Rotate; re-issue least-privilege replacements; ledger forensics |

**Durable execution [REC]:** the workflow engine checkpoints *before* every side-effecting step with the policy decision attached; recovery replays from the last verified checkpoint rather than re-executing blindly (idempotency keys make replay safe). This is why "don't reinvent Temporal" matters — durable execution with exactly-once semantics is a solved-hard problem; integrate or deeply study it.

## 7. Audit ledger design

**[REC] Construction — tamper-evident, append-only, per-tenant hash-chained log:**

- Each entry: `{seq, tenant_id, timestamp (RFC3339, synchronized clock), event_type, actor{...}, action, inputs_digest, policy{version_hash, decision}, risk{score, level}, delegation_chain, result, prev_hash, entry_hash, signature}`.
- `entry_hash = SHA-256(prev_hash ‖ canonical(entry))` — any edit, deletion, or reorder breaks the chain downstream. [CONVENTION] This hash-chained append-only pattern is the standard lightweight approach (multiple independent implementations converge on it: per-entry `prev_hash`/`entry_hash` with a verify walk). [\[audit-log\]](https://github.com/pametan/audit-log) [\[OpenMAO\]](https://github.com/OpenMAO/OpenMAO/pull/98)
- Entries signed with the control plane's Ed25519 ledger key (proves origin even if storage is compromised).
- **External anchoring:** periodically publish the chain head to an external timestamping/transparency service (e.g., Sigstore Rekor-style transparency log or tenant-visible anchor). This upgrades tamper-*evidence* to tamper-evidence-*against the operator* — the defense against "rewrite the whole chain" attacks.
- **Write path separation:** the ledger writer is independent of the execution plane; agents and tools have no write access to the ledger (only the control plane appends). Storage on WORM/immutable object storage where available.
- **PII/secret hygiene:** redact before write (never log raw credentials, prompts containing secrets, or full PII — log digests + classification tags instead).
- **Verification:** `verify(chain)` recomputes hashes oldest→newest and reports the first break with reason (content-altered vs. link-broken), plus signature checks and anchor cross-verification. Run continuously, not just on demand.

**What to record [REC]** — the master prompt's WHO/WHAT/WHEN/WHY, made concrete as mandatory event types: `AgentRegistered/Updated`, `TaskCreated/Started/Completed/Failed`, `PlanProposed/Approved`, `ToolInvoked/ToolFailed` (with args digest), `PolicyEvaluated` (inputs digest + decision + policy version), `PermissionGranted/Revoked`, `RiskAssessed`, `ApprovalRequested/Granted/Rejected` (+approver identity + evidence shown), `WorkflowStarted/Paused/Resumed/Completed`, `MemoryWritten`, `DelegationIssued/Revoked`, `CostThresholdExceeded`, `SecurityViolationDetected`, `EvaluationCompleted`, `ConfigChanged` (policy/tool/agent version changes — the supply-chain audit trail).

**[OP]** The audit ledger is the product's trust anchor and a genuine differentiator: "auditable autonomy" is what lets an enterprise *prove* to auditors/regulators what its agents did. Design it as if a regulator will read it — because for the target customers, one will.

## 8. Governance constraints → build requirements

How the master prompt's hard constraints translate into non-negotiable implementation requirements:

| Hard constraint | Build requirement (from this research) |
|---|---|
| **Policy-before-execution** | Six enforcement choke points (§2.4); policy engine on the hot path of every tool call; decisions hash-referenced in the audit ledger. No "advisory mode" in production. |
| **Fail closed on high-risk operations** | Deny-by-default policy model; approval-timeout = deny; budget-exhaustion = deny; watchdog-breach = freeze; degraded-mode never skips authorization (§6). |
| **No uncontrolled self-modification** | The learning/feedback loop may *propose* changes (prompts, policies, routing weights, tool selections) but every proposal enters as a versioned change request through policy evaluation + human approval + canary evaluation before promotion. Learning outputs are artifacts in the supply chain (§1.9), not live mutations. Agent code can never modify its own grants, policies, or the ledger. |
| **Tenant isolation** | Bridge model (§5.1); tenant claims in all identities; RLS + per-tenant keys; tenant-scoped memory/tools/policies/budgets/audit chains; cross-tenant access architecturally impossible, monitored as critical if attempted (T16). |
| **Agents never inherit user authority** | Delegation-token model (§1.4): effective authority = intersection of user-delegable ∩ agent-granted ∩ task-scope ∩ policy; downward-only narrowing; full chain in the ledger. |

## 9. Open questions & hypotheses for the architecture phase

1. **[HYP]** The deterministic-floor + ML-refinement risk engine (§2.3) needs a formal "risk algebra" (how factors compose, how decay works without boiling-frog creep). Prototype before committing.
2. **[HYP]** Taint tracking for indirect injection (§3.2) at full data-flow granularity may be too expensive; a coarse provenance-tag + trust-weighted authorization may capture 90% of the value. Measure.
3. **[?]** Standardized agent identity beyond SPIFFE: MCP's EMA and OAuth 2.1 cover *user→agent→server* auth, but *agent↔agent* identity federation across organizational boundaries has no mature standard. Watch the Agentic AI Foundation (Linux Foundation, Dec 2025) for emerging specs. [\[TechTimes\]](https://www.techtimes.com/articles/318708/20260619/mcp-enterprise-authorization-goes-stable-zero-touch-sso-okta-anthropic-vs-code.htm)
4. **[?]** The Kubernetes analogy's security boundary: K8s admission control happens at deploy time; agent policy must happen per-action at runtime. The architecture should borrow K8s *patterns* (RBAC, admission, audit) without assuming its threat model transfers.
5. **[?]** Confidential computing for agent sandboxes (§1.6): valuable for regulated tiers, but attestation of *non-deterministic* agent behavior is an unsolved UX problem (you can attest the sandbox, not the agent's decisions). The ledger remains the accountability mechanism even in TEEs.

## 10. Sources

Primary / official sources first, as researched 2026-09-14:

- OWASP GenAI Security Project — *Top 10 for Agentic Applications 2026* announcement (Dec 2025): https://genai.owasp.org/2025/12/09/owasp-genai-security-project-releases-top-10-risks-and-mitigations-for-agentic-ai-security/
- Tenable — summary of the OWASP agentic top 10 with threat descriptions: https://www.tenable.com/blog/cybersecurity-snapshot-owasp-agentic-ai-top-10-mitre-dangerous-software-weaknesses-12-12-2025
- NSA Cybersecurity Information Sheet — *Model Context Protocol (MCP): Security Design Considerations for AI-Driven Automation* (May 2026, Ver. 1.0): https://www.nsa.gov/Portals/75/documents/Cybersecurity/CSI_MCP_SECURITY.pdf?ver=bmgiSbNQLP6Z_GiWtRt6bg%3D%3D
- NIST — *AI Risk Management Framework* overview: https://www.nist.gov/itl/ai-risk-management-framework?ref=blog.aesi-inc.com
- NIST AI 600-1 — *AI RMF: Generative AI Profile* (Jul 2024): http://nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence
- RedHat — *What are SPIFFE and SPIRE?*: https://www.RedHat.com/en/topics/security/spiffe-and-spire
- AWS — *Implement SPIFFE/SPIRE authorization on Amazon EKS*: https://aws.amazon.com/blogs/containers/implement-spiffe-spire-authorization-on-amazon-eks/
- Palo Alto Unit 42 — *Post-exploitation identity misuse in SPIFFE/SPIRE* (Sep 2026): https://unit42.paloaltonetworks.com/kubernetes-spiffe-spire-identity-spoofing/
- Debenedetti et al. — *Defeating Prompt Injections by Design* (CaMeL, arXiv 2503.18813): https://arxiv.org/pdf/2503.18813v2
- Rem1L — *awesome-ipi-defense* (D1–D6 taxonomy of indirect prompt-injection defenses): https://github.com/Rem1L/awesome-ipi-defense
- MDPI Applied Sciences — *Spotlight-Guard, a Layered Defense Against Indirect Prompt Injection*: https://www.mdpi.com/2076-3417/16/15/7662/pdf
- Auth0 — *MCP Spec Updates from June 2025* (OAuth Resource Server classification, RFC 8707): https://auth0.com/blog/mcp-specs-update-all-about-auth/
- TechTarget — *MCP OAuth update adds security for personalized AI* (Nov 2025): https://www.techtarget.com/it-infrastructure/news/366634681/MCP-OAuth-update-adds-security-for-personalized-AI
- TechTimes — *MCP Enterprise Authorization Goes Stable* (EMA, Jun 2026): https://www.techtimes.com/articles/318708/20260619/mcp-enterprise-authorization-goes-stable-zero-touch-sso-okta-anthropic-vs-code.htm
- CSA / Aembit — *MCP Auth Spec & Security for Agentic AI*: https://cloudsecurityalliance.org/blog/2025/05/28/mcp-oauth-2-1-pkce-and-the-future-of-ai-authorization
- HashiCorp — *Vault credential brokering* (Boundary pattern): https://developer.hashicorp.com/vault/tutorials/cross-products/community-vault-cred-brokering-quickstart
- darthvaderrc/vault-spiffe — *SPIFFE-authenticated dynamic DB credentials demo*: https://github.com/darthvaderrc/vault-spiffe
- AWS SaaS Factory — *SaaS Tenant Isolation Strategies* whitepaper (silo/pool/bridge): https://docs.aws.amazon.com/pdfs/whitepapers/latest/saas-tenant-isolation-strategies/saas-tenant-isolation-strategies.pdf
- AWS Security Blog — *Security practices in AWS multi-tenant SaaS environments*: https://aws.amazon.com/blogs/security/security-practices-in-aws-multi-tenant-saas-environments/
- AWS Database Blog — *Multi-tenant data isolation with PostgreSQL Row Level Security*: https://aws.amazon.com/blogs/database/multi-tenant-data-isolation-with-postgresql-row-level-security/
- Google Cloud — *Confidential Space security overview*: https://docs.cloud.google.com/docs/security/confidential-space
- NVIDIA Technical Blog — *Confidential Computing on H100 GPUs for Secure and Trustworthy AI*: https://developer.nvidia.com/blog/confidential-computing-on-h100-gpus-for-secure-and-trustworthy-ai/?ncid=so-link-394138
- pametan/audit-log — *tamper-evident hash-chained audit logging* (pattern reference): https://github.com/pametan/audit-log
- OpenMAO PR #98 — *tamper-evident event log via hash chain* (pattern reference): https://github.com/OpenMAO/OpenMAO/pull/98

---

*End of security research stream. Companion streams: market/architecture analysis, technology evaluation (separate files). Next: architecture phase consumes §8's constraint table as non-negotiable requirements.*
