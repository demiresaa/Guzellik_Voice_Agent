"""
services/conversation_agent_service/app/services/session_service.py

Session Management Service

Manages user sessions using Redis for distributed session storage.
"""

import json
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from redis.asyncio import Redis

from shared.common.logging import get_logger
from shared.common.exceptions import NotFoundException, ValidationException

logger = get_logger(__name__)


class SessionService:
    """
    Session management service using Redis.

    Features:
    - Distributed session storage
    - Automatic expiration
    - Session metadata
    """

    def __init__(self, redis_client: Redis, session_ttl: int = 1800):
        """
        Initialize session service.

        Args:
            redis_client: Redis client
            session_ttl: Session TTL in seconds (default 30 minutes)
        """
        self.redis = redis_client
        self.session_ttl = session_ttl
        self.key_prefix = "session:"

    def _make_key(self, session_id: str) -> str:
        """Generate Redis key for session."""
        return f"{self.key_prefix}{session_id}"

    def generate_session_id(self) -> str:
        """
        Generate unique session ID.

        Returns:
            Secure random session ID
        """
        return f"sess_{secrets.token_urlsafe(32)}"

    async def create_session(
        self,
        user_id: Optional[str] = None,
        phone_number: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> tuple[str, datetime]:
        """
        Create new session.

        Args:
            user_id: User ID (optional)
            phone_number: Phone number (optional)
            metadata: Additional session metadata

        Returns:
            Tuple of (session_id, expires_at)
        """
        try:
            session_id = self.generate_session_id()
            expires_at = datetime.utcnow() + timedelta(seconds=self.session_ttl)

            session_data = {
                "session_id": session_id,
                "user_id": user_id,
                "phone_number": phone_number,
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": expires_at.isoformat(),
                "metadata": metadata or {}
            }

            # Store in Redis with TTL
            key = self._make_key(session_id)
            await self.redis.setex(
                key,
                self.session_ttl,
                json.dumps(session_data)
            )

            logger.info("Session created", extra={
                "session_id": session_id,
                "user_id": user_id,
                "ttl": self.session_ttl
            })

            return session_id, expires_at

        except Exception as e:
            logger.error("Failed to create session", extra={"error": str(e)})
            raise

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session data.

        Args:
            session_id: Session ID

        Returns:
            Session data or None if not found
        """
        try:
            key = self._make_key(session_id)
            data = await self.redis.get(key)

            if not data:
                logger.debug("Session not found", extra={"session_id": session_id})
                return None

            session_data = json.loads(data)

            logger.debug("Session retrieved", extra={"session_id": session_id})

            return session_data

        except json.JSONDecodeError as e:
            logger.error("Failed to parse session data", extra={
                "session_id": session_id,
                "error": str(e)
            })
            return None

        except Exception as e:
            logger.error("Failed to get session", extra={
                "session_id": session_id,
                "error": str(e)
            })
            raise

    async def update_session(
        self,
        session_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        Update session data.

        Args:
            session_id: Session ID
            updates: Fields to update

        Returns:
            True if updated, False if session not found
        """
        try:
            session_data = await self.get_session(session_id)

            if not session_data:
                return False

            # Update fields
            session_data.update(updates)

            # Store back in Redis
            key = self._make_key(session_id)
            await self.redis.setex(
                key,
                self.session_ttl,
                json.dumps(session_data)
            )

            logger.debug("Session updated", extra={
                "session_id": session_id,
                "updates": list(updates.keys())
            })

            return True

        except Exception as e:
            logger.error("Failed to update session", extra={
                "session_id": session_id,
                "error": str(e)
            })
            raise

    async def refresh_session(self, session_id: str) -> bool:
        """
        Refresh session TTL (extend expiration).

        Args:
            session_id: Session ID

        Returns:
            True if refreshed, False if session not found
        """
        try:
            key = self._make_key(session_id)
            result = await self.redis.expire(key, self.session_ttl)

            if result:
                logger.debug("Session TTL refreshed", extra={"session_id": session_id})
            else:
                logger.debug("Session not found for refresh", extra={"session_id": session_id})

            return result == 1

        except Exception as e:
            logger.error("Failed to refresh session", extra={
                "session_id": session_id,
                "error": str(e)
            })
            raise

    async def delete_session(self, session_id: str) -> bool:
        """
        Delete session.

        Args:
            session_id: Session ID

        Returns:
            True if deleted, False if session not found
        """
        try:
            key = self._make_key(session_id)
            result = await self.redis.delete(key)

            if result:
                logger.info("Session deleted", extra={"session_id": session_id})
            else:
                logger.debug("Session not found for deletion", extra={"session_id": session_id})

            return result > 0

        except Exception as e:
            logger.error("Failed to delete session", extra={
                "session_id": session_id,
                "error": str(e)
            })
            raise

    async def validate_session(self, session_id: str) -> bool:
        """
        Check if session exists and is valid.

        Args:
            session_id: Session ID

        Returns:
            True if valid, False otherwise
        """
        session = await self.get_session(session_id)
        return session is not None

    async def get_session_ttl(self, session_id: str) -> Optional[int]:
        """
        Get remaining TTL for session.

        Args:
            session_id: Session ID

        Returns:
            Remaining seconds or None if session not found
        """
        try:
            key = self._make_key(session_id)
            ttl = await self.redis.ttl(key)

            if ttl < 0:  # -2 = key doesn't exist, -1 = no expiration
                return None

            return ttl

        except Exception as e:
            logger.error("Failed to get session TTL", extra={
                "session_id": session_id,
                "error": str(e)
            })
            raise
