"""Pytest fixtures for shared module tests."""

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.database import Base


@pytest.fixture(scope="function")
async def test_db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create fresh database engine for each test."""
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        echo=False,
    )
    yield engine
    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(test_db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create database session for tests using transaction rollback.

    Uses a connection-level transaction that gets rolled back after each test,
    giving each test a clean slate WITHOUT dropping tables. This prevents the
    destructive Base.metadata.drop_all() that previously nuked all tables while
    leaving alembic_version intact (causing the "DB at head but no tables" bug).
    """
    # Ensure tables exist (idempotent — won't recreate if already present)
    async with test_db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Wrap the test in a transaction that we roll back afterward
    async with test_db_engine.connect() as conn:
        tx = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)

        yield session

        await session.close()
        await tx.rollback()
