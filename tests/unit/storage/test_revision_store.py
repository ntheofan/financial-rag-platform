"""Transactional revision-store tests over a test-only in-memory SQL engine."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import numpy as np
import pytest
import pytest_asyncio
from pgvector.sqlalchemy import VECTOR
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from financial_rag.core.errors import RevisionConflictError
from financial_rag.domain.fingerprints import fingerprint_payload
from financial_rag.domain.retrieval import ChunkRecord
from financial_rag.retrieval.corpus import records_from_documents
from financial_rag.retrieval.manifests import create_index_manifest
from financial_rag.retrieval.vectors import fingerprint_vector_matrix, normalize_l2
from financial_rag.storage.models import Base
from financial_rag.storage.revision_store import PostgresRevisionStore
from tests.unit.retrieval.helpers import fake_retrieval_config, synthetic_chunks


@compiles(VECTOR, "sqlite")
def _compile_vector_for_test(_type: VECTOR, _compiler: object, **_kwargs: object) -> str:
    """Let SQLite exercise repository transactions; it is not a runtime adapter."""
    return "TEXT"


@pytest_asyncio.fixture
async def revision_store() -> AsyncIterator[PostgresRevisionStore]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        yield PostgresRevisionStore(factory)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_corpus_round_trip_is_ordered_and_idempotent(
    revision_store: PostgresRevisionStore,
) -> None:
    records = records_from_documents(synthetic_chunks(["first chunk", "second chunk"]))
    chunking = fingerprint_payload({"chunk_size": 1500, "chunk_overlap": 200})

    created = await revision_store.persist_corpus(
        records, chunking_configuration_fingerprint=chunking, label="synthetic"
    )
    repeated = await revision_store.persist_corpus(
        records, chunking_configuration_fingerprint=chunking, label="ignored-new-label"
    )
    loaded_revision, loaded_records = await revision_store.get_corpus(created.corpus_revision_id)
    metadata_only = await revision_store.get_corpus_revision(created.corpus_revision_id)
    listed = await revision_store.list_corpus_revisions()

    assert repeated == created
    assert loaded_revision == created
    assert metadata_only == created
    assert listed == (created,)
    assert loaded_records == records
    assert loaded_revision.document_count == 1
    assert loaded_revision.chunk_count == 2


@pytest.mark.asyncio
async def test_corpus_rejects_conflicting_existing_chunk_identity(
    revision_store: PostgresRevisionStore,
) -> None:
    records = records_from_documents(synthetic_chunks(["original content"]))
    chunking = fingerprint_payload({"chunk_size": 1500})
    await revision_store.persist_corpus(records, chunking_configuration_fingerprint=chunking)
    conflicting = (ChunkRecord(content="different content", metadata=records[0].metadata),)

    with pytest.raises(RevisionConflictError, match="conflicting content"):
        await revision_store.persist_corpus(
            conflicting, chunking_configuration_fingerprint=chunking
        )


@pytest.mark.asyncio
async def test_index_round_trip_preserves_manifest_alignment(
    revision_store: PostgresRevisionStore,
) -> None:
    records = records_from_documents(synthetic_chunks(["assets", "liabilities"]))
    chunking = fingerprint_payload({"chunk_size": 1500, "chunk_overlap": 200})
    corpus = await revision_store.persist_corpus(
        records, chunking_configuration_fingerprint=chunking
    )
    vectors = np.zeros((2, 1024), dtype=np.float32)
    vectors[0, 0] = 1.0
    vectors[1, 1] = 1.0
    vectors = normalize_l2(vectors, dimension=1024)
    manifest = create_index_manifest(
        config=fake_retrieval_config(dimension=1024),
        chunking_configuration_fingerprint=chunking,
        records=records,
        index_vector_fingerprint=fingerprint_vector_matrix(vectors, dimension=1024),
        creation_timestamp=datetime(2026, 8, 1, tzinfo=UTC),
    )

    created = await revision_store.persist_index(
        corpus.corpus_revision_id,
        records=records,
        embeddings=vectors,
        manifest=manifest,
    )
    repeated = await revision_store.persist_index(
        corpus.corpus_revision_id,
        records=records,
        embeddings=vectors,
        manifest=manifest,
    )
    loaded = await revision_store.get_index(created.index_revision_id)
    metadata_only = await revision_store.get_index_revision(created.index_revision_id)
    listed = await revision_store.list_index_revisions()

    assert repeated == created
    assert loaded.revision == created
    assert metadata_only == created
    assert listed == (created,)
    assert loaded.records == records
    np.testing.assert_array_equal(loaded.embeddings, vectors)
