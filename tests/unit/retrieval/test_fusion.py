"""Tests for weighted RRF scoring, tie-breaking, and duplicate handling."""

import pytest

from financial_rag.core.errors import DuplicateChunkError
from financial_rag.retrieval.fusion import weighted_reciprocal_rank_fusion
from financial_rag.retrieval.hits import IndexHit


def _hit(row: int, chunk_id: str, rank: int, score: float) -> IndexHit:
    return IndexHit(row_index=row, chunk_id=chunk_id, rank=rank, score=score)


def test_weighted_rrf_merges_scores_from_both_retrievers() -> None:
    """A duplicate candidate receives both dense and BM25 reciprocal-rank terms."""
    dense = [_hit(0, "chunk_a", 1, 0.9), _hit(1, "chunk_b", 2, 0.8)]
    bm25 = [_hit(1, "chunk_b", 1, 4.0), _hit(2, "chunk_c", 2, 3.0)]

    fused = weighted_reciprocal_rank_fusion(dense, bm25)

    assert fused[0].chunk_id == "chunk_b"
    assert fused[0].rrf_score == pytest.approx(1.0 / 32 + 0.2 / 31)
    assert fused[0].dense_rank == 2
    assert fused[0].bm25_rank == 1


def test_duplicate_hits_in_one_source_contribute_once() -> None:
    """Repeated candidate rows cannot inflate one retriever's RRF contribution."""
    duplicate = [_hit(0, "chunk_a", 1, 0.9), _hit(0, "chunk_a", 2, 0.8)]
    fused = weighted_reciprocal_rank_fusion(duplicate, [])

    assert len(fused) == 1
    assert fused[0].rrf_score == pytest.approx(1.0 / 31)


def test_rrf_ties_use_stable_chunk_id_order() -> None:
    """Equal scores and ranks are resolved lexicographically by chunk ID."""
    fused = weighted_reciprocal_rank_fusion(
        [_hit(1, "chunk_b", 1, 0.8), _hit(0, "chunk_a", 1, 0.8)],
        [],
    )
    assert [candidate.chunk_id for candidate in fused] == ["chunk_a", "chunk_b"]


def test_conflicting_duplicate_mapping_is_rejected() -> None:
    """The same chunk ID cannot point at two corpus rows."""
    with pytest.raises(DuplicateChunkError):
        weighted_reciprocal_rank_fusion(
            [_hit(0, "chunk_a", 1, 0.9)],
            [_hit(1, "chunk_a", 1, 4.0)],
        )
