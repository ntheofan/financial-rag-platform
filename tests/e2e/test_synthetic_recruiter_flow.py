"""Offline HTTP proof of the complete local recruiter flow."""

from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
from fastapi import FastAPI
from numpy.typing import ArrayLike

from financial_rag.api import ApiContainer, create_app
from financial_rag.chunking.service import MarkdownChunker
from financial_rag.domain.chunking import ChunkingConfig
from financial_rag.domain.fingerprints import ConfigurationFingerprint
from financial_rag.domain.generation import ModelAnswer
from financial_rag.domain.indexing import CorpusBuildJob, CorpusBuildJobId, CorpusBuildStatus
from financial_rag.domain.retrieval import ChunkRecord, EmbeddingIndexManifest
from financial_rag.domain.revisions import (
    CorpusRevision,
    CorpusRevisionId,
    IndexRevision,
    IndexRevisionId,
    make_corpus_revision_id,
    make_index_revision_id,
)
from financial_rag.generation.context import ContextAssemblyConfig
from financial_rag.indexing.service import CorpusIndexingService
from financial_rag.indexing.staging import UploadStagingService
from financial_rag.ingestion.service import FolderIngestionService
from financial_rag.retrieval.embeddings import FakeEmbeddingProvider
from financial_rag.retrieval.manifests import fingerprint_chunk_mapping
from financial_rag.retrieval.rerankers import FakeReranker
from financial_rag.retrieval.vectors import fingerprint_vector_matrix, normalize_l2
from financial_rag.runtime.activation import RuntimeIndexActivator
from financial_rag.storage.revision_store import PersistedIndex
from tests.api.client import api_client
from tests.unit.generation.helpers import FakeGenerationAdapter
from tests.unit.retrieval.helpers import fake_retrieval_config

NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)


class MemoryJobStore:
    """In-memory job state for one isolated HTTP flow."""

    def __init__(self) -> None:
        self.jobs: dict[str, CorpusBuildJob] = {}

    async def create_job(self, job: CorpusBuildJob) -> CorpusBuildJob:
        self.jobs[job.job_id] = job
        return job

    async def mark_running(self, job_id: CorpusBuildJobId) -> CorpusBuildJob:
        return self._update(job_id, status=CorpusBuildStatus.RUNNING, started_at=NOW)

    async def mark_completed(
        self,
        job_id: CorpusBuildJobId,
        *,
        corpus_revision_id: str,
        index_revision_id: str,
    ) -> CorpusBuildJob:
        return self._update(
            job_id,
            status=CorpusBuildStatus.COMPLETED,
            completed_at=NOW,
            corpus_revision_id=corpus_revision_id,
            index_revision_id=index_revision_id,
        )

    async def mark_failed(self, job_id: CorpusBuildJobId, *, error_code: str) -> CorpusBuildJob:
        return self._update(
            job_id,
            status=CorpusBuildStatus.FAILED,
            completed_at=NOW,
            error_code=error_code,
        )

    async def get_job(self, job_id: CorpusBuildJobId) -> CorpusBuildJob:
        return self.jobs[job_id]

    async def list_jobs(self, *, limit: int = 50) -> tuple[CorpusBuildJob, ...]:
        return tuple(self.jobs.values())[:limit]

    def _update(self, job_id: str, **changes: object) -> CorpusBuildJob:
        updated = CorpusBuildJob.model_validate(
            self.jobs[job_id].model_copy(update=changes).model_dump()
        )
        self.jobs[job_id] = updated
        return updated


