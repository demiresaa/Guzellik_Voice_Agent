"""
services/conversation_agent_service/app/schemas/conversation.py

Request/Response Schemas for Conversation Endpoints
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.models.conversation import MessageRole


class MessageSchema(BaseModel):
    """Single message in conversation."""
    role: MessageRole = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    tool_calls: Optional[Dict[str, Any]] = Field(None, description="Tool calls")
    tool_results: Optional[Dict[str, Any]] = Field(None, description="Tool results")
    created_at: Optional[datetime] = Field(None, description="Message timestamp")

    class Config:
        from_attributes = True


class ConversationRequest(BaseModel):
    """Request to continue conversation (synchronous or streaming)."""

    session_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Session ID for conversation tracking"
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="User message text"
    )
    user_id: Optional[str] = Field(
        None,
        description="User ID (if authenticated)"
    )
    phone_number: Optional[str] = Field(
        None,
        pattern=r"^05\d{9}$",
        description="Turkish phone number (05XXXXXXXXX)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional request metadata"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "sess_abc123xyz",
                "message": "Yarın saat 14:00 için randevu almak istiyorum",
                "phone_number": "05321234567",
                "metadata": {"channel": "voice", "language": "tr"}
            }
        }


class ConversationResponse(BaseModel):
    """Synchronous conversation response."""

    success: bool = Field(..., description="Whether request succeeded")
    session_id: str = Field(..., description="Session ID")
    message: str = Field(..., description="Assistant response")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Tools called during processing"
    )
    tokens_used: Optional[int] = Field(
        None,
        description="Tokens consumed by LLM"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional response metadata"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "session_id": "sess_abc123xyz",
                "message": "Elbette! Yarın 14:00 için müsaitlik kontrolü yapıyorum...",
                "tool_calls": [
                    {"tool": "check_availability", "status": "success"}
                ],
                "tokens_used": 245
            }
        }


class ConversationHistoryResponse(BaseModel):
    """Conversation history response."""

    success: bool = Field(default=True, description="Whether request succeeded")
    session_id: str = Field(..., description="Session ID")
    messages: List[MessageSchema] = Field(..., description="Conversation messages")
    total_messages: int = Field(..., description="Total message count")
    total_tokens: int = Field(..., description="Total tokens used")
    created_at: datetime = Field(..., description="Conversation start time")
    ended_at: Optional[datetime] = Field(None, description="Conversation end time")
    is_active: bool = Field(..., description="Whether conversation is active")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "session_id": "sess_abc123xyz",
                "messages": [
                    {
                        "role": "user",
                        "content": "Merhaba, randevu almak istiyorum",
                        "created_at": "2025-10-29T12:00:00Z"
                    },
                    {
                        "role": "assistant",
                        "content": "Merhaba! Size nasıl yardımcı olabilirim?",
                        "created_at": "2025-10-29T12:00:02Z"
                    }
                ],
                "total_messages": 2,
                "total_tokens": 150,
                "created_at": "2025-10-29T12:00:00Z",
                "is_active": True
            }
        }


class SessionCreateRequest(BaseModel):
    """Request to create new session."""

    user_id: Optional[str] = Field(None, description="User ID (if authenticated)")
    phone_number: Optional[str] = Field(
        None,
        pattern=r"^05\d{9}$",
        description="Turkish phone number"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional session metadata"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "phone_number": "05321234567",
                "metadata": {"channel": "voice", "language": "tr"}
            }
        }


class SessionResponse(BaseModel):
    """Session creation/info response."""

    success: bool = Field(default=True, description="Whether request succeeded")
    session_id: str = Field(..., description="Session ID")
    expires_at: datetime = Field(..., description="Session expiration time")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Session metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "session_id": "sess_abc123xyz",
                "expires_at": "2025-10-29T12:30:00Z",
                "metadata": {"channel": "voice"}
            }
        }


class SessionDeleteResponse(BaseModel):
    """Session deletion response."""

    success: bool = Field(default=True, description="Whether deletion succeeded")
    message: str = Field(..., description="Status message")
    session_id: str = Field(..., description="Deleted session ID")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Session deleted successfully",
                "session_id": "sess_abc123xyz"
            }
        }
