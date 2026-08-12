"""HTTP tests for all reproducible retrieval modes."""

import pytest

from financial_rag.api import create_app
from tests.api.client import api_client
from tests.api.helpers import configured_container


@pytest.mark.parametrize("mode", ["dense", "hybrid", "hybrid_reranked"])
@pytest.mark.asyncio
async def test_query_endpoint_preserves_transparent_retrieval_contract(mode: str) -> None:
    async with api_client(create_app(container=configured_container())) as client:
        response = await client.post(
            "/api/v1/retrieval/query",
            json={"query": "What was capex?", "mode": mode},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == mode
    assert body["document_unknown"] is True
    assert body["query"] == "What was capex?"
    assert "answer" not in body
    assert [chunk["rank"] for chunk in body["chunks"]] == [1, 2]
    assert all(chunk["chunk_id"].startswith("chunk_") for chunk in body["chunks"])
    assert all(chunk["source_file"] == "synthetic/acme-2025-10k.md" for chunk in body["chunks"])
    if mode == "dense":
        assert all(chunk["dense_score"] is not None for chunk in body["chunks"])
    elif mode == "hybrid":
        assert all(chunk["rrf_score"] is not None for chunk in body["chunks"])
    else:
        assert all(chunk["rerank_score"] is not None for chunk in body["chunks"])


@pytest.mark.asyncio
async def test_query_defaults_to_hybrid() -> None:
    async with api_client(create_app(container=configured_container())) as client:
        response = await client.post("/api/v1/retrieval/query", json={"query": "revenue"})

    assert response.status_code == 200
    assert response.json()["mode"] == "hybrid"


@pytest.mark.parametrize(
    "payload",
    [
        {"query": "   ", "mode": "hybrid"},
        {"query": "revenue", "mode": "unknown"},
        {"query": "revenue", "unexpected": True},
    ],
)
@pytest.mark.asyncio
async def test_invalid_queries_use_sanitized_error_envelope(
    payload: dict[str, object],
) -> None:
    async with api_client(create_app(container=configured_container())) as client:
        response = await client.post("/api/v1/retrieval/query", json=payload)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "request_validation_failed"
    assert error["request_id"] == response.headers["X-Request-ID"]
    assert error["details"]
    assert "input" not in error["details"][0]


@pytest.mark.asyncio
async def test_query_is_503_when_retrieval_is_not_configured() -> None:
    async with api_client(create_app()) as client:
        response = await client.post("/api/v1/retrieval/query", json={"query": "revenue"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"
