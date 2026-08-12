"""SQLAlchemy store for privacy-minimized corpus-build job state."""

from datetime import UTC, datetime
from typing import cast

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from financial_rag.core.errors import (
    CorpusBuildJobNotFoundError,
    CorpusBuildTransitionError,
)
from financial_rag.domain.indexing import (
    CorpusBuildJob,
    CorpusBuildJobId,
    CorpusBuildStatus,
)
from financial_rag.storage.models import CorpusBuildJobRow

logger = structlog.get_logger(__name__)


def _aware(value: datetime | None) -> datetime | None:
    return value if value is None or value.tzinfo is not None else value.replace(tzinfo=UTC)


def _contract(row: CorpusBuildJobRow) -> CorpusBuildJob:
    return CorpusBuildJob(
        job_id=row.job_id,
        status=cast(CorpusBuildStatus, row.status),
        label=row.label,
        input_file_count=row.input_file_count,
        corpus_revision_id=row.corpus_revision_id,
        index_revision_id=row.index_revision_id,
        error_code=row.error_code,
        created_at=cast(datetime, _aware(row.created_at)),
        started_at=_aware(row.started_at),
        completed_at=_aware(row.completed_at),
    )


class PostgresCorpusBuildJobStore:
    """Persist bounded job transitions without retaining input paths or content."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_job(self, job: CorpusBuildJob) -> CorpusBuildJob:
        """Insert one pending job, rejecting identifier reuse."""
        if job.status is not CorpusBuildStatus.PENDING:
            raise CorpusBuildTransitionError("A new corpus-build job must be pending.")
        try:
            async with self._session_factory() as session, session.begin():
                row = CorpusBuildJobRow(
                    job_id=job.job_id,
                    status=job.status.value,
                    label=job.label,
                    input_file_count=job.input_file_count,
                    corpus_revision_id=None,
                    index_revision_id=None,
                    error_code=None,
                    created_at=job.created_at,
                    started_at=None,
                    completed_at=None,
                )
                session.add(row)
                await session.flush()
        except IntegrityError as exc:
            raise CorpusBuildTransitionError("Corpus-build job identifier already exists.") from exc
        logger.info("corpus_build_job_created", job_id=job.job_id)
        return job

    async def mark_running(self, job_id: CorpusBuildJobId) -> CorpusBuildJob:
        """Transition exactly one pending job to running."""
        return await self._transition(job_id, expected=CorpusBuildStatus.PENDING)

    async def mark_completed(
        self,
        job_id: CorpusBuildJobId,
        *,
        corpus_revision_id: str,
        index_revision_id: str,
    ) -> CorpusBuildJob:
        """Finish a running job with both immutable revision identifiers."""
        return await self._transition(
            job_id,
            expected=CorpusBuildStatus.RUNNING,
            completed=True,
            corpus_revision_id=corpus_revision_id,
            index_revision_id=index_revision_id,
        )

    async def mark_failed(self, job_id: CorpusBuildJobId, *, error_code: str) -> CorpusBuildJob:
        """Finish a running job with a safe machine-readable failure code."""
        return await self._transition(
            job_id,
            expected=CorpusBuildStatus.RUNNING,
            completed=False,
            error_code=error_code,
        )

    async def get_job(self, job_id: CorpusBuildJobId) -> CorpusBuildJob:
        """Load one job without any uploaded filename or content."""
        async with self._session_factory() as session:
            row = await session.get(CorpusBuildJobRow, job_id)
            if row is None:
                raise CorpusBuildJobNotFoundError(f"Corpus-build job not found: {job_id}")
            return _contract(row)

    async def list_jobs(self, *, limit: int = 50) -> tuple[CorpusBuildJob, ...]:
        """Return recent jobs in stable newest-first order."""
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        statement = (
            select(CorpusBuildJobRow)
            .order_by(CorpusBuildJobRow.created_at.desc(), CorpusBuildJobRow.job_id.desc())
            .limit(limit)
        )
        async with self._session_factory() as session:
            return tuple(_contract(row) for row in await session.scalars(statement))

    async def fail_interrupted_jobs(self) -> int:
        """Mark non-terminal jobs failed after a local process restart."""
        now = datetime.now(UTC)
        statement = select(CorpusBuildJobRow).where(
            CorpusBuildJobRow.status.in_(("pending", "running"))
        )
        async with self._session_factory() as session, session.begin():
            rows = tuple(await session.scalars(statement.with_for_update()))
            for row in rows:
                row.status = CorpusBuildStatus.FAILED.value
                row.started_at = row.started_at or row.created_at
                row.completed_at = now
                row.error_code = "runtime_interrupted"
        if rows:
            logger.warning("corpus_build_jobs_recovered", failed_count=len(rows))
        return len(rows)

    async def _transition(
        self,
        job_id: CorpusBuildJobId,
        *,
        expected: CorpusBuildStatus,
        completed: bool | None = None,
        corpus_revision_id: str | None = None,
        index_revision_id: str | None = None,
        error_code: str | None = None,
    ) -> CorpusBuildJob:
        now = datetime.now(UTC)
        async with self._session_factory() as session, session.begin():
            statement = (
                select(CorpusBuildJobRow)
                .where(CorpusBuildJobRow.job_id == job_id)
                .with_for_update()
            )
            row = (await session.scalars(statement)).one_or_none()
            if row is None:
                raise CorpusBuildJobNotFoundError(f"Corpus-build job not found: {job_id}")
            if row.status != expected.value:
                raise CorpusBuildTransitionError(
                    f"Corpus-build job cannot transition from {row.status}."
                )
            if expected is CorpusBuildStatus.PENDING:
                row.status = CorpusBuildStatus.RUNNING.value
                row.started_at = now
            elif completed is True:
                row.status = CorpusBuildStatus.COMPLETED.value
                row.completed_at = now
                row.corpus_revision_id = corpus_revision_id
                row.index_revision_id = index_revision_id
            else:
                row.status = CorpusBuildStatus.FAILED.value
                row.completed_at = now
                row.error_code = error_code
            await session.flush()
            return _contract(row)
