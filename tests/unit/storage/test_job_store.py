"""Transactional job-state tests over test-only SQLite."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from pgvector.sqlalchemy import VECTOR
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from financial_rag.core.errors import CorpusBuildJobNotFoundError, CorpusBuildTransitionError
from financial_rag.domain.indexing import CorpusBuildJob, CorpusBuildStatus
from financial_rag.storage.job_store import PostgresCorpusBuildJobStore
from financial_rag.storage.models import Base


@compiles(VECTOR, "sqlite")
def _compile_vector_for_test(_type: VECTOR, _compiler: object, **_kwargs: object) -> str:
    return "TEXT"


@pytest_asyncio.fixture
async def job_store() -> AsyncIterator[PostgresCorpusBuildJobStore]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        yield PostgresCorpusBuildJobStore(factory)
    finally:
        await engine.dispose()


def _pending(suffix: str = "a") -> CorpusBuildJob:
    return CorpusBuildJob(
        job_id="job_" + suffix * 32,
        status=CorpusBuildStatus.PENDING,
        label="synthetic",
        input_file_count=2,
        created_at=datetime(2026, 8, 12, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_job_state_round_trip_and_ordering(job_store: PostgresCorpusBuildJobStore) -> None:
    created = await job_store.create_job(_pending())
    running = await job_store.mark_running(created.job_id)
    completed = await job_store.mark_completed(
        created.job_id,
        corpus_revision_id="corpus_" + "c" * 32,
        index_revision_id="index_" + "d" * 32,
    )

    assert running.status is CorpusBuildStatus.RUNNING
    assert completed.status is CorpusBuildStatus.COMPLETED
    assert await job_store.get_job(created.job_id) == completed
    assert await job_store.list_jobs() == (completed,)


@pytest.mark.asyncio
async def test_invalid_transition_is_rejected(job_store: PostgresCorpusBuildJobStore) -> None:
    created = await job_store.create_job(_pending())

    with pytest.raises(CorpusBuildTransitionError, match="cannot transition"):
        await job_store.mark_completed(
            created.job_id,
            corpus_revision_id="corpus_" + "c" * 32,
            index_revision_id="index_" + "d" * 32,
        )


@pytest.mark.asyncio
async def test_missing_job_is_explicit(job_store: PostgresCorpusBuildJobStore) -> None:
    with pytest.raises(CorpusBuildJobNotFoundError, match="not found"):
        await job_store.get_job("job_" + "e" * 32)


@pytest.mark.asyncio
async def test_restart_marks_pending_and_running_jobs_failed(
    job_store: PostgresCorpusBuildJobStore,
) -> None:
    pending = await job_store.create_job(_pending("a"))
    running = await job_store.create_job(_pending("b"))
    await job_store.mark_running(running.job_id)

    count = await job_store.fail_interrupted_jobs()

    assert count == 2
    assert (await job_store.get_job(pending.job_id)).error_code == "runtime_interrupted"
    assert (await job_store.get_job(running.job_id)).status is CorpusBuildStatus.FAILED
