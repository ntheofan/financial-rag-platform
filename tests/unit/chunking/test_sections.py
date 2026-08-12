"""Tests for Markdown section-heading lineage."""

from financial_rag.chunking.sections import extract_section_heading, section_heading_at


def test_extract_section_heading_returns_first_markdown_heading() -> None:
    """Hash prefixes are excluded from stored section labels."""
    text = "Preamble\n\n## Management Discussion\nDetails"
    assert extract_section_heading(text) == "Management Discussion"


def test_section_heading_at_tracks_nearest_preceding_heading() -> None:
    """Offsets after a new heading inherit the new section label."""
    text = "# Overview\nAlpha\n\n## Liquidity\nCash discussion"

    assert section_heading_at(text, text.index("Alpha")) == "Overview"
    assert section_heading_at(text, text.index("Cash")) == "Liquidity"
    assert section_heading_at(text, 0, default="Cover") == "Overview"


def test_heading_extraction_returns_none_for_plain_text() -> None:
    """Plain text does not receive an invented section label."""
    assert extract_section_heading("No Markdown heading here") is None
