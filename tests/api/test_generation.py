"""HTTP tests for grounded generation with deterministic fake provider output."""

import pytest

from financial_rag.api import ApiContainer, create_app
from financial_rag.domain.generation import ModelAnswer
from financial_rag.generation.service import GroundedGenerationService
from tests.api.client import api_client
from tests.api.helpers import retrieval_service
from tests.unit.generation.helpers import FakeGenerationAdapter


def _container(answer: ModelAnswer) -> ApiContainer:
    retrieval = retrieval_service()
    generation = GroundedGenerationService(
        retrieval=retrieval,
        generator=FakeGenerationAdapter(answer),
    )
    return ApiContainer(retrieval=retrieval, generation=generation)


@pytest.mark.asyncio
async def test_grounded_query_returns_citations_contexts_and_retrieval_scores() -> None:
    app = create_app(
        container=_container(
            ModelAnswer(
                answer="Capital expenditures are supported by the filing.",
                abstained=False,
                citation_ids=("C1",),
            )
        )
    )

    async with api_client(app) as client:
        response = await client.post(
            "/api/v1/query",
            json={"query": "What were capital expenditures?", "mode": "hybrid"},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["citations"][0]["citation_id"] == "C1"
    assert body["contexts"][0]["chunk"]["chunk_id"] == body["citations"][0]["chunk_id"]
    assert body["retrieval"]["chunks"][0]["rrf_score"] is not None


@pytest.mark.asyncio
async def test_grounded_query_is_503_without_generation_service() -> None:
    async with api_client(
        create_app(container=ApiContainer(retrieval=retrieval_service()))
    ) as client:
        response = await client.post(
            "/api/v1/query",
            json={"query": "What changed?", "mode": "dense"},
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


@pytest.mark.asyncio
async def test_invalid_provider_citation_is_mapped_to_safe_502() -> None:
    app = create_app(
        container=_container(
            ModelAnswer(answer="Unsupported answer.", abstained=False, citation_ids=("C5",))
        )
    )

    async with api_client(app, raise_app_exceptions=False) as client:
        response = await client.post(
            "/api/v1/query",
            json={"query": "What changed?", "mode": "dense"},
        )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "generation_failed"
    assert "C5" not in response.text
