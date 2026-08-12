"""FastAPI factory backed by the explicit local runtime composition root."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from financial_rag.api.app import create_app
from financial_rag.api.settings import ApiSettings
from financial_rag.runtime.bootstrap import LocalRuntimeBuilder
from financial_rag.runtime.settings import LocalRuntimeSettings


def create_local_app(
    *,
    runtime_settings: LocalRuntimeSettings | None = None,
    api_settings: ApiSettings | None = None,
    builder: LocalRuntimeBuilder | None = None,
) -> FastAPI:
    """Create an app whose services are acquired and released by ASGI lifespan."""
    resolved_runtime_settings = runtime_settings or LocalRuntimeSettings()
    resolved_builder = builder or LocalRuntimeBuilder()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        runtime = await resolved_builder.build(resolved_runtime_settings)
        app.state.runtime = runtime
        app.state.container = runtime.container
        try:
            yield
        finally:
            await runtime.close()

    return create_app(settings=api_settings, lifespan=lifespan)
