"""Observability: OpenTelemetry (console exporter default, OTLP env-configurable),
structured JSON logs, correlation_id + W3C trace context, in-memory span
exporter backing GET /api/v1/traces."""

from __future__ import annotations

import logging
from collections import deque
from contextvars import ContextVar
from typing import Any

import structlog
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SpanExporter,
    SpanExportResult,
)

correlation_ctx: ContextVar[str | None] = ContextVar("correlation_id", default=None)

_spans: deque = deque(maxlen=2000)
_tracer = None
_configured = False


class _MemoryExporter(SpanExporter):
    def export(self, spans):
        for s in spans:
            ctx = s.get_span_context()
            _spans.append({
                "trace_id": format(ctx.trace_id, "032x"),
                "span_id": format(ctx.span_id, "016x"),
                "name": s.name,
                "start": s.start_time,
                "end": s.end_time,
                "attributes": dict(s.attributes or {}),
                "status": str(s.status.status_code),
            })
        return SpanExportResult.SUCCESS

    def shutdown(self):
        pass


def recent_spans(task_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    items = list(_spans)
    if task_id:
        items = [s for s in items if s["attributes"].get("acp.task.id") == task_id]
    return items[-limit:]


def configure_observability(service_name: str = "agent-control-plane", otlp_endpoint: str | None = None) -> None:
    global _tracer, _configured
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )
    if _configured:
        return
    provider = TracerProvider(resource=Resource({"service.name": service_name}))
    if otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint)))
    else:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    provider.add_span_processor(BatchSpanProcessor(_MemoryExporter()))
    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(service_name)
    _configured = True
    logging.getLogger(__name__).info("observability configured (otlp=%s)", bool(otlp_endpoint))


def get_tracer():
    configure_observability()
    return _tracer


def new_correlation_id() -> str:
    from acp.core.utils import new_id

    return new_id()
