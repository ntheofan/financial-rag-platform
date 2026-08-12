"""Read-only checks for an explicitly configured, already migrated test database."""

import os

import pytest
from pydantic import SecretStr
from sqlalchemy import text

from financial_rag.storage.database import create_database_engine
from financial_rag.storage.settings import StorageSettings

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        TEST_DATABASE_URL is None,
        reason="TEST_DATABASE_URL is not configured",
    ),
]


@pytest.mark.asyncio
async def test_database_has_pgvector_and_head_migration() -> None:
    """Verify infrastructure without inserting, deleting, or exposing stored content."""
    assert TEST_DATABASE_URL is not None
    settings = StorageSettings(database_url=SecretStr(TEST_DATABASE_URL))
    engine = create_database_engine(settings)
    try:
        async with engine.connect() as connection:
            vector_version = await connection.scalar(
                text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            )
            migration_version = await connection.scalar(
                text("SELECT version_num FROM alembic_version")
            )
    finally:
        await engine.dispose()

    assert vector_version is not None
    assert migration_version == "20260812_0002"
