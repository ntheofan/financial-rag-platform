"""Bounded ingestion-to-pgvector orchestration for the local single-user demo."""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime

import structlog

from financial_rag.chunking.service import MarkdownChunker
from financial_rag.core.errors import (
    ChunkingError,
    CorpusBuildTransitionError,
    FinancialRAGError,
    IngestionError,
    InvalidEmbeddingError,
    ProviderUnavailableError,
    RevisionCompatibilityError,
    RevisionConflictError,
)
from financial_rag.domain.fingerprints import fingerprint_model
from financial_rag.domain.indexing import (
    ActiveIndexSelection,
    CorpusBuildJob,
    CorpusBuildJobId,
    CorpusBuildStatus,
    UploadDocument,
    make_corpus_build_job_id,
)
from financial_rag.domain.retrieval import RetrievalConfig
from financial_rag.indexing.protocols import (
    CorpusBuildJobStore,
    DocumentEmbedder,
    IndexActivator,
    RevisionWriter,
)
from financial_rag.indexing.staging import StagedUploadBatch, UploadStagingService
from financial_rag.ingestion.service import FolderIngestionService
from financial_rag.retrieval.corpus import records_from_documents
from financial_rag.retrieval.manifests import create_index_manifest
from financial_rag.retrieval.vectors import fingerprint_vector_matrix, normalize_l2

logger = structlog.get_logger(__name__)
Clock = Callable[[], datetime]


def _error_code(exc: Exception) -> str:
    if isinstance(exc, IngestionError):
        return "ingestion_failed"
    if isinstance(exc, ChunkingError):
        return "chunking_failed"
    if isinstance(exc, (ProviderUnavailableError, InvalidEmbeddingError)):
        return "embedding_failed"
    if isinstance(exc, (RevisionCompatibilityError, RevisionConflictError)):
        return "persistence_failed"
    if isinstance(exc, FinancialRAGError):
        return "domain_error"
    return "internal_error"


