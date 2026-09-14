# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased] — v0.1.0 (MVP)

First public release of the Agent Control Plane open core.

### Added
- Agent registry: register, version, deprecate, revoke agents (`POST /api/v1/agents`).
- Tool registry: register tools with JSON schema + risk classification
  (`POST /api/v1/tools`).
- Task API: create tasks with goals and inputs; explicit task state machine
  (`POST /api/v1/tasks`, `GET /api/v1/tasks/{id}`, `POST /api/v1/tasks/{id}/execute`).
- Rule-based planner with strategy interface; capability/cost/policy-aware
  agent+model router (route, don't proxy).
- Policy engine: `allow` / `deny` / `require_approval` / `allow_with_constraints`
  decisions; platform guardrails > tenant policies > task constraints;
  deny-by-default; OPA/Rego PDP behind `PolicyEngine` interface with minimal
  built-in evaluator for local dev (not production).
- Deterministic risk engine (risk score, level, reasons) with hard approval
  triggers; hybrid model-based refinement hooks.
- Human approval state machine: requested → approved / rejected / expired;
  approval timeout = deny; evidence-based approval payloads.
- MVP durable runner: Postgres-backed task execution with retries, backoff,
  idempotency keys, heartbeats, pause/resume for approvals.
- Budget envelopes + cost records per task/agent/tenant; hard deny at 100%.
- Append-only audit ledger: hash-chained, Ed25519-signed entries; every
  policy decision, approval, and tool call recorded.
- Multi-tenancy: `X-Tenant-ID` header scoping; tenant-scoped registries,
  policies, budgets, audit chains.
- OpenTelemetry instrumentation (traces, metrics, logs) with decision
  provenance attributes (`acp.*`); Prometheus/Grafana ready.
- Reference local runtime + mock tool executor for demos.
- `docker compose up` dev stack: Postgres 16, Redis 7, API, worker,
  optional OPA sidecar.
- Read-only status dashboard at `/dashboard`.
- Logistics end-to-end example (`examples/logistics-agent/`).

### Security
- Fail-closed defaults everywhere: governance rail unreachable = deny
  high-risk, queue low-risk for re-adjudication.
- Agents hold no ambient credentials; delegation tokens are scoped,
  short-lived, task-bound, downward-narrowing only.
- Credential brokering: agents invoke tools through the control plane;
  secrets never enter agent context.

[Unreleased]: https://github.com/ekuekpodar/agent-control-plane/compare/v0.0.0...HEAD
