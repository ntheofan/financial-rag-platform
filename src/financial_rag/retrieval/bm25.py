"""Transparent thesis-compatible BM25 index and deterministic search."""

import math
import re
from collections import Counter
from collections.abc import Sequence

from financial_rag.domain.retrieval import ChunkRecord
from financial_rag.retrieval.corpus import validate_records
from financial_rag.retrieval.hits import IndexHit

TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9&\.]+")


def tokenize_for_bm25(text: str) -> list[str]:
    """Apply the ASCII finance tokenization used by the thesis notebook."""
    return TOKEN_PATTERN.findall(text.casefold())


class BM25Index:
    """In-memory BM25 using the notebook's positive IDF formula."""

    def __init__(
        self,
        records: Sequence[ChunkRecord],
        *,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        if k1 <= 0 or not 0 <= b <= 1:
            raise ValueError("BM25 requires k1 > 0 and 0 <= b <= 1")
        self._records = validate_records(records)
        self._k1 = k1
        self._b = b
        self._term_frequencies = [Counter(tokenize_for_bm25(record.content)) for record in records]
        self._document_lengths = [
            sum(frequencies.values()) for frequencies in self._term_frequencies
        ]
        self._average_document_length = sum(self._document_lengths) / len(self._document_lengths)
        self._document_frequency: Counter[str] = Counter()
        for frequencies in self._term_frequencies:
            self._document_frequency.update(frequencies.keys())

    @property
    def records(self) -> tuple[ChunkRecord, ...]:
        return self._records

    def search(self, query: str, *, top_k: int) -> list[IndexHit]:
        """Rank lexical matches with stable score/chunk-ID ordering."""
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        query_tokens = set(tokenize_for_bm25(query))
        if not query_tokens or self._average_document_length == 0:
            return []

        scores = [0.0] * len(self.records)
        corpus_size = len(self.records)
        for token in sorted(query_tokens):
            document_frequency = self._document_frequency.get(token, 0)
            if document_frequency == 0:
                continue
            inverse_document_frequency = math.log(
                1 + (corpus_size - document_frequency + 0.5) / (document_frequency + 0.5)
            )
            for row_index, frequencies in enumerate(self._term_frequencies):
                term_frequency = frequencies.get(token, 0)
                if term_frequency == 0:
                    continue
                length_ratio = self._document_lengths[row_index] / self._average_document_length
                denominator = term_frequency + self._k1 * (1 - self._b + self._b * length_ratio)
                scores[row_index] += inverse_document_frequency * (
                    term_frequency * (self._k1 + 1) / denominator
                )

        candidates = [(index, score) for index, score in enumerate(scores) if score > 0]
        candidates.sort(key=lambda item: (-item[1], self.records[item[0]].metadata.chunk_id))
        return [
            IndexHit(
                row_index=row_index,
                chunk_id=self.records[row_index].metadata.chunk_id,
                rank=rank,
                score=score,
            )
            for rank, (row_index, score) in enumerate(candidates[:top_k], start=1)
        ]
