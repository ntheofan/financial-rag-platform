"""Revision metadata and exception-boundary tests."""

from typing import NoReturn

import pytest

from financial_rag.api import ApiContainer, create_app
from financial_rag.core.errors import ProviderUnavailableError, RevisionNotFoundError
from financial_rag.domain.retrieval import RetrievalMode, RetrievalResult
from tests.api.client import api_client
from tests.api.helpers import CORPUS_ID, INDEX_ID, FakeRevisionReader


class MissingRevisionReader(FakeRevisionReader):
    async def get_corpus_revision(self, corpus_revision_id: str) -> NoReturn:
        raise RevisionNotFoundError(f"Corpus revision not found: {corpus_revision_id}")


class UnavailableRetrieval:
    def retrieve(self, query: str, *, mode: RetrievalMode) -> RetrievalResult:
        raise ProviderUnavailableError("synthetic provider detail")


class UnexpectedRetrieval:
    def retrieve(self, query: str, *, mode: RetrievalMode) -> RetrievalResult:
        raise RuntimeError("sensitive synthetic internal detail")


@pytest.mark.asyncio
async def test_revision_routes_return_metadata_without_chunks_or_vectors() -> None:
    app = create_app(container=ApiContainer(revisions=FakeRevisionReader()))
    async with api_client(app) as client:
        corpus = await client.get(f"/api/v1/corpora/{CORPUS_ID}")
        index = await client.get(f"/api/v1/indexes/{INDEX_ID}")

    assert corpus.status_code == 200
    assert corpus.json()["chunk_count"] == 3
    assert "chunks" not in corpus.json()
    assert index.status_code == 200
    assert index.json()["embedding_dimension"] == 1024
    assert "embeddings" not in index.json()


@pytest.mark.asyncio
async def test_revision_path_identifier_is_validated_before_storage_call() -> None:
    app = create_app(container=ApiContainer(revisions=FakeRevisionReader()))
    async with api_client(app) as client:
        response = await client.get("/api/v1/corpora/not-a-revision")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_validation_failed"


@pytest.mark.asyncio
async def test_missing_revision_maps_to_404() -> None:
    app = create_app(container=ApiContainer(revisions=MissingRevisionReader()))
    async with api_client(app) as client:
        response = await client.get(f"/api/v1/corpora/{CORPUS_ID}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "revision_not_found"


@pytest.mark.asyncio
async def test_provider_details_are_not_exposed() -> None:
    app = create_app(container=ApiContainer(retrieval=UnavailableRetrieval()))
    async with api_client(app) as client:
        response = await client.post("/api/v1/retrieval/query", json={"query": "revenue"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "dependency_unavailable"
    assert "synthetic provider detail" not in response.text


@pytest.mark.asyncio
async def test_unexpected_exception_is_generic() -> None:
    app = create_app(container=ApiContainer(retrieval=UnexpectedRetrieval()))
    async with api_client(app, raise_app_exceptions=False) as client:
        response = await client.post("/api/v1/retrieval/query", json={"query": "revenue"})

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert response.headers["X-Request-ID"] == response.json()["error"]["request_id"]
    assert "sensitive synthetic internal detail" not in response.text
