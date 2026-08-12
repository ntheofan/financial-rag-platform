"""Typed synchronous client for the local FastAPI demo boundary."""

from typing import Any, Self

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from financial_rag.api.schemas import (
    ErrorResponse,
    EvaluationRequest,
    ReadyResponse,
    RetrievalRequest,
)
from financial_rag.demo.settings import DemoSettings
from financial_rag.domain.evaluation import BenchmarkDataset, EvaluationConfig, EvaluationReport
from financial_rag.domain.generation import GroundedAnswer
from financial_rag.domain.indexing import ActiveIndexSelection, CorpusBuildJob, UploadDocument
from financial_rag.domain.retrieval import RetrievalMode, RetrievalResult
from financial_rag.domain.revisions import CorpusRevision, IndexRevision


class DemoApiError(Exception):
    """Safe error suitable for display by the local demo client."""

    def __init__(self, message: str, *, code: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class ComparisonFailure(BaseModel):
    """Sanitized per-mode failure that permits a useful partial comparison."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    status_code: int | None = None


class ModeComparisonItem(BaseModel):
    """Exactly one successful result or safe failure for one retrieval mode."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: RetrievalMode
    result: RetrievalResult | None = None
    failure: ComparisonFailure | None = None

    @model_validator(mode="after")
    def exactly_one_outcome(self) -> Self:
        if (self.result is None) == (self.failure is None):
            raise ValueError("comparison item requires exactly one result or failure")
        if self.result is not None and self.result.mode is not self.mode:
            raise ValueError("comparison result mode does not match its requested mode")
        return self


class ModeComparison(BaseModel):
    """Paired result set for one query across all controlled retrieval modes."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    query: str = Field(min_length=1)
    items: tuple[ModeComparisonItem, ...] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def contains_each_mode_once(self) -> Self:
        modes = [item.mode for item in self.items]
        if modes != list(RetrievalMode):
            raise ValueError("comparison must preserve dense, hybrid, reranked order")
        return self


class FinancialRagApiClient:
    """Consume only public HTTP contracts; it has no DB, model, or key access."""

    def __init__(
        self,
        settings: DemoSettings | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        verify: bool = True,
    ) -> None:
        self._settings = settings or DemoSettings()
        self._transport = transport
        self._verify = verify

    def readiness(self) -> ReadyResponse:
        """Read capability status, accepting HTTP 503 as a valid readiness payload."""
        response = self._request("GET", "/health/ready")
        if response.status_code not in {200, 503}:
            self._raise_api_error(response)
        return self._validate_response(response, ReadyResponse)

    def answer(self, query: str, *, mode: RetrievalMode) -> GroundedAnswer:
        """Request one grounded answer from the versioned API."""
        payload = RetrievalRequest(query=query, mode=mode)
        response = self._request(
            "POST",
            "/api/v1/query",
            json=payload.model_dump(mode="json"),
        )
        if response.is_error:
            self._raise_api_error(response)
        return self._validate_response(response, GroundedAnswer)

    def retrieve(self, query: str, *, mode: RetrievalMode) -> RetrievalResult:
        """Request a transparent retrieval trace for one controlled mode."""
        payload = RetrievalRequest(query=query, mode=mode)
        response = self._request(
            "POST",
            "/api/v1/retrieval/query",
            json=payload.model_dump(mode="json"),
        )
        if response.is_error:
            self._raise_api_error(response)
        return self._validate_response(response, RetrievalResult)

    def compare_retrieval(self, query: str) -> ModeComparison:
        """Run the identical query across all modes and retain partial failures."""
        normalized_query = RetrievalRequest(query=query).query
        items: list[ModeComparisonItem] = []
        for mode in RetrievalMode:
            try:
                result = self.retrieve(normalized_query, mode=mode)
                items.append(ModeComparisonItem(mode=mode, result=result))
            except DemoApiError as exc:
                items.append(
                    ModeComparisonItem(
                        mode=mode,
                        failure=ComparisonFailure(
                            code=exc.code,
                            message=str(exc),
                            status_code=exc.status_code,
                        ),
                    )
                )
        return ModeComparison(query=normalized_query, items=tuple(items))

    def evaluate(
        self,
        dataset: BenchmarkDataset,
        *,
        config: EvaluationConfig | None = None,
    ) -> EvaluationReport:
        """Run a bounded paired benchmark through the FastAPI evaluation endpoint."""
        payload = EvaluationRequest(dataset=dataset, config=config or EvaluationConfig())
        response = self._request(
            "POST",
            "/api/v1/evaluations/retrieval",
            json=payload.model_dump(mode="json"),
        )
        if response.is_error:
            self._raise_api_error(response)
        return self._validate_response(response, EvaluationReport)

    def upload_documents(
        self,
        documents: tuple[UploadDocument, ...],
        *,
        label: str | None = None,
    ) -> CorpusBuildJob:
        """Submit one bounded multipart batch to the FastAPI lifecycle boundary."""
        files = [
            ("files", (document.filename, document.content, "application/octet-stream"))
            for document in documents
        ]
        response = self._request(
            "POST",
            "/api/v1/corpus-jobs",
            files=files,
            data={"label": label} if label is not None else None,
        )
        if response.is_error:
            self._raise_api_error(response)
        return self._validate_response(response, CorpusBuildJob)

    def list_corpus_jobs(self, *, limit: int = 50) -> tuple[CorpusBuildJob, ...]:
        """List privacy-minimized local build status records."""
        response = self._request("GET", f"/api/v1/corpus-jobs?limit={limit}")
        if response.is_error:
            self._raise_api_error(response)
        return self._validate_model_list(response, CorpusBuildJob)

    def list_corpus_revisions(self, *, limit: int = 50) -> tuple[CorpusRevision, ...]:
        response = self._request("GET", f"/api/v1/corpora?limit={limit}")
        if response.is_error:
            self._raise_api_error(response)
        return self._validate_model_list(response, CorpusRevision)

    def list_index_revisions(self, *, limit: int = 50) -> tuple[IndexRevision, ...]:
        response = self._request("GET", f"/api/v1/indexes?limit={limit}")
        if response.is_error:
            self._raise_api_error(response)
        return self._validate_model_list(response, IndexRevision)

    def activate_index(self, index_revision_id: str) -> ActiveIndexSelection:
        response = self._request("POST", f"/api/v1/indexes/{index_revision_id}/activate")
        if response.is_error:
            self._raise_api_error(response)
        return self._validate_response(response, ActiveIndexSelection)

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: object | None = None,
        files: Any | None = None,
        data: dict[str, str | None] | None = None,
    ) -> httpx.Response:
        try:
            with httpx.Client(
                base_url=self._settings.financial_rag_api_url,
                timeout=self._settings.demo_request_timeout_seconds,
                transport=self._transport,
                verify=self._verify,
                headers={"User-Agent": "financial-rag-streamlit/0.1"},
            ) as client:
                return client.request(method, path, json=json, files=files, data=data)
        except httpx.RequestError as exc:
            raise DemoApiError(
                "Cannot reach the local Financial RAG API.",
                code="api_unreachable",
            ) from exc

    @staticmethod
    def _raise_api_error(response: httpx.Response) -> None:
        try:
            error = ErrorResponse.model_validate(response.json()).error
        except (ValueError, TypeError) as exc:
            raise DemoApiError(
                "The API returned an unexpected error response.",
                code="invalid_error_response",
                status_code=response.status_code,
            ) from exc
        raise DemoApiError(
            error.message,
            code=error.code,
            status_code=response.status_code,
        )

    @staticmethod
    def _validate_response[ResponseModel: BaseModel](
        response: httpx.Response,
        model: type[ResponseModel],
    ) -> ResponseModel:
        try:
            return model.model_validate(response.json())
        except (ValueError, TypeError) as exc:
            raise DemoApiError(
                "The API response did not match the expected contract.",
                code="invalid_api_response",
                status_code=response.status_code,
            ) from exc

    @staticmethod
    def _validate_model_list[ResponseModel: BaseModel](
        response: httpx.Response,
        model: type[ResponseModel],
    ) -> tuple[ResponseModel, ...]:
        try:
            payload = response.json()
            if not isinstance(payload, list):
                raise TypeError
            return tuple(model.model_validate(item) for item in payload)
        except (ValueError, TypeError) as exc:
            raise DemoApiError(
                "The API response did not match the expected contract.",
                code="invalid_api_response",
                status_code=response.status_code,
            ) from exc
