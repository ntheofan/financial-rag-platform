"""Database configuration boundary tests."""

import pytest
from pydantic import SecretStr, ValidationError

from financial_rag.core.errors import StorageConfigurationError
from financial_rag.storage.database import create_database_engine
from financial_rag.storage.settings import StorageSettings


def test_storage_settings_require_async_postgresql_and_redact_secret() -> None:
    password = "synthetic-password"
    settings = StorageSettings(
        database_url=SecretStr(
            f"postgresql+asyncpg://financial_rag:{password}@localhost:5432/financial_rag"
        )
    )

    assert password not in repr(settings)
    assert settings.sqlalchemy_url.endswith("@localhost:5432/financial_rag")


def test_storage_settings_reject_non_postgresql_driver() -> None:
    with pytest.raises((StorageConfigurationError, ValidationError)):
        StorageSettings(database_url=SecretStr("sqlite+aiosqlite:///local.db"))


@pytest.mark.asyncio
async def test_engine_construction_does_not_connect() -> None:
    settings = StorageSettings(
        database_url=SecretStr(
            "postgresql+asyncpg://financial_rag:local-only@127.0.0.1:1/financial_rag"
        )
    )

    engine = create_database_engine(settings)

    assert engine.url.drivername == "postgresql+asyncpg"
    await engine.dispose()
