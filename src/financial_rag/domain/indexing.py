"""Contracts for bounded local corpus-build jobs and active index selection."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from financial_rag.domain.revisions import CorpusRevisionId, IndexRevisionId

CorpusBuildJobId = Annotated[str, Field(pattern=r"^job_[0-9a-f]{32}$")]


class CorpusBuildStatus(StrEnum):
    """Durable state of one bounded local build attempt."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


def make_corpus_build_job_id(*, value: UUID | None = None) -> CorpusBuildJobId:
    """Create an opaque job identifier without encoding filenames or content."""
    return f"job_{(value or uuid4()).hex}"


class CorpusBuildJob(BaseModel):
    """Privacy-minimized durable status for one local indexing job."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    job_id: CorpusBuildJobId
    status: CorpusBuildStatus
    label: str | None = Field(default=None, max_length=200)
    input_file_count: int = Field(ge=1, le=10)
    corpus_revision_id: CorpusRevisionId | None = None
    index_revision_id: IndexRevisionId | None = None
    error_code: str | None = Field(default=None, pattern=r"^[a-z0-9_]{1,64}$")
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @field_validator("created_at", "started_at", "completed_at")
    @classmethod
    def timestamps_must_be_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("job timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def state_fields_are_coherent(self) -> Self:
        if self.status is CorpusBuildStatus.PENDING:
            if any(
                value is not None
                for value in (
                    self.started_at,
                    self.completed_at,
                    self.corpus_revision_id,
                    self.index_revision_id,
                    self.error_code,
                )
            ):
                raise ValueError("pending jobs cannot contain outcome fields")
        elif self.status is CorpusBuildStatus.RUNNING:
            if self.started_at is None or self.completed_at is not None:
                raise ValueError("running jobs require only started_at")
        elif self.status is CorpusBuildStatus.COMPLETED:
            if (
                self.started_at is None
                or self.completed_at is None
                or self.corpus_revision_id is None
                or self.index_revision_id is None
                or self.error_code is not None
            ):
                raise ValueError("completed jobs require revision IDs and timestamps")
        elif self.status is CorpusBuildStatus.FAILED and (
            self.started_at is None or self.completed_at is None or self.error_code is None
        ):
            raise ValueError("failed jobs require timestamps and an error code")
        return self


class ActiveIndexSelection(BaseModel):
    """Confirmation of the in-memory index selected for subsequent queries."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    corpus_revision_id: CorpusRevisionId
    index_revision_id: IndexRevisionId
    activated_at: datetime

    @field_validator("activated_at")
    @classmethod
    def activated_at_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("activated_at must be timezone-aware")
        return value


class UploadDocument(BaseModel):
    """One bounded in-memory upload crossing from HTTP into staging logic."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    filename: str = Field(min_length=1, max_length=255)
    content: bytes = Field(min_length=1, max_length=20 * 1024 * 1024)
