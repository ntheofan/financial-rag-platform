"""Deterministic weighted Reciprocal Rank Fusion."""

from dataclasses import dataclass
from math import inf

from financial_rag.core.errors import DuplicateChunkError
from financial_rag.retrieval.hits import FusedCandidate, IndexHit


@dataclass(slots=True)
class _MutableCandidate:
    row_index: int
    chunk_id: str
    dense_rank: int | None = None
    dense_score: float | None = None
    bm25_rank: int | None = None
    bm25_score: float | None = None
    rrf_score: float = 0.0


def _unique_hits(hits: list[IndexHit]) -> list[IndexHit]:
    unique: dict[str, IndexHit] = {}
    for hit in sorted(hits, key=lambda item: (item.rank, item.chunk_id)):
        existing = unique.get(hit.chunk_id)
        if existing is not None and existing.row_index != hit.row_index:
            raise DuplicateChunkError("One chunk ID points to multiple corpus rows")
        unique.setdefault(hit.chunk_id, hit)
    return list(unique.values())


def weighted_reciprocal_rank_fusion(
    dense_hits: list[IndexHit],
    bm25_hits: list[IndexHit],
    *,
    rrf_k: int = 30,
    dense_weight: float = 1.0,
    bm25_weight: float = 0.2,
    limit: int | None = None,
) -> list[FusedCandidate]:
    """Merge duplicate candidates and sort ties by best rank then chunk ID."""
    if rrf_k <= 0 or dense_weight <= 0 or bm25_weight <= 0:
        raise ValueError("RRF k and weights must be positive")
    if limit is not None and limit <= 0:
        raise ValueError("RRF limit must be positive when provided")

    fused: dict[str, _MutableCandidate] = {}
    for source, hits, weight in (
        ("dense", _unique_hits(dense_hits), dense_weight),
        ("bm25", _unique_hits(bm25_hits), bm25_weight),
    ):
        for hit in hits:
            candidate = fused.setdefault(
                hit.chunk_id,
                _MutableCandidate(row_index=hit.row_index, chunk_id=hit.chunk_id),
            )
            if candidate.row_index != hit.row_index:
                raise DuplicateChunkError("Dense and BM25 mappings disagree for a chunk ID")
            if source == "dense":
                candidate.dense_rank = hit.rank
                candidate.dense_score = hit.score
            else:
                candidate.bm25_rank = hit.rank
                candidate.bm25_score = hit.score
            candidate.rrf_score += weight / (rrf_k + hit.rank)

    ranked = [
        FusedCandidate(
            row_index=item.row_index,
            chunk_id=item.chunk_id,
            dense_rank=item.dense_rank,
            dense_score=item.dense_score,
            bm25_rank=item.bm25_rank,
            bm25_score=item.bm25_score,
            rrf_score=item.rrf_score,
        )
        for item in fused.values()
    ]
    ranked.sort(
        key=lambda item: (
            -item.rrf_score,
            min(item.dense_rank or inf, item.bm25_rank or inf),
            item.chunk_id,
        )
    )
    return ranked if limit is None else ranked[:limit]
