"""Versioned retrieval/revision routes and unversioned health probes."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, Form, Query, Response, UploadFile, status
from starlette.concurrency import run_in_threadpool

from financial_rag import __version__
from financial_rag.api.dependencies import (
    ContainerDependency,
    EvaluationDependency,
    GenerationDependency,
    IndexingDependency,
    RetrievalDependency,
    RevisionDependency,
)
from financial_rag.api.schemas import (
    ComponentStatus,
    EvaluationRequest,
    LiveResponse,
    ReadinessComponents,
    ReadyResponse,
    RetrievalRequest,
    error_responses,
)
from financial_rag.core.errors import UploadPolicyError
from financial_rag.domain.evaluation import EvaluationReport
from financial_rag.domain.generation import GroundedAnswer
from financial_rag.domain.indexing import (
    ActiveIndexSelection,
    CorpusBuildJob,
    CorpusBuildJobId,
    UploadDocument,
)
from financial_rag.domain.retrieval import RetrievalResult
from financial_rag.domain.revisions import (
    CorpusRevision,
    CorpusRevisionId,
    IndexRevision,
    IndexRevisionId,
)

health_router = APIRouter(tags=["health"])
v1_router = APIRouter(prefix="/api/v1", tags=["retrieval"])


@health_router.get("/health/live", response_model=LiveResponse, summary="Process liveness")
async def live() -> LiveResponse:
    """Confirm that the ASGI process can serve requests."""
    return LiveResponse(version=__version__)


@health_router.get(
    "/health/ready",
    response_model=ReadyResponse,
    responses={503: {"model": ReadyResponse, "description": "Retrieval is not configured"}},
    summary="Configured-capability readiness",
)
async def ready(response: Response, container: ContainerDependency) -> ReadyResponse:
    """Report injected capability readiness without connecting to dependencies."""
    retrieval = (
        ComponentStatus.READY if container.retrieval is not None else ComponentStatus.UNAVAILABLE
    )
    revisions = (
        ComponentStatus.READY if container.revisions is not None else ComponentStatus.UNAVAILABLE
    )
    generation = (
        ComponentStatus.READY if container.generation is not None else ComponentStatus.UNAVAILABLE
    )
    evaluation = (
        ComponentStatus.READY if container.evaluation is not None else ComponentStatus.UNAVAILABLE
    )
    indexing = (
        ComponentStatus.READY if container.indexing is not None else ComponentStatus.UNAVAILABLE
    )
    overall = retrieval
    if overall is ComponentStatus.UNAVAILABLE:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadyResponse(
        status=overall,
        components=ReadinessComponents(
            retrieval=retrieval,
            generation=generation,
            evaluation=evaluation,
            revisions=revisions,
            indexing=indexing,
        ),
    )


async def _read_uploads(files: list[UploadFile]) -> tuple[UploadDocument, ...]:
    """Read a bounded multipart batch without retaining client paths."""
    if not files:
        raise UploadPolicyError("At least one document is required.")
    if len(files) > 10:
        raise UploadPolicyError("At most 10 documents are allowed.")
    uploads: list[UploadDocument] = []
    total_bytes = 0
    try:
        for upload in files:
            filename = upload.filename
            if not filename:
                raise UploadPolicyError("Every uploaded document requires a filename.")
            content = bytearray()
            while chunk := await upload.read(64 * 1024):
                content.extend(chunk)
                total_bytes += len(chunk)
                if len(content) > 20 * 1024 * 1024:
                    raise UploadPolicyError("One uploaded document exceeds the 20 MiB limit.")
                if total_bytes > 50 * 1024 * 1024:
                    raise UploadPolicyError("Uploaded documents exceed the 50 MiB total limit.")
            try:
                uploads.append(UploadDocument(filename=filename, content=bytes(content)))
            except ValueError as exc:
                raise UploadPolicyError(
                    "Uploaded document metadata or content is invalid."
                ) from exc
    finally:
        for upload in files:
            await upload.close()
    return tuple(uploads)


@v1_router.post(
    "/corpus-jobs",
    response_model=CorpusBuildJob,
    status_code=status.HTTP_202_ACCEPTED,
    responses=error_responses(400, 409, 422, 500, 503),
    summary="Upload documents and schedule a local corpus build",
    tags=["corpus lifecycle"],
)
async def create_corpus_job(
    background_tasks: BackgroundTasks,
    service: IndexingDependency,
    files: Annotated[list[UploadFile], File(description="Up to 10 PDF, Markdown, or text files")],
    label: Annotated[str | None, Form(max_length=200)] = None,
) -> CorpusBuildJob:
    """Stage a bounded upload and execute it after returning HTTP 202."""
    uploads = await _read_uploads(files)
    job, batch = await service.submit_uploads(uploads, label=label)
    background_tasks.add_task(service.run_staged_job, job.job_id, batch)
    return job


@v1_router.get(
    "/corpus-jobs",
    response_model=tuple[CorpusBuildJob, ...],
    responses=error_responses(422, 500, 503),
    summary="List recent corpus-build jobs",
    tags=["corpus lifecycle"],
)
async def list_corpus_jobs(
    service: IndexingDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> tuple[CorpusBuildJob, ...]:
    return await service.list_jobs(limit=limit)


@v1_router.get(
    "/corpus-jobs/{job_id}",
    response_model=CorpusBuildJob,
    responses=error_responses(404, 422, 500, 503),
    summary="Get one corpus-build job",
    tags=["corpus lifecycle"],
)
async def get_corpus_job(
    job_id: CorpusBuildJobId,
    service: IndexingDependency,
) -> CorpusBuildJob:
    return await service.get_job(job_id)


@v1_router.post(
    "/indexes/{index_revision_id}/activate",
    response_model=ActiveIndexSelection,
    responses=error_responses(404, 409, 422, 500, 503),
    summary="Activate a persisted index for local queries",
    tags=["corpus lifecycle"],
)
async def activate_index(
    index_revision_id: IndexRevisionId,
    service: IndexingDependency,
) -> ActiveIndexSelection:
    return await service.activate_index(index_revision_id)


@v1_router.post(
    "/query",
    response_model=GroundedAnswer,
    responses=error_responses(400, 422, 500, 502, 503),
    summary="Answer from grounded financial-document context",
)
async def answer(payload: RetrievalRequest, service: GenerationDependency) -> GroundedAnswer:
    """Retrieve top contexts and return a citation-validated generated answer."""
    return await run_in_threadpool(service.answer, payload.query, mode=payload.mode)


@v1_router.post(
    "/evaluations/retrieval",
    response_model=EvaluationReport,
    responses=error_responses(400, 422, 500, 503),
    summary="Evaluate paired retrieval modes",
    tags=["evaluation"],
)
async def evaluate_retrieval(
    payload: EvaluationRequest,
    service: EvaluationDependency,
) -> EvaluationReport:
    """Run a bounded synchronous benchmark without persisting source or answer text."""
    return await run_in_threadpool(service.evaluate, payload.dataset, config=payload.config)


@v1_router.post(
    "/retrieval/query",
    response_model=RetrievalResult,
    responses=error_responses(400, 422, 500, 503),
    summary="Retrieve grounded source chunks",
)
async def retrieve(
    payload: RetrievalRequest,
    service: RetrievalDependency,
) -> RetrievalResult:
    """Execute V1, V2, or V3 without answer generation."""
    return await run_in_threadpool(service.retrieve, payload.query, mode=payload.mode)


@v1_router.get(
    "/corpora/{corpus_revision_id}",
    response_model=CorpusRevision,
    responses=error_responses(404, 409, 422, 500, 503),
    summary="Get corpus revision metadata",
)
async def get_corpus_revision(
    corpus_revision_id: CorpusRevisionId,
    revisions: RevisionDependency,
) -> CorpusRevision:
    """Return fingerprints and counts without returning the full stored corpus."""
    return await revisions.get_corpus_revision(corpus_revision_id)


@v1_router.get(
    "/indexes/{index_revision_id}",
    response_model=IndexRevision,
    responses=error_responses(404, 409, 422, 500, 503),
    summary="Get embedding-index revision metadata",
)
async def get_index_revision(
    index_revision_id: IndexRevisionId,
    revisions: RevisionDependency,
) -> IndexRevision:
    """Return index compatibility metadata without returning vectors."""
    return await revisions.get_index_revision(index_revision_id)


@v1_router.get(
    "/corpora",
    response_model=tuple[CorpusRevision, ...],
    responses=error_responses(422, 500, 503),
    summary="List recent corpus revisions",
)
async def list_corpus_revisions(
    revisions: RevisionDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> tuple[CorpusRevision, ...]:
    return await revisions.list_corpus_revisions(limit=limit)


@v1_router.get(
    "/indexes",
    response_model=tuple[IndexRevision, ...],
    responses=error_responses(422, 500, 503),
    summary="List recent embedding-index revisions",
)
async def list_index_revisions(
    revisions: RevisionDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> tuple[IndexRevision, ...]:
    return await revisions.list_index_revisions(limit=limit)
