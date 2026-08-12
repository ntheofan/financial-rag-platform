"""Validated metadata contracts shared by ingestion and chunking."""

from datetime import date
from pathlib import Path
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DocumentId = Annotated[str, Field(pattern=r"^doc_[0-9a-f]{32}$")]
ChunkId = Annotated[str, Field(pattern=r"^chunk_[0-9a-f]{32}$")]


class SourceMetadata(BaseModel):
    """User- or service-supplied metadata before a document ID is known."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    source_file: str = Field(min_length=1)
    company: str | None = None
    filing_type: str | None = None
    filing_date: date | None = None

    @field_validator("source_file")
    @classmethod
    def source_file_must_be_relative(cls, value: str) -> str:
        """Keep machine-specific absolute paths out of portable metadata."""
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("source_file must be a safe relative display path")
        return path.as_posix()

    @field_validator("company", "filing_type", mode="before")
    @classmethod
    def empty_optional_strings_become_none(cls, value: object) -> object:
        """Normalize blank optional labels without inventing metadata."""
        if isinstance(value, str) and not value.strip():
            return None
        return value


class DocumentMetadata(SourceMetadata):
    """Lineage attached to every normalized LangChain source document."""

    document_id: DocumentId
    page_number: int | None = Field(default=None, ge=1)
    section_heading: str | None = None

    @field_validator("section_heading", mode="before")
    @classmethod
    def empty_heading_becomes_none(cls, value: object) -> object:
        """Represent a missing heading consistently."""
        if isinstance(value, str) and not value.strip():
            return None
        return value


class ChunkMetadata(DocumentMetadata):
    """Complete source lineage attached to every output chunk."""

    chunk_id: ChunkId
    chunk_index: int = Field(ge=0)

    @model_validator(mode="after")
    def chunk_id_cannot_equal_document_id(self) -> Self:
        """Defend against accidentally reusing an identifier across entity types."""
        if self.chunk_id == self.document_id:
            raise ValueError("chunk_id must differ from document_id")
        return self
