"""Typed HTTP client and presentation helpers for the local Streamlit demo."""

from financial_rag.demo.client import (
    ComparisonFailure,
    DemoApiError,
    FinancialRagApiClient,
    ModeComparison,
    ModeComparisonItem,
)
from financial_rag.demo.presentation import (
    ScoreDisplay,
    available_scores,
    source_label,
    top_chunk_overlap,
)
from financial_rag.demo.settings import DemoSettings

__all__ = [
    "ComparisonFailure",
    "DemoApiError",
    "DemoSettings",
    "FinancialRagApiClient",
    "ModeComparison",
    "ModeComparisonItem",
    "ScoreDisplay",
    "available_scores",
    "source_label",
    "top_chunk_overlap",
]
