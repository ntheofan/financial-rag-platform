"""Offline tests for retrieval composition and FastAPI lifespan ownership."""

import json
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncEngine

from financial_rag.core.errors import RuntimeBootstrapError
from financial_rag.domain.chunking import ChunkingConfig
from financial_rag.domain.fingerprints import fingerprint_model
from financial_rag.domain.generation import ModelAnswer
from financial_rag.domain.retrieval import RetrievalConfig, RetrievalMode
from financial_rag.retrieval.embeddings import FakeEmbeddingProvider
from financial_rag.retrieval.rerankers import FakeReranker
from financial_rag.retrieval.service import RetrievalService
from financial_rag.runtime.app import create_local_app
from financial_rag.runtime.bootstrap import (
    LocalRuntimeBuilder,
    RuntimeComponentStatus,
    verify_postgres_runtime,
)
from financial_rag.runtime.settings import LocalRuntimeConfig, LocalRuntimeSettings
from tests.unit.generation.helpers import FakeGenerationAdapter
from tests.unit.retrieval.helpers import fake_retrieval_config, synthetic_chunks

RUNTIME_ENVIRONMENT_KEYS = (
    "DATABASE_ENABLED",
    "DATABASE_SMOKE_ON_STARTUP",
    "DATABASE_URL",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "PROJECT_ROOT",
    "RETRIEVAL_ARTIFACT_DIRECTORY",
    "RUNTIME_CONFIG_PATH",
)


@pytest.fixture(autouse=True)
def isolate_local_runtime_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep unit tests independent from a developer's ignored local .env."""
    monkeypatch.chdir(tmp_path)
    for name in RUNTIME_ENVIRONMENT_KEYS:
        monkeypatch.delenv(name, raising=False)


def _write_runtime_files(root: Path, retrieval: RetrievalConfig) -> None:
    (root / "retrieval.json").write_text(retrieval.model_dump_json(indent=2), encoding="utf-8")
    runtime = LocalRuntimeConfig(retrieval_config_path=Path("retrieval.json"))
    (root / "runtime.json").write_text(runtime.model_dump_json(indent=2), encoding="utf-8")


@pytest.mark.asyncio
async def test_runtime_without_artifacts_starts_with_capabilities_disabled(tmp_path: Path) -> None:
    retrieval = fake_retrieval_config()
    _write_runtime_files(tmp_path, retrieval)
    settings = LocalRuntimeSettings(
        project_root=tmp_path,
        runtime_config_path=Path("runtime.json"),
    )

    runtime = await LocalRuntimeBuilder().build(settings)

    assert runtime.container.retrieval is None
    assert runtime.container.revisions is None
    assert runtime.report.retrieval is RuntimeComponentStatus.DISABLED
    assert runtime.report.database_smoke is RuntimeComponentStatus.DISABLED
    await runtime.close()


@pytest.mark.asyncio
async def test_runtime_loads_synthetic_artifacts_with_injected_fake_models(tmp_path: Path) -> None:
    config = fake_retrieval_config(final_top_k=2)
    _write_runtime_files(tmp_path, config)
    provider = FakeEmbeddingProvider(dimension=config.embedding_dimension)
    service = RetrievalService.build(
        synthetic_chunks(["capital expenditure cash flow", "revenue net sales"]),
        embedding_provider=provider,
        config=config,
        chunking_configuration_fingerprint=fingerprint_model(ChunkingConfig()),
        reranker=FakeReranker(),
    )
    artifact_directory = tmp_path / "artifacts"
    service.save_artifacts(artifact_directory)
    builder = LocalRuntimeBuilder(
        embedding_factory=lambda retrieval, _runtime: FakeEmbeddingProvider(
            dimension=retrieval.embedding_dimension
        ),
        reranker_factory=lambda _retrieval, _runtime: FakeReranker(),
    )
    settings = LocalRuntimeSettings(
        project_root=tmp_path,
        runtime_config_path=Path("runtime.json"),
        retrieval_artifact_directory=Path("artifacts"),
    )

    runtime = await builder.build(settings)

    assert runtime.container.retrieval is not None
    result = runtime.container.retrieval.retrieve("capital expenditure", mode=RetrievalMode.HYBRID)
    assert result.chunks
    assert runtime.report.retrieval is RuntimeComponentStatus.CONFIGURED
    await runtime.close()


