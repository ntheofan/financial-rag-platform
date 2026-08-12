"""Load a compatible pgvector revision into the local in-memory query runtime."""

import asyncio
from datetime import UTC, datetime
from typing import Literal, Protocol, cast

from financial_rag.api.container import ApiContainer
from financial_rag.core.errors import RevisionCompatibilityError
from financial_rag.domain.indexing import ActiveIndexSelection
from financial_rag.domain.retrieval import EmbeddingIndexManifest, RetrievalConfig
from financial_rag.domain.revisions import (
    CorpusRevision,
    CorpusRevisionId,
    IndexRevision,
    IndexRevisionId,
)
from financial_rag.evaluation.runner import EvaluationRunner
from financial_rag.generation.context import ContextAssembler, ContextAssemblyConfig
from financial_rag.generation.protocols import GenerationAdapter
from financial_rag.generation.service import GroundedGenerationService
from financial_rag.retrieval.dense import DenseIndex
from financial_rag.retrieval.protocols import EmbeddingProvider, Reranker
from financial_rag.retrieval.service import RetrievalService
from financial_rag.storage.revision_store import PersistedIndex


class PersistedIndexReader(Protocol):
    """Read surface required to activate a persisted revision."""

    async def get_index(self, index_revision_id: IndexRevisionId) -> PersistedIndex: ...

    async def get_corpus_revision(self, corpus_revision_id: CorpusRevisionId) -> CorpusRevision: ...


class RuntimeIndexActivator:
    """Serialize index activation and replace local single-user query capabilities."""

    def __init__(
        self,
        *,
        container: ApiContainer,
        revisions: PersistedIndexReader,
        embedding_provider: EmbeddingProvider,
        retrieval_config: RetrievalConfig,
        reranker: Reranker | None,
        generation_adapter: GenerationAdapter | None,
        context_config: ContextAssemblyConfig,
    ) -> None:
        self._container = container
        self._revisions = revisions
        self._embedding_provider = embedding_provider
        self._retrieval_config = retrieval_config
        self._reranker = reranker
        self._generation_adapter = generation_adapter
        self._context_config = context_config
        self._lock = asyncio.Lock()

    async def activate(self, index_revision_id: str) -> ActiveIndexSelection:
        """Validate and select one persisted index without changing database state."""
        async with self._lock:
            persisted = await self._revisions.get_index(index_revision_id)
            revision = persisted.revision
            corpus = await self._revisions.get_corpus_revision(revision.corpus_revision_id)
            self._validate(revision=revision, corpus=corpus)
            dense_index = await asyncio.to_thread(
                DenseIndex.from_embeddings,
                persisted.records,
                persisted.embeddings,
                dimension=revision.embedding_dimension,
            )
            manifest = EmbeddingIndexManifest(
                embedding_model_identifier=revision.embedding_model_identifier,
                embedding_dimension=revision.embedding_dimension,
                normalization_method=revision.normalization_method,
                chunking_configuration_fingerprint=corpus.chunking_configuration_fingerprint,
                chunk_mapping_fingerprint=revision.chunk_mapping_fingerprint,
                index_vector_fingerprint=revision.index_vector_fingerprint,
                corpus_chunk_count=revision.vector_count,
                retrieval_configuration_fingerprint=(revision.retrieval_configuration_fingerprint),
                creation_timestamp=revision.created_at,
                artifact_format_version=cast(
                    Literal["faiss-flatip-v1"], revision.artifact_format_version
                ),
            )
            retrieval = RetrievalService(
                dense_index=dense_index,
                embedding_provider=self._embedding_provider,
                config=self._retrieval_config,
                manifest=manifest,
                reranker=self._reranker,
            )
            generation = (
                GroundedGenerationService(
                    retrieval=retrieval,
                    generator=self._generation_adapter,
                    context_assembler=ContextAssembler(self._context_config),
                )
                if self._generation_adapter is not None
                else None
            )
            evaluation = EvaluationRunner(
                retrieval=retrieval,
                generation=generation,
                corpus_fingerprint=revision.chunk_mapping_fingerprint,
            )
            self._container.replace_query_services(
                retrieval=retrieval,
                generation=generation,
                evaluation=evaluation,
            )
            return ActiveIndexSelection(
                corpus_revision_id=revision.corpus_revision_id,
                index_revision_id=revision.index_revision_id,
                activated_at=datetime.now(UTC),
            )

    def _validate(self, *, revision: IndexRevision, corpus: CorpusRevision) -> None:
        mismatches: list[str] = []
        if revision.status != "ready" or corpus.status != "ready":
            mismatches.append("revision status")
        if revision.embedding_model_identifier != self._embedding_provider.model_identifier:
            mismatches.append("embedding model")
        if revision.embedding_dimension != self._embedding_provider.dimension:
            mismatches.append("embedding dimension")
        if revision.normalization_method != self._embedding_provider.normalization_method:
            mismatches.append("normalization")
        if revision.retrieval_configuration_fingerprint != self._retrieval_config.fingerprint:
            mismatches.append("retrieval configuration")
        if revision.chunk_mapping_fingerprint != corpus.chunk_mapping_fingerprint:
            mismatches.append("chunk mapping")
        if mismatches:
            raise RevisionCompatibilityError(
                "Persisted index cannot be activated: " + ", ".join(mismatches)
            )
