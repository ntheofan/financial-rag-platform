"""Paired-run, failure, answer, provenance, and export tests."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from financial_rag.core.errors import EvaluationError, RetrievalError
from financial_rag.domain.evaluation import (
    BenchmarkDataset,
    BenchmarkItem,
    EvaluationConfig,
    EvaluationStatus,
)
from financial_rag.domain.generation import ModelAnswer
from financial_rag.domain.retrieval import RetrievalMode, RetrievalResult
from financial_rag.evaluation.reports import write_evaluation_report
from financial_rag.evaluation.runner import EvaluationRunner
from financial_rag.generation.service import GroundedGenerationService
from tests.api.helpers import retrieval_service
from tests.unit.generation.helpers import FakeGenerationAdapter


def _dataset() -> BenchmarkDataset:
    retrieval = retrieval_service()
    capex = retrieval.retrieve("capital expenditures", mode=RetrievalMode.DENSE).chunks[0]
    revenue = retrieval.retrieve("revenue", mode=RetrievalMode.DENSE).chunks[0]
    return BenchmarkDataset(
        dataset_id="synthetic-paired-v1",
        items=(
            BenchmarkItem(
                query_id="q-capex",
                query="capital expenditures",
                relevant_chunk_ids=(capex.chunk_id,),
                expected_answer="Supported answer.",
            ),
            BenchmarkItem(
                query_id="q-revenue",
                query="revenue",
                relevant_chunk_ids=(revenue.chunk_id,),
                expected_answer="Supported answer.",
            ),
        ),
    )


def test_runner_builds_complete_paired_matrix_and_aggregates() -> None:
    report = EvaluationRunner(
        retrieval=retrieval_service(),
        clock=lambda: datetime(2026, 8, 12, tzinfo=UTC),
    ).evaluate(_dataset())

    assert len(report.items) == 6
    assert [aggregate.mode for aggregate in report.aggregates] == list(RetrievalMode)
    assert all(aggregate.query_count == 2 for aggregate in report.aggregates)
    assert all(aggregate.mrr is not None for aggregate in report.aggregates)
    assert all(aggregate.answer_skipped == 2 for aggregate in report.aggregates)
    for mode in RetrievalMode:
        assert {item.query_id for item in report.items if item.mode is mode} == {
            "q-capex",
            "q-revenue",
        }


def test_answer_metrics_run_only_when_requested_and_configured() -> None:
    retrieval = retrieval_service()
    generation = GroundedGenerationService(
        retrieval=retrieval,
        generator=FakeGenerationAdapter(
            ModelAnswer(answer="Supported answer.", abstained=False, citation_ids=("C1",))
        ),
    )
    config = EvaluationConfig(
        modes=(RetrievalMode.DENSE,),
        hit_ks=(1,),
        include_answer_metrics=True,
    )

    report = EvaluationRunner(retrieval=retrieval, generation=generation).evaluate(
        _dataset(), config=config
    )

    assert all(item.answer_status is EvaluationStatus.COMPLETED for item in report.items)
    assert report.aggregates[0].exact_match == 1.0
    assert report.aggregates[0].token_f1 == 1.0


class FailingRetrieval:
    def retrieve(self, query: str, *, mode: RetrievalMode) -> RetrievalResult:
        if query == "revenue":
            raise RetrievalError("private provider detail")
        return retrieval_service().retrieve(query, mode=mode)


def test_failed_query_is_null_and_excluded_from_metric_denominator() -> None:
    config = EvaluationConfig(modes=(RetrievalMode.DENSE,), hit_ks=(1,))

    report = EvaluationRunner(retrieval=FailingRetrieval()).evaluate(_dataset(), config=config)

    failed = next(item for item in report.items if item.query_id == "q-revenue")
    assert failed.retrieval_status is EvaluationStatus.FAILED
    assert failed.reciprocal_rank is None
    assert failed.hit_at_k == ()
    assert failed.retrieval_issue is not None
    assert "private" not in failed.retrieval_issue.message
    assert report.aggregates[0].retrieval_completed == 1
    assert report.aggregates[0].retrieval_failed == 1


def test_export_contains_ids_and_metrics_but_no_query_or_answer_text(tmp_path: Path) -> None:
    report = EvaluationRunner(retrieval=retrieval_service()).evaluate(_dataset())
    output = tmp_path / "evaluation-runs" / "report.json"

    write_evaluation_report(report, output)
    text = output.read_text(encoding="utf-8")

    assert "q-capex" in text
    assert 'capital expenditures"' not in text
    assert "Supported answer" not in text
    with pytest.raises(EvaluationError, match="already exists"):
        write_evaluation_report(report, output)
