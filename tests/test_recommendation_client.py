from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from axum_tools_mcp.recommendation_client import (
    RecommendationClient,
    RecommendationClientError,
    RequestMetadata,
)


@pytest.mark.asyncio
async def test_recommendations_map_query_and_propagation_headers() -> None:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json={"recommendations": [{"id": "movie-1"}]})

    client = create_test_client(handler)

    try:
        result = await client.recommendations(
            limit=3,
            preference="comedy",
            metadata=RequestMetadata(
                traceparent="00-11111111111111111111111111111111-2222222222222222-01",
                correlation_id="correlation-1",
            ),
        )
    finally:
        await client.close()

    assert result == {"recommendations": [{"id": "movie-1"}]}
    assert captured_request is not None
    assert captured_request.url.path == "/recommendations"
    assert dict(captured_request.url.params) == {"limit": "3", "preference": "comedy"}
    assert captured_request.headers["traceparent"].startswith("00-")
    assert captured_request.headers["X-Correlation-Id"] == "correlation-1"


@pytest.mark.asyncio
async def test_recommendations_omit_blank_preference() -> None:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json={"recommendations": []})

    client = create_test_client(handler)

    try:
        await client.recommendations(limit=5, preference=" ", metadata=RequestMetadata())
    finally:
        await client.close()

    assert captured_request is not None
    assert dict(captured_request.url.params) == {"limit": "5"}


@pytest.mark.asyncio
async def test_http_errors_raise_client_error_for_health() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "internal dependency detail"})

    client = create_test_client(handler)

    try:
        with pytest.raises(RecommendationClientError) as raised:
            await client.health(RequestMetadata())
    finally:
        await client.close()

    assert raised.value.status_code == 503


@pytest.mark.asyncio
async def test_transport_errors_become_stable_client_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("internal connection detail", request=request)

    client = create_test_client(handler)

    try:
        with pytest.raises(RecommendationClientError) as raised:
            await client.health(RequestMetadata())
    finally:
        await client.close()

    assert raised.value.status_code == 502
    assert raised.value.payload == {"error": "dependency_unavailable"}


@pytest.mark.asyncio
async def test_malformed_payload_becomes_stable_client_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="internal response body")

    client = create_test_client(handler)

    try:
        with pytest.raises(RecommendationClientError) as raised:
            await client.health(RequestMetadata())
    finally:
        await client.close()

    assert raised.value.payload == {"error": "invalid_dependency_response"}


def create_test_client(handler: Callable[[httpx.Request], httpx.Response]) -> RecommendationClient:
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(
        base_url="https://recommendation.example.test",
        transport=transport,
    )
    return RecommendationClient(
        base_url="https://recommendation.example.test",
        http_client=http_client,
    )
