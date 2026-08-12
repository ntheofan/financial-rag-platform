"""Canonical retrieval and deterministic answer metric tests."""

import pytest

from financial_rag.evaluation.metrics import exact_match, retrieval_metrics, token_f1


def test_retrieval_metrics_use_first_relevant_rank_and_binary_hits() -> None:
    first_rank, reciprocal_rank, hits = retrieval_metrics(
        ["irrelevant", "relevant-b", "relevant-a"],
        ["relevant-a", "relevant-b"],
        hit_ks=(1, 2, 3),
    )

    assert first_rank == 2
    assert reciprocal_rank == 0.5
    assert [(hit.k, hit.value) for hit in hits] == [(1, 0.0), (2, 1.0), (3, 1.0)]


def test_retrieval_miss_is_a_real_zero_not_a_failure() -> None:
    first_rank, reciprocal_rank, hits = retrieval_metrics(["other"], ["relevant"], hit_ks=(1, 5))

    assert first_rank is None
    assert reciprocal_rank == 0.0
    assert [hit.value for hit in hits] == [0.0, 0.0]


def test_answer_metrics_are_normalized_and_deterministic() -> None:
    assert exact_match("Revenue was $20.0 million.", "revenue was 20 0 million") == 1.0
    assert token_f1(
        "capital expenditure increased", "capital expenditure declined"
    ) == pytest.approx(2 / 3)
    assert token_f1("", "") == 1.0
    assert token_f1("", "expected") == 0.0
