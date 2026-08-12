"""Application factory, health, request ID, and OpenAPI tests."""

import pytest

from financial_rag.api import ApiContainer, ApiSettings, create_app
from tests.api.client import api_client
from tests.api.helpers import configured_container


@pytest.mark.asyncio
async def test_liveness_works_without_configured_services() -> None:
    async with api_client(create_app(settings=ApiSettings(app_env="test"))) as client:
        response = await client.get("/health/live", headers={"X-Request-ID": "test-request-1"})

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "financial-rag-platform",
        "version": "0.1.0",
    }
    assert response.headers["X-Request-ID"] == "test-request-1"


@pytest.mark.asyncio
async def test_readiness_is_503_until_retrieval_is_injected() -> None:
    async with (
        api_client(create_app(container=ApiContainer())) as unavailable,
        api_client(create_app(container=configured_container())) as ready,
    ):
        unavailable_response = await unavailable.get("/health/ready")
        ready_response = await ready.get("/health/ready")

    assert unavailable_response.status_code == 503
    assert unavailable_response.json()["status"] == "unavailable"
    assert ready_response.status_code == 200
    assert ready_response.json() == {
        "status": "ready",
        "components": {
            "retrieval": "ready",
            "generation": "unavailable",
            "evaluation": "ready",
            "revisions": "ready",
            "indexing": "unavailable",
        },
    }


@pytest.mark.asyncio
async def test_invalid_request_id_is_replaced_with_bounded_generated_value() -> None:
    async with api_client(create_app()) as client:
        response = await client.get(
            "/health/live", headers={"X-Request-ID": "invalid id with spaces"}
        )

    request_id = response.headers["X-Request-ID"]
    assert request_id != "invalid id with spaces"
    assert len(request_id) == 32


@pytest.mark.asyncio
async def test_openapi_exposes_grounded_query_and_retrieval_routes() -> None:
    async with api_client(create_app(container=configured_container())) as client:
        schema = (await client.get("/openapi.json")).json()

    assert set(schema["paths"]) == {
        "/health/live",
        "/health/ready",
        "/api/v1/query",
        "/api/v1/evaluations/retrieval",
        "/api/v1/retrieval/query",
        "/api/v1/corpora/{corpus_revision_id}",
        "/api/v1/indexes/{index_revision_id}",
        "/api/v1/corpus-jobs",
        "/api/v1/corpus-jobs/{job_id}",
        "/api/v1/indexes/{index_revision_id}/activate",
        "/api/v1/corpora",
        "/api/v1/indexes",
    }
    assert schema["info"]["version"] == "0.1.0"
    answer_responses = schema["paths"]["/api/v1/query"]["post"]["responses"]
    assert {"200", "400", "422", "502", "503"}.issubset(answer_responses)
    query_responses = schema["paths"]["/api/v1/retrieval/query"]["post"]["responses"]
    assert {"200", "400", "422", "503"}.issubset(query_responses)
    assert (
        query_responses["422"]["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/ErrorResponse"
    )


@pytest.mark.asyncio
async def test_docs_can_be_disabled_without_affecting_health() -> None:
    app = create_app(settings=ApiSettings(app_env="test", api_docs_enabled=False))
    async with api_client(app) as client:
        assert (await client.get("/openapi.json")).status_code == 404
        assert (await client.get("/docs")).status_code == 404
        assert (await client.get("/health/live")).status_code == 200
