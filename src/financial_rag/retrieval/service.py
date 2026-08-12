"""Shared platform_v1 orchestration for V1, V2, and V3 retrieval."""

from collections.abc import Sequence
from pathlib import Path

import numpy as np
import structlog
from langchain_core.documents import Document

from financial_rag.core.errors import (
    InvalidEmbeddingError,
    RerankerRequiredError,
    RetrievalError,
)
from financial_rag.domain.fingerprints import ConfigurationFingerprint
from financial_rag.domain.retrieval import (
    ChunkRecord,
    EmbeddingIndexManifest,
    RetrievalConfig,
    RetrievalMode,
    RetrievalResult,
    RetrievedChunk,
)
from financial_rag.retrieval.artifacts import DenseIndexArtifactStore
from financial_rag.retrieval.bm25 import BM25Index
from financial_rag.retrieval.corpus import records_from_documents
from financial_rag.retrieval.dense import DenseIndex
from financial_rag.retrieval.fusion import weighted_reciprocal_rank_fusion
from financial_rag.retrieval.hits import FusedCandidate, IndexHit
from financial_rag.retrieval.manifests import create_index_manifest
from financial_rag.retrieval.protocols import EmbeddingProvider, Reranker
from financial_rag.retrieval.query_expansion import FinanceQueryExpander, normalize_query_text

logger = structlog.get_logger(__name__)


