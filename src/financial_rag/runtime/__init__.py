"""Local application composition with explicit lifecycle ownership."""

from financial_rag.runtime.app import create_local_app
from financial_rag.runtime.bootstrap import (
    LocalRuntime,
    LocalRuntimeBuilder,
    RuntimeComponentStatus,
    RuntimeReport,
    verify_postgres_runtime,
)
from financial_rag.runtime.settings import LocalRuntimeConfig, LocalRuntimeSettings

__all__ = [
    "LocalRuntime",
    "LocalRuntimeBuilder",
    "LocalRuntimeConfig",
    "LocalRuntimeSettings",
    "RuntimeComponentStatus",
    "RuntimeReport",
    "create_local_app",
    "verify_postgres_runtime",
]
