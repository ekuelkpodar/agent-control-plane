# Approval UX

Human-agent trust exploitation is threat T19: agents generate polished,
confident explanations that mislead operators into approving dangerous
actions. The approval UX is therefore a **security control**, not a
convenience surface.

## Evidence, not summaries

An approval request shows **raw evidence** — never just the agent's
summary:

- The exact tool call: name, arguments, target, irreversibility warning.
- Risk-score breakdown: which deterministic factors contributed and how
  much (the floor) vs. model-based refinement.
- Policy citations: which policies fired, at which version hash.
- Delegation chain: whose authority this runs under, its scope and expiry.
- Cost: estimated spend against the task/agent/tenant budget, and % of
  envelope consumed.

## Friction calibrated to risk

| Risk tier | UX |
|---|---|
| Low | Auto-allow under policy (logged). |
| Medium | Single approver, standard queue. |
| High | **Mandatory deliberation delay** (no one-click approve on $25k payments); approver must view evidence, not just the summary. |
| Critical | **Multi-person approval** above thresholds; role-based approver eligibility — you cannot approve your own agent's request (separation of duties). |

## Approval lifecycle

`requested → approved | rejected | expired`. **Timeout = deny** (never
auto-approve) — ADR-007. An expired approval can be re-issued; a rejected
approval records the reason and the agent must re-plan within its grants
or stop.

Approval decisions are themselves audit events: approver identity, evidence
shown, decision, timestamp, policy version. Accountability closes the loop.

## Anti-patterns to avoid

- **Rubber-stamping queues:** approval velocity anomalies (an approver
  clearing 40 high-risk requests in 2 minutes) trigger behavioral alerts.
- **Summary-only approvals:** if the UI hides the raw tool arguments, it's
  a vulnerability, not a feature.
- **Approving your own agent's actions:** blocked by role checks.
- **Silent re-approval:** if the plan or tool arguments change after
  evidence was shown, the approval is void and re-issued — no "approve
  drift."

## API shape

- `GET /approvals?status=requested` — pending queue for the operator.
- `POST /approvals/{id}/approve` / `POST /approvals/{id}/reject` — decision
  with optional approver note (recorded in the ledger).
