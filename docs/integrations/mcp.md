# MCP Integrations

MCP is the tool-interoperability standard: build once, any harness uses
it. The ACP **integrates MCP fully but owns what MCP lacks**: registry +
trust, policy over tool use, risk scoring, approval gates, cost
attribution. Never build a competing tool protocol.

## What MCP gives us

Tool discovery, schemas, invocation; MCP servers as OAuth Resource
Servers (spec direction since June 2025); issuer verification; Enterprise-
Managed Authorization (stable June 2026) replacing per-user consent loops.

## What the ACP adds (the gaps)

Per the research: MCP has no orchestration, no authorization policy
(OAuth = identity, not *whether agent X may call tool Y*), no
registry/trust (any server can claim any name), no observability. The ACP
supplies all four.

## Tool-registry security rules (T3/T4)

1. **Authenticate every MCP server** the ACP talks to (no anonymous tool
   servers in enterprise tiers): OAuth 2.1, issuer verification,
   audience-bound tokens.
2. **Treat all tool outputs as untrusted input** — even from authenticated
   servers (server compromise ≠ auth failure). Outputs inherit provenance
   tags and enter the quarantine pattern.
3. **Vetting at registration:** signature verification, publisher identity,
   version pinning, schema allowlisting (agents can only call declared
   tools with validated arguments — no free-form tool invention), risk
   classification per tool, and **tool-description sanitization**:
   descriptions are a known injection vector — render them as data, diff
   them on update, and re-trigger review on change.
4. **Per-tenant tool allowlists** + runtime behavior monitoring (a tool
   with anomalous payloads or new scope requests gets quarantined).
5. **Idempotency keys** on all side-effecting tool calls (compensates for
   the MCP spec gap identified in the NSA's May 2026 MCP analysis).

## Invocation path

Agent → control-plane tool gateway → MCP server. The gateway attaches
brokered credentials server-side; the agent's context never contains a
secret. Each invocation passes the enforcement point (per-action policy
evaluation) before dispatch. Per-call results are audit events with args
digest, policy version, and risk score.

## A2A (agent-to-agent)

A2A (Linux Foundation v1.0) supplies Agent Cards, task lifecycle, and
interop. The ACP **extends** it: cards are self-asserted, so the control
plane adds issuance/signing of agent identities and card verification.
Inter-agent messages flow through the control-plane bus — authenticated
sender (SVID), tenant scope, schema validation, hash-logged to the audit
ledger. No direct agent-to-agent network paths.
