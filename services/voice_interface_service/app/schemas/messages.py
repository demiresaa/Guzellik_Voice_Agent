"""
WebSocket Message Schemas

Defines message types for WebSocket communication.
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from enum import Enum


class WebSocketMessageType(str, Enum):
    """WebSocket message types."""
    # Client → Server
    AUDIO_CHUNK = "audio_chunk"
    START_SESSION = "start_session"
    END_SESSION = "end_session"
    PAUSE = "pause"
    RESUME = "resume"

    # Server → Client
    TRANSCRIPTION_INTERIM = "transcription_interim"  # Partial result
    TRANSCRIPTION_FINAL = "transcription_final"      # Final result
    CONVERSATION_RESPONSE = "conversation_response"  # LLM response
    ERROR = "error"
    STATUS = "status"
    PING = "ping"
    PONG = "pong"


# Client → Server Messages

class AudioChunkMessage(BaseModel):
    """
    Audio chunk from client.

    Sent continuously as user speaks.
    """
    type: Literal[WebSocketMessageType.AUDIO_CHUNK] = WebSocketMessageType.AUDIO_CHUNK
    data: str = Field(description="Base64-encoded audio data")
    sequence: int = Field(description="Chunk sequence number")
    timestamp: float = Field(description="Client timestamp")


class StartSessionMessage(BaseModel):
    """
    Start voice session.

    Sent when user starts speaking.
    """
    type: Literal[WebSocketMessageType.START_SESSION] = WebSocketMessageType.START_SESSION
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID (server will generate if not provided)"
    )
    language: str = Field(default="tr", description="Language code")
    phone_number: Optional[str] = Field(
        default=None,
        description="User phone number (for conversation context)"
    )
    metadata: dict = Field(default_factory=dict)


class EndSessionMessage(BaseModel):
    """
    End voice session.

    Sent when user disconnects or session ends.
    """
    type: Literal[WebSocketMessageType.END_SESSION] = WebSocketMessageType.END_SESSION
    session_id: str


# Server → Client Messages

class TranscriptionResultMessage(BaseModel):
    """
    Transcription result (interim or final).

    Sent as speech is transcribed.
    """
    type: Literal[
        WebSocketMessageType.TRANSCRIPTION_INTERIM,
        WebSocketMessageType.TRANSCRIPTION_FINAL
    ]
    text: str = Field(description="Transcribed text")
    is_final: bool = Field(description="Whether this is the final result")
    confidence: Optional[float] = Field(default=None)
    language: Optional[str] = Field(default=None)
    sequence: int = Field(default=0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ConversationResponseMessage(BaseModel):
    """
    Conversation agent response.

    Sent after transcription, contains LLM response.
    """
    type: Literal[WebSocketMessageType.CONVERSATION_RESPONSE] = WebSocketMessageType.CONVERSATION_RESPONSE
    text: str = Field(description="LLM response text")
    session_id: str
    action: Optional[str] = Field(
        default=None,
        description="Action taken (e.g., booking_created, appointment_confirmed)"
    )
    metadata: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorMessage(BaseModel):
    """
    Error message.

    Sent when an error occurs.
    """
    type: Literal[WebSocketMessageType.ERROR] = WebSocketMessageType.ERROR
    error_code: str
    error_message: str
    details: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class StatusMessage(BaseModel):
    """
    Status update message.

    Sent to inform client of system status.
    """
    type: Literal[WebSocketMessageType.STATUS] = WebSocketMessageType.STATUS
    status: str = Field(
        description="Status (connected, listening, speaking, processing, etc.)"
    )
    message: Optional[str] = Field(default=None)
    metadata: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
