"""Strict local JSON/JSONL benchmark import without dataset or network dependencies."""

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from financial_rag.core.errors import BenchmarkImportError
from financial_rag.domain.evaluation import BenchmarkDataset, BenchmarkItem

SUPPORTED_BENCHMARK_EXTENSIONS = (".json", ".jsonl")
DEFAULT_MAX_BENCHMARK_BYTES = 5 * 1024 * 1024


def load_benchmark(
    path: Path,
    *,
    dataset_id: str | None = None,
    max_bytes: int = DEFAULT_MAX_BENCHMARK_BYTES,
) -> BenchmarkDataset:
    """Read a bounded local benchmark file through pathlib and validate every item."""
    if not path.is_file():
        raise BenchmarkImportError("Benchmark path does not identify a local file.")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise BenchmarkImportError("Unable to inspect the benchmark file.") from exc
    if size == 0:
        raise BenchmarkImportError("Benchmark file is empty.")
    if size > max_bytes:
        raise BenchmarkImportError("Benchmark file exceeds the configured size limit.")
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise BenchmarkImportError("Unable to read the benchmark file.") from exc
    return parse_benchmark_bytes(
        payload,
        filename=path.name,
        dataset_id=dataset_id,
        max_bytes=max_bytes,
    )


def parse_benchmark_bytes(
    payload: bytes,
    *,
    filename: str,
    dataset_id: str | None = None,
    max_bytes: int = DEFAULT_MAX_BENCHMARK_BYTES,
) -> BenchmarkDataset:
    """Parse bounded UTF-8 JSON/JSONL bytes supplied by a local caller or UI."""
    suffix = Path(filename).suffix.casefold()
    if suffix not in SUPPORTED_BENCHMARK_EXTENSIONS:
        raise BenchmarkImportError("Benchmark must use .json or .jsonl format.")
    if not payload:
        raise BenchmarkImportError("Benchmark file is empty.")
    if len(payload) > max_bytes:
        raise BenchmarkImportError("Benchmark file exceeds the configured size limit.")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BenchmarkImportError("Benchmark file must be valid UTF-8.") from exc
    try:
        if suffix == ".json":
            raw = json.loads(text)
            if isinstance(raw, list):
                dataset_payload: dict[str, Any] = {
                    "dataset_id": dataset_id or Path(filename).stem,
                    "items": raw,
                }
            elif isinstance(raw, dict):
                dataset_payload = raw
                if dataset_id is not None:
                    dataset_payload = {**raw, "dataset_id": dataset_id}
            else:
                raise BenchmarkImportError("JSON benchmark must be an object or item array.")
            return BenchmarkDataset.model_validate(dataset_payload)

        records: list[dict[str, Any]] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise BenchmarkImportError(f"JSONL record {line_number} must be an object.")
            records.append(record)
        return BenchmarkDataset(
            dataset_id=dataset_id or Path(filename).stem,
            items=tuple(BenchmarkItem.model_validate(record) for record in records),
        )
    except BenchmarkImportError:
        raise
    except (json.JSONDecodeError, ValidationError, ValueError, TypeError) as exc:
        raise BenchmarkImportError(
            "Benchmark content does not match platform_eval_dataset_v1."
        ) from exc
