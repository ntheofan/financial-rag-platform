"""Deterministic Markdown-aware chunking."""

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from financial_rag.chunking.sections import extract_section_heading, section_heading_at
    from financial_rag.chunking.service import MarkdownChunker

__all__ = ["MarkdownChunker", "extract_section_heading", "section_heading_at"]


def __getattr__(name: str) -> Any:
    """Avoid importing the text-splitter stack for section-only consumers."""
    modules = {
        "MarkdownChunker": "financial_rag.chunking.service",
        "extract_section_heading": "financial_rag.chunking.sections",
        "section_heading_at": "financial_rag.chunking.sections",
    }
    if name not in modules:
        raise AttributeError(name)
    return getattr(import_module(modules[name]), name)
