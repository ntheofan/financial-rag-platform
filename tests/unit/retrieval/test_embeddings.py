"""Tests for fake embeddings, normalization, validation, and lazy model adapters."""

import importlib
from types import SimpleNamespace
from typing import Any, ClassVar

import numpy as np
import pytest

from financial_rag.core.errors import InvalidEmbeddingError, ProviderUnavailableError
from financial_rag.retrieval.embeddings import BgeM3EmbeddingProvider, FakeEmbeddingProvider
from financial_rag.retrieval.rerankers import BgeM3Reranker
from financial_rag.retrieval.vectors import normalize_l2, normalize_query_vector


class _SyntheticFlagModel:
    def encode(self, texts: list[str], *, batch_size: int) -> dict[str, list[list[float]]]:
        del batch_size
        return {"dense_vecs": [[float(len(text)), 1.0] for text in texts]}

    def encode_queries(self, texts: list[str], *, batch_size: int) -> dict[str, list[list[float]]]:
        del batch_size
        return {"dense_vecs": [[1.0, float(len(text))] for text in texts]}


class _SyntheticAutoModel:
    calls: ClassVar[list[tuple[str, dict[str, Any]]]] = []

    @classmethod
    def from_finetuned(cls, model_identifier: str, **kwargs: Any) -> _SyntheticFlagModel:
        cls.calls.append((model_identifier, kwargs))
        return _SyntheticFlagModel()


class _SyntheticFlagReranker:
    def compute_score(self, pairs: list[list[str]], *, batch_size: int) -> list[float]:
        del batch_size
        return [float(len(pair[1])) for pair in pairs]


class _SyntheticAutoReranker:
    @classmethod
    def from_finetuned(cls, model_identifier: str, **kwargs: Any) -> _SyntheticFlagReranker:
        del model_identifier, kwargs
        return _SyntheticFlagReranker()


def test_fake_embeddings_are_deterministic_and_l2_normalized() -> None:
    """Offline vectors repeat exactly and have unit norm."""
    provider = FakeEmbeddingProvider(dimension=64)
    first = provider.embed_documents(["revenue growth", "cash flow"])
    second = provider.embed_documents(["revenue growth", "cash flow"])

    np.testing.assert_array_equal(first, second)
    np.testing.assert_allclose(np.linalg.norm(first, axis=1), np.ones(2), atol=1e-6)
    np.testing.assert_array_equal(provider.embed_query("revenue growth"), first[0])


@pytest.mark.parametrize(
    "vectors",
    [
        [1.0, 2.0],
        [[1.0, 2.0, 3.0]],
        [[0.0, 0.0]],
        [[float("nan"), 1.0]],
    ],
)
def test_l2_normalization_rejects_invalid_vectors(vectors: Any) -> None:
    """Shape, dimension, zero-norm, and non-finite vectors fail explicitly."""
    with pytest.raises(InvalidEmbeddingError):
        normalize_l2(vectors, dimension=2)


def test_query_vector_requires_exactly_one_row() -> None:
    """A provider cannot return multiple vectors for one query."""
    with pytest.raises(InvalidEmbeddingError, match="exactly one"):
        normalize_query_vector([[1.0, 0.0], [0.0, 1.0]], dimension=2)


def test_real_model_adapters_are_lazy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Import and construction do not import FlagEmbedding or request weights."""
    imported: list[str] = []

    def blocked_import(name: str) -> None:
        imported.append(name)
        raise ImportError(name)

    monkeypatch.setattr(importlib, "import_module", blocked_import)
    embedding_provider = BgeM3EmbeddingProvider(device="cpu")
    reranker = BgeM3Reranker(device="cpu")

    assert not imported
    assert embedding_provider.is_loaded is False
    assert reranker.is_loaded is False
    with pytest.raises(ProviderUnavailableError):
        embedding_provider.embed_query("synthetic query")
    with pytest.raises(ProviderUnavailableError):
        reranker.score("synthetic query", ["synthetic passage"])
    assert imported == ["FlagEmbedding", "FlagEmbedding"]


def test_lazy_adapters_use_injected_flagembedding_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Adapter batching/device/output logic is tested without third-party weights."""
    synthetic_module = SimpleNamespace(
        FlagAutoModel=_SyntheticAutoModel,
        FlagAutoReranker=_SyntheticAutoReranker,
    )
    monkeypatch.setattr(importlib, "import_module", lambda _name: synthetic_module)
    _SyntheticAutoModel.calls.clear()

    provider = BgeM3EmbeddingProvider(dimension=2, device="cpu", batch_size=2)
    documents = provider.embed_documents(["alpha", "beta"])
    query = provider.embed_query("query")
    reranker = BgeM3Reranker(device="cpu", batch_size=2)
    scores = reranker.score("query", ["a", "longer"])

    np.testing.assert_allclose(np.linalg.norm(documents, axis=1), np.ones(2), atol=1e-6)
    assert query.shape == (2,)
    assert scores == [1.0, 6.0]
    assert provider.is_loaded is True
    assert reranker.is_loaded is True
    assert _SyntheticAutoModel.calls == [("BAAI/bge-m3", {"use_fp16": False, "devices": "cpu"})]
