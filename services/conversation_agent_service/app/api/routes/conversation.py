"""
services/conversation_agent_service/app/api/routes/conversation.py

Conversation API Routes

Endpoints for conversation management and SSE streaming.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from shared.database import get_async_session
from shared.security import require_api_key
from shared.common.logging import get_logger
from shared.common.models import BaseResponse

from app.schemas.conversation import (
    ConversationRequest,
    ConversationHistoryResponse,
    SessionCreateRequest,
    SessionResponse,
    SessionDeleteResponse,
    MessageSchema
)
from app.services.conversation_service import ConversationService
from app.services.session_service import SessionService
from app.repositories.conversation_repository import ConversationRepository
from app.dependencies import get_conversation_service, get_session_service

logger = get_logger(__name__)

router = APIRouter(prefix="/api/conversation", tags=["conversation"])


@router.post("/stream", response_model=None)
async def stream_conversation(
    request: ConversationRequest,
    conversation_service: ConversationService = Depends(get_conversation_service),
    api_key: str = Depends(require_api_key)
) -> StreamingResponse:
    """
    Process conversation with SSE streaming.

    **Security:** Requires API key authentication

    **Request:**
    ```json
    {
        "session_id": "sess_abc123",
        "message": "Yarın saat 14:00 için randevu almak istiyorum",
        "phone_number": "05321234567"
    }
    ```

    **Response:** Server-Sent Events (text/event-stream)

    **Events:**
    - `status`: Status updates (e.g., "İşleniyor...")
    - `tool_call`: Tool execution notifications
    - `token`: LLM response tokens (streaming)
    - `done`: Conversation completed
    - `error`: Error occurred

    **Example:**
    ```
    event: status
    data: {"message": "İşleniyor..."}

    event: tool_call
    data: {"tool": "get_customer_info", "status": "running"}

    event: token
    data: {"token": "Merhaba"}

    event: token
    data: {"token": " Ayşe"}

    event: done
    data: {"session_id": "sess_abc123", "latency_ms": 1234}
    ```
    """
    logger.info("SSE conversation stream requested", extra={
        "session_id": request.session_id,
        "user_id": request.user_id
    })

    async def event_generator():
        """Generate SSE events."""
        try:
            async for sse_message in conversation_service.process_message_stream(
                session_id=request.session_id,
                user_message=request.message,
                user_id=request.user_id,
                phone_number=request.phone_number,
                metadata=request.metadata
            ):
                yield sse_message

        except Exception as e:
            logger.error("Stream error", extra={
                "session_id": request.session_id,
                "error": str(e)
            })
            # Send error event
            error_event = f"event: error\ndata: {{\"code\": \"STREAM_ERROR\", \"message\": \"{str(e)}\"}}\n\n"
            yield error_event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@router.get("/history/{session_id}", response_model=ConversationHistoryResponse)
async def get_conversation_history(
    session_id: str,
    session: AsyncSession = Depends(get_async_session),
    api_key: str = Depends(require_api_key)
):
    """
    Get conversation history by session ID.

    **Security:** Requires API key authentication

    **Returns:** Conversation with all messages
    """
    repo = ConversationRepository(session)

    conversation = await repo.find_by_session_id(session_id, include_messages=True)

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Convert messages to schema
    messages_schema = [
        MessageSchema(
            role=msg.role,
            content=msg.content,
            tool_calls=msg.tool_calls,
            tool_results=msg.tool_results,
            created_at=msg.created_at
        )
        for msg in conversation.messages
    ]

    return ConversationHistoryResponse(
        success=True,
        session_id=conversation.session_id,
        messages=messages_schema,
        total_messages=conversation.total_messages,
        total_tokens=conversation.total_tokens_used,
        created_at=conversation.created_at,
        ended_at=conversation.ended_at,
        is_active=conversation.is_active
    )


@router.post("/session", response_model=SessionResponse)
async def create_session(
    request: SessionCreateRequest,
    session_service: SessionService = Depends(get_session_service),
    api_key: str = Depends(require_api_key)
):
    """
    Create new conversation session.

    **Security:** Requires API key authentication

    **Returns:** Session ID and expiration
    """
    session_id, expires_at = await session_service.create_session(
        user_id=request.user_id,
        phone_number=request.phone_number,
        metadata=request.metadata
    )

    logger.info("Session created", extra={
        "session_id": session_id,
        "user_id": request.user_id
    })

    return SessionResponse(
        success=True,
        session_id=session_id,
        expires_at=expires_at,
        metadata=request.metadata
    )


@router.delete("/session/{session_id}", response_model=SessionDeleteResponse)
async def delete_session(
    session_id: str,
    session: AsyncSession = Depends(get_async_session),
    session_service: SessionService = Depends(get_session_service),
    api_key: str = Depends(require_api_key)
):
    """
    Delete conversation session and end conversation.

    **Security:** Requires API key authentication

    **Returns:** Deletion confirmation
    """
    # End conversation in database
    repo = ConversationRepository(session)
    conversation = await repo.find_active_by_session(session_id)

    if conversation:
        await repo.end_conversation(conversation.id)

    # Delete session from Redis
    deleted = await session_service.delete_session(session_id)

    logger.info("Session deleted", extra={
        "session_id": session_id,
        "deleted": deleted
    })

    return SessionDeleteResponse(
        success=True,
        message="Session deleted successfully" if deleted else "Session not found",
        session_id=session_id
    )


@router.get("/session/{session_id}/status")
async def get_session_status(
    session_id: str,
    session_service: SessionService = Depends(get_session_service),
    api_key: str = Depends(require_api_key)
):
    """
    Get session status and remaining TTL.

    **Security:** Requires API key authentication

    **Returns:** Session validity and TTL
    """
    session_data = await session_service.get_session(session_id)

    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    ttl = await session_service.get_session_ttl(session_id)

    return BaseResponse(
        success=True,
        message="Session is active",
        data={
            "session_id": session_id,
            "is_active": True,
            "remaining_seconds": ttl,
            "user_id": session_data.get("user_id"),
            "phone_number": session_data.get("phone_number")
        }
    )
