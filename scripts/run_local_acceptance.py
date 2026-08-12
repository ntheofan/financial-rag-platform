"""Run the full local API acceptance flow with the checked-in synthetic fixture."""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Literal, Protocol, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from financial_rag.api.schemas import ComponentStatus, ReadyResponse
from financial_rag.demo.client import (
    DemoApiError,
    FinancialRagApiClient,
    ModeComparison,
)
from financial_rag.demo.settings import DemoSettings
from financial_rag.domain.evaluation import (
    BenchmarkDataset,
    BenchmarkItem,
    EvaluationConfig,
    EvaluationReport,
    EvaluationStatus,
)
from financial_rag.domain.generation import GroundedAnswer
from financial_rag.domain.indexing import CorpusBuildJob, CorpusBuildStatus, UploadDocument
from financial_rag.domain.retrieval import RetrievalMode

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "release" / "local_acceptance_v1.json"
SYNTHETIC_FIXTURE_ROOT = (PROJECT_ROOT / "tests" / "fixtures" / "demo").resolve()


class AcceptanceError(Exception):
    """Safe, content-free local acceptance failure."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class AcceptanceConfig(BaseModel):
    """Versioned, non-secret configuration for one local acceptance run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["local_acceptance_v1"] = "local_acceptance_v1"
    api_url: str
    fixture_path: Path
    fixture_label: str = Field(min_length=1, max_length=200)
    query: str = Field(min_length=1, max_length=4096)
    request_timeout_seconds: float = Field(gt=0, le=300)
    job_timeout_seconds: float = Field(gt=0, le=3600)
    poll_interval_seconds: float = Field(gt=0, le=30)

    @field_validator("api_url")
    @classmethod
    def api_must_be_loopback(cls, value: str) -> str:
        return validate_loopback_url(value)

    @classmethod
    def from_json_file(cls, path: Path) -> Self:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return cls.model_validate(payload)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise AcceptanceError("invalid_acceptance_config") from exc

    def fixture(self, root: Path = PROJECT_ROOT) -> Path:
        candidate = self.fixture_path
        resolved = (candidate if candidate.is_absolute() else root / candidate).resolve()
        if resolved.parent != SYNTHETIC_FIXTURE_ROOT or resolved.suffix.lower() not in {
            ".md",
            ".txt",
        }:
            raise AcceptanceError("fixture_outside_synthetic_boundary")
        return resolved


class AcceptanceApi(Protocol):
    """Existing tested API-client surface used by the acceptance orchestrator."""

    def readiness(self) -> ReadyResponse: ...

    def upload_documents(
        self,
        documents: tuple[UploadDocument, ...],
        *,
        label: str | None = None,
    ) -> CorpusBuildJob: ...

    def list_corpus_jobs(self, *, limit: int = 50) -> tuple[CorpusBuildJob, ...]: ...

    def compare_retrieval(self, query: str) -> ModeComparison: ...

    def answer(self, query: str, *, mode: RetrievalMode) -> GroundedAnswer: ...

    def evaluate(
        self,
        dataset: BenchmarkDataset,
        *,
        config: EvaluationConfig | None = None,
    ) -> EvaluationReport: ...


