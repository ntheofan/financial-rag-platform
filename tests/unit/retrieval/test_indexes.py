"""Offline tests for FAISS dense and thesis-compatible BM25 ranking."""

from typing import Any

import faiss
import numpy as np
import pytest

from financial_rag.core.errors import RetrievalError
from financial_rag.retrieval.bm25 import BM25Index
from financial_rag.retrieval.corpus import records_from_documents
from financial_rag.retrieval.dense import DenseIndex
from financial_rag.retrieval.embeddings import FakeEmbeddingProvider
from tests.unit.retrieval.helpers import synthetic_chunks


def test_faiss_dense_ranking_uses_normalized_inner_product() -> None:
    """A query ranks the identical synthetic chunk first under IndexFlatIP."""
    records = records_from_documents(
        synthetic_chunks(["revenue growth", "cash flow", "inventory balance"])
    )
    provider = FakeEmbeddingProvider(dimension=128)
    index = DenseIndex.build(records, provider)

    hits = index.search(provider.embed_query("revenue growth"), top_k=3)

    assert hits[0].row_index == 0
    assert hits[0].score > hits[1].score
    assert [hit.rank for hit in hits] == [1, 2, 3]


def test_dense_index_rejects_non_inner_product_faiss_index() -> None:
    """An L2 FAISS artifact cannot masquerade as the cosine-ranking protocol."""
    records = records_from_documents(synthetic_chunks(["revenue growth"]))
    l2_index: Any = faiss.IndexFlatL2(2)
    l2_index.add(np.asarray([[1.0, 0.0]], dtype=np.float32))

    with pytest.raises(RetrievalError, match="inner-product"):
        DenseIndex(l2_index, records, dimension=2)


def test_bm25_ranks_matching_financial_terms() -> None:
    """The exact thesis BM25 parameters favor the matching synthetic passage."""
    records = records_from_documents(
        synthetic_chunks(
            [
                "capital expenditures purchases property plant equipment",
                "revenue and net income",
                "risk factors and litigation",
            ]
        )
    )
    index = BM25Index(records, k1=1.5, b=0.75)

    hits = index.search("capital expenditures", top_k=3)

    assert hits[0].row_index == 0
    assert index.search("unmatchedtoken", top_k=3) == []


def test_bm25_equal_scores_use_chunk_id_tie_breaking() -> None:
    """Equal lexical scores have a stable public ordering."""
    records = records_from_documents(synthetic_chunks(["cash alpha", "cash bravo"]))
    hits = BM25Index(records).search("cash", top_k=2)

    assert [hit.chunk_id for hit in hits] == sorted(hit.chunk_id for hit in hits)
