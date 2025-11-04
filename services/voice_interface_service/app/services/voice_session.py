"""
services/voice_interface_service/app/services/voice_session.py

Voice Session Management

Manages individual voice sessions with state tracking and lifecycle management.
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
import uuid

from shared.common.logging import get_logger
from shared.speech_to_text.streaming import StreamState

logger = get_logger(__name__)


class SessionStatus(str, Enum):
    """Session status."""
    CREATED = "created"
    ACTIVE = "active"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    PROCESSING = "processing"
    PAUSED = "paused"
    ENDED = "ended"
    ERROR = "error"


@dataclass
class VoiceSession:
    """
    Represents a single voice interaction session.

    Tracks session state, metadata, and conversation context.
    """
    session_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: SessionStatus = SessionStatus.CREATED
    language: str = "tr"
    phone_number: Optional[str] = None

    # Session tracking
    last_activity: datetime = field(default_factory=datetime.utcnow)
    transcription_count: int = 0
    message_count: int = 0

    # Context
    conversation_history: list = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Conversation agent session
    agent_session_id: Optional[str] = None

    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.utcnow()

    def is_expired(self, timeout_seconds: int = 300) -> bool:
        """
        Check if session is expired.

        Args:
            timeout_seconds: Timeout in seconds

        Returns:
            True if expired
        """
        elapsed = (datetime.utcnow() - self.last_activity).total_seconds()
        return elapsed > timeout_seconds

    def add_transcription(self, text: str, is_final: bool = True) -> None:
        """
        Add transcription to session.

        Args:
            text: Transcribed text
            is_final: Whether this is final result
        """
        if is_final:
            self.transcription_count += 1
            self.conversation_history.append({
                "type": "user",
                "text": text,
                "timestamp": datetime.utcnow().isoformat()
            })
        self.update_activity()

    def add_response(self, text: str) -> None:
        """
        Add AI response to session.

        Args:
            text: Response text
        """
        self.message_count += 1
        self.conversation_history.append({
            "type": "assistant",
            "text": text,
            "timestamp": datetime.utcnow().isoformat()
        })
        self.update_activity()

    def to_dict(self) -> dict:
        """Convert session to dictionary."""
        return {
            "session_id": self.session_id,
            "status": self.status.value,
            "language": self.language,
            "phone_number": self.phone_number,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "transcription_count": self.transcription_count,
            "message_count": self.message_count,
            "metadata": self.metadata
        }


class VoiceSessionManager:
    """
    Manages multiple voice sessions.

    Features:
    - Session creation and lifecycle
    - Session cleanup (timeout)
    - Session retrieval
    """

    def __init__(self, session_timeout: int = 300):
        """
        Initialize session manager.

        Args:
            session_timeout: Session timeout in seconds
        """
        self.session_timeout = session_timeout
        self.sessions: Dict[str, VoiceSession] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None

        logger.info(
            "Session manager initialized",
            extra={"timeout": session_timeout}
        )

    async def create_session(
        self,
        session_id: Optional[str] = None,
        language: str = "tr",
        phone_number: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> VoiceSession:
        """
        Create new voice session.

        Args:
            session_id: Optional session ID (generated if not provided)
            language: Language code
            phone_number: User phone number
            metadata: Additional metadata

        Returns:
            Created VoiceSession
        """
        if session_id is None:
            session_id = str(uuid.uuid4())

        async with self._lock:
            session = VoiceSession(
                session_id=session_id,
                language=language,
                phone_number=phone_number,
                metadata=metadata or {}
            )
            self.sessions[session_id] = session

            logger.info(
                "Session created",
                extra={
                    "session_id": session_id,
                    "language": language,
                    "total_sessions": len(self.sessions)
                }
            )

            return session

    async def get_session(self, session_id: str) -> Optional[VoiceSession]:
        """
        Get session by ID.

        Args:
            session_id: Session ID

        Returns:
            VoiceSession if exists, None otherwise
        """
        return self.sessions.get(session_id)

    async def update_session_status(
        self,
        session_id: str,
        status: SessionStatus
    ) -> bool:
        """
        Update session status.

        Args:
            session_id: Session ID
            status: New status

        Returns:
            True if updated, False if not found
        """
        session = await self.get_session(session_id)
        if not session:
            return False

        old_status = session.status
        session.status = status
        session.update_activity()

        logger.debug(
            "Session status updated",
            extra={
                "session_id": session_id,
                "old_status": old_status.value,
                "new_status": status.value
            }
        )

        return True

    async def end_session(self, session_id: str) -> bool:
        """
        End session.

        Args:
            session_id: Session ID

        Returns:
            True if ended, False if not found
        """
        async with self._lock:
            session = self.sessions.get(session_id)
            if not session:
                return False

            session.status = SessionStatus.ENDED
            session.update_activity()

            logger.info(
                "Session ended",
                extra={
                    "session_id": session_id,
                    "duration_seconds": (
                        datetime.utcnow() - session.created_at
                    ).total_seconds(),
                    "transcriptions": session.transcription_count,
                    "messages": session.message_count
                }
            )

            # Remove from active sessions
            del self.sessions[session_id]

            return True

    async def cleanup_expired_sessions(self) -> int:
        """
        Remove expired sessions.

        Returns:
            Number of sessions cleaned up
        """
        async with self._lock:
            expired = [
                session_id
                for session_id, session in self.sessions.items()
                if session.is_expired(self.session_timeout)
            ]

            for session_id in expired:
                logger.info(
                    "Session expired",
                    extra={"session_id": session_id}
                )
                del self.sessions[session_id]

            if expired:
                logger.info(
                    "Expired sessions cleaned up",
                    extra={
                        "count": len(expired),
                        "remaining": len(self.sessions)
                    }
                )

            return len(expired)

    async def start_cleanup_task(self, interval: int = 60) -> None:
        """
        Start background cleanup task.

        Args:
            interval: Cleanup interval in seconds
        """
        if self._cleanup_task:
            logger.warning("Cleanup task already running")
            return

        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(interval)
                    await self.cleanup_expired_sessions()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(
                        "Cleanup task error",
                        extra={"error": str(e)}
                    )

        self._cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info("Cleanup task started", extra={"interval": interval})

    async def stop_cleanup_task(self) -> None:
        """Stop background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("Cleanup task stopped")

    @property
    def session_count(self) -> int:
        """Get active session count."""
        return len(self.sessions)

    def get_all_sessions(self) -> list[VoiceSession]:
        """Get all active sessions."""
        return list(self.sessions.values())