class AcceptanceSummary(BaseModel):
    """Privacy-minimized stdout contract; it contains no source or answer text."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["local_acceptance_result_v1"] = "local_acceptance_result_v1"
    status: Literal["passed"] = "passed"
    job_id: str
    corpus_revision_id: str
    index_revision_id: str
    dense_chunk_count: int = Field(gt=0)
    hybrid_chunk_count: int = Field(gt=0)
    reranked_chunk_count: int = Field(gt=0)
    citation_count: int = Field(gt=0, le=5)
    evaluation_completed_modes: tuple[RetrievalMode, ...]


def validate_loopback_url(value: str) -> str:
    """Reject credentials and non-loopback upload targets."""
    normalized = value.strip().rstrip("/")
    parsed = urlsplit(normalized)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1", "localhost"}:
        raise ValueError("Acceptance API URL must use HTTP on loopback.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path:
        raise ValueError("Acceptance API URL cannot contain credentials, path, query, or fragment.")
    return normalized


def _require_components(readiness: ReadyResponse, names: tuple[str, ...]) -> None:
    values = readiness.components.model_dump(mode="json")
    if any(values[name] != ComponentStatus.READY.value for name in names):
        raise AcceptanceError("required_component_unavailable")


def _wait_for_job(
    client: AcceptanceApi,
    submitted: CorpusBuildJob,
    *,
    timeout_seconds: float,
    poll_interval_seconds: float,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> CorpusBuildJob:
    deadline = monotonic() + timeout_seconds
    while True:
        current = next(
            (job for job in client.list_corpus_jobs(limit=100) if job.job_id == submitted.job_id),
            None,
        )
        if current is not None and current.status is CorpusBuildStatus.COMPLETED:
            return current
        if current is not None and current.status is CorpusBuildStatus.FAILED:
            raise AcceptanceError(current.error_code or "corpus_build_failed")
        if monotonic() >= deadline:
            raise AcceptanceError("corpus_build_timeout")
        sleep(poll_interval_seconds)


def run_acceptance(
    client: AcceptanceApi,
    config: AcceptanceConfig,
    *,
    root: Path = PROJECT_ROOT,
) -> AcceptanceSummary:
    """Execute the bounded real-service acceptance sequence."""
    _require_components(client.readiness(), ("revisions", "indexing"))
    fixture = config.fixture(root)
    try:
        content = fixture.read_bytes()
    except OSError as exc:
        raise AcceptanceError("synthetic_fixture_unreadable") from exc
    submitted = client.upload_documents(
        (UploadDocument(filename=fixture.name, content=content),),
        label=config.fixture_label,
    )
    completed = _wait_for_job(
        client,
        submitted,
        timeout_seconds=config.job_timeout_seconds,
        poll_interval_seconds=config.poll_interval_seconds,
    )
    if completed.corpus_revision_id is None or completed.index_revision_id is None:
        raise AcceptanceError("completed_job_missing_revisions")

    _require_components(
        client.readiness(),
        ("retrieval", "generation", "evaluation", "revisions", "indexing"),
    )
    comparison = client.compare_retrieval(config.query)
    counts: dict[RetrievalMode, int] = {}
    relevant_chunk_id: str | None = None
    for item in comparison.items:
        if item.failure is not None or item.result is None or not item.result.chunks:
            raise AcceptanceError("retrieval_mode_failed")
        if Path(item.result.chunks[0].source_file).name != fixture.name:
            raise AcceptanceError("retrieval_lineage_mismatch")
        counts[item.mode] = len(item.result.chunks)
        if item.mode is RetrievalMode.DENSE:
            relevant_chunk_id = item.result.chunks[0].chunk_id
    if relevant_chunk_id is None:
        raise AcceptanceError("dense_result_missing")

    answer = client.answer(config.query, mode=RetrievalMode.HYBRID_RERANKED)
    if answer.abstained or not answer.citations:
        raise AcceptanceError("grounded_answer_missing")
    if any(Path(citation.source_file).name != fixture.name for citation in answer.citations):
        raise AcceptanceError("citation_lineage_mismatch")

    dataset = BenchmarkDataset(
        dataset_id="synthetic-local-acceptance",
        items=(
            BenchmarkItem(
                query_id="synthetic-acceptance-q1",
                query=config.query,
                relevant_chunk_ids=(relevant_chunk_id,),
            ),
        ),
    )
    report = client.evaluate(dataset, config=EvaluationConfig(include_answer_metrics=False))
    completed_modes = tuple(
        aggregate.mode
        for aggregate in report.aggregates
        if aggregate.retrieval_completed == report.manifest.query_count
        and aggregate.retrieval_failed == 0
    )
    if completed_modes != tuple(RetrievalMode) or any(
        item.retrieval_status is not EvaluationStatus.COMPLETED for item in report.items
    ):
        raise AcceptanceError("paired_evaluation_incomplete")

    return AcceptanceSummary(
        job_id=completed.job_id,
        corpus_revision_id=completed.corpus_revision_id,
        index_revision_id=completed.index_revision_id,
        dense_chunk_count=counts[RetrievalMode.DENSE],
        hybrid_chunk_count=counts[RetrievalMode.HYBRID],
        reranked_chunk_count=counts[RetrievalMode.HYBRID_RERANKED],
        citation_count=len(answer.citations),
        evaluation_completed_modes=completed_modes,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--api-url", help="loopback override; credentials are forbidden")
    args = parser.parse_args()
    try:
        config = AcceptanceConfig.from_json_file(args.config.resolve())
        if args.api_url is not None:
            config = config.model_copy(update={"api_url": validate_loopback_url(args.api_url)})
        settings = DemoSettings(
            financial_rag_api_url=config.api_url,
            demo_request_timeout_seconds=config.request_timeout_seconds,
        )
        summary = run_acceptance(
            FinancialRagApiClient(settings, verify=False),
            config,
        )
    except DemoApiError as exc:
        print(
            json.dumps(
                {
                    "schema_version": "local_acceptance_result_v1",
                    "status": "failed",
                    "error_code": exc.code,
                },
                sort_keys=True,
            )
        )
        return 1
    except (AcceptanceError, OSError, ValueError) as exc:
        code = exc.code if isinstance(exc, AcceptanceError) else "acceptance_configuration_failed"
        print(
            json.dumps(
                {
                    "schema_version": "local_acceptance_result_v1",
                    "status": "failed",
                    "error_code": code,
                },
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
