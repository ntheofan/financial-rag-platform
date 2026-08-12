"""Pure display-helper and non-secret settings tests."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from financial_rag.chunking.service import MarkdownChunker
from financial_rag.demo.presentation import (
    available_scores,
    refresh_submitted_job,
    source_label,
    top_chunk_overlap,
)
from financial_rag.demo.settings import DemoSettings
from financial_rag.domain.evaluation import BenchmarkDataset
from financial_rag.domain.indexing import CorpusBuildJob, CorpusBuildStatus
from financial_rag.ingestion.loaders import TextMarkdownLoader
from tests.unit.generation.helpers import retrieval_result

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_source_label_and_scores_preserve_available_lineage() -> None:
    chunk = retrieval_result(1).chunks[0]

    assert "synthetic/acme-2025-10k.md" in source_label(chunk)
    assert "page 1" in source_label(chunk)
    assert [(score.label, score.value) for score in available_scores(chunk)] == [("Dense", 1.0)]


def test_overlap_uses_chunk_identity_not_rank_or_text() -> None:
    chunks = retrieval_result(3).chunks

    assert top_chunk_overlap(chunks[:2], chunks[1:]) == pytest.approx(1 / 3)
    assert top_chunk_overlap((), ()) == 1.0


def test_job_refresh_replaces_only_the_matching_submitted_snapshot() -> None:
    now = datetime(2026, 8, 12, tzinfo=UTC)
    pending = CorpusBuildJob(
        job_id="job_" + "a" * 32,
        status=CorpusBuildStatus.PENDING,
        input_file_count=1,
        created_at=now,
    )
    completed = CorpusBuildJob(
        job_id=pending.job_id,
        status=CorpusBuildStatus.COMPLETED,
        input_file_count=1,
        corpus_revision_id="corpus_" + "b" * 32,
        index_revision_id="index_" + "c" * 32,
        created_at=now,
        started_at=now,
        completed_at=now,
    )

    assert refresh_submitted_job(pending, (completed,)) == completed
    assert refresh_submitted_job(pending, ()) == pending
    assert refresh_submitted_job(None, (completed,)) is None


def test_demo_benchmark_ids_match_the_checked_synthetic_document() -> None:
    document_path = PROJECT_ROOT / "tests" / "fixtures" / "demo" / "acme-2025-10k.md"
    benchmark_path = PROJECT_ROOT / "tests" / "fixtures" / "demo" / "acme-benchmark.json"
    chunks = MarkdownChunker().chunk_documents(TextMarkdownLoader().load(document_path))
    benchmark = BenchmarkDataset.model_validate(
        json.loads(benchmark_path.read_text(encoding="utf-8"))
    )

    chunk_ids = {str(chunk.metadata["chunk_id"]) for chunk in chunks}
    assert chunk_ids
    assert all(set(item.relevant_chunk_ids) <= chunk_ids for item in benchmark.items)


@pytest.mark.parametrize(
    "url",
    [
        "not-a-url",
        "ftp://localhost:8000",
        "http://user:password@localhost:8000",
        "http://localhost:8000?secret=value",
    ],
)
def test_demo_api_url_rejects_unsafe_or_invalid_values(url: str) -> None:
    with pytest.raises(ValidationError):
        DemoSettings(financial_rag_api_url=url)


def test_demo_settings_normalize_trailing_slash() -> None:
    settings = DemoSettings(financial_rag_api_url="http://127.0.0.1:8000/")

    assert settings.financial_rag_api_url == "http://127.0.0.1:8000"


def test_demo_settings_have_no_provider_secret_field() -> None:
    assert all("openai" not in name for name in DemoSettings.model_fields)
    assert all("api_key" not in name for name in DemoSettings.model_fields)
