"""Deterministic fake and lazy FlagEmbedding cross-encoder rerankers."""

import importlib
import re
from collections.abc import Mapping, Sequence
from typing import Any, Literal

import numpy as np

from financial_rag.core.errors import EmptyQueryError, ProviderUnavailableError, RetrievalError

Device = Literal["cpu", "cuda", "auto"]
TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9&\.]+")


class FakeReranker:
    """Offline reranker using explicit text scores or deterministic token overlap."""

    def __init__(self, scores_by_text: Mapping[str, float] | None = None) -> None:
        self._scores_by_text = dict(scores_by_text or {})

    @property
    def model_identifier(self) -> str:
        return "fake-reranker-v1"

    def score(
        self,
        query: str,
        documents: Sequence[str],
        *,
        batch_size: int | None = None,
    ) -> list[float]:
        del batch_size
        if not query.strip():
            raise EmptyQueryError("Query cannot be blank")
        query_tokens = set(TOKEN_PATTERN.findall(query.casefold()))
        return [
            self._scores_by_text.get(
                document,
                float(len(query_tokens & set(TOKEN_PATTERN.findall(document.casefold())))),
            )
            for document in documents
        ]


class BgeM3Reranker:
    """Lazy BAAI/bge-reranker-v2-m3 adapter from the optional models extra."""

    def __init__(
        self,
        *,
        model_identifier: str = "BAAI/bge-reranker-v2-m3",
        device: Device = "auto",
        batch_size: int = 8,
        use_fp16: bool | None = None,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        self._model_identifier = model_identifier
        self._device = device
        self._batch_size = batch_size
        self._use_fp16 = device != "cpu" if use_fp16 is None else use_fp16
        self._model: Any | None = None

    @property
    def model_identifier(self) -> str:
        return self._model_identifier

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def score(
        self,
        query: str,
        documents: Sequence[str],
        *,
        batch_size: int | None = None,
    ) -> list[float]:
        if not query.strip():
            raise EmptyQueryError("Query cannot be blank")
        if not documents:
            return []
        model = self._load_model()
        pairs = [[query, document] for document in documents]
        raw_scores = model.compute_score(pairs, batch_size=batch_size or self._batch_size)
        scores = np.asarray(raw_scores, dtype=np.float64).reshape(-1)
        if len(scores) != len(documents) or not np.isfinite(scores).all():
            raise RetrievalError("Reranker returned invalid scores")
        return [float(score) for score in scores]

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            module = importlib.import_module("FlagEmbedding")
            factory = module.FlagAutoReranker
            kwargs: dict[str, Any] = {"use_fp16": self._use_fp16}
            if self._device != "auto":
                kwargs["devices"] = self._device
            self._model = factory.from_finetuned(self.model_identifier, **kwargs)
        except Exception as exc:
            raise ProviderUnavailableError(
                "Unable to load the optional FlagEmbedding reranker. "
                "Install the 'models' extra and ensure model weights are available."
            ) from exc
        return self._model
