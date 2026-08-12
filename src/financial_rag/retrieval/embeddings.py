"""Deterministic fake and lazy FlagEmbedding BGE-M3 providers."""

import hashlib
import importlib
import re
from collections.abc import Mapping, Sequence
from typing import Any, Literal, cast

import numpy as np
from numpy.typing import NDArray

from financial_rag.core.errors import EmptyQueryError, ProviderUnavailableError
from financial_rag.retrieval.vectors import normalize_l2, normalize_query_vector

TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9&\.]+")
Device = Literal["cpu", "cuda", "auto"]


class FakeEmbeddingProvider:
    """Deterministic token-hashing embeddings for offline tests and examples."""

    def __init__(self, *, dimension: int = 32, model_identifier: str = "fake-hash-v1") -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self._dimension = dimension
        self._model_identifier = model_identifier

    @property
    def model_identifier(self) -> str:
        return self._model_identifier

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def normalization_method(self) -> str:
        return "l2"

    def embed_documents(
        self, texts: Sequence[str], *, batch_size: int | None = None
    ) -> NDArray[np.float32]:
        del batch_size
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)
        matrix = np.vstack([self._embed_text(text) for text in texts])
        return normalize_l2(matrix, dimension=self.dimension)

    def embed_query(self, text: str) -> NDArray[np.float32]:
        if not text.strip():
            raise EmptyQueryError("Query cannot be blank")
        normalized = normalize_query_vector(self._embed_text(text), dimension=self.dimension)
        return cast(NDArray[np.float32], normalized[0])

    def _embed_text(self, text: str) -> NDArray[np.float32]:
        tokens = TOKEN_PATTERN.findall(text.casefold())
        vector = np.zeros(self.dimension, dtype=np.float32)
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:8], "big") % self.dimension
            sign = 1.0 if digest[8] % 2 == 0 else -1.0
            vector[index] += sign
        if not np.any(vector):
            vector[0] = 1.0
        return vector


class BgeM3EmbeddingProvider:
    """Lazy BAAI/bge-m3 adapter backed by the optional FlagEmbedding extra."""

    def __init__(
        self,
        *,
        model_identifier: str = "BAAI/bge-m3",
        dimension: int = 1024,
        device: Device = "auto",
        batch_size: int = 8,
        use_fp16: bool | None = None,
    ) -> None:
        if dimension <= 0 or batch_size <= 0:
            raise ValueError("dimension and batch_size must be positive")
        self._model_identifier = model_identifier
        self._dimension = dimension
        self._device = device
        self._batch_size = batch_size
        self._use_fp16 = device != "cpu" if use_fp16 is None else use_fp16
        self._model: Any | None = None

    @property
    def model_identifier(self) -> str:
        return self._model_identifier

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def normalization_method(self) -> str:
        return "l2"

    @property
    def is_loaded(self) -> bool:
        """Expose lazy state without importing or loading the optional model."""
        return self._model is not None

    def embed_documents(
        self, texts: Sequence[str], *, batch_size: int | None = None
    ) -> NDArray[np.float32]:
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)
        output = self._encode("encode", texts, batch_size=batch_size)
        return normalize_l2(output, dimension=self.dimension)

    def embed_query(self, text: str) -> NDArray[np.float32]:
        if not text.strip():
            raise EmptyQueryError("Query cannot be blank")
        model = self._load_model()
        method_name = "encode_queries" if hasattr(model, "encode_queries") else "encode"
        output = self._encode(method_name, [text], batch_size=1)
        normalized = normalize_query_vector(output, dimension=self.dimension)
        return cast(NDArray[np.float32], normalized[0])

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            module = importlib.import_module("FlagEmbedding")
            factory = module.FlagAutoModel
            kwargs: dict[str, Any] = {"use_fp16": self._use_fp16}
            if self._device != "auto":
                kwargs["devices"] = self._device
            self._model = factory.from_finetuned(self.model_identifier, **kwargs)
        except Exception as exc:
            raise ProviderUnavailableError(
                "Unable to load the optional FlagEmbedding BGE-M3 provider. "
                "Install the 'models' extra and ensure model weights are available."
            ) from exc
        return self._model

    def _encode(
        self, method_name: str, texts: Sequence[str], *, batch_size: int | None
    ) -> NDArray[np.float32]:
        model = self._load_model()
        method = getattr(model, method_name)
        raw_output = method(list(texts), batch_size=batch_size or self._batch_size)
        if isinstance(raw_output, Mapping):
            if "dense_vecs" not in raw_output:
                raise ProviderUnavailableError("BGE-M3 output does not contain dense_vecs")
            raw_output = raw_output["dense_vecs"]
        return np.asarray(raw_output, dtype=np.float32)
