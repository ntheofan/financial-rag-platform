"""Validated configuration for the thesis-compatible text splitter."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

DEFAULT_SEPARATORS: tuple[str, ...] = (
    "\n# ",
    "\n## ",
    "\n### ",
    "\n\n",
    "\n",
    ". ",
    " ",
    "",
)


class ChunkingConfig(BaseModel):
    """Explicit, immutable parameters migrated from the thesis notebook."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_size: int = Field(default=1500, gt=0)
    chunk_overlap: int = Field(default=200, ge=0)
    min_chunk_chars: int = Field(default=200, ge=0)
    separators: tuple[str, ...] = DEFAULT_SEPARATORS

    @model_validator(mode="after")
    def overlap_must_be_smaller_than_chunk(self) -> Self:
        """Reject configurations the recursive splitter cannot apply safely."""
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        if not self.separators or self.separators[-1] != "":
            raise ValueError("separators must end with an empty-string fallback")
        return self
