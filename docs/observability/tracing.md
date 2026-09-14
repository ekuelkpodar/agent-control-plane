# Tracing & Observability

OpenTelemetry from day one. The ACP's observability differs from standard
service telemetry in one way: traces must explain **decisions**, not just
latency — *why* this agent, *why* this model, *which policy* fired, *who*
approved.

## Decision provenance spans

Every task trace links task → plan → agent selection → policy evaluation
→ risk score → approval → tool calls → outcome via span attributes:

| Attribute | Meaning |
|---|---|
| `acp.task.id` | task identifier |
| `acp.plan.id` | plan version evaluated |
| `acp.agent.selected` | chosen agent (+ version) |
| `acp.model.selected` | chosen model (+ provider) |
| `acp.policy.decision` | allow / deny / require_approval / allow_with_constraints |
| `acp.policy.version` | policy bundle hash that decided |
| `acp.risk.score` / `acp.risk.level` | risk assessment |
| `acp.approval.id` | approval, if any |
| `correlation_id` / `trace_id` | first-class on every task (W3C trace context) |

Follow OTel GenAI semantic conventions where applicable.

## Pillars

- **Traces:** decision provenance as above; emitted by control plane,
  governance rail, and execution plane.
- **Metrics:** task lifecycle counters, policy-decision rates, approval
  latency, budget consumption (50/80/95% gauges), cost telemetry
  (tokens, tool calls) — this closes the "can't meter agents" gap.
- **Logs:** structured JSON; secret/PII redaction pre-write (never log raw
  credentials, secrets, or full PII — digests + classification tags only).

## Sinks

- Prometheus + Grafana for metrics/dashboards (compose includes a
  collector path).
- SSE streams from the API for live execution traces and approval
  notifications (`/api/v1/tasks/{id}/events`, `/api/v1/approvals/stream`).
- Eval/telemetry *platforms* (LangSmith, Arize, Langfuse) are integrations:
  consume their signals for drift detection and behavioral evaluation —
  don't rebuild their dashboards.

## Red lines

- The audit ledger is separate from trace storage: evidence (hash-chained,
  signed) vs. telemetry (high-volume, queryable). Don't put spans in the
  ledger; don't treat traces as legal evidence.
- Policy evaluation on the tool-call hot path must be local/cached with
  async audit — synchronous full-trace writes per tool call would let
  agents route around the rail.
