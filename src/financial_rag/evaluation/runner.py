"""Paired offline evaluation orchestration over explicit retrieval/generation ports."""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

import structlog

from financial_rag.core.errors import FinancialRAGError
from financial_rag.domain.evaluation import (
    BenchmarkDataset,
    BenchmarkItem,
    EvaluationConfig,
    EvaluationIssue,
    EvaluationItemResult,
    EvaluationReport,
    EvaluationRunManifest,
    EvaluationStatus,
    HitAtK,
    ModeAggregate,
)
from financial_rag.domain.fingerprints import ConfigurationFingerprint
from financial_rag.domain.generation import GroundedAnswer
from financial_rag.domain.retrieval import RetrievalMode, RetrievalResult
from financial_rag.evaluation.metrics import exact_match, retrieval_metrics, token_f1

logger = structlog.get_logger(__name__)


class EvaluationRetrieval(Protocol):
    """Retrieval port used by the offline runner."""

    def retrieve(self, query: str, *, mode: RetrievalMode) -> RetrievalResult: ...


class EvaluationGeneration(Protocol):
    """Optional grounded-answer port used only when answer metrics are requested."""

    def answer(self, query: str, *, mode: RetrievalMode) -> GroundedAnswer: ...


Clock = Callable[[], datetime]


@dataclass(frozen=True, slots=True)
class _AnswerOutcome:
    status: EvaluationStatus
    issue: EvaluationIssue | None = None
    exact_match: float | None = None
    token_f1: float | None = None
    abstained: bool | None = None


