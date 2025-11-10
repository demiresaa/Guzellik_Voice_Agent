"""
services/voice_interface_service/app/services/connection_manager.py

WebSocket Connection Manager

Manages active WebSocket connections with concurrent session limits.
"""

from typing import Dict, Optional
from fastapi import WebSocket
import asyncio
from typing import Dict, List
from fastapi import WebSocket, WebSocketDisconnect

from shared.common.logging import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """
    Manages active WebSocket connections.

    Ensures thread-safe access to connections and handles connection
    limits, broadcasting, and cleanup.
    """

    def __init__(self, max_connections: int = 100):
        """
        Initialize connection manager.

        Args:
            max_connections: Maximum number of concurrent connections
        """
        self.max_connections = max_connections
        self.active_connections: Dict[str, WebSocket] = {}
        self._lock = asyncio.Lock()
        self._logger = logger  # Initialize logger for the instance

        self._logger.info(f"Connection manager initialized with max_connections={max_connections}")

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

    async def re_register_connection(self, old_id: str, new_id: str):
        """Re-register a connection with a new session ID."""
        async with self._lock:
            if old_id in self.active_connections:
                websocket = self.active_connections.pop(old_id)
                self.active_connections[new_id] = websocket
                self._logger.info(f"Connection re-registered from {old_id} to {new_id}")
            else:
                self._logger.warning(f"Attempted to re-register a non-existent connection: {old_id}")

    async def send_error(self, session_id: str, code: str, message: str):
        """Send an error message to a specific client."""
        await self.send_message(session_id, {
            "type": "error",
            "error_code": code,
            "error_message": message
        })

    async def send_message(self, session_id: str, message: dict):
        """Send a JSON message to a specific client."""
        async with self._lock:
            websocket = self.active_connections.get(session_id)
        
        if websocket:
            try:
                await websocket.send_json(message)
            except WebSocketDisconnect:
                self._logger.warning(f"Tried to send to a disconnected client: {session_id}")
                await self.disconnect(session_id)
        else:
            self._logger.warning(f"No active connection found for session_id: {session_id}")


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
