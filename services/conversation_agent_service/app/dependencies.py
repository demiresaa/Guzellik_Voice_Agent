"""
services/conversation_agent_service/app/dependencies.py

FastAPI Dependencies

Dependency injection for services and repositories.
"""

from functools import lru_cache
from typing import AsyncGenerator

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_async_session
from shared.common.logging import get_logger

from app.services.conversation_service import ConversationService
from app.services.session_service import SessionService
from app.repositories.conversation_repository import ConversationRepository
from config import get_settings

logger = get_logger(__name__)

# Global instances (initialized at startup)
_redis_client: Redis | None = None
_session_service: SessionService | None = None


def init_redis(redis_url: str) -> Redis:
    """
    Initialize Redis client.

    Args:
        redis_url: Redis connection URL

    Returns:
        Redis client
    """
    global _redis_client

    _redis_client = Redis.from_url(
        redis_url,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=5,
        socket_keepalive=True,
        health_check_interval=30
    )

    logger.info("Redis client initialized")

    return _redis_client


def get_redis_client() -> Redis:
    """
    Get Redis client (dependency).

    Returns:
        Redis client

    Raises:
        RuntimeError: If Redis not initialized
    """
    if _redis_client is None:
        raise RuntimeError("Redis client not initialized")
    return _redis_client


def init_session_service(redis_client: Redis, session_ttl: int) -> SessionService:
    """
    Initialize session service.

    Args:
        redis_client: Redis client
        session_ttl: Session TTL in seconds

    Returns:
        SessionService instance
    """
    global _session_service

    _session_service = SessionService(redis_client, session_ttl)

    logger.info("Session service initialized", extra={"session_ttl": session_ttl})

    return _session_service


def get_session_service() -> SessionService:
    """
    Get session service (dependency).

    Returns:
        SessionService instance

    Raises:
        RuntimeError: If session service not initialized
    """
    if _session_service is None:
        raise RuntimeError("Session service not initialized")
    return _session_service


async def get_conversation_repository(
    session: AsyncSession = get_async_session
) -> ConversationRepository:
    """
    Get conversation repository (dependency).

    Args:
        session: Database session

    Returns:
        ConversationRepository instance
    """
    return ConversationRepository(session)


def get_conversation_service(
    session: AsyncSession = get_async_session
) -> ConversationService:
    """
    Get conversation service (dependency).

    This creates a new service instance for each request.

    Args:
        session: Database session

    Returns:
        ConversationService instance
    """
    settings = get_settings()
    conversation_repo = ConversationRepository(session)
    session_service = get_session_service()

    return ConversationService(
        settings=settings,
        conversation_repo=conversation_repo,
        session_service=session_service
    )


async def close_redis():
    """Close Redis connection."""
    global _redis_client

    if _redis_client:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis connection closed")
