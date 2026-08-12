"""Offline validation and staging-boundary tests."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from financial_rag.core.errors import UploadPolicyError
from financial_rag.domain.indexing import (
    CorpusBuildJob,
    CorpusBuildStatus,
    UploadDocument,
    make_corpus_build_job_id,
)
from financial_rag.indexing.staging import UploadPolicy, UploadStagingService


def test_job_identifier_is_opaque_and_deterministic_when_uuid_is_injected() -> None:
    job_id = make_corpus_build_job_id(value=UUID(int=1))

    assert job_id == "job_00000000000000000000000000000001"
    assert "document" not in job_id


def test_completed_job_requires_both_revision_ids() -> None:
    with pytest.raises(ValidationError, match="revision IDs"):
        CorpusBuildJob(
            job_id="job_" + "a" * 32,
            status=CorpusBuildStatus.COMPLETED,
            input_file_count=1,
            created_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )


def test_staging_uses_server_names_and_portable_source_metadata(tmp_path: Path) -> None:
    service = UploadStagingService(tmp_path / "uploads")
    job_id = "job_" + "a" * 32

    batch = service.stage(
        job_id,
        (
            UploadDocument(filename="Annual Report.md", content=b"# Synthetic\n" + b"x" * 300),
            UploadDocument(filename="notes.txt", content=b"synthetic " * 40),
        ),
    )

    assert sorted(path.name for path in batch.folder.iterdir()) == ["01.md", "02.txt"]
    metadata = batch.metadata_provider(batch.folder / "01.md", Path("01.md"))
    assert metadata.source_file == "Annual Report.md"
    service.cleanup(batch)
    assert not batch.folder.exists()


@pytest.mark.parametrize(
    "filename",
    ("../secret.pdf", "folder/file.txt", "folder\\file.md", "unsupported.csv"),
)
def test_staging_rejects_unsafe_or_unsupported_names(tmp_path: Path, filename: str) -> None:
    service = UploadStagingService(tmp_path / "uploads")

    with pytest.raises(UploadPolicyError):
        service.stage(
            "job_" + "b" * 32,
            (UploadDocument(filename=filename, content=b"synthetic"),),
        )


def test_staging_enforces_total_size_before_writing(tmp_path: Path) -> None:
    service = UploadStagingService(
        tmp_path / "uploads",
        policy=UploadPolicy(max_file_bytes=10, max_total_bytes=12),
    )

    with pytest.raises(UploadPolicyError, match="total"):
        service.stage(
            "job_" + "c" * 32,
            (
                UploadDocument(filename="one.txt", content=b"1234567"),
                UploadDocument(filename="two.txt", content=b"1234567"),
            ),
        )

    assert not (tmp_path / "uploads").exists()
