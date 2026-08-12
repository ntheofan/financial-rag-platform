"""Tests for configurable chunking and metadata preservation."""

from datetime import date

import pytest
from langchain_core.documents import Document
from pydantic import ValidationError

from financial_rag.chunking.service import MarkdownChunker
from financial_rag.core.errors import ChunkingError
from financial_rag.domain.chunking import DEFAULT_SEPARATORS, ChunkingConfig
from financial_rag.domain.identifiers import make_document_id
from financial_rag.domain.metadata import ChunkMetadata, DocumentMetadata


def _source_document(text: str, *, page_number: int | None = 3) -> Document:
    metadata = DocumentMetadata(
        document_id=make_document_id(b"stable synthetic source"),
        source_file="synthetic/acme-2025-10k.md",
        company="ACME Corp",
        filing_type="10-K",
        filing_date=date(2025, 12, 31),
        page_number=page_number,
        section_heading=None,
    )
    return Document(page_content=text, metadata=metadata.model_dump(mode="json"))


def test_chunking_defaults_match_thesis_protocol() -> None:
    """The migrated experimental parameters are explicit and unchanged."""
    config = ChunkingConfig()

    assert config.chunk_size == 1500
    assert config.chunk_overlap == 200
    assert config.min_chunk_chars == 200
    assert config.separators == DEFAULT_SEPARATORS


def test_chunking_config_rejects_invalid_overlap() -> None:
    """Overlap cannot consume the whole chunk window."""
    with pytest.raises(ValidationError):
        ChunkingConfig(chunk_size=100, chunk_overlap=100)


def test_chunk_size_and_overlap_are_applied() -> None:
    """Small explicit settings produce bounded chunks with shared boundary text."""
    text = " ".join(f"token{index:03d}" for index in range(60))
    chunker = MarkdownChunker(ChunkingConfig(chunk_size=80, chunk_overlap=20, min_chunk_chars=1))

    chunks = chunker.chunk_documents([_source_document(text, page_number=None)])

    assert len(chunks) > 1
    assert all(len(chunk.page_content) <= 80 for chunk in chunks)
    first_words = set(chunks[0].page_content.split())
    second_words = set(chunks[1].page_content.split())
    assert first_words & second_words


def test_chunking_preserves_complete_metadata_lineage() -> None:
    """Every chunk validates against the exact public metadata contract."""
    text = (
        "# Overview\n"
        + "Revenue remained stable. " * 16
        + "\n\n## Liquidity\n"
        + "Cash resources remained adequate. " * 16
    )
    chunker = MarkdownChunker(ChunkingConfig(chunk_size=180, chunk_overlap=30, min_chunk_chars=1))

    chunks = chunker.chunk_documents([_source_document(text)])
    validated = [ChunkMetadata.model_validate(chunk.metadata) for chunk in chunks]

    expected_keys = {
        "document_id",
        "source_file",
        "company",
        "filing_type",
        "filing_date",
        "page_number",
        "section_heading",
        "chunk_id",
        "chunk_index",
    }
    assert all(set(chunk.metadata) == expected_keys for chunk in chunks)
    assert [metadata.chunk_index for metadata in validated] == list(range(len(chunks)))
    assert all(metadata.page_number == 3 for metadata in validated)
    assert all(metadata.company == "ACME Corp" for metadata in validated)
    assert {metadata.section_heading for metadata in validated} == {"Overview", "Liquidity"}


def test_chunk_identifiers_are_repeatable() -> None:
    """Identical source and configuration produce identical chunk IDs."""
    source = _source_document("# Notes\n" + "Synthetic note. " * 40)
    chunker = MarkdownChunker(ChunkingConfig(chunk_size=120, chunk_overlap=20, min_chunk_chars=1))

    first = chunker.chunk_documents([source])
    second = chunker.chunk_documents([source])

    assert [chunk.metadata["chunk_id"] for chunk in first] == [
        chunk.metadata["chunk_id"] for chunk in second
    ]


def test_chunking_rejects_empty_or_invalid_input() -> None:
    """Missing source documents and invalid metadata fail clearly."""
    chunker = MarkdownChunker(ChunkingConfig(min_chunk_chars=1))

    with pytest.raises(ChunkingError, match="At least one"):
        chunker.chunk_documents([])
    with pytest.raises(ChunkingError, match="metadata is invalid"):
        chunker.chunk_documents([Document(page_content="content", metadata={})])


def test_chunking_reports_when_minimum_discards_all_content() -> None:
    """The preserved 200-character thesis filter cannot fail silently."""
    with pytest.raises(ChunkingError, match="200 characters"):
        MarkdownChunker().chunk_documents([_source_document("Short synthetic note.")])
