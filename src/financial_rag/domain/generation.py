"""Typed contracts for grounded answer generation and citation lineage."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from financial_rag.domain.retrieval import RetrievalResult, RetrievedChunk


class CitationContext(BaseModel):
    """One retrieved chunk exposed to the generator under a stable citation label."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    citation_id: str = Field(pattern=r"^C[1-5]$")
    chunk: RetrievedChunk
    content: str = Field(min_length=1)
    content_truncated: bool = False


class AssembledContext(BaseModel):
    """Deterministic, bounded context sent to one generation request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    items: tuple[CitationContext, ...]
    estimated_token_count: int = Field(ge=0)
    token_budget: int = Field(gt=0)

    @model_validator(mode="after")
    def citation_labels_are_contiguous(self) -> Self:
        expected = [f"C{index}" for index in range(1, len(self.items) + 1)]
        if [item.citation_id for item in self.items] != expected:
            raise ValueError("citation labels must be contiguous and one-based")
        return self


class GenerationPrompt(BaseModel):
    """Provider-neutral prompt payload assembled from trusted instructions and local context."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    instructions: str = Field(min_length=1)
    input_text: str = Field(min_length=1)


class ModelAnswer(BaseModel):
    """Small structured response expected from a generation adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    answer: str = Field(min_length=1)
    abstained: bool
    citation_ids: tuple[str, ...] = ()


class GenerationUsage(BaseModel):
    """Provider-reported token usage when available."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class GenerationResult(BaseModel):
    """Adapter output plus non-secret provider metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    answer: ModelAnswer
    model_identifier: str = Field(min_length=1)
    usage: GenerationUsage = GenerationUsage()


class AnswerCitation(BaseModel):
    """Validated citation mapped back to immutable document/chunk lineage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    citation_id: str = Field(pattern=r"^C[1-5]$")
    chunk_id: str
    document_id: str
    source_file: str
    page_number: int | None
    section_heading: str | None
    retrieval_rank: int = Field(ge=1)


class GroundedAnswer(BaseModel):
    """End-to-end retrieval and generation result returned by the API."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    answer: str = Field(min_length=1)
    abstained: bool
    citations: tuple[AnswerCitation, ...]
    contexts: tuple[CitationContext, ...]
    retrieval: RetrievalResult
    model_identifier: str = Field(min_length=1)
    usage: GenerationUsage

    @model_validator(mode="after")
    def grounded_or_abstained(self) -> Self:
        if self.abstained and self.citations:
            raise ValueError("abstained answers cannot include citations")
        if not self.abstained and not self.citations:
            raise ValueError("non-abstained answers require at least one citation")
        return self
