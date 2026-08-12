"""Explicit local command-line entry points for reproducible platform workflows."""

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from financial_rag.core.errors import FinancialRAGError
from financial_rag.domain.evaluation import EvaluationConfig
from financial_rag.domain.indexing import UploadDocument
from financial_rag.evaluation import EvaluationRunner, load_benchmark, write_evaluation_report
from financial_rag.retrieval.service import RetrievalService
from financial_rag.runtime.bootstrap import LocalRuntimeBuilder
from financial_rag.runtime.settings import LocalRuntimeSettings

MAX_FOLDER_FILES = 10
MAX_FOLDER_FILE_BYTES = 20 * 1024 * 1024
MAX_FOLDER_TOTAL_BYTES = 50 * 1024 * 1024
FOLDER_EXTENSIONS = frozenset({".md", ".pdf", ".txt"})


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI without reading files, environment, models, or infrastructure."""
    parser = argparse.ArgumentParser(prog="financial-rag")
    commands = parser.add_subparsers(dest="command", required=True)
    evaluate = commands.add_parser(
        "evaluate-retrieval",
        help="Run platform_eval_v1 against explicit local retrieval artifacts.",
    )
    evaluate.add_argument("--benchmark", type=Path, required=True)
    evaluate.add_argument("--artifact-directory", type=Path, required=True)
    evaluate.add_argument(
        "--runtime-config",
        type=Path,
        default=Path("configs/runtime/local_v1.json"),
    )
    evaluate.add_argument(
        "--evaluation-config",
        type=Path,
        default=Path("configs/evaluation/platform_eval_v1.json"),
    )
    evaluate.add_argument("--dataset-id")
    evaluate.add_argument("--output", type=Path)
    evaluate.add_argument("--overwrite", action="store_true")
    index_folder = commands.add_parser(
        "index-folder",
        help="Build and activate a pgvector revision from a bounded local folder.",
    )
    index_folder.add_argument("--input-directory", type=Path, required=True)
    index_folder.add_argument(
        "--runtime-config",
        type=Path,
        default=Path("configs/runtime/local_v1.json"),
    )
    index_folder.add_argument("--label")
    return parser


async def _run_evaluate_retrieval(args: argparse.Namespace) -> int:
    dataset = load_benchmark(args.benchmark, dataset_id=args.dataset_id)
    config = EvaluationConfig.from_json_file(args.evaluation_config)
    settings = LocalRuntimeSettings(
        project_root=Path.cwd(),
        runtime_config_path=args.runtime_config,
        retrieval_artifact_directory=args.artifact_directory,
        database_enabled=False,
        database_smoke_on_startup=False,
    )
    runtime = await LocalRuntimeBuilder().build(settings)
    try:
        retrieval = runtime.container.retrieval
        if not isinstance(retrieval, RetrievalService):
            raise FinancialRAGError("Retrieval was not composed for evaluation.")
        runner = EvaluationRunner(
            retrieval=retrieval,
            generation=runtime.container.generation,
            corpus_fingerprint=retrieval.manifest.chunk_mapping_fingerprint,
        )
        report = runner.evaluate(dataset, config=config)
        if args.output is not None:
            write_evaluation_report(report, args.output, overwrite=args.overwrite)
        summary = {
            "manifest": report.manifest.model_dump(mode="json"),
            "aggregates": [item.model_dump(mode="json") for item in report.aggregates],
        }
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0
    finally:
        await runtime.close()


async def _run_index_folder(args: argparse.Namespace) -> int:
    folder: Path = args.input_directory
    if not folder.is_dir():
        raise FinancialRAGError("The input directory does not exist or is not a folder.")
    paths = sorted(
        (path for path in folder.iterdir() if path.is_file()),
        key=lambda path: (path.name.casefold(), path.name),
    )
    if not paths:
        raise FinancialRAGError("The input directory contains no files.")
    if len(paths) > MAX_FOLDER_FILES:
        raise FinancialRAGError(
            f"The input directory may contain at most {MAX_FOLDER_FILES} files."
        )
    if any(path.suffix.lower() not in FOLDER_EXTENSIONS for path in paths):
        raise FinancialRAGError("The input directory contains an unsupported file type.")
    try:
        sizes = [path.stat().st_size for path in paths]
        if any(size <= 0 or size > MAX_FOLDER_FILE_BYTES for size in sizes):
            raise FinancialRAGError("An input file is empty or exceeds the 20 MiB limit.")
        if sum(sizes) > MAX_FOLDER_TOTAL_BYTES:
            raise FinancialRAGError("The input directory exceeds the 50 MiB total limit.")
        documents = tuple(
            UploadDocument(filename=path.name, content=path.read_bytes()) for path in paths
        )
    except OSError as exc:
        raise FinancialRAGError("Unable to read the bounded local input folder.") from exc
    settings = LocalRuntimeSettings(
        project_root=Path.cwd(),
        runtime_config_path=args.runtime_config,
        database_enabled=True,
        database_smoke_on_startup=True,
    )
    runtime = await LocalRuntimeBuilder().build(settings)
    try:
        indexing = runtime.container.indexing
        if indexing is None:
            raise FinancialRAGError("Corpus indexing was not composed.")
        job, batch = await indexing.submit_uploads(documents, label=args.label)
        await indexing.run_staged_job(job.job_id, batch)
        result = await indexing.get_job(job.job_id)
        print(result.model_dump_json())
        return 0 if result.status.value == "completed" else 2
    finally:
        await runtime.close()


def main(argv: Sequence[str] | None = None) -> int:
    """Execute a command and emit only safe expected-error messages."""
    args = build_parser().parse_args(argv)
    try:
        if args.command == "evaluate-retrieval":
            return asyncio.run(_run_evaluate_retrieval(args))
        if args.command == "index-folder":
            return asyncio.run(_run_index_folder(args))
    except (FinancialRAGError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
