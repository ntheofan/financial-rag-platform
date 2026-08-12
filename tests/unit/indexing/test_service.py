"""End-to-end synthetic tests for ingestion-to-revision job orchestration."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from financial_rag.chunking.service import MarkdownChunker
from financial_rag.core.errors import CorpusBuildTransitionError
from financial_rag.domain.chunking import ChunkingConfig
from financial_rag.domain.fingerprints import ConfigurationFingerprint
from financial_rag.domain.indexing import (
    ActiveIndexSelection,
    CorpusBuildJob,
    CorpusBuildJobId,
    CorpusBuildStatus,
    UploadDocument,
)
from financial_rag.domain.retrieval import ChunkRecord, EmbeddingIndexManifest
from financial_rag.domain.revisions import CorpusRevision, IndexRevision
from financial_rag.indexing.service import CorpusIndexingService
from financial_rag.indexing.staging import UploadStagingService
from financial_rag.ingestion.service import FolderIngestionService
from financial_rag.retrieval.embeddings import FakeEmbeddingProvider
from tests.unit.retrieval.helpers import fake_retrieval_config

NOW = datetime(2026, 8, 12, 10, 0, tzinfo=UTC)
FINGERPRINT = ConfigurationFingerprint(value="f" * 64)


class MemoryJobStore:
    def __init__(self) -> None:
        self.jobs: dict[str, CorpusBuildJob] = {}

    async def create_job(self, job: CorpusBuildJob) -> CorpusBuildJob:
        self.jobs[job.job_id] = job
        return job

    async def mark_running(self, job_id: CorpusBuildJobId) -> CorpusBuildJob:
        job = self.jobs[job_id]
        updated = job.model_copy(update={"status": CorpusBuildStatus.RUNNING, "started_at": NOW})
        self.jobs[job_id] = updated
        return updated

    async def mark_completed(
        self,
        job_id: CorpusBuildJobId,
        *,
        corpus_revision_id: str,
        index_revision_id: str,
    ) -> CorpusBuildJob:
        job = self.jobs[job_id]
        updated = job.model_copy(
            update={
                "status": CorpusBuildStatus.COMPLETED,
                "completed_at": NOW,
                "corpus_revision_id": corpus_revision_id,
                "index_revision_id": index_revision_id,
            }
        )
        updated = CorpusBuildJob.model_validate(updated.model_dump())
        self.jobs[job_id] = updated
        return updated

    async def mark_failed(self, job_id: CorpusBuildJobId, *, error_code: str) -> CorpusBuildJob:
        job = self.jobs[job_id]
        updated = CorpusBuildJob.model_validate(
            job.model_copy(
                update={
                    "status": CorpusBuildStatus.FAILED,
                    "completed_at": NOW,
                    "error_code": error_code,
                }
            ).model_dump()
        )
        self.jobs[job_id] = updated
        return updated

    async def get_job(self, job_id: CorpusBuildJobId) -> CorpusBuildJob:
        return self.jobs[job_id]

    async def list_jobs(self, *, limit: int = 50) -> tuple[CorpusBuildJob, ...]:
        return tuple(self.jobs.values())[:limit]


class MemoryRevisionWriter:
    def __init__(self) -> None:
        self.records: tuple[ChunkRecord, ...] = ()
        self.manifest: EmbeddingIndexManifest | None = None

    async def persist_corpus(
        self,
        records: tuple[ChunkRecord, ...],
        *,
        chunking_configuration_fingerprint: ConfigurationFingerprint,
        label: str | None = None,
    ) -> CorpusRevision:
        self.records = records
        return CorpusRevision(
            corpus_revision_id="corpus_" + "a" * 32,
            status="ready",
            label=label,
            chunking_configuration_fingerprint=chunking_configuration_fingerprint,
            chunk_mapping_fingerprint=FINGERPRINT,
            document_count=1,
            chunk_count=len(records),
            created_at=NOW,
        )

    async def persist_index(
        self,
        corpus_revision_id: str,
        *,
        records: tuple[ChunkRecord, ...],
        embeddings: object,
        manifest: EmbeddingIndexManifest,
    ) -> IndexRevision:
        del embeddings
        assert records == self.records
        self.manifest = manifest
        return IndexRevision(
            index_revision_id="index_" + "b" * 32,
            corpus_revision_id=corpus_revision_id,
            status="ready",
            embedding_model_identifier=manifest.embedding_model_identifier,
            embedding_dimension=manifest.embedding_dimension,
            normalization_method=manifest.normalization_method,
            chunk_mapping_fingerprint=manifest.chunk_mapping_fingerprint,
            index_vector_fingerprint=manifest.index_vector_fingerprint,
            retrieval_configuration_fingerprint=manifest.retrieval_configuration_fingerprint,
            vector_count=len(records),
            artifact_format_version=manifest.artifact_format_version,
            created_at=manifest.creation_timestamp,
        )


class FakeActivator:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.activated: list[str] = []

    async def activate(self, index_revision_id: str) -> ActiveIndexSelection:
        if self.fail:
            raise RuntimeError("synthetic activation failure")
        self.activated.append(index_revision_id)
        return ActiveIndexSelection(
            corpus_revision_id="corpus_" + "a" * 32,
            index_revision_id=index_revision_id,
            activated_at=NOW,
        )


def _service(
    tmp_path: Path,
    jobs: MemoryJobStore,
    revisions: MemoryRevisionWriter,
    activator: FakeActivator,
) -> CorpusIndexingService:
    config = fake_retrieval_config(dimension=32)
    return CorpusIndexingService(
        jobs=jobs,
        revisions=revisions,
        embedder=FakeEmbeddingProvider(dimension=32),
        retrieval_config=config,
        ingestion=FolderIngestionService(),
        chunker=MarkdownChunker(ChunkingConfig(min_chunk_chars=20)),
        staging=UploadStagingService(tmp_path / "uploads"),
        activator=activator,
        clock=lambda: NOW,
    )


@pytest.mark.asyncio
async def test_successful_job_persists_activates_and_cleans_staging(tmp_path: Path) -> None:
    jobs = MemoryJobStore()
    revisions = MemoryRevisionWriter()
    activator = FakeActivator()
    service = _service(tmp_path, jobs, revisions, activator)

    job, batch = await service.submit_uploads(
        (
            UploadDocument(
                filename="synthetic.md",
                content=("# Revenue\n" + "Synthetic financial evidence. " * 30).encode(),
            ),
        ),
        label="demo corpus",
    )
    await service.run_staged_job(job.job_id, batch)
    completed = await service.get_job(job.job_id)

    assert completed.status is CorpusBuildStatus.COMPLETED
    assert completed.corpus_revision_id == "corpus_" + "a" * 32
    assert activator.activated == ["index_" + "b" * 32]
    assert revisions.records[0].metadata.source_file == "synthetic.md"
    assert revisions.manifest is not None
    assert not batch.folder.exists()


@pytest.mark.asyncio
async def test_failed_activation_is_recorded_without_exposing_exception(tmp_path: Path) -> None:
    jobs = MemoryJobStore()
    service = _service(tmp_path, jobs, MemoryRevisionWriter(), FakeActivator(fail=True))
    job, batch = await service.submit_uploads(
        (UploadDocument(filename="synthetic.txt", content=b"evidence " * 80),)
    )

    await service.run_staged_job(job.job_id, batch)
    failed = await service.get_job(job.job_id)

    assert failed.status is CorpusBuildStatus.FAILED
    assert failed.error_code == "internal_error"
    assert not batch.folder.exists()


@pytest.mark.asyncio
async def test_only_one_local_job_can_be_active(tmp_path: Path) -> None:
    jobs = MemoryJobStore()
    service = _service(tmp_path, jobs, MemoryRevisionWriter(), FakeActivator())
    upload = (UploadDocument(filename="synthetic.txt", content=b"evidence " * 80),)
    _job, batch = await service.submit_uploads(upload)

    with pytest.raises(CorpusBuildTransitionError, match="Only one"):
        await service.submit_uploads(upload)

    assert batch.folder.exists()


@pytest.mark.asyncio
async def test_invalid_job_metadata_is_rejected_before_staging(tmp_path: Path) -> None:
    service = _service(tmp_path, MemoryJobStore(), MemoryRevisionWriter(), FakeActivator())

    with pytest.raises(ValueError):
        await service.submit_uploads(
            (UploadDocument(filename="synthetic.txt", content=b"evidence " * 80),),
            label="x" * 201,
        )

    assert not (tmp_path / "uploads").exists()
