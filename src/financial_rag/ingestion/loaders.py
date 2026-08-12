"""Local Markdown, text, and PDF ingestion adapters."""

from pathlib import Path
from typing import Any

import pymupdf
import structlog
from langchain_core.documents import Document

from financial_rag.core.errors import (
    CorruptDocumentError,
    DocumentNotFoundError,
    EmptyInputError,
    IngestionError,
    UnsupportedDocumentTypeError,
)
from financial_rag.domain.identifiers import make_document_id
from financial_rag.domain.metadata import DocumentMetadata, SourceMetadata
from financial_rag.ingestion.normalization import normalize_document_text

logger = structlog.get_logger(__name__)


def _validate_file(path: Path, supported_extensions: frozenset[str]) -> None:
    if not path.is_file():
        raise DocumentNotFoundError(path)
    if path.suffix.lower() not in supported_extensions:
        raise UnsupportedDocumentTypeError(path, tuple(sorted(supported_extensions)))


def _read_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise IngestionError(f"Unable to read local document {path.name}: {exc}") from exc


def _source_metadata(path: Path, supplied: SourceMetadata | None) -> SourceMetadata:
    return supplied or SourceMetadata(source_file=path.name)


def _document_metadata(
    *,
    source: SourceMetadata,
    document_id: str,
    page_number: int | None,
) -> DocumentMetadata:
    return DocumentMetadata(
        document_id=document_id,
        source_file=source.source_file,
        company=source.company,
        filing_type=source.filing_type,
        filing_date=source.filing_date,
        page_number=page_number,
        section_heading=None,
    )


def _langchain_metadata(metadata: DocumentMetadata) -> dict[str, Any]:
    return metadata.model_dump(mode="json")


class TextMarkdownLoader:
    """Load local UTF-8 Markdown and plain-text files."""

    @property
    def supported_extensions(self) -> frozenset[str]:
        """Return the explicit extensions handled by this adapter."""
        return frozenset({".md", ".txt"})

    def load(self, path: Path, *, metadata: SourceMetadata | None = None) -> list[Document]:
        """Validate, decode, normalize, and convert one local file."""
        _validate_file(path, self.supported_extensions)
        content_bytes = _read_bytes(path)
        if b"\x00" in content_bytes:
            raise CorruptDocumentError(f"Text document contains NUL bytes: {path.name}")

        try:
            raw_text = content_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise CorruptDocumentError(f"Text document is not valid UTF-8: {path.name}") from exc

        normalized = normalize_document_text(raw_text)
        if not normalized.strip():
            raise EmptyInputError(f"Document contains no text: {path.name}")

        document_id = make_document_id(content_bytes)
        document_metadata = _document_metadata(
            source=_source_metadata(path, metadata),
            document_id=document_id,
            page_number=None,
        )
        logger.info(
            "local_text_document_loaded",
            document_id=document_id,
            source_file=document_metadata.source_file,
        )
        return [Document(page_content=normalized, metadata=_langchain_metadata(document_metadata))]


class PyMuPDFLoader:
    """Extract local PDF text page by page with PyMuPDF.

    This adapter performs no OCR. Image-only or otherwise textless PDFs fail
    explicitly instead of being presented as successfully parsed documents.
    """

    @property
    def supported_extensions(self) -> frozenset[str]:
        """Return the PDF extension handled by this adapter."""
        return frozenset({".pdf"})

    def load(self, path: Path, *, metadata: SourceMetadata | None = None) -> list[Document]:
        """Validate a PDF and return one normalized LangChain document per text page."""
        _validate_file(path, self.supported_extensions)
        content_bytes = _read_bytes(path)
        if not content_bytes:
            raise EmptyInputError(f"PDF file is empty: {path.name}")

        try:
            pdf: Any = pymupdf.open(  # type: ignore[no-untyped-call]
                stream=content_bytes, filetype="pdf"
            )
        except (pymupdf.FileDataError, RuntimeError, ValueError) as exc:
            raise CorruptDocumentError(f"PDF cannot be parsed: {path.name}") from exc

        source = _source_metadata(path, metadata)
        document_id = make_document_id(content_bytes)
        documents: list[Document] = []
        try:
            if pdf.needs_pass:
                raise CorruptDocumentError(f"Password-protected PDF is not supported: {path.name}")

            for page_index, page in enumerate(pdf):
                extracted = normalize_document_text(page.get_text("text", sort=True))
                if not extracted.strip():
                    continue
                page_metadata = _document_metadata(
                    source=source,
                    document_id=document_id,
                    page_number=page_index + 1,
                )
                documents.append(
                    Document(page_content=extracted, metadata=_langchain_metadata(page_metadata))
                )
        finally:
            pdf.close()

        if not documents:
            raise EmptyInputError(
                f"PDF contains no extractable text: {path.name}. OCR is not implemented."
            )

        logger.info(
            "local_pdf_document_loaded",
            document_id=document_id,
            page_count=len(documents),
            source_file=source.source_file,
        )
        return documents