class CorpusIndexingService:
    """Own upload staging, durable job state, revision writes, and activation."""

    def __init__(
        self,
        *,
        jobs: CorpusBuildJobStore,
        revisions: RevisionWriter,
        embedder: DocumentEmbedder,
        retrieval_config: RetrievalConfig,
        ingestion: FolderIngestionService,
        chunker: MarkdownChunker,
        staging: UploadStagingService,
        activator: IndexActivator,
        embedding_batch_size: int = 8,
        clock: Clock = lambda: datetime.now(UTC),
    ) -> None:
        if embedding_batch_size <= 0:
            raise ValueError("embedding_batch_size must be positive")
        if embedder.model_identifier != retrieval_config.embedding_model_identifier:
            raise ValueError("Indexing embedder model does not match retrieval configuration")
        if embedder.dimension != retrieval_config.embedding_dimension:
            raise ValueError("Indexing embedder dimension does not match retrieval configuration")
        if embedder.normalization_method != retrieval_config.normalization_method:
            raise ValueError("Indexing normalization does not match retrieval configuration")
        self._jobs = jobs
        self._revisions = revisions
        self._embedder = embedder
        self._retrieval_config = retrieval_config
        self._ingestion = ingestion
        self._chunker = chunker
        self._staging = staging
        self._activator = activator
        self._embedding_batch_size = embedding_batch_size
        self._clock = clock
        self._submission_lock = asyncio.Lock()

    async def submit_uploads(
        self,
        uploads: tuple[UploadDocument, ...],
        *,
        label: str | None = None,
    ) -> tuple[CorpusBuildJob, StagedUploadBatch]:
        """Stage a validated batch and create its durable pending job."""
        async with self._submission_lock:
            recent = await self._jobs.list_jobs(limit=100)
            if any(
                item.status in {CorpusBuildStatus.PENDING, CorpusBuildStatus.RUNNING}
                for item in recent
            ):
                raise CorpusBuildTransitionError(
                    "Only one local corpus-build job may be active at a time."
                )
            job_id = make_corpus_build_job_id()
            job = CorpusBuildJob(
                job_id=job_id,
                status=CorpusBuildStatus.PENDING,
                label=label,
                input_file_count=len(uploads),
                created_at=self._clock(),
            )
            batch = await asyncio.to_thread(self._staging.stage, job_id, uploads)
            try:
                persisted = await self._jobs.create_job(job)
            except Exception:
                await asyncio.to_thread(self._staging.cleanup, batch)
                raise
            return persisted, batch

    async def run_staged_job(self, job_id: CorpusBuildJobId, batch: StagedUploadBatch) -> None:
        """Run one in-process job and always attempt to remove its staging files."""
        try:
            await self._run(job_id, batch)
        finally:
            try:
                await asyncio.to_thread(self._staging.cleanup, batch)
            except Exception as exc:
                logger.error(
                    "upload_batch_cleanup_failed",
                    job_id=job_id,
                    exception_type=type(exc).__name__,
                )

    async def _run(self, job_id: CorpusBuildJobId, batch: StagedUploadBatch) -> CorpusBuildJob:
        await self._jobs.mark_running(job_id)
        try:
            documents = await asyncio.to_thread(
                self._ingestion.ingest_folder,
                batch.folder,
                recursive=False,
                metadata_provider=batch.metadata_provider,
            )
            chunks = await asyncio.to_thread(self._chunker.chunk_documents, documents)
            records = records_from_documents(chunks)
            matrix = await asyncio.to_thread(
                self._embedder.embed_documents,
                [record.content for record in records],
                batch_size=self._embedding_batch_size,
            )
            normalized = normalize_l2(matrix, dimension=self._embedder.dimension)
            chunking_fingerprint = fingerprint_model(self._chunker.config)
            manifest = create_index_manifest(
                config=self._retrieval_config,
                chunking_configuration_fingerprint=chunking_fingerprint,
                records=records,
                index_vector_fingerprint=fingerprint_vector_matrix(
                    normalized,
                    dimension=self._embedder.dimension,
                ),
                creation_timestamp=self._clock(),
            )
            corpus = await self._revisions.persist_corpus(
                records,
                chunking_configuration_fingerprint=chunking_fingerprint,
                label=(await self._jobs.get_job(job_id)).label,
            )
            index = await self._revisions.persist_index(
                corpus.corpus_revision_id,
                records=records,
                embeddings=normalized,
                manifest=manifest,
            )
            await self._activator.activate(index.index_revision_id)
            completed = await self._jobs.mark_completed(
                job_id,
                corpus_revision_id=corpus.corpus_revision_id,
                index_revision_id=index.index_revision_id,
            )
            logger.info(
                "corpus_build_completed",
                job_id=job_id,
                corpus_revision_id=corpus.corpus_revision_id,
                index_revision_id=index.index_revision_id,
                chunk_count=len(records),
            )
            return completed
        except Exception as exc:
            code = _error_code(exc)
            logger.error(
                "corpus_build_failed",
                job_id=job_id,
                error_code=code,
                exception_type=type(exc).__name__,
            )
            return await self._jobs.mark_failed(job_id, error_code=code)

    async def get_job(self, job_id: CorpusBuildJobId) -> CorpusBuildJob:
        """Return one privacy-minimized durable job record."""
        return await self._jobs.get_job(job_id)

    async def list_jobs(self, *, limit: int = 50) -> tuple[CorpusBuildJob, ...]:
        """List recent jobs without returning filenames or source content."""
        return await self._jobs.list_jobs(limit=limit)

    async def activate_index(self, index_revision_id: str) -> ActiveIndexSelection:
        """Select an existing compatible persisted index for subsequent queries."""
        activated = await self._activator.activate(index_revision_id)
        if not isinstance(activated, ActiveIndexSelection):
            raise TypeError("Index activator returned an invalid selection contract")
        return activated
