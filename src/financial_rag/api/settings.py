"""Non-secret FastAPI presentation settings."""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    """Settings read only when the application factory is invoked."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    api_docs_enabled: bool = True
    api_title: str = Field(default="financial-rag-platform", min_length=1, max_length=100)
