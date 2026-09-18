from __future__ import annotations

import io
import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from axum_tools_mcp import server, telemetry
from axum_tools_mcp.recommendation_client import RecommendationClient, RecommendationClientError, RequestMetadata

TRACE_ID = "11111111111111111111111111111111"
PARENT_SPAN_ID = "2222222222222222"
TRACEPARENT = f"00-{TRACE_ID}-{PARENT_SPAN_ID}-01"


@dataclass
class TelemetryCapture:
    span_exporter: InMemorySpanExporter
    metric_reader: InMemoryMetricReader
    tracer_provider: TracerProvider

    def spans(self) -> dict[str, Any]:
        return {span.name: span for span in self.span_exporter.get_finished_spans()}

    def metric(self, name: str) -> Any:
        metrics_data = self.metric_reader.get_metrics_data()
        assert metrics_data is not None
        for resource_metrics in metrics_data.resource_metrics:
            for scope_metrics in resource_metrics.scope_metrics:
                for metric in scope_metrics.metrics:
                    if metric.name == name:
                        return metric
        raise AssertionError(f"Metric {name!r} was not exported")


@pytest.fixture
def telemetry_capture(monkeypatch: pytest.MonkeyPatch) -> TelemetryCapture:
    resource = Resource.create(
        {
            "service.name": "movie-recommendation-mcp",
            "service.namespace": "movie-platform",
            "service.version": "test-version",
            "deployment.environment.name": "test",
        }
    )
    span_exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(SimpleSpanProcessor(span_exporter))

    metric_reader = InMemoryMetricReader()
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    meter = meter_provider.get_meter(telemetry.SERVICE_NAME)

    monkeypatch.setattr(telemetry, "_tracer", tracer_provider.get_tracer(telemetry.SERVICE_NAME))
    monkeypatch.setattr(
        telemetry,
        "_tool_calls",
        meter.create_counter("axum_tools_mcp_tool_calls_total", unit="{call}"),
    )
    monkeypatch.setattr(
        telemetry,
        "_tool_duration",
        meter.create_histogram("axum_tools_mcp_tool_duration_ms", unit="ms"),
    )

    capture = TelemetryCapture(
        span_exporter=span_exporter,
        metric_reader=metric_reader,
        tracer_provider=tracer_provider,
    )
    yield capture
    tracer_provider.shutdown()
    meter_provider.shutdown()


@pytest.mark.asyncio
async def test_success_joins_incoming_trace_and_emits_bounded_metrics(
    monkeypatch: pytest.MonkeyPatch,
    telemetry_capture: TelemetryCapture,
) -> None:
    captured_request: httpx.Request | None = None

    async def fake_handle_async_request(
        _transport: httpx.AsyncHTTPTransport,
        request: httpx.Request,
    ) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(
            200,
            json={"recommendations": [{"id": "movie-1"}]},
            request=request,
        )

    instrumentor = HTTPXClientInstrumentor()
    instrumentor.uninstrument()
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", fake_handle_async_request)
    instrumentor.instrument(tracer_provider=telemetry_capture.tracer_provider)
    http_client = httpx.AsyncClient(base_url="https://recommendation.example.test")
    client = RecommendationClient(
        base_url="https://recommendation.example.test",
        http_client=http_client,
    )
    monkeypatch.setattr(server, "client", client)
    try:
        result = await server.recommendation_get_movies(
            traceparent=TRACEPARENT,
            tracestate="vendor=value",
            correlation_id="c" * 300,
            request_id="r" * 300,
            demo_fault="f" * 100,
        )
    finally:
        await client.close()
        instrumentor.uninstrument()
        instrumentor.instrument()

    assert result["ok"] is True
    spans = telemetry_capture.spans()
    tool_span = spans["mcp.tool.recommendation_get_movies"]
    downstream_span = spans["GET"]
    assert f"{tool_span.context.trace_id:032x}" == TRACE_ID
    assert f"{tool_span.parent.span_id:016x}" == PARENT_SPAN_ID
    assert downstream_span.parent.span_id == tool_span.context.span_id
    assert captured_request is not None
    assert captured_request.headers["traceparent"] == (f"00-{TRACE_ID}-{downstream_span.context.span_id:016x}-01")
    assert tool_span.status.status_code is StatusCode.OK
    assert tool_span.attributes["mcp.tool.outcome"] == "success"
    assert tool_span.attributes["demo.fault"] == "f" * telemetry.MAX_FAULT_FIELD_LENGTH
    assert tool_span.attributes["app.correlation_id"] == "c" * telemetry.MAX_DIAGNOSTIC_FIELD_LENGTH
    assert tool_span.resource.attributes["service.name"] == "movie-recommendation-mcp"
    assert tool_span.resource.attributes["deployment.environment.name"] == "test"

    calls = telemetry_capture.metric("axum_tools_mcp_tool_calls_total")
    assert calls.unit == "{call}"
    assert [(point.value, dict(point.attributes)) for point in calls.data.data_points] == [
        (1, {"mcp.tool.name": "recommendation_get_movies", "outcome": "success"})
    ]
    duration = telemetry_capture.metric("axum_tools_mcp_tool_duration_ms")
    assert duration.unit == "ms"
    assert [dict(point.attributes) for point in duration.data.data_points] == [
        {"mcp.tool.name": "recommendation_get_movies", "outcome": "success"}
    ]
    assert duration.data.data_points[0].count == 1


