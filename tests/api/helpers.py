"""Synthetic API dependencies; no database, model, or network is used."""

from datetime import UTC, datetime

from financial_rag.api.container import ApiContainer
from financial_rag.domain.chunking import ChunkingConfig
from financial_rag.domain.fingerprints import ConfigurationFingerprint, fingerprint_model
from financial_rag.domain.revisions import CorpusRevision, IndexRevision
from financial_rag.evaluation.runner import EvaluationRunner
from financial_rag.retrieval.embeddings import FakeEmbeddingProvider
from financial_rag.retrieval.rerankers import FakeReranker
from financial_rag.retrieval.service import RetrievalService
from tests.unit.retrieval.helpers import fake_retrieval_config, synthetic_chunks

CORPUS_ID = "corpus_" + "a" * 32
INDEX_ID = "index_" + "b" * 32
FINGERPRINT = ConfigurationFingerprint(value="c" * 64)


def retrieval_service() -> RetrievalService:
    """Build the real retrieval orchestration around deterministic fake providers."""
    config = fake_retrieval_config(final_top_k=2)
    return RetrievalService.build(
        synthetic_chunks(
            [
                "capital expenditures property plant equipment cash flow",
                "revenue net sales income statement",
                "working capital current assets current liabilities",
            ]
        ),
        embedding_provider=FakeEmbeddingProvider(dimension=config.embedding_dimension),
        config=config,
        chunking_configuration_fingerprint=fingerprint_model(ChunkingConfig()),
        reranker=FakeReranker(),
    )


class FakeRevisionReader:
    """Return metadata-only synthetic revisions through the production protocol."""

    async def get_corpus_revision(self, corpus_revision_id: str) -> CorpusRevision:
        return CorpusRevision(
            corpus_revision_id=corpus_revision_id,
            status="ready",
            label="synthetic",
            chunking_configuration_fingerprint=FINGERPRINT,
            chunk_mapping_fingerprint=FINGERPRINT,
            document_count=1,
            chunk_count=3,
            created_at=datetime(2026, 8, 2, tzinfo=UTC),
        )

    async def get_index_revision(self, index_revision_id: str) -> IndexRevision:
        return IndexRevision(
            index_revision_id=index_revision_id,
            corpus_revision_id=CORPUS_ID,
            status="ready",
            embedding_model_identifier="BAAI/bge-m3",
            embedding_dimension=1024,
            normalization_method="l2",
            chunk_mapping_fingerprint=FINGERPRINT,
            index_vector_fingerprint=FINGERPRINT,
            retrieval_configuration_fingerprint=FINGERPRINT,
            vector_count=3,
            artifact_format_version="pgvector-v1",
            created_at=datetime(2026, 8, 2, tzinfo=UTC),
        )

    async def list_corpus_revisions(self, *, limit: int = 50) -> tuple[CorpusRevision, ...]:
        del limit
        return (await self.get_corpus_revision(CORPUS_ID),)

    async def list_index_revisions(self, *, limit: int = 50) -> tuple[IndexRevision, ...]:
        del limit
        return (await self.get_index_revision(INDEX_ID),)


def configured_container() -> ApiContainer:
    """Provide every API capability without external infrastructure."""
    retrieval = retrieval_service()
    return ApiContainer(
        retrieval=retrieval,
        evaluation=EvaluationRunner(retrieval=retrieval),
        revisions=FakeRevisionReader(),
    )
