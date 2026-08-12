"""Offline tests for selecting a persisted index into the query runtime."""

from datetime import UTC, datetime

import numpy as np
import pytest

from financial_rag.api.container import ApiContainer
from financial_rag.core.errors import RevisionCompatibilityError
from financial_rag.domain.fingerprints import fingerprint_payload
from financial_rag.domain.revisions import CorpusRevision, IndexRevision
from financial_rag.generation.context import ContextAssemblyConfig
from financial_rag.retrieval.corpus import records_from_documents
from financial_rag.retrieval.embeddings import FakeEmbeddingProvider
from financial_rag.retrieval.manifests import fingerprint_chunk_mapping
from financial_rag.retrieval.rerankers import FakeReranker
from financial_rag.retrieval.vectors import fingerprint_vector_matrix, normalize_l2
from financial_rag.runtime.activation import RuntimeIndexActivator
from financial_rag.storage.revision_store import PersistedIndex
from tests.unit.retrieval.helpers import fake_retrieval_config, synthetic_chunks


class FakePersistedReader:
    def __init__(self, *, incompatible: bool = False) -> None:
        config = fake_retrieval_config(dimension=32)
        records = records_from_documents(synthetic_chunks(["capital evidence", "revenue evidence"]))
        vectors = np.zeros((2, 32), dtype=np.float32)
        vectors[0, 0] = 1
        vectors[1, 1] = 1
        vectors = normalize_l2(vectors, dimension=32)
        mapping = fingerprint_chunk_mapping(records)
        chunking = fingerprint_payload({"synthetic": True})
        corpus_id = "corpus_" + "a" * 32
        self.corpus = CorpusRevision(
            corpus_revision_id=corpus_id,
            status="ready",
            chunking_configuration_fingerprint=chunking,
            chunk_mapping_fingerprint=mapping,
            document_count=1,
            chunk_count=2,
            created_at=datetime(2026, 8, 12, tzinfo=UTC),
        )
        revision = IndexRevision(
            index_revision_id="index_" + "b" * 32,
            corpus_revision_id=corpus_id,
            status="ready",
            embedding_model_identifier="wrong"
            if incompatible
            else config.embedding_model_identifier,
            embedding_dimension=32,
            normalization_method="l2",
            chunk_mapping_fingerprint=mapping,
            index_vector_fingerprint=fingerprint_vector_matrix(vectors, dimension=32),
            retrieval_configuration_fingerprint=config.fingerprint,
            vector_count=2,
            artifact_format_version="faiss-flatip-v1",
            created_at=datetime(2026, 8, 12, tzinfo=UTC),
        )
        self.persisted = PersistedIndex(revision=revision, records=records, embeddings=vectors)

    async def get_index(self, _index_revision_id: str) -> PersistedIndex:
        return self.persisted

    async def get_corpus_revision(self, _corpus_revision_id: str) -> CorpusRevision:
        return self.corpus


@pytest.mark.asyncio
async def test_activation_replaces_all_query_services() -> None:
    config = fake_retrieval_config(dimension=32)
    container = ApiContainer()
    activator = RuntimeIndexActivator(
        container=container,
        revisions=FakePersistedReader(),
        embedding_provider=FakeEmbeddingProvider(dimension=32),
        retrieval_config=config,
        reranker=FakeReranker(),
        generation_adapter=None,
        context_config=ContextAssemblyConfig(),
    )

    selected = await activator.activate("index_" + "b" * 32)

    assert selected.index_revision_id == "index_" + "b" * 32
    assert container.retrieval is not None
    assert container.evaluation is not None
    assert container.generation is None


@pytest.mark.asyncio
async def test_activation_rejects_incompatible_model_without_replacing_services() -> None:
    config = fake_retrieval_config(dimension=32)
    container = ApiContainer()
    activator = RuntimeIndexActivator(
        container=container,
        revisions=FakePersistedReader(incompatible=True),
        embedding_provider=FakeEmbeddingProvider(dimension=32),
        retrieval_config=config,
        reranker=FakeReranker(),
        generation_adapter=None,
        context_config=ContextAssemblyConfig(),
    )

    with pytest.raises(RevisionCompatibilityError, match="embedding model"):
        await activator.activate("index_" + "b" * 32)

    assert container.retrieval is None
