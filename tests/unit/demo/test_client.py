"""Offline contract tests for the Streamlit-to-FastAPI client."""

import json
from datetime import UTC, datetime

import httpx
import pytest

from financial_rag.api.schemas import (
    ComponentStatus,
    ErrorBody,
    ErrorResponse,
    ReadinessComponents,
    ReadyResponse,
)
from financial_rag.demo.client import DemoApiError, FinancialRagApiClient
from financial_rag.demo.settings import DemoSettings
from financial_rag.domain.evaluation import BenchmarkDataset, BenchmarkItem, EvaluationConfig
from financial_rag.domain.generation import ModelAnswer
from financial_rag.domain.indexing import (
    ActiveIndexSelection,
    CorpusBuildJob,
    CorpusBuildStatus,
    UploadDocument,
)
from financial_rag.domain.retrieval import RetrievalMode
from financial_rag.evaluation.runner import EvaluationRunner
from financial_rag.generation.service import GroundedGenerationService
from tests.api.helpers import retrieval_service
from tests.unit.generation.helpers import FakeGenerationAdapter


def _settings() -> DemoSettings:
    return DemoSettings(
        financial_rag_api_url="http://testserver",
        demo_request_timeout_seconds=5,
    )


def _grounded_service() -> GroundedGenerationService:
    return GroundedGenerationService(
        retrieval=retrieval_service(),
        generator=FakeGenerationAdapter(
            ModelAnswer(answer="Supported answer.", abstained=False, citation_ids=("C1",))
        ),
    )


def test_readiness_accepts_structured_503_as_capability_state() -> None:
    payload = ReadyResponse(
        status=ComponentStatus.UNAVAILABLE,
        components=ReadinessComponents(
            retrieval=ComponentStatus.UNAVAILABLE,
            generation=ComponentStatus.UNAVAILABLE,
            evaluation=ComponentStatus.UNAVAILABLE,
            revisions=ComponentStatus.UNAVAILABLE,
        ),
    )
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(503, json=payload.model_dump(mode="json"))
    )

    readiness = FinancialRagApiClient(_settings(), transport=transport).readiness()

    assert readiness.status is ComponentStatus.UNAVAILABLE


def test_answer_parses_full_grounded_contract() -> None:
    service = _grounded_service()

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        answer = service.answer(payload["query"], mode=RetrievalMode(payload["mode"]))
        return httpx.Response(200, json=answer.model_dump(mode="json"))

    client = FinancialRagApiClient(_settings(), transport=httpx.MockTransport(handler))

    answer = client.answer("What were capital expenditures?", mode=RetrievalMode.HYBRID)

    assert answer.citations[0].citation_id == "C1"
    assert answer.retrieval.mode is RetrievalMode.HYBRID
    assert answer.contexts[0].chunk.chunk_id == answer.citations[0].chunk_id