@pytest.mark.asyncio
async def test_returned_dependency_error_marks_span_and_metrics_as_failed(
    monkeypatch: pytest.MonkeyPatch,
    telemetry_capture: TelemetryCapture,
) -> None:
    class FailingClient:
        async def recommendations(
            self,
            *,
            limit: int,
            preference: str | None,
            metadata: RequestMetadata,
        ) -> dict[str, Any]:
            raise RecommendationClientError(500, {"error": "private detail"})

    monkeypatch.setattr(server, "client", FailingClient())

    result = await server.recommendation_get_movies(traceparent=TRACEPARENT)

    assert result["ok"] is False
    tool_span = telemetry_capture.spans()["mcp.tool.recommendation_get_movies"]
    assert tool_span.status.status_code is StatusCode.ERROR
    assert tool_span.status.description == "dependency_error"
    assert tool_span.attributes["mcp.tool.outcome"] == "dependency_error"
    calls = telemetry_capture.metric("axum_tools_mcp_tool_calls_total")
    assert [dict(point.attributes) for point in calls.data.data_points] == [
        {"mcp.tool.name": "recommendation_get_movies", "outcome": "dependency_error"}
    ]


def test_raised_internal_error_is_recorded_and_re_raised(telemetry_capture: TelemetryCapture) -> None:
    with (
        pytest.raises(RuntimeError, match="private detail"),
        telemetry.tool_span("recommendation_health", {}, traceparent=TRACEPARENT),
    ):
        raise RuntimeError("private detail")

    tool_span = telemetry_capture.spans()["mcp.tool.recommendation_health"]
    assert tool_span.status.status_code is StatusCode.ERROR
    assert tool_span.status.description == "internal_error"
    assert tool_span.attributes["mcp.tool.outcome"] == "internal_error"
    calls = telemetry_capture.metric("axum_tools_mcp_tool_calls_total")
    assert [dict(point.attributes) for point in calls.data.data_points] == [
        {"mcp.tool.name": "recommendation_health", "outcome": "internal_error"}
    ]


def test_invalid_trace_context_and_no_exporter_are_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = TracerProvider()
    meter_provider = MeterProvider()
    meter = meter_provider.get_meter(telemetry.SERVICE_NAME)
    monkeypatch.setattr(telemetry, "_tracer", provider.get_tracer(telemetry.SERVICE_NAME))
    monkeypatch.setattr(telemetry, "_tool_calls", meter.create_counter("test_calls"))
    monkeypatch.setattr(telemetry, "_tool_duration", meter.create_histogram("test_duration"))

    with telemetry.tool_span("recommendation_health", {}, traceparent="not-a-traceparent"):
        pass

    provider.shutdown()
    meter_provider.shutdown()


def test_resource_uses_canonical_defaults_and_standard_environment_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SERVICE_VERSION", "sha256:test")
    monkeypatch.setenv("DEPLOYMENT_ENVIRONMENT", "fallback")
    monkeypatch.setenv(
        "OTEL_RESOURCE_ATTRIBUTES",
        "service.namespace=custom-platform,deployment.environment.name=aws-demo",
    )

    attributes = telemetry.build_resource().attributes

    assert attributes["service.name"] == "movie-recommendation-mcp"
    assert attributes["service.namespace"] == "custom-platform"
    assert attributes["service.version"] == "sha256:test"
    assert attributes["deployment.environment.name"] == "aws-demo"


def test_json_log_contains_active_trace_identity_and_bounds_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
    telemetry_capture: TelemetryCapture,
) -> None:
    monkeypatch.setenv("SERVICE_VERSION", "test-version")
    output = io.StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(telemetry.JsonFormatter())
    logger = logging.getLogger("telemetry-test")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)

    with telemetry._tracer.start_as_current_span("log-parent") as span:
        telemetry.log_event(logger, "mcp.test", "message", request_id="r" * 300)

    payload = json.loads(output.getvalue())

    assert payload["trace_id"] == f"{span.context.trace_id:032x}"
    assert payload["span_id"] == f"{span.context.span_id:016x}"
    assert payload["service_version"] == "test-version"
    assert payload["request_id"] == "r" * telemetry.MAX_DIAGNOSTIC_FIELD_LENGTH
