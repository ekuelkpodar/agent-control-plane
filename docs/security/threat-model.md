# Threat Model (condensed T1–T20)

Condensed from `docs/research/security-analysis.md` §4 (formal threat
model, researched 2026-09-14). Likelihood/Impact are qualitative
architectural judgments for a typical enterprise deployment; **re-rate per
deployment** before production sign-off. Full defenses live in the
research doc's §3; the architecture consequences live in
[ARCHITECTURE.md](../../ARCHITECTURE.md).

Core stance: **the model is never the security boundary** — every property
must hold even if the model is fully compromised.

| # | Threat | Likelihood | Impact | Mitigation (primary) | Detection | Recovery |
|---|---|---|---|---|---|---|
| T1 | Malicious user — weaponizes agents (data theft, fraud) | High | High | Tenant-scoped least privilege; tool allowlists; DLP egress; content policies; no cross-tenant reach | Audit anomaly rules; approval-tier triggers; behavior baselines | Revoke grants; quarantine tasks; forensic tenant audit export |
| T2 | Compromised agent — context/plan hijacked via injection or stolen delegation token | High | High | No ambient authority; short-lived scoped tokens; per-action policy evaluation; sandboxing | Goal-drift detection; tool-call vs. plan anomaly; risk-score spikes | Kill switch; revoke delegation chain; re-plan from last verified checkpoint |
| T3 | Malicious tool / tool poisoning — schema/description smuggles instructions or exfiltrates args | Medium | High | Registry vetting + signatures; schema allowlisting; description sanitization + diff-on-update; brokered creds (args never contain secrets) | Tool-output validation; payload anomalies; canary args | Quarantine tool registry-wide; revoke grants; rotate exposed creds |
| T4 | Compromised MCP server — trusted server turns hostile/breached | Medium | High | Authenticated MCP (OAuth 2.1, issuer verification); outputs treated as untrusted; per-tenant allowlists; idempotency keys | Behavior-change monitoring; scope anomalies; attestation failures | Quarantine server; fail over; replay-safe re-execution from checkpoint |
| T5 | Direct prompt injection | High | Medium | Architectural isolation (control/data-flow separation); privilege separation; input/output filtering | Injection-pattern detectors; dual-LLM disagreement | Discard tainted context; re-issue with quarantined reader |
| T6 | Indirect prompt injection (RAG, web, tool outputs, memory) | High | High | Provenance tagging + taint tracking; quarantine pattern; trust-weighted tool authorization | Low-trust content driving high-impact actions | Purge tainted context/memory; human review of affected tasks |
| T7 | Data exfiltration — via tool args, model calls, DNS, outputs | Medium | Critical | DLP egress inspection; classification-tagged flows; default-deny egress proxy; brokered credentials | Egress anomaly; classification-violation alerts | Revoke grants; rotate keys; breach workflow; ledger forensics |
| T8 | Credential theft — from context, traces, memory, logs | Medium | Critical | Agents never see raw secrets; short-lived dynamic creds; field-level encryption; secret redaction pre-write | Secret-shape scanning in traces/logs | Immediate revocation + rotation; leases bound blast radius to minutes |
| T9 | Privilege escalation — agent widens its own authority | Medium | Critical | Downward-only delegation; no self-grant; per-action re-evaluation; non-overridable platform guardrails | Grant-change alerts; scope-widening attempts = security events | Revoke to last-known-good; human re-authorization required |
| T10 | Tool poisoning, supply-chain variant (poisoned distribution) | Low–Med | High | Signed registry; SLSA provenance; version pinning; publisher identity | Signature failures; checksum drift | Roll back to last signed version; registry-wide quarantine |
| T11 | Model manipulation — backdoored/poisoned model or prompt | Low | High | Model allowlisting; prompt versioning; output verification for high-stakes tasks | Eval regressions; output-distribution drift | Swap to alternate approved model; invalidate affected outputs |
| T12 | Supply-chain attack (libraries, images, datasets, policies) | Medium | High | Signed artifacts; SBOM; image scanning; policy-bundle signatures; provenance in ledger | CI signature/scan gates; attestation mismatch | Pin to last-good; rebuild from signed sources; rotate keys |
| T13 | Runaway agent — loops, goal thrash | Medium | Medium | Watchdogs (iteration/time/token/spend caps); loop detection; kill switch | Tripwire alerts; cost-velocity anomalies | Kill + checkpoint; human decides resume vs. abort |
| T14 | Denial of service — resource exhaustion | Medium | Medium | Per-tenant quotas; rate limits; bulkheads; sandbox caps | Saturation metrics; queue-depth alerts | Shed load per policy; scale execution plane |
| T15 | Cost attack — token/compute burn | Medium | High | Budget envelopes at invocation choke point; hard deny at 100% | 50/80/95% alerts; velocity anomalies | Freeze spend; human re-authorization; cost in ledger |
| T16 | Cross-tenant data leakage — via models, memory, logs, side channels | Low–Med | Critical | Tenant IDs on every row (RLS); per-tenant keys; tenant-scoped memory; no shared mutable cross-tenant caches | Cross-tenant access attempts (impossible by design → any attempt is critical) | Key destruction; forensic audit; notification |
| T17 | Memory/context poisoning (persistent influence) | Medium | High | Write provenance; signed hash-chained memory; quarantine low-trust writes | Write anomalies; fact-contradiction checks | Roll back to signed snapshot; purge tainted entries |
| T18 | Insecure inter-agent communication — spoofing/interception | Medium | High | Control-plane message bus; SVID-authenticated senders; schema validation | Signature/sequence failures | Rekey bus; replay from ledger |
| T19 | Human-agent trust exploitation — misleading approvals | Medium | High | Evidence-based approval UX; deliberation delays; multi-person thresholds (see `docs/governance/approval-ux.md`) | Approval-velocity anomalies | Revoke wrongly-approved actions where reversible; compensation workflows |
| T20 | Rogue agent — persistent misalignment / self-directed action | Low | Critical | Kill switch; behavioral tripwires; no self-modification; platform guardrails | Drift + anomaly ensembles; canary tasks | Full revocation; forensic export; human post-mortem before redeploy |

**Cross-cutting:** detection feeds one SIEM/audit pipeline — a threat the
ledger can't see is a threat you can't recover from. Recovery assumes
checkpoints + replay: durable workflow state is what makes "revoke and
re-plan" possible instead of "revoke and lose everything." Likelihood "Low"
for T16/T20 reflects *design intent* (architecturally near-impossible); the
mitigations are what make them low.
