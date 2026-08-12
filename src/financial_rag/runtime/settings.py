"""Validated local composition settings and versioned non-secret runtime config."""

import json
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from financial_rag.core.errors import RuntimeBootstrapError
from financial_rag.domain.chunking import ChunkingConfig
from financial_rag.generation.context import ContextAssemblyConfig
from financial_rag.retrieval.embeddings import Device


class LocalRuntimeConfig(BaseModel):
    """Versioned, non-secret configuration for the local single-user runtime."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    runtime_version: Literal["local_v1"] = "local_v1"
    retrieval_config_path: Path = Path("configs/retrieval/platform_v1.json")
    chunking: ChunkingConfig = ChunkingConfig()
    embedding_device: Device = "auto"
    embedding_batch_size: int = Field(default=8, gt=0)
    reranker_enabled: bool = True
    generation_context: ContextAssemblyConfig = ContextAssemblyConfig()

    @classmethod
    def from_json_file(cls, path: Path) -> Self:
        """Load a checked-in runtime configuration without resolving local artifacts."""
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeBootstrapError("Unable to load the local runtime configuration.") from exc
        try:
            return cls.model_validate(payload)
        except ValueError as exc:
            raise RuntimeBootstrapError("The local runtime configuration is invalid.") from exc


class LocalRuntimeSettings(BaseSettings):
    """Environment-controlled paths and opt-in infrastructure switches."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    project_root: Path = Path(".")
    runtime_config_path: Path = Path("configs/runtime/local_v1.json")
    retrieval_artifact_directory: Path | None = None
    upload_staging_directory: Path = Path("uploads")
    database_enabled: bool = False
    database_smoke_on_startup: bool = False
    database_url: SecretStr | None = None
    database_echo: bool = False
    openai_api_key: SecretStr | None = None
    openai_model: str = Field(default="gpt-4o-mini", min_length=1)
    generation_timeout_seconds: float = Field(default=30.0, gt=0)
    generation_max_retries: int = Field(default=2, ge=0, le=5)
    generation_max_output_tokens: int = Field(default=1000, gt=0)

    @field_validator("openai_api_key", "retrieval_artifact_directory", mode="before")
    @classmethod
    def blank_optional_setting_is_unconfigured(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def database_switches_are_consistent(self) -> Self:
        if self.database_enabled and self.database_url is None:
            raise ValueError("DATABASE_URL is required when DATABASE_ENABLED is true")
        if self.database_smoke_on_startup and not self.database_enabled:
            raise ValueError("DATABASE_SMOKE_ON_STARTUP requires DATABASE_ENABLED=true")
        return self

    def project_path(self, path: Path) -> Path:
        """Resolve a configured relative path against the explicit project root."""
        return path if path.is_absolute() else self.project_root / path