@pytest.mark.asyncio
async def test_runtime_composes_generation_only_with_key_and_retrieval(tmp_path: Path) -> None:
    config = fake_retrieval_config(final_top_k=2)
    _write_runtime_files(tmp_path, config)
    service = RetrievalService.build(
        synthetic_chunks(["capital expenditure evidence", "revenue evidence"]),
        embedding_provider=FakeEmbeddingProvider(dimension=config.embedding_dimension),
        config=config,
        chunking_configuration_fingerprint=fingerprint_model(ChunkingConfig()),
        reranker=FakeReranker(),
    )
    service.save_artifacts(tmp_path / "artifacts")
    builder = LocalRuntimeBuilder(
        embedding_factory=lambda retrieval, _runtime: FakeEmbeddingProvider(
            dimension=retrieval.embedding_dimension
        ),
        reranker_factory=lambda _retrieval, _runtime: FakeReranker(),
        generation_factory=lambda _settings: FakeGenerationAdapter(
            ModelAnswer(answer="Grounded.", abstained=False, citation_ids=("C1",))
        ),
    )
    settings = LocalRuntimeSettings(
        project_root=tmp_path,
        runtime_config_path=Path("runtime.json"),
        retrieval_artifact_directory=Path("artifacts"),
        openai_api_key=SecretStr("test-only"),
    )

    runtime = await builder.build(settings)

    assert runtime.container.generation is not None
    assert runtime.container.evaluation is not None
    answer = runtime.container.generation.answer("capital expenditure", mode=RetrievalMode.DENSE)
    assert answer.citations[0].citation_id == "C1"
    assert runtime.report.generation is RuntimeComponentStatus.CONFIGURED
    assert runtime.report.evaluation is RuntimeComponentStatus.CONFIGURED
    await runtime.close()


@pytest.mark.asyncio
async def test_explicit_missing_artifacts_fail_startup_clearly(tmp_path: Path) -> None:
    config = fake_retrieval_config()
    _write_runtime_files(tmp_path, config)
    settings = LocalRuntimeSettings(
        project_root=tmp_path,
        runtime_config_path=Path("runtime.json"),
        retrieval_artifact_directory=Path("missing"),
    )

    with pytest.raises(RuntimeBootstrapError, match="artifacts could not be loaded"):
        await LocalRuntimeBuilder(
            embedding_factory=lambda retrieval, _runtime: FakeEmbeddingProvider(
                dimension=retrieval.embedding_dimension
            )
        ).build(settings)


@pytest.mark.asyncio
async def test_fastapi_lifespan_installs_composed_container(tmp_path: Path) -> None:
    config = fake_retrieval_config()
    _write_runtime_files(tmp_path, config)
    settings = LocalRuntimeSettings(
        project_root=tmp_path,
        runtime_config_path=Path("runtime.json"),
    )
    app = create_local_app(runtime_settings=settings)

    async with app.router.lifespan_context(app):
        assert app.state.runtime.report.runtime_version == "local_v1"
        assert app.state.container.retrieval is None


def test_runtime_config_rejects_unversioned_fields(tmp_path: Path) -> None:
    path = tmp_path / "runtime.json"
    path.write_text(json.dumps({"runtime_version": "local_v1", "magic": True}), encoding="utf-8")

    with pytest.raises(RuntimeBootstrapError, match="invalid"):
        LocalRuntimeConfig.from_json_file(path)


class _FakeConnection:
    def __init__(self, *, migration_head: str = "20260812_0002") -> None:
        self._migration_head = migration_head

    async def execute(self, _statement: object) -> None:
        return None

    async def scalar(self, statement: Any) -> str:
        return "vector" if "pg_extension" in statement.text else self._migration_head


class _FakeConnectionContext:
    def __init__(self, connection: _FakeConnection) -> None:
        self._connection = connection

    async def __aenter__(self) -> _FakeConnection:
        return self._connection

    async def __aexit__(self, *args: object) -> None:
        return None


class _FakeEngine:
    def __init__(self, *, migration_head: str = "20260812_0002") -> None:
        self._connection = _FakeConnection(migration_head=migration_head)

    def connect(self) -> _FakeConnectionContext:
        return _FakeConnectionContext(self._connection)


@pytest.mark.asyncio
async def test_postgres_smoke_validates_vector_and_alembic_head() -> None:
    await verify_postgres_runtime(cast(AsyncEngine, _FakeEngine()))


@pytest.mark.asyncio
async def test_postgres_smoke_rejects_wrong_alembic_head() -> None:
    engine = cast(AsyncEngine, _FakeEngine(migration_head="old"))

    with pytest.raises(RuntimeBootstrapError, match="Alembic head"):
        await verify_postgres_runtime(engine)
