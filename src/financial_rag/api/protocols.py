"""Structural ports consumed by the HTTP adapter."""

from typing import Protocol

from financial_rag.domain.evaluation import BenchmarkDataset, EvaluationConfig, EvaluationReport
from financial_rag.domain.generation import GroundedAnswer
from financial_rag.domain.indexing import (
    ActiveIndexSelection,
    CorpusBuildJob,
    CorpusBuildJobId,
    UploadDocument,
)
from financial_rag.domain.retrieval import RetrievalMode, RetrievalResult
from financial_rag.domain.revisions import (
    CorpusRevision,
    CorpusRevisionId,
    IndexRevision,
    IndexRevisionId,
)
from financial_rag.indexing.staging import StagedUploadBatch


class RetrievalUseCase(Protocol):
    """Minimal synchronous retrieval surface required by the query endpoint."""

    def retrieve(self, query: str, *, mode: RetrievalMode) -> RetrievalResult:
        """Return transparent ranked chunks for one retrieval mode."""
        ...


class GroundedGenerationUseCase(Protocol):
    """Synchronous grounded-answer surface required by the generation endpoint."""

    def answer(self, query: str, *, mode: RetrievalMode) -> GroundedAnswer:
        """Return a grounded answer and its transparent retrieval result."""
        ...


class EvaluationUseCase(Protocol):
    """Synchronous paired-evaluation surface required by the evaluation endpoint."""

    def evaluate(
        self,
        dataset: BenchmarkDataset,
        *,
        config: EvaluationConfig | None = None,
    ) -> EvaluationReport:
        """Evaluate one validated benchmark across its configured modes."""
        ...


class RevisionReader(Protocol):
    """Read-only revision metadata surface required by API routes."""

    async def get_corpus_revision(self, corpus_revision_id: CorpusRevisionId) -> CorpusRevision:
        """Load corpus metadata without returning all chunk text."""
        ...

    async def get_index_revision(self, index_revision_id: IndexRevisionId) -> IndexRevision:
        """Load index metadata without returning embedding vectors."""
        ...

    async def list_corpus_revisions(self, *, limit: int = 50) -> tuple[CorpusRevision, ...]:
        """List recent corpus metadata without loading chunk text."""
        ...

    async def list_index_revisions(self, *, limit: int = 50) -> tuple[IndexRevision, ...]:
        """List recent index metadata without loading vectors."""
        ...


class CorpusIndexingUseCase(Protocol):
    """Bounded local upload, build-job, and activation surface."""

    async def submit_uploads(
        self,
        uploads: tuple[UploadDocument, ...],
        *,
        label: str | None = None,
    ) -> tuple[CorpusBuildJob, StagedUploadBatch]: ...

    async def run_staged_job(self, job_id: CorpusBuildJobId, batch: StagedUploadBatch) -> None: ...

    async def get_job(self, job_id: CorpusBuildJobId) -> CorpusBuildJob: ...

    async def list_jobs(self, *, limit: int = 50) -> tuple[CorpusBuildJob, ...]: ...

    async def activate_index(self, index_revision_id: str) -> ActiveIndexSelection: ...
