"""FastAPI application factory with no import-time infrastructure access."""

from fastapi import FastAPI
from starlette.types import Lifespan

from financial_rag import __version__
from financial_rag.api.container import ApiContainer
from financial_rag.api.errors import install_exception_handlers
from financial_rag.api.middleware import RequestContextMiddleware
from financial_rag.api.routes import health_router, v1_router
from financial_rag.api.settings import ApiSettings


def create_app(
    *,
    container: ApiContainer | None = None,
    settings: ApiSettings | None = None,
    lifespan: Lifespan[FastAPI] | None = None,
) -> FastAPI:
    """Build an application around already-constructed domain services."""
    resolved_settings = settings or ApiSettings()
    docs_url = "/docs" if resolved_settings.api_docs_enabled else None
    openapi_url = "/openapi.json" if resolved_settings.api_docs_enabled else None
    app = FastAPI(
        title=resolved_settings.api_title,
        version=__version__,
        description=(
            "In-development local API for transparent financial-document retrieval and "
            "citation-validated grounded answers."
        ),
        docs_url=docs_url,
        redoc_url=None,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )
    app.state.container = container or ApiContainer()
    app.add_middleware(RequestContextMiddleware)
    install_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(v1_router)
    return app
