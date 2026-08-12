"""Strict synthetic benchmark import tests."""

import json
from pathlib import Path

import pytest

from financial_rag.core.errors import BenchmarkImportError
from financial_rag.evaluation.importers import load_benchmark, parse_benchmark_bytes

PROJECT_ROOT = Path(__file__).parents[3]


def test_load_checked_in_synthetic_jsonl_fixture() -> None:
    dataset = load_benchmark(PROJECT_ROOT / "tests" / "fixtures" / "evaluation" / "benchmark.jsonl")

    assert dataset.schema_version == "platform_eval_dataset_v1"
    assert dataset.dataset_id == "benchmark"
    assert [item.query_id for item in dataset.items] == ["synthetic-q1", "synthetic-q2"]


def test_json_object_and_item_array_are_supported() -> None:
    item = {
        "query_id": "q1",
        "query": "Synthetic question?",
        "relevant_chunk_ids": ["chunk_1"],
    }
    object_dataset = parse_benchmark_bytes(
        json.dumps({"dataset_id": "object", "items": [item]}).encode(),
        filename="benchmark.json",
    )
    array_dataset = parse_benchmark_bytes(
        json.dumps([item]).encode(),
        filename="array.json",
        dataset_id="override",
    )

    assert object_dataset.dataset_id == "object"
    assert array_dataset.dataset_id == "override"
    assert object_dataset.items == array_dataset.items


@pytest.mark.parametrize(
    ("payload", "filename", "message"),
    [
        (b"", "empty.jsonl", "empty"),
        (b"{}", "benchmark.csv", ".json"),
        (b"\xff", "benchmark.json", "UTF-8"),
        (b"[]", "benchmark.json", "platform_eval_dataset_v1"),
        (b"[]\n", "benchmark.jsonl", "must be an object"),
    ],
)
def test_invalid_benchmark_inputs_fail_clearly(payload: bytes, filename: str, message: str) -> None:
    with pytest.raises(BenchmarkImportError, match=message):
        parse_benchmark_bytes(payload, filename=filename)


def test_duplicate_query_ids_are_rejected() -> None:
    line = b'{"query_id":"q1","query":"Q?","relevant_chunk_ids":["c1"]}'

    with pytest.raises(BenchmarkImportError, match="platform_eval_dataset_v1"):
        parse_benchmark_bytes(line + b"\n" + line, filename="duplicate.jsonl")


def test_size_limit_is_enforced_before_parsing() -> None:
    with pytest.raises(BenchmarkImportError, match="size limit"):
        parse_benchmark_bytes(b"{}", filename="benchmark.json", max_bytes=1)
