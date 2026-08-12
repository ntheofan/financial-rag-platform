"""Deterministic top-five context assembly with a transparent token estimate."""

import re
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from financial_rag.domain.generation import AssembledContext, CitationContext
from financial_rag.domain.retrieval import RetrievalResult

TOKEN_PATTERN = re.compile(r"\S+")


class ContextAssemblyConfig(BaseModel):
    """Explicit limits for the generation context boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    top_k: int = Field(default=5, ge=1, le=5)
    token_budget: int = Field(default=6000, gt=0)


class TokenCounter(Protocol):
    """Minimal boundary for deterministic counting and prefix truncation."""

    def count(self, text: str) -> int:
        """Return a token count for one text."""
        ...

    def truncate(self, text: str, max_tokens: int) -> str:
        """Return a prefix containing no more than the requested tokens."""
        ...


class RegexTokenCounter:
    """Offline whitespace-token estimate; it is not a provider billing tokenizer."""

    def count(self, text: str) -> int:
        return len(TOKEN_PATTERN.findall(text))

    def truncate(self, text: str, max_tokens: int) -> str:
        if max_tokens <= 0:
            return ""
        matches = list(TOKEN_PATTERN.finditer(text))
        if len(matches) <= max_tokens:
            return text
        return text[: matches[max_tokens - 1].end()].rstrip()


class ContextAssembler:
    """Select ranked chunks in order and apply one deterministic total budget."""

    def __init__(
        self,
        config: ContextAssemblyConfig | None = None,
        *,
        token_counter: TokenCounter | None = None,
    ) -> None:
        self._config = config or ContextAssemblyConfig()
        self._tokens = token_counter or RegexTokenCounter()

    def assemble(self, retrieval: RetrievalResult) -> AssembledContext:
        """Assemble at most five contexts while preserving retrieved chunk lineage."""
        remaining = self._config.token_budget
        items: list[CitationContext] = []
        for chunk in retrieval.chunks[: self._config.top_k]:
            if remaining <= 0:
                break
            count = self._tokens.count(chunk.content)
            content = chunk.content
            truncated = False
            if count > remaining:
                content = self._tokens.truncate(content, remaining)
                count = self._tokens.count(content)
                truncated = True
            if not content:
                break
            items.append(
                CitationContext(
                    citation_id=f"C{len(items) + 1}",
                    chunk=chunk,
                    content=content,
                    content_truncated=truncated,
                )
            )
            remaining -= count
        return AssembledContext(
            items=tuple(items),
            estimated_token_count=self._config.token_budget - remaining,
            token_budget=self._config.token_budget,
        )
