"""
shared/database/database.py

Async Database Engine & Session Management

Provides PostgreSQL connection pool with async support.
"""

from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker
)
from sqlalchemy.pool import NullPool

from shared.common.logging import get_logger
from shared.common.config import BaseSettings

logger = get_logger(__name__)


# Global engine and session factory
_engine: Optional[AsyncEngine] = None
_async_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def init_database(
    database_url: str,
    pool_size: int = 10,
    max_overflow: int = 20,
    pool_timeout: int = 30,
    echo: bool = False
) -> AsyncEngine:
    """
    Initialize async database engine.

    Args:
        database_url: PostgreSQL connection URL (postgresql+asyncpg://...)
        pool_size: Connection pool size
        max_overflow: Max connections above pool_size
        pool_timeout: Seconds to wait for connection
        echo: Log SQL queries (debug mode)

    Returns:
        AsyncEngine instance

    Raises:
        ValueError: If database URL is invalid
    """
    global _engine, _async_session_factory

    if not database_url:
        raise ValueError("Database URL is required")

    if not database_url.startswith("postgresql+asyncpg://"):
        # Convert postgresql:// to postgresql+asyncpg://
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        else:
            raise ValueError("Database URL must be a PostgreSQL URL")

    logger.info("Initializing database engine", extra={
        "pool_size": pool_size,
        "max_overflow": max_overflow
    })

    # Create engine
    _engine = create_async_engine(
        database_url,
        echo=echo,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_pre_ping=True,  # Verify connections before using
        pool_recycle=3600,   # Recycle connections after 1 hour
    )

    # Create session factory
    _async_session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )

    logger.info("Database engine initialized successfully")

    return _engine


def get_engine() -> AsyncEngine:
    """
    Get database engine.

    Returns:
        AsyncEngine instance

    Raises:
        RuntimeError: If engine not initialized
    """
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call init_database() first.")
    return _engine


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get async database session (FastAPI dependency).

    Usage:
        @app.get("/users")
        async def get_users(session: AsyncSession = Depends(get_async_session)):
            result = await session.execute(select(User))
            return result.scalars().all()

    Yields:
        AsyncSession instance
    """
    if _async_session_factory is None:
        raise RuntimeError("Database session factory not initialized")

    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_database() -> None:
    """Close database engine and connections."""
    global _engine, _async_session_factory

    if _engine:
        logger.info("Closing database engine")
        await _engine.dispose()
        _engine = None
        _async_session_factory = None
        logger.info("Database engine closed")


async def check_database_connection() -> bool:
    """
    Check database connection (for health checks).

    Returns:
        True if database is reachable, False otherwise
    """
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error("Database health check failed", extra={"error": str(e)})
        return False
