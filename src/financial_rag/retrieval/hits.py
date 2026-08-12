"""Small internal ranked-hit value objects."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IndexHit:
    """One ranked hit from a dense or lexical index."""

    row_index: int
    chunk_id: str
    rank: int
    score: float


@dataclass(frozen=True, slots=True)
class FusedCandidate:
    """A unique candidate with transparent component and RRF scores."""

    row_index: int
    chunk_id: str
    dense_rank: int | None
    dense_score: float | None
    bm25_rank: int | None
    bm25_score: float | None
    rrf_score: float
