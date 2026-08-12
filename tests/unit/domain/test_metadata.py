"""Tests for strict document and chunk metadata contracts."""

from datetime import date

import pytest
from pydantic import ValidationError

from financial_rag.domain.metadata import ChunkMetadata, DocumentMetadata, SourceMetadata

DOCUMENT_ID = "doc_0123456789abcdef0123456789abcdef"
CHUNK_ID = "chunk_fedcba9876543210fedcba9876543210"


def test_document_metadata_accepts_complete_lineage() -> None:
    """All required lineage fields remain typed and serializable."""
    metadata = DocumentMetadata(
        document_id=DOCUMENT_ID,
        source_file="filings/acme-2025-10k.md",
        company="ACME Corp",
        filing_type="10-K",
        filing_date=date(2025, 12, 31),
        page_number=7,
        section_heading="Revenue",
    )

    assert metadata.source_file == "filings/acme-2025-10k.md"
    assert metadata.filing_date == date(2025, 12, 31)
    assert metadata.page_number == 7


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("document_id", "acme-file"),
        ("page_number", 0),
        ("source_file", "../private/report.md"),
    ],
)
def test_document_metadata_rejects_invalid_lineage(field: str, value: object) -> None:
    """Malformed identifiers, pages, and unsafe source paths fail validation."""
    values: dict[str, object] = {
        "document_id": DOCUMENT_ID,
        "source_file": "report.md",
        "page_number": 1,
    }
    values[field] = value

    with pytest.raises(ValidationError):
        DocumentMetadata.model_validate(values)


def test_metadata_rejects_unknown_fields() -> None:
    """Silent metadata drift is disallowed."""
    with pytest.raises(ValidationError):
        SourceMetadata(source_file="report.md", secret_path="private")  # type: ignore[call-arg]


def test_chunk_metadata_requires_non_negative_index() -> None:
    """Chunk ordering begins at zero and cannot use negative values."""
    with pytest.raises(ValidationError):
        ChunkMetadata(
            document_id=DOCUMENT_ID,
            source_file="report.md",
            chunk_id=CHUNK_ID,
            chunk_index=-1,
        )
