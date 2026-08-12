"""API exception mapping that keeps internal details out of responses."""

from collections.abc import Sequence

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from financial_rag.api.middleware import safe_route_path
from financial_rag.api.schemas import ErrorBody, ErrorDetail, ErrorResponse
from financial_rag.core.errors import (
    CitationValidationError,
    CorpusBuildJobNotFoundError,
    CorpusBuildTransitionError,
    FinancialRAGError,
    GenerationProviderError,
    ProviderUnavailableError,
    RerankerRequiredError,
    RetrievalArtifactError,
    RevisionCompatibilityError,
    RevisionConflictError,
    RevisionNotFoundError,
    StorageConfigurationError,
    UploadPolicyError,
)

logger = structlog.get_logger(__name__)


class ApiServiceUnavailableError(Exception):
    """Raised when a route's optional injected service is not configured."""


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "unknown"))


def _response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: Sequence[ErrorDetail] = (),
) -> JSONResponse:
    request_id = _request_id(request)
    payload = ErrorResponse(
        error=ErrorBody(
            code=code,
            message=message,
            request_id=request_id,
            details=tuple(details),
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
        headers={"X-Request-ID": request_id},
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return field locations without echoing submitted document/query content."""
    details = tuple(
        ErrorDetail(
            location=tuple(part for part in error["loc"] if isinstance(part, (str, int))),
            message=str(error["msg"]),
            error_type=str(error["type"]),
        )
        for error in exc.errors()
    )
    return _response(
        request,
        status_code=422,
        code="request_validation_failed",
        message="The request did not match the API contract.",
        details=details,
    )


async def unavailable_error_handler(
    request: Request, _exc: ApiServiceUnavailableError
) -> JSONResponse:
    """Report configuration availability without exposing local configuration."""
    return _response(
        request,
        status_code=503,
        code="service_unavailable",
        message="The requested capability is not configured.",
    )


async def domain_error_handler(request: Request, exc: FinancialRAGError) -> JSONResponse:
    """Map expected domain failures into stable HTTP semantics."""
    if isinstance(exc, RevisionNotFoundError):
        return _response(request, status_code=404, code="revision_not_found", message=str(exc))
    if isinstance(exc, CorpusBuildJobNotFoundError):
        return _response(request, status_code=404, code="job_not_found", message=str(exc))
    if isinstance(exc, CorpusBuildTransitionError):
        return _response(request, status_code=409, code="job_conflict", message=str(exc))
    if isinstance(exc, (RevisionConflictError, RevisionCompatibilityError)):
        return _response(request, status_code=409, code="revision_conflict", message=str(exc))
    if isinstance(exc, (CitationValidationError, GenerationProviderError)):
        return _response(
            request,
            status_code=502,
            code="generation_failed",
            message="The generated answer could not be validated safely.",
        )
    if isinstance(exc, UploadPolicyError):
        return _response(request, status_code=400, code="upload_rejected", message=str(exc))
    if isinstance(
        exc,
        (
            ProviderUnavailableError,
            RetrievalArtifactError,
            StorageConfigurationError,
            RerankerRequiredError,
        ),
    ):
        return _response(
            request,
            status_code=503,
            code="dependency_unavailable",
            message="A required local dependency is unavailable.",
        )
    return _response(request, status_code=400, code="domain_error", message=str(exc))


async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log an unexpected exception type and return a non-sensitive response."""
    logger.exception(
        "api_unhandled_error",
        request_id=_request_id(request),
        method=request.method,
        path=safe_route_path(request),
        exception_type=type(exc).__name__,
    )
    return _response(
        request,
        status_code=500,
        code="internal_error",
        message="An unexpected internal error occurred.",
    )


def install_exception_handlers(app: FastAPI) -> None:
    """Install all mappings in one visible application-factory step."""
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(ApiServiceUnavailableError, unavailable_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(FinancialRAGError, domain_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, internal_error_handler)
