"""Offline tests for the real-service local acceptance orchestrator."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from financial_rag.api.schemas import (
    ComponentStatus,
    ReadinessComponents,
    ReadyResponse,
)
from financial_rag.demo.client import ModeComparison, ModeComparisonItem
from financial_rag.domain.evaluation import BenchmarkDataset, EvaluationConfig, EvaluationReport
from financial_rag.domain.generation import GroundedAnswer, ModelAnswer
from financial_rag.domain.indexing import CorpusBuildJob, CorpusBuildStatus, UploadDocument
from financial_rag.domain.retrieval import RetrievalMode
from financial_rag.evaluation.runner import EvaluationRunner
from financial_rag.generation.service import GroundedGenerationService
from scripts.run_local_acceptance import (
    AcceptanceConfig,
    AcceptanceError,
    run_acceptance,
    validate_loopback_url,
)
from tests.api.helpers import retrieval_service
from tests.unit.generation.helpers import FakeGenerationAdapter

PROJECT_ROOT = Path(__file__).parents[1]
CONFIG_PATH = PROJECT_ROOT / "configs" / "release" / "local_acceptance_v1.json"
NOW = datetime(2026, 8, 12, tzinfo=UTC)
CORPUS_ID = "corpus_" + "a" * 32
INDEX_ID = "index_" + "b" * 32
JOB_ID = "job_" + "c" * 32


class FakeAcceptanceClient:
    """Exercise orchestration with the already tested deterministic services."""

    def __init__(self) -> None:
        self.retrieval = retrieval_service()
        self.generation = GroundedGenerationService(
            retrieval=self.retrieval,
            generator=FakeGenerationAdapter(
                ModelAnswer(
                    answer="Synthetic capital expenditures were supported by the filing.",
                    abstained=False,
                    citation_ids=("C1",),
                )
            ),
        )
        self.runner = EvaluationRunner(retrieval=self.retrieval)

    def readiness(self) -> ReadyResponse:
        return ReadyResponse(
            status=ComponentStatus.READY,
            components=ReadinessComponents(
                retrieval=ComponentStatus.READY,
                generation=ComponentStatus.READY,
                evaluation=ComponentStatus.READY,
                revisions=ComponentStatus.READY,
                indexing=ComponentStatus.READY,
            ),
        )

    def upload_documents(
        self,
        documents: tuple[UploadDocument, ...],
        *,
        label: str | None = None,
    ) -> CorpusBuildJob:
        assert documents[0].filename == "acme-2025-10k.md"
        assert b"original synthetic test fixture" in documents[0].content
        return CorpusBuildJob(
            job_id=JOB_ID,
            status=CorpusBuildStatus.PENDING,
            label=label,
            input_file_count=1,
            created_at=NOW,
        )

    def list_corpus_jobs(self, *, limit: int = 50) -> tuple[CorpusBuildJob, ...]:
        del limit
        return (
            CorpusBuildJob(
                job_id=JOB_ID,
                status=CorpusBuildStatus.COMPLETED,
                label="synthetic local acceptance corpus",
                input_file_count=1,
                corpus_revision_id=CORPUS_ID,
                index_revision_id=INDEX_ID,
                created_at=NOW,
                started_at=NOW,
                completed_at=NOW,
            ),
        )

    def compare_retrieval(self, query: str) -> ModeComparison:
        return ModeComparison(
            query=query,
            items=tuple(
                ModeComparisonItem(
                    mode=mode,
                    result=self.retrieval.retrieve(query, mode=mode),
                )
                for mode in RetrievalMode
            ),
        )

    def answer(self, query: str, *, mode: RetrievalMode) -> GroundedAnswer:
        return self.generation.answer(query, mode=mode)

    def evaluate(
        self,
        dataset: BenchmarkDataset,
        *,
        config: EvaluationConfig | None = None,
    ) -> EvaluationReport:
        return self.runner.evaluate(dataset, config=config)


def test_acceptance_orchestrator_returns_only_minimized_evidence() -> None:
    summary = run_acceptance(
        FakeAcceptanceClient(),
        AcceptanceConfig.from_json_file(CONFIG_PATH),
    )

    assert summary.status == "passed"
    assert summary.evaluation_completed_modes == tuple(RetrievalMode)
    serialized = summary.model_dump_json()
    assert "Synthetic capital" not in serialized
    assert "content" not in serialized
    assert "answer" not in serialized


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:8000",
        "http://example.com",
        "http://user:password@localhost:8000",
        "http://localhost:8000/api",
    ],
)
def test_acceptance_rejects_non_loopback_or_credentialed_targets(url: str) -> None:
    with pytest.raises(ValueError):
        validate_loopback_url(url)


def test_acceptance_fixture_cannot_escape_checked_synthetic_directory() -> None:
    config = AcceptanceConfig.from_json_file(CONFIG_PATH).model_copy(
        update={"fixture_path": Path("README.md")}
    )

    with pytest.raises(AcceptanceError, match="fixture_outside"):
        config.fixture()
