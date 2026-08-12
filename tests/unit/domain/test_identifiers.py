"""Tests for deterministic content and lineage identifiers."""

from financial_rag.domain.identifiers import make_chunk_id, make_document_id


def test_document_identifier_is_content_deterministic() -> None:
    """The same bytes yield the same ID while changed bytes do not."""
    first = make_document_id(b"synthetic filing")

    assert first == make_document_id(b"synthetic filing")
    assert first != make_document_id(b"synthetic filing revised")
    assert first.startswith("doc_")


def test_chunk_identifier_is_lineage_deterministic() -> None:
    """A chunk ID changes when its content or lineage changes."""
    document_id = make_document_id(b"synthetic filing")
    first = make_chunk_id(
        document_id=document_id,
        chunk_index=0,
        page_number=2,
        section_heading="Liquidity",
        content="Synthetic liquidity discussion.",
    )

    assert first == make_chunk_id(
        document_id=document_id,
        chunk_index=0,
        page_number=2,
        section_heading="Liquidity",
        content="Synthetic liquidity discussion.",
    )
    assert first != make_chunk_id(
        document_id=document_id,
        chunk_index=1,
        page_number=2,
        section_heading="Liquidity",
        content="Synthetic liquidity discussion.",
    )
    assert first != make_chunk_id(
        document_id=document_id,
        chunk_index=0,
        page_number=2,
        section_heading="Liquidity",
        content="Changed content.",
    )
    assert first.startswith("chunk_")
