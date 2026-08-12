"""Pre-database vector and manifest compatibility tests."""

from datetime import UTC, datetime
from typing import Any, cast

import numpy as np
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from financial_rag.core.errors import RevisionCompatibilityError
from financial_rag.domain.fingerprints import fingerprint_payload
from financial_rag.retrieval.corpus import records_from_documents
from financial_rag.retrieval.manifests import create_index_manifest
from financial_rag.retrieval.vectors import fingerprint_vector_matrix, normalize_l2
from financial_rag.storage.revision_store import PostgresRevisionStore
from tests.unit.retrieval.helpers import fake_retrieval_config, synthetic_chunks


def test_vector_matrix_fingerprint_matches_normalized_float32_content() -> None:
    vectors = np.asarray([[3.0, 4.0], [0.0, 2.0]], dtype=np.float64)

    raw_fingerprint = fingerprint_vector_matrix(vectors, dimension=2)
    normalized_fingerprint = fingerprint_vector_matrix(
        normalize_l2(vectors, dimension=2), dimension=2
    )

    assert raw_fingerprint == normalized_fingerprint


@pytest.mark.asyncio
async def test_store_rejects_non_schema_embedding_dimension_before_database_use() -> None:
    records = records_from_documents(synthetic_chunks(["synthetic revenue statement"]))
    config = fake_retrieval_config(dimension=2)
    vectors = normalize_l2([[1.0, 0.0]], dimension=2)
    manifest = create_index_manifest(
        config=config,
        chunking_configuration_fingerprint=fingerprint_payload({"chunk_size": 1500}),
        records=records,
        index_vector_fingerprint=fingerprint_vector_matrix(vectors, dimension=2),
        creation_timestamp=datetime(2026, 8, 1, tzinfo=UTC),
    )
    unused_factory = cast(async_sessionmaker[AsyncSession], cast(Any, object()))
    store = PostgresRevisionStore(unused_factory)

    with pytest.raises(RevisionCompatibilityError, match="1024-dimensional"):
        await store.persist_index(
            "corpus_" + "a" * 32,
            records=records,
            embeddings=vectors,
            manifest=manifest,
        )
