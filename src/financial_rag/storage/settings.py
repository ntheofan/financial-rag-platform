"""Explicit database settings with secret-safe representation."""

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from financial_rag.core.errors import StorageConfigurationError


class StorageSettings(BaseSettings):
    """PostgreSQL settings loaded only when a caller constructs this object."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: SecretStr = Field(description="SQLAlchemy async PostgreSQL URL")
    database_echo: bool = False

    @field_validator("database_url")
    @classmethod
    def require_async_postgresql(cls, value: SecretStr) -> SecretStr:
        url = value.get_secret_value()
        if not url.startswith("postgresql+asyncpg://"):
            raise StorageConfigurationError(
                "DATABASE_URL must use the postgresql+asyncpg SQLAlchemy driver"
            )
        return value

    @property
    def sqlalchemy_url(self) -> str:
        """Reveal the connection string only at the explicit engine boundary."""
        return self.database_url.get_secret_value()
