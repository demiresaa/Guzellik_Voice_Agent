"""
shared/speech_to_text/providers/openai_whisper.py

OpenAI Whisper API Provider

Uses OpenAI's cloud-based Whisper API for transcription.

Features:
- Cloud-based (no local resources)
- High accuracy
- Fast processing
- Supports multiple languages
- Automatic language detection

Limitations:
- Requires API key
- Costs per minute of audio
- 25MB file size limit
- Network dependency
"""

import os
import time
from typing import Optional
from pathlib import Path
import tempfile

import httpx
from openai import AsyncOpenAI
from openai import OpenAIError, APIError, APIConnectionError, RateLimitError

from shared.common.logging import get_logger
from shared.speech_to_text.base import BaseSTTProvider
from shared.speech_to_text.schemas import TranscriptionResponse, STTHealthCheck
from shared.speech_to_text.exceptions import (
    TranscriptionException,
    ProviderUnavailableException,
    AudioValidationException
)

logger = get_logger(__name__)


class OpenAIWhisperProvider(BaseSTTProvider):
    """
    OpenAI Whisper API provider implementation.

    Uses OpenAI's hosted Whisper API for transcription.
    Requires OPENAI_API_KEY environment variable.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "whisper-1",
        timeout: int = 30,
        max_retries: int = 3
    ):
        """
        Initialize OpenAI Whisper provider.

        Args:
            api_key: OpenAI API key (default: from OPENAI_API_KEY env var)
            model: Model name (default: "whisper-1")
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries on failure
        """
        super().__init__(provider_name="openai")

        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key is required. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.client: Optional[AsyncOpenAI] = None

        self._logger.info(
            "OpenAI Whisper provider created",
            extra={"model": model, "timeout": timeout, "max_retries": max_retries}
        )

    async def initialize(self) -> None:
        """
        Initialize OpenAI client.

        Creates async HTTP client with connection pooling and retry logic.
        """
        if self.client is None:
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                timeout=httpx.Timeout(self.timeout, connect=10.0),
                max_retries=self.max_retries
            )
            self._logger.info("OpenAI client initialized")

    async def transcribe_file(
        self,
        file_path: str,
        language: Optional[str] = None,
        **kwargs
    ) -> TranscriptionResponse:
        """
        Transcribe audio file using OpenAI Whisper API.

        Args:
            file_path: Path to audio file
            language: Language code (ISO 639-1) or None for auto-detection
            **kwargs: Additional options (prompt, temperature)

        Returns:
            TranscriptionResponse with transcription

        Raises:
            TranscriptionException: If transcription fails
            ProviderUnavailableException: If API is unavailable
        """
        start_time = time.time()

        try:
            # Ensure client is initialized
            if not self.client:
                await self.initialize()

            # Prepare API call parameters
            params = {
                "model": self.model,
                "response_format": "verbose_json"  # Get detailed response with timing
            }

            # Add language if specified (not "auto")
            if language and language != "auto":
                params["language"] = language

            # Add optional parameters
            if "prompt" in kwargs and kwargs["prompt"]:
                params["prompt"] = kwargs["prompt"]

            if "temperature" in kwargs:
                params["temperature"] = kwargs["temperature"]

            self._logger.debug(
                "Calling OpenAI Whisper API",
                extra={"file": file_path, "params": params}
            )

            # Open and send file
            with open(file_path, "rb") as audio_file:
                response = await self.client.audio.transcriptions.create(
                    file=audio_file,
                    **params
                )

            # Parse response
            processing_time = time.time() - start_time

            # Extract segments if available
            segments = None
            if hasattr(response, "segments") and response.segments:
                from shared.speech_to_text.schemas import TranscriptionSegment
                segments = [
                    TranscriptionSegment(
                        id=seg.get("id", idx),
                        start=seg.get("start", 0.0),
                        end=seg.get("end", 0.0),
                        text=seg.get("text", ""),
                        confidence=seg.get("confidence")
                    )
                    for idx, seg in enumerate(response.segments)
                ]

            transcription = TranscriptionResponse(
                text=response.text,
                language=getattr(response, "language", language),
                duration=getattr(response, "duration", None),
                segments=segments,
                provider=self.provider_name,
                model=self.model,
                processing_time=processing_time,
                metadata={
                    "api_version": "v1",
                    "response_format": "verbose_json"
                }
            )

            self._logger.info(
                "OpenAI transcription successful",
                extra={
                    "file": file_path,
                    "text_length": len(transcription.text),
                    "processing_time": processing_time
                }
            )

            return transcription

        except RateLimitError as e:
            self._logger.warning("OpenAI rate limit exceeded", extra={"error": str(e)})
            raise ProviderUnavailableException(
                provider=self.provider_name,
                message="OpenAI rate limit exceeded",
                retry_after=60,
                details={"error": str(e)}
            )

        except APIConnectionError as e:
            self._logger.error("OpenAI API connection failed", extra={"error": str(e)})
            raise ProviderUnavailableException(
                provider=self.provider_name,
                message="Failed to connect to OpenAI API",
                details={"error": str(e)}
            )

        except APIError as e:
            self._logger.error("OpenAI API error", extra={"error": str(e)})
            raise TranscriptionException(
                message=f"OpenAI API error: {str(e)}",
                provider=self.provider_name,
                original_error=e
            )

        except OpenAIError as e:
            self._logger.error("OpenAI error", extra={"error": str(e)})
            raise TranscriptionException(
                message=f"OpenAI error: {str(e)}",
                provider=self.provider_name,
                original_error=e
            )

        except Exception as e:
            self._logger.error(
                "Unexpected error during OpenAI transcription",
                extra={"error": str(e), "type": type(e).__name__}
            )
            raise TranscriptionException(
                message="Transcription failed",
                provider=self.provider_name,
                original_error=e
            )

    async def transcribe_bytes(
        self,
        audio_data: bytes,
        audio_format: str,
        language: Optional[str] = None,
        **kwargs
    ) -> TranscriptionResponse:
        """
        Transcribe audio from bytes using OpenAI Whisper API.

        OpenAI API requires a file, so we write to a temporary file.

        Args:
            audio_data: Raw audio data
            audio_format: Audio format (e.g., "wav", "mp3")
            language: Language code or None for auto-detection
            **kwargs: Additional options

        Returns:
            TranscriptionResponse with transcription

        Raises:
            TranscriptionException: If transcription fails
        """
        # Write to temporary file
        with tempfile.NamedTemporaryFile(
            suffix=f".{audio_format}",
            delete=False
        ) as temp_file:
            temp_path = temp_file.name
            temp_file.write(audio_data)

        try:
            # Transcribe using file method
            return await self.transcribe_file(
                file_path=temp_path,
                language=language,
                **kwargs
            )
        finally:
            # Cleanup temp file
            try:
                os.unlink(temp_path)
            except Exception as e:
                self._logger.warning(
                    "Failed to delete temp file",
                    extra={"path": temp_path, "error": str(e)}
                )

    async def health_check(self) -> STTHealthCheck:
        """
        Check OpenAI API health.

        Attempts to make a minimal API call to verify connectivity.

        Returns:
            STTHealthCheck with health status
        """
        start_time = time.time()

        try:
            # Ensure client is initialized
            if not self.client:
                await self.initialize()

            # Simple API call to check connectivity
            # We'll use the models endpoint (lightweight)
            models = await self.client.models.list()

            response_time = (time.time() - start_time) * 1000  # ms

            return STTHealthCheck(
                provider=self.provider_name,
                is_healthy=True,
                api_reachable=True,
                response_time_ms=response_time,
                last_error=None
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000  # ms

            self._logger.error(
                "OpenAI health check failed",
                extra={"error": str(e)}
            )

            return STTHealthCheck(
                provider=self.provider_name,
                is_healthy=False,
                api_reachable=False,
                response_time_ms=response_time,
                last_error=str(e)
            )

    async def cleanup(self) -> None:
        """Close OpenAI client and cleanup resources."""
        if self.client:
            await self.client.close()
            self.client = None
            self._logger.info("OpenAI client closed")

        await super().cleanup()
