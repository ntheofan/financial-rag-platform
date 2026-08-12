"""Provider-neutral generation port."""

from typing import Protocol

from financial_rag.domain.generation import GenerationPrompt, GenerationResult


class GenerationAdapter(Protocol):
    """Generate one structured answer without owning retrieval logic."""

    @property
    def model_identifier(self) -> str:
        """Return the stable provider model identifier."""
        ...

    def generate(self, prompt: GenerationPrompt) -> GenerationResult:
        """Generate and parse one provider response."""
        ...
