"""Modular platform_v1 dense, hybrid, and reranked retrieval."""

from financial_rag.retrieval.artifacts import DenseIndexArtifactStore
from financial_rag.retrieval.bm25 import BM25Index
from financial_rag.retrieval.dense import DenseIndex
from financial_rag.retrieval.embeddings import BgeM3EmbeddingProvider, FakeEmbeddingProvider
from financial_rag.retrieval.fusion import weighted_reciprocal_rank_fusion
from financial_rag.retrieval.protocols import EmbeddingProvider, Reranker
from financial_rag.retrieval.query_expansion import FinanceQueryExpander
from financial_rag.retrieval.rerankers import BgeM3Reranker, FakeReranker
from financial_rag.retrieval.service import RetrievalService

__all__ = [
    "BM25Index",
    "BgeM3EmbeddingProvider",
    "BgeM3Reranker",
    "DenseIndex",
    "DenseIndexArtifactStore",
    "EmbeddingProvider",
    "FakeEmbeddingProvider",
    "FakeReranker",
    "FinanceQueryExpander",
    "Reranker",
    "RetrievalService",
    "weighted_reciprocal_rank_fusion",
]
