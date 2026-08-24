from __future__ import annotations

import inspect

import pytest

from axum_tools_mcp import server
from axum_tools_mcp.recommendation_client import PROPAGATED_HEADERS, RequestMetadata
from axum_tools_mcp.telemetry import SERVICE_NAME as TELEMETRY_SERVICE_NAME


@pytest.mark.asyncio
async def test_recommendation_tool_names_are_registered() -> None:
    tools = await server.mcp.list_tools()

    assert {tool.name for tool in tools} == {
        "recommendation_get_movies",
        "recommendation_health",
    }


def test_recommendation_tool_arguments_stay_stable() -> None:
    assert list(inspect.signature(server.recommendation_get_movies).parameters) == [
        "limit",
        "preference",
        "fault",
        "traceparent",
        "tracestate",
        "correlation_id",
        "request_id",
        "demo_fault",
    ]
    assert list(inspect.signature(server.recommendation_health).parameters) == [
        "traceparent",
        "tracestate",
        "correlation_id",
        "request_id",
        "demo_fault",
    ]


def test_service_name_matches_standalone_artifact() -> None:
    assert server.SERVICE_NAME == "movie-recommendation-mcp"
    assert TELEMETRY_SERVICE_NAME == server.SERVICE_NAME


def test_limit_is_clamped_to_downstream_contract() -> None:
    assert server.clamp_limit(-1) == 1
    assert server.clamp_limit(0) == 1
    assert server.clamp_limit(5) == 5
    assert server.clamp_limit(200) == server.MAX_LIMIT


def test_propagated_headers_keep_expected_wire_names() -> None:
    assert PROPAGATED_HEADERS == {
        "traceparent": "traceparent",
        "tracestate": "tracestate",
        "correlation_id": "X-Correlation-Id",
        "request_id": "X-Request-Id",
        "demo_fault": "X-Demo-Fault",
    }

    metadata = RequestMetadata(
        traceparent="00-11111111111111111111111111111111-2222222222222222-01",
        tracestate="vendor=value",
        correlation_id="corr-1",
        request_id="req-1",
        demo_fault="recommendation-error",
    )

    assert metadata.headers() == {
        "traceparent": "00-11111111111111111111111111111111-2222222222222222-01",
        "tracestate": "vendor=value",
        "X-Correlation-Id": "corr-1",
        "X-Request-Id": "req-1",
        "X-Demo-Fault": "recommendation-error",
    }


def test_blank_metadata_values_are_not_forwarded() -> None:
    metadata = RequestMetadata(
        traceparent=" ",
        tracestate=None,
        correlation_id="corr-1",
        request_id="",
        demo_fault="none",
    )

    assert metadata.headers() == {
        "X-Correlation-Id": "corr-1",
        "X-Demo-Fault": "none",
    }
