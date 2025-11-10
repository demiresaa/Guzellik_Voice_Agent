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
import httpx

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
    conversation_agent_url=settings.CONVERSATION_AGENT_URL,
    api_key=settings.API_KEY
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info(
        f"Starting {settings.SERVICE_NAME} v{settings.SERVICE_VERSION}",
        extra={"port": settings.SERVICE_PORT, "env": settings.ENVIRONMENT}
    )

    # Initialize STT provider (loads model)
    try:
        logger.info("Initializing STT provider...")
        stt_provider = audio_handler.stt_provider
        await stt_provider.initialize()
        logger.info("STT provider initialized successfully.")
    except Exception as e:
        logger.critical(
            "Failed to initialize STT provider. Service will not work correctly.",
            extra={"error": str(e)}
        )
        # Depending on policy, you might want to exit here
        # raise SystemExit("STT Provider failed to load")

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
    3. Server creates a session with the Conversation Agent
    4. Client streams audio_chunk messages
    5. Server streams transcription_interim/final messages
    6. Server sends conversation_response messages
    7. Client sends end_session or disconnects
    """
    session_id: str = None
    
    # This will be a temporary ID until we get the real one from the conversation agent
    temp_id = f"temp_{id(websocket)}"
    await connection_manager.connect(temp_id, websocket)

    try:
        # Wait for start_session message from client
        init_message = await websocket.receive_json()
        if init_message.get("type") != WebSocketMessageType.START_SESSION:
            await connection_manager.close_connection(
                temp_id,
                code=1002,
                reason="Expected start_session message"
            )
            return

        logger.info("start_session received, creating session with conversation agent.", extra={"temp_id": temp_id})

        # Create a session with the conversation agent service
        real_session_id = None
        try:
            async with httpx.AsyncClient() as client:
                session_payload = {
                    "user_id": init_message.get("user_id"),
                    "phone_number": init_message.get("phone_number"),
                    "metadata": init_message.get("metadata", {})
                }
                headers = {"X-API-Key": settings.API_KEY}
                
                response = await client.post(
                    f"{settings.CONVERSATION_AGENT_URL}/api/conversation/session",
                    json=session_payload,
                    headers=headers,
                    timeout=10.0
                )
                response.raise_for_status()
                session_data = response.json()
                real_session_id = session_data.get("session_id")

                if not real_session_id:
                    raise Exception("No session_id in conversation agent response")

        except Exception as e:
            import traceback
            tb_str = traceback.format_exc()
            logger.error(f"Could not create session with conversation agent: {str(e)}\nTRACEBACK:\n{tb_str}")
            await connection_manager.send_error(temp_id, "SESSION_CREATION_FAILED", "Could not create conversation session.")
            await connection_manager.close_connection(temp_id, code=1011, reason="Session creation failed")
            return

        # We have a real session ID, re-register the connection with the correct ID
        session_id = real_session_id
        await connection_manager.re_register_connection(temp_id, session_id)
        
        logger.info(f"WebSocket connection established: {session_id}")

        # Send status
        await connection_manager.send_message(session_id, {
            "type": WebSocketMessageType.STATUS,
            "status": "connected",
            "message": "Connection established",
            "metadata": {"session_id": session_id}
        })

        # Create local voice session
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
                except WebSocketDisconnect:
                    logger.info(f"WebSocket disconnected during audio stream: {session_id}")
                    break

        # Callbacks for the audio handler
        async def on_transcription(chunk: TranscriptionChunk):
            message_type = WebSocketMessageType.TRANSCRIPTION_FINAL if chunk.is_final else WebSocketMessageType.TRANSCRIPTION_INTERIM
            await connection_manager.send_message(session_id, {"type": message_type, "text": chunk.text})

        async def on_response(response_text: str):
            await connection_manager.send_message(session_id, {"type": WebSocketMessageType.CONVERSATION_RESPONSE, "text": response_text})

        async def on_error(error: str):
            await connection_manager.send_error(session_id, "TRANSCRIPTION_ERROR", error)

        # Start audio stream handling
        await audio_handler.handle_audio_stream(
            audio_stream=audio_stream_generator(),
            session=session,
            on_transcription=on_transcription,
            on_response=on_response,
            on_error=on_error
        )

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id or temp_id}")

    except Exception as e:
        import traceback
        tb_str = traceback.format_exc()
        logger.error(
            f"WebSocket error: {session_id or temp_id}\nTRACEBACK:\n{tb_str}",
            extra={"error": str(e), "type": type(e).__name__}
        )
        if session_id or temp_id:
            try:
                await connection_manager.send_error(session_id or temp_id, "INTERNAL_ERROR", str(e))
            except:
                pass

    finally:
        # Cleanup
        final_id = session_id or temp_id
        await session_manager.end_session(final_id)
        await connection_manager.disconnect(final_id)
        logger.info(f"Session cleaned up: {final_id}")


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
    import os
    # Get the absolute path to the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Construct the full path to index.html
    file_path = os.path.join(script_dir, "static", "index.html")
    
    if not os.path.exists(file_path):
        logger.error(f"Could not find UI file at {file_path}")
        raise HTTPException(status_code=404, detail="Web UI file not found.")

    with open(file_path, "r", encoding="utf-8") as f:
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
