"""Versioned paired evaluation with canonical deterministic metrics."""

from financial_rag.evaluation.importers import load_benchmark, parse_benchmark_bytes
from financial_rag.evaluation.metrics import exact_match, retrieval_metrics, token_f1
from financial_rag.evaluation.reports import write_evaluation_report
from financial_rag.evaluation.runner import (
    EvaluationGeneration,
    EvaluationRetrieval,
    EvaluationRunner,
)

__all__ = [
    "EvaluationGeneration",
    "EvaluationRetrieval",
    "EvaluationRunner",
    "exact_match",
    "load_benchmark",
    "parse_benchmark_bytes",
    "retrieval_metrics",
    "token_f1",
    "write_evaluation_report",
]
