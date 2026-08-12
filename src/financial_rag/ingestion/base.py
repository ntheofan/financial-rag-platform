"""Loader contracts used by the deterministic folder-ingestion service."""

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from langchain_core.documents import Document

from financial_rag.domain.metadata import SourceMetadata


class DocumentLoader(Protocol):
    """Port implemented by local file-format adapters."""

    @property
    def supported_extensions(self) -> frozenset[str]:
        """Return lowercase extensions handled by this loader."""
        ...

    def load(self, path: Path, *, metadata: SourceMetadata | None = None) -> list[Document]:
        """Load one local file as normalized LangChain documents."""
        ...


MetadataProvider = Callable[[Path, Path], SourceMetadata]
"""Build metadata from an absolute input path and its relative folder path."""