class EvaluationRunner:
    """Evaluate the identical validated query set across every configured mode."""

    def __init__(
        self,
        *,
        retrieval: EvaluationRetrieval,
        generation: EvaluationGeneration | None = None,
        corpus_fingerprint: ConfigurationFingerprint | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._retrieval = retrieval
        self._generation = generation
        self._corpus_fingerprint = corpus_fingerprint
        self._clock = clock or (lambda: datetime.now(UTC))

    def evaluate(
        self,
        dataset: BenchmarkDataset,
        *,
        config: EvaluationConfig | None = None,
    ) -> EvaluationReport:
        """Produce a complete paired matrix; failures remain null, never numeric zero."""
        resolved = config or EvaluationConfig()
        created_at = self._clock()
        items = tuple(
            self._evaluate_item(item, mode=mode, config=resolved)
            for mode in resolved.modes
            for item in dataset.items
        )
        manifest = EvaluationRunManifest(
            evaluation_run_id=_make_run_id(dataset, resolved, created_at),
            created_at=created_at,
            dataset_id=dataset.dataset_id,
            dataset_fingerprint=dataset.fingerprint,
            evaluation_configuration_fingerprint=resolved.fingerprint,
            corpus_fingerprint=self._corpus_fingerprint,
            query_count=len(dataset.items),
            modes=resolved.modes,
        )
        report = EvaluationReport(
            manifest=manifest,
            aggregates=tuple(
                _aggregate_mode(items, mode=mode, hit_ks=resolved.hit_ks) for mode in resolved.modes
            ),
            items=items,
        )
        logger.info(
            "evaluation_completed",
            evaluation_run_id=manifest.evaluation_run_id,
            dataset_fingerprint=manifest.dataset_fingerprint.value,
            query_count=manifest.query_count,
            modes=[mode.value for mode in manifest.modes],
        )
        return report

    def _evaluate_item(
        self,
        item: BenchmarkItem,
        *,
        mode: RetrievalMode,
        config: EvaluationConfig,
    ) -> EvaluationItemResult:
        try:
            result = self._retrieval.retrieve(item.query, mode=mode)
        except FinancialRAGError:
            return EvaluationItemResult(
                query_id=item.query_id,
                mode=mode,
                retrieval_status=EvaluationStatus.FAILED,
                retrieval_issue=EvaluationIssue(
                    code="retrieval_failed",
                    message="Retrieval failed for this query and mode.",
                ),
                answer_status=EvaluationStatus.SKIPPED,
                answer_issue=EvaluationIssue(
                    code="retrieval_failed",
                    message="Answer evaluation was skipped because retrieval failed.",
                ),
            )
        retrieved_ids = tuple(chunk.chunk_id for chunk in result.chunks)
        first_rank, reciprocal_rank, hits = retrieval_metrics(
            retrieved_ids,
            item.relevant_chunk_ids,
            hit_ks=config.hit_ks,
        )
        answer = self._evaluate_answer(item, mode=mode, config=config)
        return EvaluationItemResult(
            query_id=item.query_id,
            mode=mode,
            retrieval_status=EvaluationStatus.COMPLETED,
            retrieved_chunk_ids=retrieved_ids,
            first_relevant_rank=first_rank,
            reciprocal_rank=reciprocal_rank,
            hit_at_k=hits,
            retrieval_configuration_fingerprint=result.retrieval_configuration_fingerprint,
            answer_status=answer.status,
            answer_issue=answer.issue,
            exact_match=answer.exact_match,
            token_f1=answer.token_f1,
            abstained=answer.abstained,
        )

    def _evaluate_answer(
        self,
        item: BenchmarkItem,
        *,
        mode: RetrievalMode,
        config: EvaluationConfig,
    ) -> _AnswerOutcome:
        if not config.include_answer_metrics:
            return _skipped_answer("not_requested", "Answer metrics were not requested.")
        if item.expected_answer is None:
            return _skipped_answer("missing_reference", "No reference answer was supplied.")
        if self._generation is None:
            return _skipped_answer("generation_unavailable", "Generation is not configured.")
        try:
            answer = self._generation.answer(item.query, mode=mode)
        except FinancialRAGError:
            return _AnswerOutcome(
                status=EvaluationStatus.FAILED,
                issue=EvaluationIssue(
                    code="generation_failed",
                    message="Grounded generation failed for this query and mode.",
                ),
            )
        return _AnswerOutcome(
            status=EvaluationStatus.COMPLETED,
            exact_match=exact_match(answer.answer, item.expected_answer),
            token_f1=token_f1(answer.answer, item.expected_answer),
            abstained=answer.abstained,
        )


def _skipped_answer(code: str, message: str) -> _AnswerOutcome:
    return _AnswerOutcome(
        status=EvaluationStatus.SKIPPED,
        issue=EvaluationIssue(code=code, message=message),
    )


def _make_run_id(
    dataset: BenchmarkDataset,
    config: EvaluationConfig,
    created_at: datetime,
) -> str:
    payload = (
        f"{dataset.fingerprint.value}:{config.fingerprint.value}:{created_at.isoformat()}"
    ).encode()
    return f"eval_{hashlib.sha256(payload).hexdigest()[:32]}"


def _aggregate_mode(
    items: tuple[EvaluationItemResult, ...],
    *,
    mode: RetrievalMode,
    hit_ks: tuple[int, ...],
) -> ModeAggregate:
    selected = tuple(item for item in items if item.mode is mode)
    completed = tuple(
        item for item in selected if item.retrieval_status is EvaluationStatus.COMPLETED
    )
    completed_answers = tuple(
        item for item in selected if item.answer_status is EvaluationStatus.COMPLETED
    )
    hit_values = (
        tuple(
            HitAtK(
                k=k,
                value=sum(
                    next(metric.value for metric in item.hit_at_k if metric.k == k)
                    for item in completed
                )
                / len(completed),
            )
            for k in hit_ks
        )
        if completed
        else ()
    )
    return ModeAggregate(
        mode=mode,
        query_count=len(selected),
        retrieval_completed=len(completed),
        retrieval_failed=len(selected) - len(completed),
        mrr=(
            sum(item.reciprocal_rank or 0.0 for item in completed) / len(completed)
            if completed
            else None
        ),
        hit_at_k=hit_values,
        answer_completed=len(completed_answers),
        answer_skipped=sum(item.answer_status is EvaluationStatus.SKIPPED for item in selected),
        answer_failed=sum(item.answer_status is EvaluationStatus.FAILED for item in selected),
        exact_match=(
            sum(item.exact_match or 0.0 for item in completed_answers) / len(completed_answers)
            if completed_answers
            else None
        ),
        token_f1=(
            sum(item.token_f1 or 0.0 for item in completed_answers) / len(completed_answers)
            if completed_answers
            else None
        ),
    )
