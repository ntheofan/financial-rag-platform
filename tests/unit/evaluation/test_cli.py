"""Side-effect-free CLI parser and safe early-failure tests."""

import argparse
import json
from pathlib import Path

import pytest

from financial_rag.api.container import ApiContainer
from financial_rag.cli import _run_evaluate_retrieval, build_parser, main
from financial_rag.domain.retrieval import RetrievalMode
from financial_rag.retrieval.service import RetrievalService
from financial_rag.runtime.settings import LocalRuntimeSettings
from tests.api.helpers import retrieval_service


def test_cli_parser_exposes_explicit_evaluation_paths() -> None:
    args = build_parser().parse_args(
        [
            "evaluate-retrieval",
            "--benchmark",
            "benchmark.jsonl",
            "--artifact-directory",
            "artifacts/index",
        ]
    )

    assert args.benchmark == Path("benchmark.jsonl")
    assert args.artifact_directory == Path("artifacts/index")


def test_cli_parser_exposes_bounded_folder_indexing() -> None:
    args = build_parser().parse_args(["index-folder", "--input-directory", "local-docs"])

    assert args.input_directory == Path("local-docs")


def test_cli_missing_benchmark_fails_before_runtime_composition() -> None:
    result = main(
        [
            "evaluate-retrieval",
            "--benchmark",
            "missing.jsonl",
            "--artifact-directory",
            "missing-artifacts",
        ]
    )

    assert result == 2


class FakeRuntime:
    def __init__(self, retrieval: RetrievalService) -> None:
        self.container = ApiContainer(retrieval=retrieval)
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class FakeRuntimeBuilder:
    runtime: FakeRuntime

    async def build(self, _settings: LocalRuntimeSettings) -> FakeRuntime:
        return self.runtime


@pytest.mark.asyncio
async def test_cli_success_writes_privacy_minimized_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retrieval = retrieval_service()
    relevant = retrieval.retrieve("capital expenditures", mode=RetrievalMode.DENSE).chunks[0]
    benchmark = tmp_path / "benchmark.jsonl"
    benchmark.write_text(
        json.dumps(
            {
                "query_id": "q1",
                "query": "capital expenditures",
                "relevant_chunk_ids": [relevant.chunk_id],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "evaluation-runs" / "report.json"
    FakeRuntimeBuilder.runtime = FakeRuntime(retrieval)
    monkeypatch.setattr("financial_rag.cli.LocalRuntimeBuilder", FakeRuntimeBuilder)
    args = argparse.Namespace(
        benchmark=benchmark,
        dataset_id="synthetic-cli",
        evaluation_config=Path("configs/evaluation/platform_eval_v1.json"),
        runtime_config=Path("configs/runtime/local_v1.json"),
        artifact_directory=Path("ignored-artifacts"),
        output=output,
        overwrite=False,
    )

    result = await _run_evaluate_retrieval(args)

    assert result == 0
    assert output.is_file()
    report_text = output.read_text(encoding="utf-8")
    assert "q1" in report_text
    assert "capital expenditures" not in report_text
    assert FakeRuntimeBuilder.runtime.closed is True
