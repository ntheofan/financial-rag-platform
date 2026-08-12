"""Tests for local_v1 runtime configuration and environment boundaries."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from financial_rag.core.errors import RuntimeBootstrapError
from financial_rag.runtime.settings import LocalRuntimeConfig, LocalRuntimeSettings

PROJECT_ROOT = Path(__file__).parents[3]

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
    """Keep settings tests independent from a developer's ignored local .env."""
    monkeypatch.chdir(tmp_path)
    for name in RUNTIME_ENVIRONMENT_KEYS:
        monkeypatch.delenv(name, raising=False)


def test_checked_in_runtime_config_preserves_thesis_chunking_defaults() -> None:
    config = LocalRuntimeConfig.from_json_file(
        PROJECT_ROOT / "configs" / "runtime" / "local_v1.json"
    )

    assert config.runtime_version == "local_v1"
    assert config.chunking.chunk_size == 1500
    assert config.chunking.chunk_overlap == 200
    assert config.chunking.separators[-1] == ""
    assert config.embedding_device == "cpu"
    assert config.embedding_batch_size == 1


def test_database_smoke_requires_explicit_database_opt_in() -> None:
    with pytest.raises(ValidationError, match="DATABASE_SMOKE_ON_STARTUP"):
        LocalRuntimeSettings(database_enabled=False, database_smoke_on_startup=True)


def test_database_opt_in_requires_url() -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        LocalRuntimeSettings(database_enabled=True, database_url=None)


def test_invalid_runtime_file_has_safe_error(tmp_path: Path) -> None:
    config_path = tmp_path / "runtime.json"
    config_path.write_text("not-json", encoding="utf-8")

    with pytest.raises(RuntimeBootstrapError, match="Unable to load"):
        LocalRuntimeConfig.from_json_file(config_path)


def test_project_path_keeps_absolute_paths_and_resolves_relative_paths(tmp_path: Path) -> None:
    settings = LocalRuntimeSettings(project_root=tmp_path)

    assert settings.project_path(Path("relative/file.json")) == tmp_path / "relative/file.json"
    assert settings.project_path(tmp_path / "absolute.json") == tmp_path / "absolute.json"


def test_blank_optional_runtime_values_are_unconfigured() -> None:
    settings = LocalRuntimeSettings.model_validate(
        {"retrieval_artifact_directory": "", "openai_api_key": ""}
    )

    assert settings.retrieval_artifact_directory is None
    assert settings.openai_api_key is None


def test_generation_default_preserves_the_thesis_model() -> None:
    assert LocalRuntimeSettings().openai_model == "gpt-4o-mini"