class MemoryRevisionStore:
    """Protocol-complete immutable revision store with no disk or database writes."""

    def __init__(self) -> None:
        self.corpora: dict[str, CorpusRevision] = {}
        self.indexes: dict[str, PersistedIndex] = {}
        self.records: dict[str, tuple[ChunkRecord, ...]] = {}

    async def persist_corpus(
        self,
        records: tuple[ChunkRecord, ...],
        *,
        chunking_configuration_fingerprint: ConfigurationFingerprint,
        label: str | None = None,
    ) -> CorpusRevision:
        corpus_id = make_corpus_revision_id(
            records,
            chunking_configuration_fingerprint=chunking_configuration_fingerprint,
        )
        revision = CorpusRevision(
            corpus_revision_id=corpus_id,
            status="ready",
            label=label,
            chunking_configuration_fingerprint=chunking_configuration_fingerprint,
            chunk_mapping_fingerprint=fingerprint_chunk_mapping(records),
            document_count=len({record.metadata.document_id for record in records}),
            chunk_count=len(records),
            created_at=NOW,
        )
        self.corpora[corpus_id] = revision
        self.records[corpus_id] = records
        return revision

    async def persist_index(
        self,
        corpus_revision_id: CorpusRevisionId,
        *,
        records: tuple[ChunkRecord, ...],
        embeddings: ArrayLike,
        manifest: EmbeddingIndexManifest,
    ) -> IndexRevision:
        vectors = normalize_l2(embeddings, dimension=manifest.embedding_dimension)
        assert records == self.records[corpus_revision_id]
        assert (
            fingerprint_vector_matrix(vectors, dimension=manifest.embedding_dimension)
            == manifest.index_vector_fingerprint
        )
        index_id = make_index_revision_id(corpus_revision_id, manifest=manifest)
        revision = IndexRevision(
            index_revision_id=index_id,
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
        self.indexes[index_id] = PersistedIndex(
            revision=revision,
            records=records,
            embeddings=np.asarray(vectors, dtype=np.float32),
        )
        return revision

    async def get_index(self, index_revision_id: IndexRevisionId) -> PersistedIndex:
        return self.indexes[index_revision_id]

    async def get_corpus_revision(self, corpus_revision_id: CorpusRevisionId) -> CorpusRevision:
        return self.corpora[corpus_revision_id]

    async def get_index_revision(self, index_revision_id: IndexRevisionId) -> IndexRevision:
        return self.indexes[index_revision_id].revision

    async def list_corpus_revisions(self, *, limit: int = 50) -> tuple[CorpusRevision, ...]:
        return tuple(self.corpora.values())[:limit]

    async def list_index_revisions(self, *, limit: int = 50) -> tuple[IndexRevision, ...]:
        return tuple(item.revision for item in self.indexes.values())[:limit]


def _build_app(tmp_path: Path) -> FastAPI:
    config = fake_retrieval_config(dimension=32, final_top_k=5)
    embedder = FakeEmbeddingProvider(dimension=32)
    revisions = MemoryRevisionStore()
    container = ApiContainer(revisions=revisions)
    activator = RuntimeIndexActivator(
        container=container,
        revisions=revisions,
        embedding_provider=embedder,
        retrieval_config=config,
        reranker=FakeReranker(),
        generation_adapter=FakeGenerationAdapter(
            ModelAnswer(
                answer="Synthetic revenue increased according to the filing.",
                abstained=False,
                citation_ids=("C1",),
            )
        ),
        context_config=ContextAssemblyConfig(top_k=5),
    )
    container.indexing = CorpusIndexingService(
        jobs=MemoryJobStore(),
        revisions=revisions,
        embedder=embedder,
        retrieval_config=config,
        ingestion=FolderIngestionService(),
        chunker=MarkdownChunker(ChunkingConfig(min_chunk_chars=20)),
        staging=UploadStagingService(tmp_path / "uploads"),
        activator=activator,
        clock=lambda: NOW,
    )
    return create_app(container=container)


@pytest.mark.asyncio
async def test_upload_to_grounded_query_and_paired_evaluation(tmp_path: Path) -> None:
    app = _build_app(tmp_path)
    filing = (
        "# Revenue\n\n"
        "Synthetic ACME revenue increased to 120 units from 100 units. "
        * 30
        + "\n\n## Cash flow\n\nSynthetic operating cash flow was 40 units. " * 20
    ).encode()

    async with api_client(app) as client:
        submitted = await client.post(
            "/api/v1/corpus-jobs",
            files={"files": ("synthetic-acme.md", filing, "text/markdown")},
            data={"label": "synthetic release-candidate corpus"},
        )
        assert submitted.status_code == 202
        job_id = submitted.json()["job_id"]

        job = await client.get(f"/api/v1/corpus-jobs/{job_id}")
        assert job.status_code == 200
        assert job.json()["status"] == "completed"
        assert not (tmp_path / "uploads" / job_id).exists()

        ready = await client.get("/health/ready")
        assert ready.status_code == 200
        assert set(ready.json()["components"].values()) == {"ready"}

        retrieved = await client.post(
            "/api/v1/retrieval/query",
            json={"query": "How did synthetic revenue change?", "mode": "dense"},
        )
        assert retrieved.status_code == 200
        relevant_chunk_id = retrieved.json()["chunks"][0]["chunk_id"]

        answer = await client.post(
            "/api/v1/query",
            json={"query": "How did synthetic revenue change?", "mode": "hybrid_reranked"},
        )
        assert answer.status_code == 200
        assert answer.json()["citations"][0]["citation_id"] == "C1"
        assert answer.json()["citations"][0]["source_file"] == "synthetic-acme.md"

        evaluated = await client.post(
            "/api/v1/evaluations/retrieval",
            json={
                "dataset": {
                    "schema_version": "platform_eval_dataset_v1",
                    "dataset_id": "synthetic-release-candidate",
                    "items": [
                        {
                            "query_id": "synthetic-q1",
                            "query": "How did synthetic revenue change?",
                            "relevant_chunk_ids": [relevant_chunk_id],
                        }
                    ],
                },
                "config": {"hit_ks": [1, 3, 5]},
            },
        )

    assert evaluated.status_code == 200
    report = evaluated.json()
    assert [item["mode"] for item in report["items"]] == [
        "dense",
        "hybrid",
        "hybrid_reranked",
    ]
    assert {item["retrieval_status"] for item in report["items"]} == {"completed"}
    assert "content" not in report["items"][0]
