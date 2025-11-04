"""
services/voice_interface_service/app/services/audio_handler.py

Real-Time Audio Stream Handler

Handles incoming audio streams, coordinates STT, and manages transcription flow.
"""

import asyncio
import base64
from typing import AsyncIterator, Optional, Callable
import httpx

from shared.common.logging import get_logger
from shared.speech_to_text import get_stt_provider
from shared.speech_to_text.streaming import TranscriptionChunk

from .voice_session import VoiceSession, SessionStatus

logger = get_logger(__name__)


class AudioStreamHandler:
    """
    Handles real-time audio streaming and transcription.

    Coordinates:
    - Audio data reception
    - STT streaming
    - Transcription result handling
    - Conversation agent integration
    """

    def __init__(
        self,
        conversation_agent_url: str = "http://localhost:8002"
    ):
        """
        Initialize audio stream handler.

        Args:
            conversation_agent_url: URL of conversation agent service
        """
        self.stt_provider = get_stt_provider()
        self.conversation_agent_url = conversation_agent_url
        self.http_client = httpx.AsyncClient(timeout=30.0)

        logger.info(
            "Audio stream handler initialized",
            extra={
                "stt_provider": self.stt_provider.provider_name,
                "conversation_agent": conversation_agent_url
            }
        )

    async def handle_audio_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        session: VoiceSession,
        on_transcription: Callable,
        on_response: Callable,
        on_error: Callable
    ) -> None:
        """
        Handle incoming audio stream.

        Processes audio chunks, transcribes in real-time, and sends to conversation agent.

        Args:
            audio_stream: Async iterator of audio chunks
            session: Voice session
            on_transcription: Callback for transcription results (chunk)
            on_response: Callback for conversation responses (text)
            on_error: Callback for errors (error)
        """
        try:
            # Update session status
            session.status = SessionStatus.LISTENING
            session.update_activity()

            logger.info(
                "Starting audio stream handling",
                extra={"session_id": session.session_id, "language": session.language}
            )

            # Check if provider supports streaming
            if not self.stt_provider.supports_streaming:
                logger.warning(
                    "STT provider does not support streaming, using batch mode",
                    extra={"provider": self.stt_provider.provider_name}
                )
                # Fallback to batch mode
                await self._handle_batch_mode(
                    audio_stream,
                    session,
                    on_transcription,
                    on_response,
                    on_error
                )
                return

            # Stream transcription
            async for transcription_chunk in self.stt_provider.transcribe_stream(
                audio_stream=audio_stream,
                language=session.language if session.language != "auto" else None,
                sample_rate=16000
            ):
                # Update session
                session.status = SessionStatus.TRANSCRIBING
                session.update_activity()

                # Send transcription to client
                await on_transcription(transcription_chunk)

                # If final transcription, send to conversation agent
                if transcription_chunk.is_final and transcription_chunk.text.strip():
                    logger.info(
                        "Final transcription received",
                        extra={
                            "session_id": session.session_id,
                            "text": transcription_chunk.text[:50]
                        }
                    )

                    # Add to session history
                    session.add_transcription(transcription_chunk.text)

                    # Send to conversation agent
                    session.status = SessionStatus.PROCESSING
                    response = await self._call_conversation_agent(
                        session=session,
                        message=transcription_chunk.text
                    )

                    if response:
                        # Add response to session
                        session.add_response(response)

                        # Send to client
                        await on_response(response)

                    # Back to listening
                    session.status = SessionStatus.LISTENING

            logger.info(
                "Audio stream handling completed",
                extra={"session_id": session.session_id}
            )

        except Exception as e:
            logger.error(
                "Error handling audio stream",
                extra={
                    "session_id": session.session_id,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            session.status = SessionStatus.ERROR
            await on_error(str(e))

    async def _handle_batch_mode(
        self,
        audio_stream: AsyncIterator[bytes],
        session: VoiceSession,
        on_transcription: Callable,
        on_response: Callable,
        on_error: Callable
    ) -> None:
        """
        Fallback batch mode handling.

        Collects audio, transcribes once, sends to agent.
        """
        logger.info("Using batch mode transcription")

        # Collect all audio
        audio_chunks = []
        async for chunk in audio_stream:
            audio_chunks.append(chunk)
            # Limit to prevent memory issues
            if len(audio_chunks) > 1000:  # ~4MB at 4096 bytes/chunk
                break

        if not audio_chunks:
            return

        full_audio = b"".join(audio_chunks)

        # Transcribe
        from shared.speech_to_text.schemas import TranscriptionRequest
        request = TranscriptionRequest(
            audio_data=full_audio,
            language=session.language
        )

        response = await self.stt_provider.transcribe(request)

        # Send result
        chunk = TranscriptionChunk(
            text=response.text,
            is_final=True,
            language=response.language,
            sequence=0
        )

        await on_transcription(chunk)

        # Send to conversation agent
        if response.text.strip():
            session.add_transcription(response.text)
            agent_response = await self._call_conversation_agent(
                session=session,
                message=response.text
            )
            if agent_response:
                session.add_response(agent_response)
                await on_response(agent_response)

    async def _call_conversation_agent(
        self,
        session: VoiceSession,
        message: str
    ) -> Optional[str]:
        """
        Call conversation agent service.

        Args:
            session: Voice session
            message: User message

        Returns:
            Agent response text or None if failed
        """
        try:
            url = f"{self.conversation_agent_url}/api/conversation/sync"

            payload = {
                "session_id": session.agent_session_id or session.session_id,
                "message": message,
                "phone_number": session.phone_number,
                "metadata": session.metadata
            }

            logger.debug(
                "Calling conversation agent",
                extra={
                    "session_id": session.session_id,
                    "message": message[:50]
                }
            )

            response = await self.http_client.post(url, json=payload)
            response.raise_for_status()

            data = response.json()

            # Store agent session ID for context
            if "session_id" in data:
                session.agent_session_id = data["session_id"]

            response_text = data.get("response", "")

            logger.info(
                "Conversation agent response received",
                extra={
                    "session_id": session.session_id,
                    "response_length": len(response_text)
                }
            )

            return response_text

        except httpx.HTTPError as e:
            logger.error(
                "HTTP error calling conversation agent",
                extra={
                    "session_id": session.session_id,
                    "error": str(e),
                    "status_code": getattr(e.response, "status_code", None)
                }
            )
            return None

        except Exception as e:
            logger.error(
                "Error calling conversation agent",
                extra={
                    "session_id": session.session_id,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            return None

    async def cleanup(self) -> None:
        """Cleanup resources."""
        await self.http_client.aclose()
        logger.info("Audio stream handler cleaned up")
