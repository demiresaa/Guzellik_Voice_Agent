"""
services/voice_interface_service/main.py

Voice Interface Service - Real-Time AI Voice Assistant

Provides real-time voice interaction via WebSocket:
- Audio streaming
- Real-time STT (Speech-to-Text)
- Conversation agent integration
- Live transcription updates
"""

import asyncio
import base64
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import uvicorn

from shared.common.logging import get_logger, setup_logging
from shared.speech_to_text.streaming import TranscriptionChunk

from .config import get_settings
from .app.services import (
    ConnectionManager,
    VoiceSessionManager,
    AudioStreamHandler
)
from .app.schemas import (
    WebSocketMessageType,
    TranscriptionResultMessage,
    ConversationResponseMessage,
    ErrorMessage,
    StatusMessage
)

# Initializ
settings = get_settings()
setup_logging(settings.SERVICE_NAME)
logger = get_logger(__name__)

# Global managers
connection_manager = ConnectionManager(
    max_connections=settings.MAX_CONCURRENT_SESSIONS
)
session_manager = VoiceSessionManager(
    session_timeout=settings.SESSION_TIMEOUT_SECONDS
)
audio_handler = AudioStreamHandler(
    conversation_agent_url=settings.CONVERSATION_AGENT_URL
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info(
        f"Starting {settings.SERVICE_NAME} v{settings.SERVICE_VERSION}",
        extra={"port": settings.SERVICE_PORT, "env": settings.ENVIRONMENT}
    )

    # Start session cleanup task
    await session_manager.start_cleanup_task(interval=60)

    yield

    # Shutdown
    logger.info("Shutting down...")
    await session_manager.stop_cleanup_task()
    await connection_manager.cleanup_all()
    await audio_handler.cleanup()
    logger.info("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Voice Interface Service",
    description="Real-Time AI Voice Assistant",
    version=settings.SERVICE_VERSION,
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# WebSocket Endpoint
@app.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    """
    Real-time voice WebSocket endpoint.

    Protocol:
    1. Client connects
    2. Client sends start_session message
    3. Client streams audio_chunk messages
    4. Server streams transcription_interim/final messages
    5. Server sends conversation_response messages
    6. Client sends end_session or disconnects
    """
    session_id: str = None

    try:
        # Generate session ID
        import uuid
        session_id = str(uuid.uuid4())

        # Connect
        connected = await connection_manager.connect(session_id, websocket)
        if not connected:
            await websocket.close(code=1008, reason="Server at capacity")
            return

        logger.info(f"WebSocket connection established: {session_id}")

        # Send status
        await connection_manager.send_message(session_id, {
            "type": WebSocketMessageType.STATUS,
            "status": "connected",
            "message": "Connection established",
            "metadata": {"session_id": session_id}
        })

        # Wait for start_session message
        init_message = await websocket.receive_json()

        if init_message.get("type") != WebSocketMessageType.START_SESSION:
            await websocket.close(code=1002, reason="Expected start_session message")
            return

        # Create session
        session = await session_manager.create_session(
            session_id=session_id,
            language=init_message.get("language", "tr"),
            phone_number=init_message.get("phone_number"),
            metadata=init_message.get("metadata", {})
        )

        logger.info(
            "Voice session started",
            extra={
                "session_id": session_id,
                "language": session.language,
                "phone": session.phone_number
            }
        )

        # Send listening status
        await connection_manager.send_message(session_id, {
            "type": WebSocketMessageType.STATUS,
            "status": "listening",
            "message": "Ready to receive audio"
        })

        # Audio stream generator
        async def audio_stream_generator() -> AsyncIterator[bytes]:
            """Generate audio stream from WebSocket messages."""
            while True:
                try:
                    message = await websocket.receive_json()

                    if message.get("type") == WebSocketMessageType.AUDIO_CHUNK:
                        # Decode base64 audio data
                        audio_data_b64 = message.get("data")
                        if audio_data_b64:
                            audio_bytes = base64.b64decode(audio_data_b64)
                            yield audio_bytes

                    elif message.get("type") == WebSocketMessageType.END_SESSION:
                        logger.info(f"End session requested: {session_id}")
                        break

                    elif message.get("type") == WebSocketMessageType.PAUSE:
                        logger.debug(f"Session paused: {session_id}")
                        # TODO: Implement pause logic

                    elif message.get("type") == WebSocketMessageType.RESUME:
                        logger.debug(f"Session resumed: {session_id}")
                        # TODO: Implement resume logic

                except WebSocketDisconnect:
                    logger.info(f"WebSocket disconnected: {session_id}")
                    break

        # Transcription callback
        async def on_transcription(chunk: TranscriptionChunk):
            """Handle transcription results."""
            message_type = (
                WebSocketMessageType.TRANSCRIPTION_FINAL
                if chunk.is_final
                else WebSocketMessageType.TRANSCRIPTION_INTERIM
            )

            await connection_manager.send_message(session_id, {
                "type": message_type,
                "text": chunk.text,
                "is_final": chunk.is_final,
                "confidence": chunk.confidence,
                "language": chunk.language,
                "sequence": chunk.sequence
            })

        # Response callback
        async def on_response(response_text: str):
            """Handle conversation responses."""
            await connection_manager.send_message(session_id, {
                "type": WebSocketMessageType.CONVERSATION_RESPONSE,
                "text": response_text,
                "session_id": session_id
            })

        # Error callback
        async def on_error(error: str):
            """Handle errors."""
            await connection_manager.send_message(session_id, {
                "type": WebSocketMessageType.ERROR,
                "error_code": "TRANSCRIPTION_ERROR",
                "error_message": error
            })

        # Start audio stream handling
        await audio_handler.handle_audio_stream(
            audio_stream=audio_stream_generator(),
            session=session,
            on_transcription=on_transcription,
            on_response=on_response,
            on_error=on_error
        )

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")

    except Exception as e:
        logger.error(
            f"WebSocket error: {session_id}",
            extra={"error": str(e), "type": type(e).__name__}
        )

        if session_id:
            try:
                await connection_manager.send_message(session_id, {
                    "type": WebSocketMessageType.ERROR,
                    "error_code": "INTERNAL_ERROR",
                    "error_message": str(e)
                })
            except:
                pass

    finally:
        # Cleanup
        if session_id:
            await session_manager.end_session(session_id)
            await connection_manager.disconnect(session_id)
            logger.info(f"Session cleaned up: {session_id}")


# Health Check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    from shared.speech_to_text import get_stt_provider

    stt = get_stt_provider()
    stt_health = await stt.health_check()

    return {
        "service": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "status": "healthy",
        "checks": {
            "stt": {
                "provider": stt_health.provider,
                "healthy": stt_health.is_healthy,
                "model_loaded": stt_health.model_loaded
            },
            "connections": {
                "active": connection_manager.connection_count,
                "max": settings.MAX_CONCURRENT_SESSIONS
            },
            "sessions": {
                "active": session_manager.session_count
            }
        }
    }


# Web UI (Simple test page)
@app.get("/", response_class=HTMLResponse)
async def get_web_ui():
    """Serve simple web UI for testing."""
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()


# Main
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.SERVICE_PORT,
        log_level=settings.LOG_LEVEL.lower(),
        reload=settings.ENVIRONMENT == "development"
    )
