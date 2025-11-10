"""
shared/speech_to_text/base.py

Abstract Base Class for Speech-to-Text Providers

Defines the interface that all STT providers must implement.
Ensures consistency and enables strategy pattern for provider selection.

Supports both:
- Batch transcription (full audio files)
- Streaming transcription (real-time audio chunks)
"""

from abc import ABC, abstractmethod
from typing import Optional, AsyncIterator
import time

from shared.common.logging import get_logger
from shared.speech_to_text.schemas import (
    TranscriptionRequest,
    TranscriptionResponse,
    STTHealthCheck
)
from shared.speech_to_text.validators import validate_audio_file, validate_audio_data
from shared.speech_to_text.streaming import TranscriptionChunk, AudioStreamProcessor

logger = get_logger(__name__)


class BaseSTTProvider(ABC):
    """
    Abstract base class for all STT providers.

    All STT providers (OpenAI, Faster-Whisper, etc.) must inherit from this
    class and implement the required methods.

    Design Patterns:
    - Strategy Pattern: Providers are interchangeable strategies
    - Template Method: Common logic in base class, specifics in subclasses
    - Factory Pattern: Providers created via factory (see factory.py)
    """

    def __init__(self, provider_name: str):
        """
        Initialize base provider.

        Args:
            provider_name: Name of the provider (e.g., "openai", "faster-whisper")
        """
        self.provider_name = provider_name
        self._is_initialized = False
        self._logger = get_logger(f"stt.{provider_name}")

    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize the provider (load models, setup connections, etc.).

        This method is called once when the provider is first created.
        Should be idempotent (safe to call multiple times).

        Raises:
            Exception: If initialization fails
        """
        pass

    @abstractmethod
    async def transcribe_file(
        self,
        file_path: str,
        language: Optional[str] = None,
        **kwargs
    ) -> TranscriptionResponse:
        """
        Transcribe audio from file.

        Args:
            file_path: Path to audio file
            language: Language code (ISO 639-1) or 'auto' for auto-detection
            **kwargs: Provider-specific options

        Returns:
            TranscriptionResponse with transcribed text and metadata

        Raises:
            AudioValidationException: If audio file is invalid
            TranscriptionException: If transcription fails
        """
        pass

    @abstractmethod
    async def transcribe_bytes(
        self,
        audio_data: bytes,
        audio_format: str,
        language: Optional[str] = None,
        **kwargs
    ) -> TranscriptionResponse:
        """
        Transcribe audio from bytes.

        Args:
            audio_data: Raw audio data
            audio_format: Audio format (e.g., "wav", "mp3")
            language: Language code (ISO 639-1) or 'auto' for auto-detection
            **kwargs: Provider-specific options

        Returns:
            TranscriptionResponse with transcribed text and metadata

        Raises:
            AudioValidationException: If audio data is invalid
            TranscriptionException: If transcription fails
        """
        pass

    @abstractmethod
    async def health_check(self) -> STTHealthCheck:
        """
        Check provider health status.

        Returns:
            STTHealthCheck with health status and diagnostics

        Raises:
            Exception: Should not raise, return is_healthy=False instead
        """
        pass

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        language: Optional[str] = None,
        sample_rate: int = 16000,
        **kwargs
    ) -> AsyncIterator[TranscriptionChunk]:
        """
        Transcribe audio stream in real-time.

        This is an optional method. Providers that don't support streaming
        will raise NotImplementedError.

        Args:
            audio_stream: Async iterator yielding audio chunks
            language: Language code or 'auto' for detection
            sample_rate: Audio sample rate (default: 16kHz)
            **kwargs: Provider-specific options

        Yields:
            TranscriptionChunk with partial/final results

        Raises:
            NotImplementedError: If provider doesn't support streaming
            TranscriptionException: If streaming fails
        """
        raise NotImplementedError(
            f"{self.provider_name} provider does not support streaming transcription"
        )

    @property
    def supports_streaming(self) -> bool:
        """
        Check if provider supports streaming.

        Returns:
            True if streaming is supported
        """
        # Correct way to check if a method is overridden in a subclass.
        # We check if the method on the instance is different from the one on the base class.
        return self.transcribe_stream != BaseSTTProvider.transcribe_stream

    async def transcribe(
        self,
        request: TranscriptionRequest
    ) -> TranscriptionResponse:
        """
        High-level transcription method (template method).

        Handles routing to file or bytes transcription, validation,
        logging, and timing.

        Args:
            request: TranscriptionRequest with audio source and options

        Returns:
            TranscriptionResponse with transcribed text

        Raises:
            AudioValidationException: If audio is invalid
            TranscriptionException: If transcription fails
        """
        start_time = time.time()

        try:
            # Ensure provider is initialized
            if not self._is_initialized:
                self._logger.info(f"Initializing {self.provider_name} provider")
                await self.initialize()
                self._is_initialized = True

            # Route to appropriate method
            if request.audio_path:
                self._logger.info(
                    "Starting file transcription",
                    extra={
                        "provider": self.provider_name,
                        "path": request.audio_path,
                        "language": request.language
                    }
                )

                # Validate file
                validation_result = validate_audio_file(request.audio_path)
                self._logger.debug(
                    "Audio file validated",
                    extra={"validation": validation_result.model_dump()}
                )

                # Transcribe
                response = await self.transcribe_file(
                    file_path=request.audio_path,
                    language=request.language,
                    prompt=request.prompt,
                    temperature=request.temperature
                )

            elif request.audio_data:
                self._logger.info(
                    "Starting bytes transcription",
                    extra={
                        "provider": self.provider_name,
                        "size_bytes": len(request.audio_data),
                        "language": request.language
                    }
                )

                # Validate data
                validation_result = validate_audio_data(request.audio_data)
                self._logger.debug(
                    "Audio data validated",
                    extra={"validation": validation_result.model_dump()}
                )

                # Detect format from MIME type (simplified)
                format = validation_result.mime_type.split("/")[-1] if validation_result.mime_type else "wav"

                # Transcribe
                response = await self.transcribe_bytes(
                    audio_data=request.audio_data,
                    audio_format=format,
                    language=request.language,
                    prompt=request.prompt,
                    temperature=request.temperature
                )

            else:
                # Should not happen (validated in TranscriptionRequest)
                raise ValueError("Either audio_path or audio_data must be provided")

            # Add processing time
            processing_time = time.time() - start_time
            response.processing_time = processing_time

            self._logger.info(
                "Transcription completed",
                extra={
                    "provider": self.provider_name,
                    "processing_time": processing_time,
                    "text_length": len(response.text),
                    "language": response.language
                }
            )

            return response

        except Exception as e:
            processing_time = time.time() - start_time
            self._logger.error(
                "Transcription failed",
                extra={
                    "provider": self.provider_name,
                    "processing_time": processing_time,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            raise

    async def cleanup(self) -> None:
        """
        Cleanup resources (connections, models, etc.).

        Called when provider is no longer needed.
        Should be idempotent (safe to call multiple times).
        """
        self._logger.info(f"Cleaning up {self.provider_name} provider")
        self._is_initialized = False

    @property
    def is_initialized(self) -> bool:
        """Check if provider is initialized."""
        return self._is_initialized

    def __repr__(self) -> str:
        """String representation."""
        return f"{self.__class__.__name__}(provider={self.provider_name}, initialized={self._is_initialized})"
