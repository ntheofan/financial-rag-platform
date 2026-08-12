"""Phase 0 package smoke tests with no external services or API calls."""

from importlib import import_module

import pytest

import financial_rag


def test_package_import_exposes_version() -> None:
    """The installed package can be imported from the src layout."""
    assert financial_rag.__version__ == "0.1.0"


@pytest.mark.parametrize(
    "subpackage",
    [
        "api",
        "chunking",
        "core",
        "domain",
        "evaluation",
        "generation",
        "ingestion",
        "retrieval",
        "storage",
    ],
)
def test_foundation_subpackages_are_importable(subpackage: str) -> None:
    """Reserved package boundaries exist without importing future frameworks."""
    module = import_module(f"financial_rag.{subpackage}")

    assert module.__name__ == f"financial_rag.{subpackage}"
