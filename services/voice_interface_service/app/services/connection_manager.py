"""
services/voice_interface_service/app/services/connection_manager.py

WebSocket Connection Manager

Manages active WebSocket connections with concurrent session limits.
"""

from typing import Dict, Optional
from fastapi import WebSocket
import asyncio
from datetime import datetime

from shared.common.logging import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections.

    Features:
    - Connection tracking
    - Concurrent connection limits
    - Broadcast messaging
    - Graceful disconnection
    """

    def __init__(self, max_connections: int = 100):
        """
        Initialize connection manager.

        Args:
            max_connections: Maximum concurrent connections
        """
        self.max_connections = max_connections
        self.active_connections: Dict[str, WebSocket] = {}
        self._lock = asyncio.Lock()

        logger.info(
            "Connection manager initialized",
            extra={"max_connections": max_connections}
        )

    async def connect(self, session_id: str, websocket: WebSocket) -> bool:
        """
        Register new WebSocket connection.

        Args:
            session_id: Unique session ID
            websocket: WebSocket connection

        Returns:
            True if connected, False if limit reached
        """
        async with self._lock:
            # Check limit
            if len(self.active_connections) >= self.max_connections:
                logger.warning(
                    "Connection limit reached",
                    extra={
                        "session_id": session_id,
                        "active": len(self.active_connections),
                        "limit": self.max_connections
                    }
                )
                return False

            # Accept connection
            await websocket.accept()
            self.active_connections[session_id] = websocket

            logger.info(
                "Connection established",
                extra={
                    "session_id": session_id,
                    "total_connections": len(self.active_connections)
                }
            )

            return True

    async def disconnect(self, session_id: str) -> None:
        """
        Remove WebSocket connection.

        Args:
            session_id: Session ID to disconnect
        """
        async with self._lock:
            if session_id in self.active_connections:
                websocket = self.active_connections[session_id]

                try:
                    await websocket.close()
                except Exception as e:
                    logger.warning(
                        "Error closing WebSocket",
                        extra={"session_id": session_id, "error": str(e)}
                    )

                del self.active_connections[session_id]

                logger.info(
                    "Connection closed",
                    extra={
                        "session_id": session_id,
                        "remaining_connections": len(self.active_connections)
                    }
                )

    async def send_message(self, session_id: str, message: dict) -> bool:
        """
        Send message to specific connection.

        Args:
            session_id: Target session ID
            message: Message dictionary (will be JSON-encoded)

        Returns:
            True if sent, False if failed
        """
        if session_id not in self.active_connections:
            logger.warning(
                "Attempted to send to non-existent session",
                extra={"session_id": session_id}
            )
            return False

        websocket = self.active_connections[session_id]

        try:
            await websocket.send_json(message)
            return True

        except Exception as e:
            logger.error(
                "Failed to send message",
                extra={
                    "session_id": session_id,
                    "error": str(e),
                    "message_type": message.get("type")
                }
            )
            # Connection is broken, disconnect
            await self.disconnect(session_id)
            return False

    async def broadcast(self, message: dict, exclude: Optional[str] = None) -> int:
        """
        Broadcast message to all connections.

        Args:
            message: Message to broadcast
            exclude: Optional session ID to exclude

        Returns:
            Number of successful sends
        """
        count = 0
        failed_sessions = []

        for session_id, websocket in list(self.active_connections.items()):
            if session_id == exclude:
                continue

            try:
                await websocket.send_json(message)
                count += 1
            except Exception as e:
                logger.error(
                    "Broadcast failed",
                    extra={"session_id": session_id, "error": str(e)}
                )
                failed_sessions.append(session_id)

        # Cleanup failed connections
        for session_id in failed_sessions:
            await self.disconnect(session_id)

        return count

    def get_connection(self, session_id: str) -> Optional[WebSocket]:
        """
        Get WebSocket connection by session ID.

        Args:
            session_id: Session ID

        Returns:
            WebSocket if exists, None otherwise
        """
        return self.active_connections.get(session_id)

    def is_connected(self, session_id: str) -> bool:
        """Check if session is connected."""
        return session_id in self.active_connections

    @property
    def connection_count(self) -> int:
        """Get active connection count."""
        return len(self.active_connections)

    async def cleanup_all(self) -> None:
        """Disconnect all connections (shutdown)."""
        logger.info("Cleaning up all connections")

        for session_id in list(self.active_connections.keys()):
            await self.disconnect(session_id)

        logger.info("All connections closed")
