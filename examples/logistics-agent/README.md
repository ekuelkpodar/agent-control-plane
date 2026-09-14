# Logistics Agent — End-to-End Walkthrough

Run it:

```bash
export ACP_API_KEY=<your key>            # never commit a real key
export ACP_API_URL=http://localhost:8000 # default
python examples/logistics-agent/demo.py
```

The script drives **only** the REST contract (`/api/v1`, Bearer auth,
`X-Tenant-ID` header). All carrier data and the `mock_*` callables in the
script are **MOCK** — they stand in for the real carrier APIs and the
execution plane's tool dispatch. The control plane is never told the mocks
are real.

Below: every stage of the pipeline, what happens, and which event / audit
entry is emitted.

## Stage 1 — User submits intent

The operator (or AGRL, via a task intent) calls `POST /tasks` with a
natural-language goal:

> *"Find the best carrier for this shipment and book it if the total cost
> is under $2,500."*

plus structured input (shipment details, budget).  
**Audit:** `TaskCreated` {actor, goal digest, input digest, tenant}.

## Stage 2 — Control plane admits the task

Admission checks: tenant scope valid, agent `logistics-agent` exists and
is `active`, the caller's delegation permits `freight_quoting` /
`carrier_booking`. Anything missing ⇒ deny at the door.  
**Audit:** `PolicyEvaluated` {decision: allow, policy version hash}.

## Stage 3 — Task lifecycle starts

`POST /tasks/{id}/execute` moves the task from `created` into the governed
pipeline. The orchestrator creates a workflow execution with a checkpoint
*before* any side effect.  
**Audit:** `TaskStarted`, `WorkflowStarted`.

## Stage 4 — Planner produces a plan

The rule-based planner (strategy interface) decomposes the goal:

1. `carrier.quote` (low risk) — gather quotes.
2. Evaluate quotes against the $2,500 budget constraint.
3. `carrier.book` (high risk) — book the winner, only if under budget.

The plan declares tools, argument schemas, cost estimate, and risk tier.
**Audit:** `PlanProposed` {steps, cost estimate, tool set}.

## Stage 5 — Router selects agent + model

The router scores on capability × cost × risk × policy × residency:
`logistics-agent` (capabilities match) + cheapest approved model that
satisfies the tenant allowlist. **Route, don't proxy** — the router never
touches tokens.  
**Audit:** `TaskRouted` {agent, model, scoring inputs}.

## Stage 6 — Agent registered; tools resolved via the tool registry

`carrier.quote` and `carrier.book` resolve from the registry with their
JSON schemas and **risk classes** (low / high). The agent can only call
*declared* tools with *validated* arguments — no free-form tool invention.
Tool definitions are signed and versioned.  
*(In the demo, the mock callables illustrate what the real tool executors
would return: 3 carriers, rates, transit days.)*

## Stage 7 — Carrier APIs (mock)

The execution plane invokes `carrier.quote` through the tool gateway; the
gateway attaches brokered credentials server-side — the agent never sees a
secret. Quotes return; best = **SwiftFreight, $2,100, 5 days** (scenario A).  
**Audit:** `ToolInvoked` {tool, args digest, policy version}.

## Stage 8 — Knowledge / RAG (consulted, provenance-tagged)

If the agent consults carrier knowledge (contract terms, past
performance), every retrieved chunk carries
`{source, trust_level, retrieved_at, hash}`. Low-trust content is
quarantined; tool calls proposed on untrusted content re-enter policy
evaluation. (Not exercised by the demo's canned path, but enforced by the
same rail.)

## Stage 9 — Risk engine scores the booking

Deterministic factors: **financial transaction** + **irreversible external
action** + **external side effect** ⇒ risk floor forces `require_approval`.
The model-based refiner may raise, never lower.  
**Audit:** `RiskAssessed` {score, level, reasons[], breakdown}.

## Stage 10 — Policy engine decides

Guardrails ("no financial commitment without human approval") fire before
tenant policy. Decision: **`require_approval`**.  
**Audit:** `PolicyEvaluated` {decision: require_approval, inputs digest,
policy version hash}.

## Stage 11 — Cost evaluation

The cost manager checks the plan's $0.02 estimated cost against the task/agent/tenant
envelopes. Within budget ⇒ no block (a 100%-exhausted envelope would be a
hard deny regardless of approval).  
**Audit:** `CostThresholdExceeded` only if a 50/80/95% threshold trips.

## Stage 12 — Human approval (evidence-based)

Task pauses at `awaiting_approval`. The approval payload shows **raw
evidence**: the exact `carrier.book` call, arguments, irreversible-effects
warning, risk breakdown, policy citations, delegation chain, and budget
impact — not the agent's summary.  
**Audit:** `ApprovalRequested` {evidence shown, risk, policy refs}.

- **Scenario A** ($2,100 < $2,500): operator approves ⇒
  `ApprovalGranted` {approver identity, evidence}.
- **Scenario B** ($2,688 > $2,500): operator rejects ⇒
  `ApprovalRejected`; the task is denied and the agent must stop — the
  deny path.

## Stage 13 — Booking executes

On approval, the execution plane invokes `carrier.book` via the gateway
with per-action authorization at the enforcement point. The plan-level
approval *covers* the booking invocation — the human already approved this
exact action, so the per-tool choke point does not demand a second
approval; denials (least privilege, tenant denylist, risk clearance) still
win, and direct invocation outside an approved plan still requires its own
approval.  
**Audit:** `ToolInvoked` {booking ref digest}.

## Stage 14 — Audit chain

`GET /audit?task_id=` returns the full hash-chained sequence (scenario A):
`TaskCreated → PolicyEvaluated → TaskPlanned → TaskRouted →
PolicyEvaluated → RiskAssessed → ApprovalRequested →
ApprovalGranted/Rejected → TaskStarted → DelegationIssued →
PolicyEvaluated → RiskAssessed → ToolInvoked → TaskCompleted`
(denied tasks end `ApprovalRejected → PermissionDenied` with no tool calls).
Each entry links `prev_hash → entry_hash` and is signed — tampering breaks
the chain downstream. `GET /audit/verify` checks the whole chain.

## Stage 15 — Evaluation

`EvaluationCompleted` records the outcome score (on-time booking under
budget ⇒ pass; rejected over-budget ⇒ correct denial). The signal feeds
the behavioral controllers and the agent's quality history for future
routing.
