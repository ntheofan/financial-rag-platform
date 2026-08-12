"""Bounded local corpus-build and upload-staging services."""

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from financial_rag.indexing.service import CorpusIndexingService
    from financial_rag.indexing.staging import (
        StagedUploadBatch,
        UploadPolicy,
        UploadStagingService,
    )

__all__ = [
    "CorpusIndexingService",
    "StagedUploadBatch",
    "UploadPolicy",
    "UploadStagingService",
]


def __getattr__(name: str) -> Any:
    """Keep staging imports independent from the heavier indexing composition."""
    modules = {
        "CorpusIndexingService": "financial_rag.indexing.service",
        "StagedUploadBatch": "financial_rag.indexing.staging",
        "UploadPolicy": "financial_rag.indexing.staging",
        "UploadStagingService": "financial_rag.indexing.staging",
    }
    if name not in modules:
        raise AttributeError(name)
    return getattr(import_module(modules[name]), name)
