# Security Policy

## Reporting a vulnerability

**Do not open a public issue for a suspected vulnerability.**

Email the maintainers privately at the address listed in the repository's
contact page (or open a GitHub Security Advisory if enabled). Include:

- A description of the vulnerability and its impact.
- Steps to reproduce, or a minimal proof of concept.
- Any relevant logs, traces, or audit entries.

We aim to acknowledge reports within **3 business days** and to provide a
remediation timeline within **10 business days**. We will credit reporters
unless they request anonymity.

## Security boundaries

The control plane treats the following as *untrusted by default*:

- Everything produced by an LLM (tool arguments, plans, summaries).
- Tool outputs, MCP server responses, web/RAG content, memory contents.
- Inter-agent messages.
- Agent runtime processes themselves (governed principals, not trusted
  infrastructure).

Core stance, from the research: **the model is never the security boundary.**
Every security property must hold even if the model is fully compromised —
enforced by the control plane around it.

## What the MVP guarantees

- **Fail closed:** governance rail unreachable → deny high-risk actions;
  approval timeout = deny; budget exhaustion = deny; deny-by-default
  policy model.
- **No ambient authority:** agents never inherit user authority; effective
  authority is the intersection of user-delegable ∩ agent-granted ∩
  task-scope ∩ policy decision. Delegation tokens are short-lived, scoped,
  audience-bound, and downward-narrowing only.
- **Credential brokering:** agents never see raw secrets; the control plane
  attaches credentials server-side at tool invocation.
- **Immutable audit:** every policy decision, approval, and tool invocation
  is written to a hash-chained, signed, append-only ledger the execution
  plane cannot modify.

## What the MVP does NOT guarantee

- The minimal built-in policy evaluator (`dev` profile) is a development
  aid, **not production authorization**. Production deployments must use
  the OPA/Rego PDP (see `docs/architecture/decisions.md` ADR-005).
- Sandboxing tiers: the MVP runs the local runtime unprivileged but without
  microVM isolation. Use untrusted-task isolation (gVisor/Firecracker-class)
  in production per the deployment hardening guide.
- Cross-tenant encryption at rest with per-tenant KMS keys, external audit
  anchoring, and SPIFFE/SPIRE issuance are V1 features; the MVP uses
  tenant-scoped IDs, RLS scoping, and an internal issuer behind the same
  identity interface.
- No formal third-party security audit has been performed. Regulated
  deployments should commission one before production use.

## Threat model

See `docs/security/threat-model.md` for the full T1–T20 threat model
(attacker classes, mitigations, detection, recovery).

## Dependencies & supply chain

- Pinned dependencies; CI runs secret scanning (gitleaks) and dependency
  auditing (`pip-audit`).
- Tool schemas, agent definitions, and policy bundles are versioned and
  signature-verified at load time.