def test_comparison_sends_identical_query_in_controlled_mode_order() -> None:
    service = retrieval_service()
    requests: list[tuple[str, RetrievalMode]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        mode = RetrievalMode(payload["mode"])
        requests.append((payload["query"], mode))
        result = service.retrieve(payload["query"], mode=mode)
        return httpx.Response(200, json=result.model_dump(mode="json"))

    client = FinancialRagApiClient(_settings(), transport=httpx.MockTransport(handler))

    comparison = client.compare_retrieval("  What was capex?  ")

    assert [item.mode for item in comparison.items] == list(RetrievalMode)
    assert requests == [("What was capex?", mode) for mode in RetrievalMode]
    assert all(item.result is not None for item in comparison.items)


def test_comparison_retains_safe_partial_failure() -> None:
    service = retrieval_service()

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        mode = RetrievalMode(payload["mode"])
        if mode is RetrievalMode.HYBRID_RERANKED:
            error = ErrorResponse(
                error=ErrorBody(
                    code="dependency_unavailable",
                    message="A required local dependency is unavailable.",
                    request_id="test-request",
                )
            )
            return httpx.Response(503, json=error.model_dump(mode="json"))
        result = service.retrieve(payload["query"], mode=mode)
        return httpx.Response(200, json=result.model_dump(mode="json"))

    comparison = FinancialRagApiClient(
        _settings(), transport=httpx.MockTransport(handler)
    ).compare_retrieval("What was capex?")

    assert comparison.items[0].result is not None
    assert comparison.items[1].result is not None
    assert comparison.items[2].failure is not None
    assert comparison.items[2].failure.code == "dependency_unavailable"


def test_unreachable_api_uses_safe_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("private detail", request=request)

    client = FinancialRagApiClient(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(DemoApiError, match="Cannot reach") as raised:
        client.readiness()

    assert raised.value.code == "api_unreachable"
    assert "private detail" not in str(raised.value)


def test_malformed_success_response_is_rejected() -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json={"unexpected": True}))
    client = FinancialRagApiClient(_settings(), transport=transport)

    with pytest.raises(DemoApiError, match="expected contract"):
        client.retrieve("What changed?", mode=RetrievalMode.DENSE)


def test_demo_client_parses_evaluation_report() -> None:
    retrieval = retrieval_service()
    relevant = retrieval.retrieve("capital expenditures", mode=RetrievalMode.DENSE).chunks[0]
    dataset = BenchmarkDataset(
        dataset_id="synthetic-demo-eval",
        items=(
            BenchmarkItem(
                query_id="q1",
                query="capital expenditures",
                relevant_chunk_ids=(relevant.chunk_id,),
            ),
        ),
    )
    runner = EvaluationRunner(retrieval=retrieval)

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        received_dataset = BenchmarkDataset.model_validate(payload["dataset"])
        config = EvaluationConfig.model_validate(payload["config"])
        report = runner.evaluate(received_dataset, config=config)
        return httpx.Response(200, json=report.model_dump(mode="json"))

    client = FinancialRagApiClient(_settings(), transport=httpx.MockTransport(handler))

    report = client.evaluate(dataset, config=EvaluationConfig(hit_ks=(1,)))

    assert report.manifest.dataset_id == "synthetic-demo-eval"
    assert len(report.items) == 3


def test_demo_client_sends_multipart_upload_and_parses_job() -> None:
    now = datetime(2026, 8, 12, tzinfo=UTC)
    job = CorpusBuildJob(
        job_id="job_" + "a" * 32,
        status=CorpusBuildStatus.PENDING,
        label="demo",
        input_file_count=1,
        created_at=now,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["content-type"].startswith("multipart/form-data")
        assert b"synthetic.md" in request.content
        assert b"Synthetic evidence" in request.content
        return httpx.Response(202, json=job.model_dump(mode="json"))

    client = FinancialRagApiClient(_settings(), transport=httpx.MockTransport(handler))
    created = client.upload_documents(
        (UploadDocument(filename="synthetic.md", content=b"Synthetic evidence"),),
        label="demo",
    )

    assert created == job


def test_demo_client_lists_jobs_and_activates_index() -> None:
    now = datetime(2026, 8, 12, tzinfo=UTC)
    job = CorpusBuildJob(
        job_id="job_" + "a" * 32,
        status=CorpusBuildStatus.PENDING,
        input_file_count=1,
        created_at=now,
    )
    selection = ActiveIndexSelection(
        corpus_revision_id="corpus_" + "b" * 32,
        index_revision_id="index_" + "c" * 32,
        activated_at=now,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/corpus-jobs":
            return httpx.Response(200, json=[job.model_dump(mode="json")])
        return httpx.Response(200, json=selection.model_dump(mode="json"))

    client = FinancialRagApiClient(_settings(), transport=httpx.MockTransport(handler))

    assert client.list_corpus_jobs() == (job,)
    assert client.activate_index(selection.index_revision_id) == selection
