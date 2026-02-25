"""Database configuration and session management."""

from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

# Create async engine with connection pooling
# Pool size is configurable for multi-worker deployments:
# 4 workers x (pool_size + max_overflow) should stay under PostgreSQL max_connections (100)
engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,  # Test connections before using
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_pool_max_overflow,
    pool_recycle=settings.db_pool_recycle,  # Recycle after 1h to avoid PostgreSQL idle timeouts
    echo=settings.environment == "development",  # Log SQL in development
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# Base class for SQLAlchemy models
class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


@asynccontextmanager
async def get_db_context() -> AsyncIterator[AsyncSession]:
    """Create a standalone async session for use outside FastAPI request lifecycle.

    Used by agent tools that need DB access without a FastAPI request context.

    Yields:
        AsyncSession: Database session.
    """
    session = AsyncSessionLocal()
    try:
        yield session
    finally:
        await session.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides a database session.

    Yields:
        AsyncSession: Database session for the request.

    Example:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
