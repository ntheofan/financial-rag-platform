"""HTTP tests for bounded synchronous paired evaluation."""

import pytest

from financial_rag.api import ApiContainer, create_app
from financial_rag.domain.evaluation import BenchmarkDataset, BenchmarkItem
from financial_rag.domain.retrieval import RetrievalMode
from financial_rag.evaluation.runner import EvaluationRunner
from tests.api.client import api_client
from tests.api.helpers import retrieval_service


def _dataset_payload() -> dict[str, object]:
    retrieval = retrieval_service()
    relevant = retrieval.retrieve("capital expenditures", mode=RetrievalMode.DENSE).chunks[0]
    return BenchmarkDataset(
        dataset_id="synthetic-api-eval",
        items=(
            BenchmarkItem(
                query_id="q1",
                query="capital expenditures",
                relevant_chunk_ids=(relevant.chunk_id,),
            ),
        ),
    ).model_dump(mode="json")


@pytest.mark.asyncio
async def test_evaluation_endpoint_returns_complete_paired_report_without_text() -> None:
    retrieval = retrieval_service()
    app = create_app(
        container=ApiContainer(
            retrieval=retrieval,
            evaluation=EvaluationRunner(retrieval=retrieval),
        )
    )

    async with api_client(app) as client:
        response = await client.post(
            "/api/v1/evaluations/retrieval",
            json={"dataset": _dataset_payload(), "config": {"hit_ks": [1, 3]}},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["manifest"]["query_count"] == 1
    assert [aggregate["mode"] for aggregate in body["aggregates"]] == [
        "dense",
        "hybrid",
        "hybrid_reranked",
    ]
    assert len(body["items"]) == 3
    assert "capital expenditures" not in response.text
    assert "content" not in body["items"][0]


@pytest.mark.asyncio
async def test_evaluation_endpoint_is_503_without_evaluator() -> None:
    async with api_client(
        create_app(container=ApiContainer(retrieval=retrieval_service()))
    ) as client:
        response = await client.post(
            "/api/v1/evaluations/retrieval",
            json={"dataset": _dataset_payload(), "config": {}},
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


@pytest.mark.asyncio
async def test_evaluation_request_rejects_duplicate_query_ids() -> None:
    dataset = _dataset_payload()
    dataset["items"] = [dataset["items"][0], dataset["items"][0]]  # type: ignore[index]
    retrieval = retrieval_service()
    app = create_app(
        container=ApiContainer(
            retrieval=retrieval,
            evaluation=EvaluationRunner(retrieval=retrieval),
        )
    )

    async with api_client(app) as client:
        response = await client.post(
            "/api/v1/evaluations/retrieval",
            json={"dataset": dataset, "config": {}},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_validation_failed"
