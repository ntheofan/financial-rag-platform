"""Tests for conservative Markdown and text normalization."""

from financial_rag.ingestion.normalization import normalize_document_text


def test_normalization_preserves_headings_and_table_like_content() -> None:
    """Structural Markdown and meaningful internal spacing are not flattened."""
    raw = (
        "# Revenue\r\n\r\n\r\n\r\n"
        "| Segment | 2025 | 2024 |  \r\n"
        "| North   |  42  |  39  |\r\n"
        "Indented   financial detail\u00a0here\r\n"
    )

    normalized = normalize_document_text(raw)

    assert normalized.startswith("# Revenue\n\n")
    assert "| North   |  42  |  39  |" in normalized
    assert "Indented   financial detail here" in normalized
    assert "\n\n\n" not in normalized


def test_normalization_is_idempotent() -> None:
    """Repeated normalization does not continue changing content."""
    text = "## Cash Flow\n\nLine one.\n\nLine two."
    assert normalize_document_text(normalize_document_text(text)) == text
