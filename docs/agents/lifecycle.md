# Agent Lifecycle

The agent lifecycle is an explicit state machine — lifecycle management is
reconciliation over behavioral state, not just deployment. See
[ARCHITECTURE.md §12](../../ARCHITECTURE.md#12-agent-lifecycle) for the
state diagram.

## States and transitions

| From | To | Trigger |
|---|---|---|
| — | `registered` | `POST /agents` with identity, capabilities, version |
| `registered` | `validated` | schema/signature verification passes; eval smoke tests |
| `validated` | `deployed` | deployment created (canary, then promotion) |
| `deployed` | `tested` | eval gate passes (behavioral acceptance per version) |
| `tested` | `active` | activation — routable, task-claimable |
| `active` | `evaluating` | new version candidate proposed |
| `evaluating` | `active` | promote (new default) or rollback |
| `active` | `quarantined` | behavioral tripwire (loop, drift, budget burn) |
| `quarantined` | `active` | human review clears |
| `quarantined` / `active` | `revoked` | revocation — leases expire within seconds |
| `active` | `deprecated` | superseded; no new tasks, in-flight tasks drain |
| `deprecated` | `revoked` | end of life |
| `revoked` | — | terminal |

## Identity

Every agent instance carries a SPIFFE-shaped identity,
`spiffe://acp/tenant/{t}/agent/{name}/{version}`, issued behind an
`AgentIdentity` interface (SPIRE in production, internal CA + JWT issuer in
MVP). Identity is distinct from authority: identity says *which agent*;
delegation + policy say *what it may do*.

## Versioning

An agent version bundles: code/prompt hash, model pin, tool set, capability
list, eval results. Upgrading **capabilities requires re-approval** —
grant creep via "helpful" capability additions is a privilege-escalation
path (T9). Rollback restores the prior behavioral contract; it does not
undo world effects (emails sent, money moved) — those are compensated via
workflows, not erased.

## Behavioral controllers

K8s-style reconciliation loops watch: stuck/loop signatures, eval/trajectory
drift (consuming LangSmith/Arize-class signals), budget burn, health. On
tripwire: auto-quarantine/pause/rollback as actuators; approval escalation
on anomaly. Controllers are level-triggered (converge actual→desired),
same pattern as K8s controllers, new signals.

## Kill switch

Per agent / task / tenant: revokes credentials, freezes sandboxes within
seconds, halts the workflow at its checkpoint. A watchdog breach never
grants "one last tool call" (fail closed).
