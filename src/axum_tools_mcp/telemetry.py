from __future__ import annotations

import json
import logging
import os
import sys
import time
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import OTELResourceDetector, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span, SpanKind, Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

SERVICE_NAME = "movie-recommendation-mcp"
SERVICE_NAMESPACE = "movie-platform"
MAX_DIAGNOSTIC_FIELD_LENGTH = 256
MAX_FAULT_FIELD_LENGTH = 64

ToolOutcome = Literal["success", "dependency_error", "internal_error"]


def _create_instruments() -> tuple[Any, Any, Any, Any]:
    tracer = trace.get_tracer(SERVICE_NAME)
    meter = metrics.get_meter(SERVICE_NAME)
    calls = meter.create_counter(
        "axum_tools_mcp_tool_calls_total",
        unit="{call}",
        description="Total MCP tool calls by tool and outcome.",
    )
    duration = meter.create_histogram(
        "axum_tools_mcp_tool_duration_ms",
        unit="ms",
        description="MCP tool call duration in milliseconds.",
    )
    return tracer, meter, calls, duration


_tracer, _meter, _tool_calls, _tool_duration = _create_instruments()


@dataclass
class ToolCallObservation:
    span: Span
    outcome: ToolOutcome = "success"

    def record_failure(self, outcome: Literal["dependency_error", "internal_error"]) -> None:
        self.outcome = outcome
        self.span.set_attribute("mcp.tool.outcome", outcome)
        self.span.set_status(Status(StatusCode.ERROR, outcome))


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "service_name": os.getenv("OTEL_SERVICE_NAME", SERVICE_NAME),
            "service_version": os.getenv("SERVICE_VERSION", "local"),
            "deployment_environment": os.getenv("DEPLOYMENT_ENVIRONMENT", "local"),
            "event": getattr(record, "event", record.getMessage()),
            "level": record.levelname.lower(),
            "message": record.getMessage(),
        }

        span_context = trace.get_current_span().get_span_context()
        if span_context.is_valid:
            payload["trace_id"] = f"{span_context.trace_id:032x}"
            payload["span_id"] = f"{span_context.span_id:016x}"

        for key, value in getattr(record, "fields", {}).items():
            if value is not None:
                payload[key] = value

        return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def build_resource() -> Resource:
    defaults = Resource.create(
        {
            "service.name": os.getenv("OTEL_SERVICE_NAME", SERVICE_NAME),
            "service.namespace": SERVICE_NAMESPACE,
            "service.version": os.getenv("SERVICE_VERSION", "local"),
            "deployment.environment.name": os.getenv("DEPLOYMENT_ENVIRONMENT", "local"),
        }
    )
    return defaults.merge(OTELResourceDetector().detect())


def configure_telemetry() -> None:
    global _tracer, _meter, _tool_calls, _tool_duration

    if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        resource = build_resource()
        tracer_provider = TracerProvider(resource=resource)
        tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        trace.set_tracer_provider(tracer_provider)

        metric_reader = PeriodicExportingMetricReader(OTLPMetricExporter())
        metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[metric_reader]))
        _tracer, _meter, _tool_calls, _tool_duration = _create_instruments()

    HTTPXClientInstrumentor().instrument()
    configure_logging()


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


@contextmanager
def tool_span(
    tool_name: str,
    fields: Mapping[str, Any],
    *,
    traceparent: str | None = None,
    tracestate: str | None = None,
):
    started_at = time.perf_counter()
    parent_context = _extract_w3c_context(traceparent, tracestate)
    attributes: dict[str, str] = {
        "mcp.tool.name": tool_name,
        "mcp.tool.outcome": "success",
    }
    _add_bounded_attribute(attributes, "demo.fault", fields.get("fault"), MAX_FAULT_FIELD_LENGTH)
    _add_bounded_attribute(attributes, "app.correlation_id", fields.get("correlation_id"))
    _add_bounded_attribute(attributes, "app.request_id", fields.get("request_id"))

    with _tracer.start_as_current_span(
        f"mcp.tool.{tool_name}",
        context=parent_context,
        kind=SpanKind.SERVER,
        attributes=attributes,
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        observation = ToolCallObservation(span=span)
        try:
            yield observation
        except Exception as exc:
            span.set_attribute("error.type", type(exc).__name__[:MAX_DIAGNOSTIC_FIELD_LENGTH])
            observation.record_failure("internal_error")
            raise
        else:
            if observation.outcome == "success":
                span.set_status(Status(StatusCode.OK))
        finally:
            record_tool_metrics(tool_name, observation.outcome, started_at)


def record_tool_metrics(tool_name: str, outcome: ToolOutcome, started_at: float) -> None:
    duration_ms = (time.perf_counter() - started_at) * 1000
    attributes = {
        "mcp.tool.name": tool_name,
        "outcome": outcome,
    }
    _tool_calls.add(1, attributes)
    _tool_duration.record(duration_ms, attributes)


def log_event(logger: logging.Logger, event: str, message: str, **fields: Any) -> None:
    logger.info(
        message,
        extra={
            "event": event,
            "fields": {key: _bounded_log_value(value) for key, value in fields.items()},
        },
    )


def _extract_w3c_context(traceparent: str | None, tracestate: str | None):
    carrier = {
        key: value.strip()
        for key, value in {"traceparent": traceparent, "tracestate": tracestate}.items()
        if value is not None and value.strip()
    }
    return TraceContextTextMapPropagator().extract(carrier=carrier)


def _add_bounded_attribute(
    attributes: dict[str, str],
    key: str,
    value: object,
    maximum_length: int = MAX_DIAGNOSTIC_FIELD_LENGTH,
) -> None:
    if value is None:
        return
    bounded = str(value).strip()[:maximum_length]
    if bounded:
        attributes[key] = bounded


def _bounded_log_value(value: Any) -> Any:
    if isinstance(value, str):
        return value[:MAX_DIAGNOSTIC_FIELD_LENGTH]
    return value
