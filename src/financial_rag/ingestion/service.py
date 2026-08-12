"""Deterministic local folder-ingestion orchestration."""

from collections.abc import Iterable
from pathlib import Path

import structlog
from langchain_core.documents import Document

from financial_rag.core.errors import (
    EmptyInputError,
    InputFolderError,
    UnsupportedDocumentTypeError,
)
from financial_rag.domain.metadata import SourceMetadata
from financial_rag.ingestion.base import DocumentLoader, MetadataProvider
from financial_rag.ingestion.loaders import PyMuPDFLoader, TextMarkdownLoader

logger = structlog.get_logger(__name__)


def default_metadata_provider(_path: Path, relative_path: Path) -> SourceMetadata:
    """Create portable source metadata from a folder-relative path."""
    return SourceMetadata(source_file=relative_path.as_posix())


class FolderIngestionService:
    """Load a folder in stable relative-path order through injected adapters."""

    def __init__(
        self,
        loaders: Iterable[DocumentLoader] | None = None,
        *,
        fail_on_unsupported: bool = True,
    ) -> None:
        selected_loaders = tuple(loaders or (TextMarkdownLoader(), PyMuPDFLoader()))
        registry: dict[str, DocumentLoader] = {}
        for loader in selected_loaders:
            for extension in loader.supported_extensions:
                normalized_extension = extension.lower()
                if normalized_extension in registry:
                    raise ValueError(f"Duplicate loader registration for {normalized_extension}")
                registry[normalized_extension] = loader

        if not registry:
            raise ValueError("At least one document loader must be registered")
        self._registry = registry
        self._fail_on_unsupported = fail_on_unsupported

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        """Return all registered extensions in deterministic order."""
        return tuple(sorted(self._registry))

    def ingest_folder(
        self,
        folder: Path,
        *,
        recursive: bool = True,
        metadata_provider: MetadataProvider = default_metadata_provider,
    ) -> list[Document]:
        """Ingest supported files from a folder with explicit failure semantics."""
        if not folder.exists():
            raise InputFolderError(f"Input folder does not exist: {folder}")
        if not folder.is_dir():
            raise InputFolderError(f"Input path is not a folder: {folder}")

        candidates = folder.rglob("*") if recursive else folder.glob("*")
        files = [path for path in candidates if path.is_file()]
        files.sort(key=lambda path: (path.relative_to(folder).as_posix().casefold(), path.name))
        if not files:
            raise EmptyInputError(f"Input folder contains no files: {folder.name}")

        unsupported = [path for path in files if path.suffix.lower() not in self._registry]
        if unsupported and self._fail_on_unsupported:
            raise UnsupportedDocumentTypeError(unsupported[0], self.supported_extensions)

        supported = [path for path in files if path.suffix.lower() in self._registry]
        if not supported:
            raise EmptyInputError(f"Input folder contains no supported documents: {folder.name}")

        logger.info(
            "folder_ingestion_started",
            folder_name=folder.name,
            supported_file_count=len(supported),
        )
        documents: list[Document] = []
        for path in supported:
            relative_path = path.relative_to(folder)
            metadata = metadata_provider(path, relative_path)
            loader = self._registry[path.suffix.lower()]
            documents.extend(loader.load(path, metadata=metadata))

        logger.info(
            "folder_ingestion_completed",
            folder_name=folder.name,
            langchain_document_count=len(documents),
        )
        return documents
