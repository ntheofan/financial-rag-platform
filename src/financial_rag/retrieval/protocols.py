"""Typed provider ports for embeddings and reranking."""

from collections.abc import Sequence
from typing import Protocol

import numpy as np
from numpy.typing import NDArray


class EmbeddingProvider(Protocol):
    """Explicit dense-embedding provider contract."""

    @property
    def model_identifier(self) -> str:
        """Return the exact model or deterministic fake identifier."""
        ...

    @property
    def dimension(self) -> int:
        """Return the dense vector dimension."""
        ...

    @property
    def normalization_method(self) -> str:
        """Return the provider's declared output normalization."""
        ...

    def embed_documents(
        self, texts: Sequence[str], *, batch_size: int | None = None
    ) -> NDArray[np.float32]:
        """Embed corpus passages without external side effects beyond the provider."""
        ...

    def embed_query(self, text: str) -> NDArray[np.float32]:
        """Embed one retrieval query."""
        ...


class Reranker(Protocol):
    """Cross-encoder scoring contract."""

    @property
    def model_identifier(self) -> str:
        """Return the exact model or deterministic fake identifier."""
        ...

    def score(
        self,
        query: str,
        documents: Sequence[str],
        *,
        batch_size: int | None = None,
    ) -> list[float]:
        """Return one score per query-document pair in input order."""
        ...
