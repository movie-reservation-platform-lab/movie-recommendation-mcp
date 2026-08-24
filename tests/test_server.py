from __future__ import annotations

from typing import Any

import pytest

from axum_tools_mcp import server
from axum_tools_mcp.recommendation_client import RecommendationClientError, RequestMetadata


class FakeRecommendationClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def recommendations(
        self,
        *,
        limit: int,
        preference: str | None,
        metadata: RequestMetadata,
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "recommendations",
                {"limit": limit, "preference": preference, "metadata": metadata},
            )
        )
        return {"recommendations": [{"id": "movie-1"}]}

    async def health(self, metadata: RequestMetadata) -> dict[str, Any]:
        self.calls.append(("health", {"metadata": metadata}))
        return {"status": "ok"}


@pytest.fixture
def fake_client(monkeypatch: pytest.MonkeyPatch) -> FakeRecommendationClient:
    client = FakeRecommendationClient()
    monkeypatch.setattr(server, "client", client)
    return client


@pytest.mark.asyncio
async def test_recommendation_tool_maps_result_and_propagates_context(
    fake_client: FakeRecommendationClient,
) -> None:
    result = await server.recommendation_get_movies(
        limit=200,
        preference="comedy",
        fault="ignored",
        demo_fault="recommendation-slow",
        correlation_id="correlation-1",
    )

    assert result == {
        "ok": True,
        "service_name": "movie-recommendation-mcp",
        "fault": "recommendation-slow",
        "recommendations": [{"id": "movie-1"}],
    }
    _, call = fake_client.calls[0]
    assert call["limit"] == server.MAX_LIMIT
    assert call["preference"] == "comedy"
    assert call["metadata"].demo_fault == "recommendation-slow"
    assert call["metadata"].correlation_id == "correlation-1"


@pytest.mark.asyncio
async def test_recommendation_tool_returns_bounded_dependency_error(
    fake_client: FakeRecommendationClient,
) -> None:
    async def fail_recommendations(
        *,
        limit: int,
        preference: str | None,
        metadata: RequestMetadata,
    ) -> dict[str, Any]:
        raise RecommendationClientError(500, {"error": "sensitive downstream detail"})

    fake_client.recommendations = fail_recommendations  # type: ignore[method-assign]

    result = await server.recommendation_get_movies()

    assert result == {
        "ok": False,
        "service_name": "movie-recommendation-mcp",
        "tool_name": "recommendation_get_movies",
        "fault": "none",
        "status_code": 500,
        "error": "recommendation_dependency_failed",
    }


@pytest.mark.asyncio
async def test_health_tool_returns_bounded_dependency_error(fake_client: FakeRecommendationClient) -> None:
    async def fail_health(metadata: RequestMetadata) -> dict[str, Any]:
        raise RecommendationClientError(503, {"error": "sensitive downstream detail"})

    fake_client.health = fail_health  # type: ignore[method-assign]

    result = await server.recommendation_health(demo_fault="recommendation-error")

    assert result == {
        "ok": False,
        "service_name": "movie-recommendation-mcp",
        "tool_name": "recommendation_health",
        "fault": "recommendation-error",
        "status_code": 503,
        "error": "recommendation_dependency_failed",
    }
