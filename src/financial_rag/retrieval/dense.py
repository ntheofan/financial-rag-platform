"""FAISS IndexFlatIP construction and deterministic dense search."""

import hashlib
from collections.abc import Sequence
from typing import Any

import faiss
import numpy as np
from numpy.typing import ArrayLike

from financial_rag.core.errors import InvalidEmbeddingError, RetrievalError
from financial_rag.domain.fingerprints import ConfigurationFingerprint
from financial_rag.domain.retrieval import ChunkRecord
from financial_rag.retrieval.corpus import validate_records
from financial_rag.retrieval.hits import IndexHit
from financial_rag.retrieval.protocols import EmbeddingProvider
from financial_rag.retrieval.vectors import normalize_l2, normalize_query_vector


class DenseIndex:
    """Aligned FAISS inner-product index over L2-normalized chunk vectors."""

    def __init__(self, index: Any, records: Sequence[ChunkRecord], *, dimension: int) -> None:
        self._records = validate_records(records)
        self._index = index
        self._dimension = dimension
        if int(index.metric_type) != int(faiss.METRIC_INNER_PRODUCT):
            raise RetrievalError("FAISS index must use inner-product search")
        if int(index.d) != dimension:
            raise InvalidEmbeddingError(
                f"FAISS dimension mismatch: expected {dimension}, got {index.d}"
            )
        if int(index.ntotal) != len(self._records):
            raise RetrievalError("FAISS rows and chunk mapping are not aligned")

    @classmethod
    def build(
        cls,
        records: Sequence[ChunkRecord],
        provider: EmbeddingProvider,
        *,
        batch_size: int | None = None,
    ) -> "DenseIndex":
        """Embed records, enforce L2 normalization, and build IndexFlatIP."""
        validated = validate_records(records)
        embeddings = provider.embed_documents(
            [record.content for record in validated], batch_size=batch_size
        )
        if embeddings.shape[0] != len(validated):
            raise InvalidEmbeddingError("Embedding rows and chunk records are not aligned")
        matrix = normalize_l2(embeddings, dimension=provider.dimension)
        index: Any = faiss.IndexFlatIP(provider.dimension)
        index.add(matrix)
        return cls(index, validated, dimension=provider.dimension)

    @classmethod
    def from_embeddings(
        cls,
        records: Sequence[ChunkRecord],
        embeddings: ArrayLike,
        *,
        dimension: int,
    ) -> "DenseIndex":
        """Build IndexFlatIP from already persisted and aligned embeddings."""
        validated = validate_records(records)
        matrix = normalize_l2(embeddings, dimension=dimension)
        if matrix.shape[0] != len(validated):
            raise InvalidEmbeddingError("Embedding rows and chunk records are not aligned")
        index: Any = faiss.IndexFlatIP(dimension)
        index.add(matrix)
        return cls(index, validated, dimension=dimension)

    @property
    def records(self) -> tuple[ChunkRecord, ...]:
        return self._records

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def count(self) -> int:
        return len(self._records)

    @property
    def raw_index(self) -> Any:
        """Expose the FAISS object only to the local artifact adapter."""
        return self._index

    @property
    def vector_fingerprint(self) -> ConfigurationFingerprint:
        """Hash stored vectors in bounded batches to detect mixed artifact sets."""
        digest = hashlib.sha256()
        digest.update(f"float32:{self.count}:{self.dimension}".encode("ascii"))
        batch_size = 1024
        for start in range(0, self.count, batch_size):
            count = min(batch_size, self.count - start)
            reconstructed = np.asarray(self._index.reconstruct_n(start, count), dtype=np.float32)
            digest.update(np.ascontiguousarray(reconstructed).tobytes())
        return ConfigurationFingerprint(value=digest.hexdigest())

    def search(self, query_vector: ArrayLike, *, top_k: int) -> list[IndexHit]:
        """Search the complete index and stabilize equal-score ordering by chunk ID."""
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        vector = normalize_query_vector(query_vector, dimension=self.dimension)
        scores, row_indices = self._index.search(vector, min(top_k, self.count))
        candidates = [
            (int(row_index), float(score))
            for row_index, score in zip(row_indices[0], scores[0], strict=True)
            if int(row_index) >= 0
        ]
        candidates.sort(key=lambda item: (-item[1], self.records[item[0]].metadata.chunk_id))
        return [
            IndexHit(
                row_index=row_index,
                chunk_id=self.records[row_index].metadata.chunk_id,
                rank=rank,
                score=score,
            )
            for rank, (row_index, score) in enumerate(candidates, start=1)
        ]
