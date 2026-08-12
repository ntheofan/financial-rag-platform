"""HTTP-only request, health, and error contracts."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from financial_rag.domain.evaluation import BenchmarkDataset, EvaluationConfig
from financial_rag.domain.retrieval import RetrievalMode


class ComponentStatus(StrEnum):
    """Readiness state of an injected application capability."""

    READY = "ready"
    UNAVAILABLE = "unavailable"


class LiveResponse(BaseModel):
    """Process liveness response; it makes no dependency-readiness claim."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str = "ok"
    service: str = "financial-rag-platform"
    version: str


class ReadinessComponents(BaseModel):
    """Availability of API capabilities, not a live network probe."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    retrieval: ComponentStatus
    generation: ComponentStatus
    evaluation: ComponentStatus
    revisions: ComponentStatus
    indexing: ComponentStatus = ComponentStatus.UNAVAILABLE


class ReadyResponse(BaseModel):
    """Readiness response used by local operators and the future demo client."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: ComponentStatus
    components: ReadinessComponents


class RetrievalRequest(BaseModel):
    """One versioned retrieval request with no generation behavior."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [{"query": "What were the capital expenditures?", "mode": "hybrid"}]
        },
    )

    query: str = Field(min_length=1, max_length=4096)
    mode: RetrievalMode = RetrievalMode.HYBRID


class EvaluationRequest(BaseModel):
    """One bounded, synchronous platform_eval_v1 request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset: BenchmarkDataset
    config: EvaluationConfig = EvaluationConfig()


class ErrorDetail(BaseModel):
    """Sanitized validation detail that excludes submitted input values."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    location: tuple[str | int, ...]
    message: str
    error_type: str


class ErrorBody(BaseModel):
    """Stable machine-readable error body."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str
    request_id: str
    details: tuple[ErrorDetail, ...] = ()


class ErrorResponse(BaseModel):
    """Envelope shared by validation, domain, availability, and internal errors."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    error: ErrorBody


def error_responses(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    """Describe the shared error envelope in generated OpenAPI operations."""
    descriptions = {
        400: "Domain request rejected",
        404: "Revision not found",
        409: "Revision compatibility conflict",
        422: "Request validation failed",
        500: "Unexpected internal error",
        502: "Generation provider or grounding validation failed",
        503: "Required capability unavailable",
    }
    return {
        status_code: {
            "model": ErrorResponse,
            "description": descriptions[status_code],
        }
        for status_code in status_codes
    }
