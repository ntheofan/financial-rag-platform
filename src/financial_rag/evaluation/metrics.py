"""Canonical deterministic retrieval and answer metrics for platform_eval_v1."""

import re
from collections import Counter
from collections.abc import Sequence

from financial_rag.domain.evaluation import HitAtK

ANSWER_TOKEN_PATTERN = re.compile(r"\w+", flags=re.UNICODE)


def retrieval_metrics(
    retrieved_chunk_ids: Sequence[str],
    relevant_chunk_ids: Sequence[str],
    *,
    hit_ks: tuple[int, ...],
) -> tuple[int | None, float, tuple[HitAtK, ...]]:
    """Compute first relevant rank, reciprocal rank, and binary Hit@K."""
    relevant = set(relevant_chunk_ids)
    first_rank = next(
        (
            rank
            for rank, chunk_id in enumerate(retrieved_chunk_ids, start=1)
            if chunk_id in relevant
        ),
        None,
    )
    reciprocal_rank = 0.0 if first_rank is None else 1.0 / first_rank
    hits = tuple(
        HitAtK(k=k, value=float(any(chunk_id in relevant for chunk_id in retrieved_chunk_ids[:k])))
        for k in hit_ks
    )
    return first_rank, reciprocal_rank, hits


def normalize_answer(text: str) -> tuple[str, ...]:
    """Case-fold and remove punctuation/whitespace for deterministic comparison."""
    return tuple(ANSWER_TOKEN_PATTERN.findall(text.casefold()))


def exact_match(predicted: str, expected: str) -> float:
    """Return normalized token-sequence exact match."""
    return float(normalize_answer(predicted) == normalize_answer(expected))


def token_f1(predicted: str, expected: str) -> float:
    """Return bag-of-token F1 with deterministic empty-answer semantics."""
    predicted_tokens = normalize_answer(predicted)
    expected_tokens = normalize_answer(expected)
    if not predicted_tokens and not expected_tokens:
        return 1.0
    if not predicted_tokens or not expected_tokens:
        return 0.0
    overlap = sum((Counter(predicted_tokens) & Counter(expected_tokens)).values())
    if overlap == 0:
        return 0.0
    precision = overlap / len(predicted_tokens)
    recall = overlap / len(expected_tokens)
    return 2 * precision * recall / (precision + recall)
