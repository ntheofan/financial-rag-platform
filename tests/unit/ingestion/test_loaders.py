"""Offline tests for local text, Markdown, and PDF adapters."""

from pathlib import Path
from typing import Any

import pymupdf
import pytest

from financial_rag.core.errors import (
    CorruptDocumentError,
    DocumentNotFoundError,
    EmptyInputError,
    UnsupportedDocumentTypeError,
)
from financial_rag.domain.metadata import DocumentMetadata, SourceMetadata
from financial_rag.ingestion.loaders import PyMuPDFLoader, TextMarkdownLoader


def test_markdown_loader_returns_normalized_langchain_document(tmp_path: Path) -> None:
    """A local Markdown file becomes one validated source document."""
    path = tmp_path / "report.md"
    path.write_text("# Results\r\n\r\nSynthetic results.\r\n", encoding="utf-8")

    documents = TextMarkdownLoader().load(
        path,
        metadata=SourceMetadata(
            source_file="filings/report.md",
            company="ACME Corp",
            filing_type="10-Q",
        ),
    )
    metadata = DocumentMetadata.model_validate(documents[0].metadata)

    assert documents[0].page_content == "# Results\n\nSynthetic results."
    assert metadata.source_file == "filings/report.md"
    assert metadata.company == "ACME Corp"
    assert metadata.page_number is None


def test_pdf_loader_extracts_synthetic_pages_with_page_numbers(tmp_path: Path) -> None:
    """PyMuPDF extraction emits one document per non-empty synthetic page."""
    path = tmp_path / "synthetic.pdf"
    pdf: Any = pymupdf.open()  # type: ignore[no-untyped-call]
    first_page = pdf.new_page()
    first_page.insert_text((72, 72), "Synthetic page one")
    second_page = pdf.new_page()
    second_page.insert_text((72, 72), "Synthetic page two")
    pdf.save(path)
    pdf.close()

    documents = PyMuPDFLoader().load(path)
    metadata = [DocumentMetadata.model_validate(document.metadata) for document in documents]

    assert [item.page_number for item in metadata] == [1, 2]
    assert len({item.document_id for item in metadata}) == 1
    assert [document.page_content for document in documents] == [
        "Synthetic page one",
        "Synthetic page two",
    ]


@pytest.mark.parametrize("content", [b"", b"\xff\xfe", b"text\x00content"])
def test_text_loader_rejects_empty_or_corrupt_input(tmp_path: Path, content: bytes) -> None:
    """Empty, non-UTF-8, and NUL-bearing inputs fail as domain errors."""
    path = tmp_path / "invalid.md"
    path.write_bytes(content)

    with pytest.raises((EmptyInputError, CorruptDocumentError)):
        TextMarkdownLoader().load(path)


def test_pdf_loader_rejects_corrupt_input(tmp_path: Path) -> None:
    """A file with a PDF suffix but invalid bytes is not accepted."""
    path = tmp_path / "corrupt.pdf"
    path.write_bytes(b"not a valid pdf")

    with pytest.raises(CorruptDocumentError, match="cannot be parsed"):
        PyMuPDFLoader().load(path)


def test_loader_rejects_missing_and_unsupported_paths(tmp_path: Path) -> None:
    """Path validation distinguishes absent files from unsupported extensions."""
    loader = TextMarkdownLoader()
    unsupported = tmp_path / "report.csv"
    unsupported.write_text("synthetic", encoding="utf-8")

    with pytest.raises(DocumentNotFoundError):
        loader.load(tmp_path / "missing.md")
    with pytest.raises(UnsupportedDocumentTypeError, match=r"\.csv"):
        loader.load(unsupported)
