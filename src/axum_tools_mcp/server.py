from __future__ import annotations

import os
from typing import Any

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from axum_tools_mcp.recommendation_client import (
    RecommendationClient,
    RecommendationClientError,
    RequestMetadata,
)
from axum_tools_mcp.telemetry import configure_telemetry, get_logger, log_event, tool_span

SERVICE_NAME = "movie-recommendation-mcp"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8092
MAX_LIMIT = 20

configure_telemetry()

logger = get_logger(__name__)
mcp = FastMCP("Axum Tools Recommendation MCP")
client = RecommendationClient()


@mcp.custom_route("/health", methods=["GET"])
async def health_check(_request: Request) -> JSONResponse:
    try:
        downstream = await client.health(RequestMetadata())
    except RecommendationClientError as exc:
        log_event(
            logger,
            "mcp.health.failed",
            "MCP health check failed.",
            http_status=503,
            dependency_status=exc.status_code,
        )
        return JSONResponse(
            {
                "status": "degraded",
                "service_name": SERVICE_NAME,
                "downstream": {"status": "unavailable"},
            },
            status_code=503,
        )

    return JSONResponse(
        {
            "status": "ok",
            "service_name": SERVICE_NAME,
            "downstream": downstream,
        }
    )


@mcp.tool
async def recommendation_get_movies(
    limit: int = 5,
    preference: str | None = None,
    fault: str | None = None,
    traceparent: str | None = None,
    tracestate: str | None = None,
    correlation_id: str | None = None,
    request_id: str | None = None,
    demo_fault: str | None = None,
) -> dict[str, Any]:
    """Return compact movie recommendations from the Axum recommendation API."""

    effective_fault = demo_fault or fault
    bounded_limit = clamp_limit(limit)
    metadata = RequestMetadata(
        traceparent=traceparent,
        tracestate=tracestate,
        correlation_id=correlation_id,
        request_id=request_id,
        demo_fault=effective_fault,
    )
    fields = {
        "tool_name": "recommendation_get_movies",
        "limit": bounded_limit,
        "fault": effective_fault or "none",
        "correlation_id": correlation_id,
        "request_id": request_id,
    }

    with tool_span(
        "recommendation_get_movies",
        fields,
        traceparent=traceparent,
        tracestate=tracestate,
    ) as observation:
        log_event(logger, "mcp.tool.started", "Recommendation tool started.", **fields)
        try:
            payload = await client.recommendations(
                limit=bounded_limit,
                preference=preference,
                metadata=metadata,
            )
        except RecommendationClientError as exc:
            log_event(
                logger,
                "mcp.tool.failed",
                "Recommendation tool failed with downstream API error.",
                **fields,
                http_status=exc.status_code,
            )
            observation.record_failure("dependency_error")
            return downstream_error("recommendation_get_movies", effective_fault, exc)

        recommendations = payload.get("recommendations", [])
        log_event(
            logger,
            "mcp.tool.succeeded",
            "Recommendation tool succeeded.",
            **fields,
            recommendation_count=len(recommendations),
        )
    return {
        "ok": True,
        "service_name": SERVICE_NAME,
        "fault": effective_fault or "none",
        "recommendations": recommendations,
    }


@mcp.tool
async def recommendation_health(
    traceparent: str | None = None,
    tracestate: str | None = None,
    correlation_id: str | None = None,
    request_id: str | None = None,
    demo_fault: str | None = None,
) -> dict[str, Any]:
    """Return the downstream Axum recommendation API health response."""

    metadata = RequestMetadata(
        traceparent=traceparent,
        tracestate=tracestate,
        correlation_id=correlation_id,
        request_id=request_id,
        demo_fault=demo_fault,
    )
    fields = {
        "tool_name": "recommendation_health",
        "fault": demo_fault or "none",
        "correlation_id": correlation_id,
        "request_id": request_id,
    }

    with tool_span(
        "recommendation_health",
        fields,
        traceparent=traceparent,
        tracestate=tracestate,
    ) as observation:
        log_event(logger, "mcp.tool.started", "Recommendation health tool started.", **fields)
        try:
            payload = await client.health(metadata)
        except RecommendationClientError as exc:
            log_event(
                logger,
                "mcp.tool.failed",
                "Recommendation health tool failed with downstream API error.",
                **fields,
                http_status=exc.status_code,
            )
            observation.record_failure("dependency_error")
            return downstream_error("recommendation_health", demo_fault, exc)

        log_event(logger, "mcp.tool.succeeded", "Recommendation health tool succeeded.", **fields)
    return {"ok": True, "service_name": SERVICE_NAME, "health": payload}


def clamp_limit(limit: int) -> int:
    return max(1, min(limit, MAX_LIMIT))


def downstream_error(
    tool_name: str,
    fault: str | None,
    error: RecommendationClientError,
) -> dict[str, Any]:
    return {
        "ok": False,
        "service_name": SERVICE_NAME,
        "tool_name": tool_name,
        "fault": fault or "none",
        "status_code": error.status_code,
        "error": "recommendation_dependency_failed",
    }


def main() -> None:
    host = os.getenv("HOST", DEFAULT_HOST)
    port = int(os.getenv("PORT", str(DEFAULT_PORT)))
    mcp.run(transport="http", host=host, port=port, path="/mcp")


if __name__ == "__main__":
    main()
