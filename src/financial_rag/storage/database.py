"""Side-effect-free SQLAlchemy async engine and session construction."""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from financial_rag.storage.settings import StorageSettings


def create_database_engine(settings: StorageSettings) -> AsyncEngine:
    """Create an engine without opening a connection until first explicit use."""
    return create_async_engine(
        settings.sqlalchemy_url,
        echo=settings.database_echo,
        pool_pre_ping=True,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create sessions that do not expire loaded state after commit."""
    return async_sessionmaker(engine, expire_on_commit=False)
