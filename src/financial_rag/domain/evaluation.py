"""Versioned, immutable contracts for paired retrieval and answer evaluation."""

import json
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from financial_rag.core.errors import EvaluationError
from financial_rag.domain.fingerprints import ConfigurationFingerprint, fingerprint_model
from financial_rag.domain.retrieval import RetrievalMode

QueryId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")]
EvaluationRunId = Annotated[str, StringConstraints(pattern=r"^eval_[a-f0-9]{32}$")]


class BenchmarkItem(BaseModel):
    """One query with explicit chunk-level relevance and optional reference answer."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    query_id: QueryId
    query: str = Field(min_length=1, max_length=4096)
    relevant_chunk_ids: tuple[str, ...] = Field(min_length=1)
    expected_answer: str | None = Field(default=None, min_length=1, max_length=8192)

    @field_validator("relevant_chunk_ids")
    @classmethod
    def relevance_ids_are_unique_and_non_blank(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(value.strip() for value in values)
        if any(not value for value in normalized):
            raise ValueError("relevant chunk IDs cannot be blank")
        if len(normalized) != len(set(normalized)):
            raise ValueError("relevant chunk IDs must be unique")
        return normalized


class BenchmarkDataset(BaseModel):
    """Small public-contract benchmark; source documents are never embedded here."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    schema_version: Literal["platform_eval_dataset_v1"] = "platform_eval_dataset_v1"
    dataset_id: str = Field(min_length=1, max_length=128)
    items: tuple[BenchmarkItem, ...] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def query_ids_are_unique(self) -> Self:
        query_ids = [item.query_id for item in self.items]
        if len(query_ids) != len(set(query_ids)):
            raise ValueError("benchmark query IDs must be unique")
        return self

    @property
    def fingerprint(self) -> ConfigurationFingerprint:
        """Fingerprint the complete validated dataset contract."""
        return fingerprint_model(self)


class EvaluationConfig(BaseModel):
    """Versioned paired-run configuration for the corrected platform protocol."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol_version: Literal["platform_eval_v1"] = "platform_eval_v1"
    modes: tuple[RetrievalMode, ...] = tuple(RetrievalMode)
    hit_ks: tuple[int, ...] = (1, 3, 5, 10)
    include_answer_metrics: bool = False

    @field_validator("modes")
    @classmethod
    def modes_are_unique_and_non_empty(
        cls, values: tuple[RetrievalMode, ...]
    ) -> tuple[RetrievalMode, ...]:
        if not values:
            raise ValueError("at least one retrieval mode is required")
        if len(values) != len(set(values)):
            raise ValueError("retrieval modes must be unique")
        return values

    @field_validator("hit_ks")
    @classmethod
    def hit_ks_are_sorted_unique_and_bounded(cls, values: tuple[int, ...]) -> tuple[int, ...]:
        if not values or any(value <= 0 or value > 100 for value in values):
            raise ValueError("Hit@K values must be between 1 and 100")
        if tuple(sorted(set(values))) != values:
            raise ValueError("Hit@K values must be sorted and unique")
        return values

    @property
    def fingerprint(self) -> ConfigurationFingerprint:
        return fingerprint_model(self)

    @classmethod
    def from_json_file(cls, path: Path) -> Self:
        """Load a checked-in, non-secret evaluation configuration."""
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return cls.model_validate(payload)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise EvaluationError("Unable to load the evaluation configuration.") from exc


class EvaluationStatus(StrEnum):
    """Status that keeps skipped/failed work distinct from numeric zero."""

    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class EvaluationIssue(BaseModel):
    """Safe machine-readable failure or skip explanation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=256)


