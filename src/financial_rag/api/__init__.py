"""Typed FastAPI adapter over injected platform services."""

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from financial_rag.api.app import create_app
    from financial_rag.api.container import ApiContainer
    from financial_rag.api.settings import ApiSettings

__all__ = ["ApiContainer", "ApiSettings", "create_app"]


def __getattr__(name: str) -> Any:
    """Resolve public adapters lazily so schema imports do not compose the app."""
    modules = {
        "ApiContainer": "financial_rag.api.container",
        "ApiSettings": "financial_rag.api.settings",
        "create_app": "financial_rag.api.app",
    }
    if name not in modules:
        raise AttributeError(name)
    return getattr(import_module(modules[name]), name)
