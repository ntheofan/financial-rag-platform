"""Structural ports for durable corpus-build orchestration."""

from collections.abc import Sequence
from typing import Protocol

from numpy.typing import ArrayLike

from financial_rag.domain.fingerprints import ConfigurationFingerprint
from financial_rag.domain.indexing import CorpusBuildJob, CorpusBuildJobId
from financial_rag.domain.retrieval import ChunkRecord, EmbeddingIndexManifest
from financial_rag.domain.revisions import CorpusRevision, CorpusRevisionId, IndexRevision


class CorpusBuildJobStore(Protocol):
    """Durable job state required by the indexing service."""

    async def create_job(self, job: CorpusBuildJob) -> CorpusBuildJob: ...

    async def mark_running(self, job_id: CorpusBuildJobId) -> CorpusBuildJob: ...

    async def mark_completed(
        self,
        job_id: CorpusBuildJobId,
        *,
        corpus_revision_id: str,
        index_revision_id: str,
    ) -> CorpusBuildJob: ...

    async def mark_failed(self, job_id: CorpusBuildJobId, *, error_code: str) -> CorpusBuildJob: ...

    async def get_job(self, job_id: CorpusBuildJobId) -> CorpusBuildJob: ...

    async def list_jobs(self, *, limit: int = 50) -> tuple[CorpusBuildJob, ...]: ...


class RevisionWriter(Protocol):
    """Immutable revision writes used by one corpus-build job."""

    async def persist_corpus(
        self,
        records: tuple[ChunkRecord, ...],
        *,
        chunking_configuration_fingerprint: ConfigurationFingerprint,
        label: str | None = None,
    ) -> CorpusRevision: ...

    async def persist_index(
        self,
        corpus_revision_id: CorpusRevisionId,
        *,
        records: tuple[ChunkRecord, ...],
        embeddings: ArrayLike,
        manifest: EmbeddingIndexManifest,
    ) -> IndexRevision: ...


class IndexActivator(Protocol):
    """Load one persisted index into the local query-service boundary."""

    async def activate(self, index_revision_id: str) -> object: ...


class DocumentEmbedder(Protocol):
    """Minimal embedding surface used while building a corpus."""

    @property
    def model_identifier(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    @property
    def normalization_method(self) -> str: ...

    def embed_documents(
        self, texts: Sequence[str], *, batch_size: int | None = None
    ) -> ArrayLike: ...
