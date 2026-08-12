"""Synthetic multipart, job-status, and index-activation API tests."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from financial_rag.api import ApiContainer, create_app
from financial_rag.domain.indexing import (
    ActiveIndexSelection,
    CorpusBuildJob,
    CorpusBuildJobId,
    CorpusBuildStatus,
    UploadDocument,
)
from financial_rag.indexing.staging import StagedUploadBatch
from tests.api.client import api_client

JOB_ID = "job_" + "a" * 32
CORPUS_ID = "corpus_" + "b" * 32
INDEX_ID = "index_" + "c" * 32
NOW = datetime(2026, 8, 12, tzinfo=UTC)


class FakeIndexingService:
    def __init__(self) -> None:
        self.uploads: tuple[UploadDocument, ...] = ()
        self.job = CorpusBuildJob(
            job_id=JOB_ID,
            status=CorpusBuildStatus.PENDING,
            label="synthetic",
            input_file_count=1,
            created_at=NOW,
        )

    async def submit_uploads(
        self,
        uploads: tuple[UploadDocument, ...],
        *,
        label: str | None = None,
    ) -> tuple[CorpusBuildJob, StagedUploadBatch]:
        self.uploads = uploads
        self.job = self.job.model_copy(update={"label": label, "input_file_count": len(uploads)})
        return self.job, StagedUploadBatch(
            job_id=JOB_ID,
            folder=Path("synthetic-staging"),
            source_names=(),
        )

    async def run_staged_job(self, job_id: CorpusBuildJobId, _batch: StagedUploadBatch) -> None:
        assert job_id == JOB_ID

    async def get_job(self, job_id: CorpusBuildJobId) -> CorpusBuildJob:
        assert job_id == JOB_ID
        return self.job

    async def list_jobs(self, *, limit: int = 50) -> tuple[CorpusBuildJob, ...]:
        del limit
        return (self.job,)

    async def activate_index(self, index_revision_id: str) -> ActiveIndexSelection:
        return ActiveIndexSelection(
            corpus_revision_id=CORPUS_ID,
            index_revision_id=index_revision_id,
            activated_at=NOW,
        )


@pytest.mark.asyncio
async def test_multipart_upload_returns_privacy_minimized_pending_job() -> None:
    service = FakeIndexingService()
    app = create_app(container=ApiContainer(indexing=service))
    async with api_client(app) as client:
        response = await client.post(
            "/api/v1/corpus-jobs",
            files={"files": ("synthetic.md", b"# Synthetic\nEvidence", "text/markdown")},
            data={"label": "Recruiter demo"},
        )

    assert response.status_code == 202
    assert response.json()["status"] == "pending"
    assert response.json()["label"] == "Recruiter demo"
    assert "filename" not in response.text
    assert service.uploads[0].filename == "synthetic.md"


@pytest.mark.asyncio
async def test_upload_count_is_bounded_before_service_submission() -> None:
    service = FakeIndexingService()
    app = create_app(container=ApiContainer(indexing=service))
    files = [("files", (f"{index}.txt", b"x", "text/plain")) for index in range(11)]
    async with api_client(app) as client:
        response = await client.post("/api/v1/corpus-jobs", files=files)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "upload_rejected"
    assert service.uploads == ()


@pytest.mark.asyncio
async def test_empty_uploaded_file_is_rejected_without_echoing_content() -> None:
    service = FakeIndexingService()
    app = create_app(container=ApiContainer(indexing=service))
    async with api_client(app) as client:
        response = await client.post(
            "/api/v1/corpus-jobs",
            files={"files": ("empty.txt", b"", "text/plain")},
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "upload_rejected"
    assert "empty.txt" not in response.text


@pytest.mark.asyncio
async def test_job_list_get_and_activation_contracts() -> None:
    service = FakeIndexingService()
    app = create_app(container=ApiContainer(indexing=service))
    async with api_client(app) as client:
        jobs = await client.get("/api/v1/corpus-jobs")
        job = await client.get(f"/api/v1/corpus-jobs/{JOB_ID}")
        activated = await client.post(f"/api/v1/indexes/{INDEX_ID}/activate")

    assert jobs.status_code == 200
    assert jobs.json()[0]["job_id"] == JOB_ID
    assert job.status_code == 200
    assert activated.status_code == 200
    assert activated.json()["index_revision_id"] == INDEX_ID


@pytest.mark.asyncio
async def test_upload_route_is_unavailable_without_database_composition() -> None:
    async with api_client(create_app()) as client:
        response = await client.post(
            "/api/v1/corpus-jobs",
            files={"files": ("synthetic.txt", b"evidence", "text/plain")},
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"