class HitAtK(BaseModel):
    """One per-query or aggregate Hit@K value."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    k: int = Field(gt=0, le=100)
    value: float = Field(ge=0, le=1)


class EvaluationItemResult(BaseModel):
    """One query/mode result without source chunk text or generated answer text."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    query_id: QueryId
    mode: RetrievalMode
    retrieval_status: EvaluationStatus
    retrieval_issue: EvaluationIssue | None = None
    retrieved_chunk_ids: tuple[str, ...] = ()
    first_relevant_rank: int | None = Field(default=None, ge=1)
    reciprocal_rank: float | None = Field(default=None, ge=0, le=1)
    hit_at_k: tuple[HitAtK, ...] = ()
    retrieval_configuration_fingerprint: ConfigurationFingerprint | None = None
    answer_status: EvaluationStatus
    answer_issue: EvaluationIssue | None = None
    exact_match: float | None = Field(default=None, ge=0, le=1)
    token_f1: float | None = Field(default=None, ge=0, le=1)
    abstained: bool | None = None

    @model_validator(mode="after")
    def statuses_match_metrics(self) -> Self:
        if self.retrieval_status is EvaluationStatus.COMPLETED:
            if self.reciprocal_rank is None or not self.hit_at_k:
                raise ValueError("completed retrieval requires metrics")
            if self.retrieval_issue is not None:
                raise ValueError("completed retrieval cannot contain an issue")
        elif self.reciprocal_rank is not None or self.hit_at_k:
            raise ValueError("incomplete retrieval cannot contain numeric metrics")
        if self.answer_status is EvaluationStatus.COMPLETED:
            if self.exact_match is None or self.token_f1 is None or self.abstained is None:
                raise ValueError("completed answer evaluation requires metrics")
            if self.answer_issue is not None:
                raise ValueError("completed answer evaluation cannot contain an issue")
        elif self.exact_match is not None or self.token_f1 is not None:
            raise ValueError("incomplete answer evaluation cannot contain numeric metrics")
        return self


class ModeAggregate(BaseModel):
    """Aggregate metrics with explicit denominators and failure counts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: RetrievalMode
    query_count: int = Field(gt=0)
    retrieval_completed: int = Field(ge=0)
    retrieval_failed: int = Field(ge=0)
    mrr: float | None = Field(default=None, ge=0, le=1)
    hit_at_k: tuple[HitAtK, ...]
    answer_completed: int = Field(ge=0)
    answer_skipped: int = Field(ge=0)
    answer_failed: int = Field(ge=0)
    exact_match: float | None = Field(default=None, ge=0, le=1)
    token_f1: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def counts_have_consistent_denominators(self) -> Self:
        if self.retrieval_completed + self.retrieval_failed != self.query_count:
            raise ValueError("retrieval aggregate counts do not match query count")
        if self.answer_completed + self.answer_skipped + self.answer_failed != self.query_count:
            raise ValueError("answer aggregate counts do not match query count")
        if (self.retrieval_completed == 0) != (self.mrr is None):
            raise ValueError("MRR must be null exactly when no retrieval completed")
        if (self.answer_completed == 0) != (self.exact_match is None):
            raise ValueError("answer metrics must be null exactly when no answer completed")
        return self


class EvaluationRunManifest(BaseModel):
    """Provenance for one immutable in-memory or exported evaluation run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evaluation_run_id: EvaluationRunId
    protocol_version: Literal["platform_eval_v1"] = "platform_eval_v1"
    created_at: datetime
    dataset_id: str
    dataset_fingerprint: ConfigurationFingerprint
    evaluation_configuration_fingerprint: ConfigurationFingerprint
    corpus_fingerprint: ConfigurationFingerprint | None = None
    query_count: int = Field(gt=0)
    modes: tuple[RetrievalMode, ...]

    @field_validator("created_at")
    @classmethod
    def timestamp_is_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value


class EvaluationReport(BaseModel):
    """Complete paired evaluation output with no source or answer text."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest: EvaluationRunManifest
    aggregates: tuple[ModeAggregate, ...]
    items: tuple[EvaluationItemResult, ...]

    @model_validator(mode="after")
    def matrix_is_paired_and_complete(self) -> Self:
        expected_count = self.manifest.query_count * len(self.manifest.modes)
        if len(self.items) != expected_count:
            raise ValueError("evaluation report does not contain the complete query/mode matrix")
        query_sets = {
            mode: {item.query_id for item in self.items if item.mode is mode}
            for mode in self.manifest.modes
        }
        if len({frozenset(values) for values in query_sets.values()}) != 1:
            raise ValueError("paired evaluation modes do not contain equal query ID sets")
        if tuple(aggregate.mode for aggregate in self.aggregates) != self.manifest.modes:
            raise ValueError("aggregate mode order must match the run manifest")
        return self
