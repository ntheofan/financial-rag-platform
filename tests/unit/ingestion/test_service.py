"""Tests for deterministic folder ingestion and loader injection."""

from pathlib import Path

import pytest

from financial_rag.core.errors import (
    EmptyInputError,
    InputFolderError,
    UnsupportedDocumentTypeError,
)
from financial_rag.domain.metadata import DocumentMetadata, SourceMetadata
from financial_rag.ingestion.service import FolderIngestionService


def test_folder_ingestion_uses_deterministic_relative_path_order(tmp_path: Path) -> None:
    """Filesystem enumeration order cannot change output document ordering."""
    nested = tmp_path / "nested"
    nested.mkdir()
    (tmp_path / "b.txt").write_text("Second synthetic document.", encoding="utf-8")
    (tmp_path / "A.md").write_text("First synthetic document.", encoding="utf-8")
    (nested / "c.md").write_text("Third synthetic document.", encoding="utf-8")

    documents = FolderIngestionService().ingest_folder(tmp_path)
    sources = [
        DocumentMetadata.model_validate(document.metadata).source_file for document in documents
    ]

    assert sources == ["A.md", "b.txt", "nested/c.md"]


def test_folder_ingestion_accepts_metadata_provider_injection(tmp_path: Path) -> None:
    """Caller-owned filing metadata is propagated without coupling to a dataset."""
    (tmp_path / "report.md").write_text("Synthetic filing content.", encoding="utf-8")

    def metadata_provider(_path: Path, relative_path: Path) -> SourceMetadata:
        return SourceMetadata(
            source_file=relative_path.as_posix(),
            company="Synthetic Holdings",
            filing_type="10-K",
        )

    document = FolderIngestionService().ingest_folder(
        tmp_path, metadata_provider=metadata_provider
    )[0]
    metadata = DocumentMetadata.model_validate(document.metadata)

    assert metadata.company == "Synthetic Holdings"
    assert metadata.filing_type == "10-K"


def test_folder_ingestion_fails_on_unsupported_file_by_default(tmp_path: Path) -> None:
    """Unknown file formats are explicit failures rather than silent skips."""
    (tmp_path / "notes.csv").write_text("synthetic", encoding="utf-8")

    with pytest.raises(UnsupportedDocumentTypeError, match=r"\.csv"):
        FolderIngestionService().ingest_folder(tmp_path)


def test_folder_ingestion_can_explicitly_skip_unsupported_files(tmp_path: Path) -> None:
    """Opt-in skip behavior still returns only registered formats."""
    (tmp_path / "notes.csv").write_text("synthetic", encoding="utf-8")
    (tmp_path / "report.md").write_text("Synthetic report.", encoding="utf-8")

    documents = FolderIngestionService(fail_on_unsupported=False).ingest_folder(tmp_path)

    assert len(documents) == 1
    assert documents[0].metadata["source_file"] == "report.md"


def test_folder_ingestion_rejects_missing_and_empty_folders(tmp_path: Path) -> None:
    """Folder validation provides clear failures for absent and empty inputs."""
    with pytest.raises(InputFolderError, match="does not exist"):
        FolderIngestionService().ingest_folder(tmp_path / "missing")
    with pytest.raises(EmptyInputError, match="contains no files"):
        FolderIngestionService().ingest_folder(tmp_path)