class RetrievalService:
    """Compose dense, hybrid, and reranked retrieval without duplicated logic."""

    def __init__(
        self,
        *,
        dense_index: DenseIndex,
        embedding_provider: EmbeddingProvider,
        config: RetrievalConfig,
        manifest: EmbeddingIndexManifest,
        reranker: Reranker | None = None,
    ) -> None:
        self._validate_provider(embedding_provider, config)
        if reranker is not None and reranker.model_identifier != config.reranker_model_identifier:
            raise RetrievalError("Reranker is incompatible with retrieval config: model identifier")
        if dense_index.dimension != config.embedding_dimension:
            raise InvalidEmbeddingError("Dense index and retrieval configuration disagree")
        if manifest.corpus_chunk_count != dense_index.count:
            raise RetrievalError("Manifest and dense index corpus counts disagree")
        self._dense_index = dense_index
        self._bm25_index = BM25Index(
            dense_index.records,
            k1=config.bm25_k1,
            b=config.bm25_b,
        )
        self._embedding_provider = embedding_provider
        self._config = config
        self._manifest = manifest
        self._reranker = reranker
        self._expander = FinanceQueryExpander(config.query_expansion)

    @classmethod
    def build(
        cls,
        chunks: Sequence[Document],
        *,
        embedding_provider: EmbeddingProvider,
        config: RetrievalConfig,
        chunking_configuration_fingerprint: ConfigurationFingerprint,
        reranker: Reranker | None = None,
        embedding_batch_size: int | None = None,
    ) -> "RetrievalService":
        """Build aligned dense and lexical indexes from validated ingestion chunks."""
        cls._validate_provider(embedding_provider, config)
        records = records_from_documents(chunks)
        dense_index = DenseIndex.build(
            records,
            embedding_provider,
            batch_size=embedding_batch_size,
        )
        manifest = create_index_manifest(
            config=config,
            chunking_configuration_fingerprint=chunking_configuration_fingerprint,
            records=records,
            index_vector_fingerprint=dense_index.vector_fingerprint,
        )
        logger.info(
            "retrieval_indexes_built",
            corpus_chunk_count=len(records),
            embedding_model=config.embedding_model_identifier,
            configuration_fingerprint=config.fingerprint.value,
        )
        return cls(
            dense_index=dense_index,
            embedding_provider=embedding_provider,
            config=config,
            manifest=manifest,
            reranker=reranker,
        )

    @classmethod
    def load_artifacts(
        cls,
        directory: Path,
        *,
        embedding_provider: EmbeddingProvider,
        config: RetrievalConfig,
        chunking_configuration_fingerprint: ConfigurationFingerprint,
        reranker: Reranker | None = None,
        artifact_store: DenseIndexArtifactStore | None = None,
    ) -> "RetrievalService":
        """Restore an ignored local index after compatibility validation."""
        store = artifact_store or DenseIndexArtifactStore()
        dense_index, manifest = store.load(
            directory,
            config=config,
            chunking_configuration_fingerprint=chunking_configuration_fingerprint,
        )
        return cls(
            dense_index=dense_index,
            embedding_provider=embedding_provider,
            config=config,
            manifest=manifest,
            reranker=reranker,
        )

    @property
    def manifest(self) -> EmbeddingIndexManifest:
        return self._manifest

    def save_artifacts(
        self,
        directory: Path,
        *,
        artifact_store: DenseIndexArtifactStore | None = None,
    ) -> None:
        """Persist the local dense index and row mapping under an explicit path."""
        (artifact_store or DenseIndexArtifactStore()).save(
            directory,
            dense_index=self._dense_index,
            manifest=self._manifest,
        )

    def retrieve(self, query: str, *, mode: RetrievalMode) -> RetrievalResult:
        """Run V1, V2, or V3 over the full indexed chunk collection."""
        normalized_query = normalize_query_text(query)
        expanded_query = self._expander.expand(query)
        query_vector = self._embedding_provider.embed_query(expanded_query)

        dense_limit = (
            self._config.final_top_k
            if mode is RetrievalMode.DENSE
            else self._config.dense_candidate_count
        )
        dense_hits = self._dense_index.search(query_vector, top_k=dense_limit)
        if mode is RetrievalMode.DENSE:
            chunks = tuple(
                self._from_dense_hit(hit, rank=rank)
                for rank, hit in enumerate(dense_hits[: self._config.final_top_k], start=1)
            )
        else:
            fused = self._hybrid_candidates(expanded_query, dense_hits)
            if mode is RetrievalMode.HYBRID:
                chunks = tuple(
                    self._from_fused(candidate, rank=rank)
                    for rank, candidate in enumerate(fused[: self._config.final_top_k], start=1)
                )
            elif mode is RetrievalMode.HYBRID_RERANKED:
                chunks = self._rerank(normalized_query, fused)
            else:
                raise RetrievalError(f"Unsupported retrieval mode: {mode}")

        logger.info(
            "retrieval_completed",
            mode=mode.value,
            result_count=len(chunks),
            corpus_chunk_count=self._dense_index.count,
            configuration_fingerprint=self._config.fingerprint.value,
        )
        return RetrievalResult(
            query=query.strip(),
            expanded_query=expanded_query,
            mode=mode,
            retrieval_configuration_fingerprint=self._config.fingerprint,
            chunks=chunks,
        )

    def _hybrid_candidates(
        self, expanded_query: str, dense_hits: list[IndexHit]
    ) -> list[FusedCandidate]:
        bm25_hits = self._bm25_index.search(
            expanded_query,
            top_k=self._config.bm25_candidate_count,
        )
        return weighted_reciprocal_rank_fusion(
            dense_hits,
            bm25_hits,
            rrf_k=self._config.rrf_k,
            dense_weight=self._config.dense_rrf_weight,
            bm25_weight=self._config.bm25_rrf_weight,
        )

    def _rerank(self, query: str, fused: list[FusedCandidate]) -> tuple[RetrievedChunk, ...]:
        if self._reranker is None:
            raise RerankerRequiredError("hybrid_reranked mode requires a reranker")
        contents = [self._record(candidate.row_index).content for candidate in fused]
        scores = self._reranker.score(query, contents)
        if len(scores) != len(fused) or not np.isfinite(scores).all():
            raise RetrievalError("Reranker returned invalid or misaligned scores")
        reranked = list(zip(fused, scores, range(1, len(fused) + 1), strict=True))
        reranked.sort(key=lambda item: (-item[1], item[2], item[0].chunk_id))
        return tuple(
            self._from_fused(candidate, rank=rank, rerank_score=float(score))
            for rank, (candidate, score, _previous_rank) in enumerate(
                reranked[: self._config.final_top_k], start=1
            )
        )

    def _from_dense_hit(self, hit: IndexHit, *, rank: int) -> RetrievedChunk:
        record = self._record(hit.row_index)
        return self._retrieved_chunk(
            record,
            rank=rank,
            dense_rank=hit.rank,
            dense_score=hit.score,
        )

    def _from_fused(
        self,
        candidate: FusedCandidate,
        *,
        rank: int,
        rerank_score: float | None = None,
    ) -> RetrievedChunk:
        return self._retrieved_chunk(
            self._record(candidate.row_index),
            rank=rank,
            dense_rank=candidate.dense_rank,
            dense_score=candidate.dense_score,
            bm25_rank=candidate.bm25_rank,
            bm25_score=candidate.bm25_score,
            rrf_score=candidate.rrf_score,
            rerank_score=rerank_score,
        )

    @staticmethod
    def _retrieved_chunk(
        record: ChunkRecord,
        *,
        rank: int,
        dense_rank: int | None = None,
        dense_score: float | None = None,
        bm25_rank: int | None = None,
        bm25_score: float | None = None,
        rrf_score: float | None = None,
        rerank_score: float | None = None,
    ) -> RetrievedChunk:
        metadata = record.metadata
        return RetrievedChunk(
            **metadata.model_dump(),
            content=record.content,
            rank=rank,
            dense_rank=dense_rank,
            dense_score=dense_score,
            bm25_rank=bm25_rank,
            bm25_score=bm25_score,
            rrf_score=rrf_score,
            rerank_score=rerank_score,
        )

    def _record(self, row_index: int) -> ChunkRecord:
        return self._dense_index.records[row_index]

    @staticmethod
    def _validate_provider(
        provider: EmbeddingProvider,
        config: RetrievalConfig,
    ) -> None:
        mismatches: list[str] = []
        if provider.model_identifier != config.embedding_model_identifier:
            mismatches.append("model identifier")
        if provider.dimension != config.embedding_dimension:
            mismatches.append("dimension")
        if provider.normalization_method != config.normalization_method:
            mismatches.append("normalization method")
        if mismatches:
            raise InvalidEmbeddingError(
                "Embedding provider is incompatible with retrieval config: " + ", ".join(mismatches)
            )
