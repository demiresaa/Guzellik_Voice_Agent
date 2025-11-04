"""
shared/speech_to_text/providers/faster_whisper.py

Faster-Whisper Local Provider

Uses faster-whisper library for local transcription.

Features:
- Local execution (no API costs)
- No network dependency
- Privacy (audio stays local)
- GPU acceleration support
- Multiple model sizes (tiny to large)
- Real-time streaming support

Limitations:
- Requires local resources (CPU/GPU, RAM, disk)
- Model download on first use
- Slower than cloud API (depends on hardware)
"""

import time
from typing import Optional, AsyncIterator
import tempfile
from pathlib import Path
import asyncio

from faster_whisper import WhisperModel
from faster_whisper.transcribe import Segment

from shared.common.logging import get_logger
from shared.speech_to_text.base import BaseSTTProvider
from shared.speech_to_text.schemas import (
    TranscriptionResponse,
    TranscriptionSegment,
    STTHealthCheck
)
from shared.speech_to_text.streaming import (
    TranscriptionChunk,
    AudioStreamProcessor
)
from shared.speech_to_text.exceptions import (
    TranscriptionException,
    ModelNotLoadedException
)

logger = get_logger(__name__)


class FasterWhisperProvider(BaseSTTProvider):
    """
    Faster-Whisper local provider implementation.

    Uses CTranslate2-optimized Whisper models for fast local transcription.
    Models are downloaded automatically on first use.
    """

    def __init__(
        self,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "auto",
        cpu_threads: int = 4,
        num_workers: int = 1
    ):
        """
        Initialize Faster-Whisper provider.

        Args:
            model_size: Model size (tiny, base, small, medium, large-v2, large-v3)
            device: Device to use ("cpu", "cuda", "auto")
            compute_type: Compute type ("int8", "float16", "float32", "auto")
            cpu_threads: Number of CPU threads to use
            num_workers: Number of parallel workers for transcription
        """
        super().__init__(provider_name="faster-whisper")

        self.model_size = model_size
        self.device = self._resolve_device(device)
        self.compute_type = self._resolve_compute_type(compute_type, self.device)
        self.cpu_threads = cpu_threads
        self.num_workers = num_workers
        self.model: Optional[WhisperModel] = None

        self._logger.info(
            "Faster-Whisper provider created",
            extra={
                "model_size": model_size,
                "device": self.device,
                "compute_type": self.compute_type,
                "cpu_threads": cpu_threads
            }
        )

    def _resolve_device(self, device: str) -> str:
        """
        Resolve device (auto-detect if "auto").

        Args:
            device: Device string ("cpu", "cuda", "auto")

        Returns:
            Resolved device ("cpu" or "cuda")
        """
        if device == "auto":
            try:
                import torch
                return "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                self._logger.warning("PyTorch not available, falling back to CPU")
                return "cpu"
        return device

    def _resolve_compute_type(self, compute_type: str, device: str) -> str:
        """
        Resolve compute type based on device.

        Args:
            compute_type: Compute type string
            device: Device being used

        Returns:
            Resolved compute type
        """
        if compute_type == "auto":
            if device == "cuda":
                return "float16"  # GPU: use float16 for speed
            else:
                return "int8"  # CPU: use int8 for speed and memory
        return compute_type

    async def initialize(self) -> None:
        """
        Initialize and load Faster-Whisper model.

        Downloads model if not cached locally.
        This may take time on first run.

        Raises:
            ModelNotLoadedException: If model fails to load
        """
        if self.model is not None:
            self._logger.debug("Model already loaded")
            return

        try:
            self._logger.info(
                f"Loading Faster-Whisper model: {self.model_size}",
                extra={
                    "model": self.model_size,
                    "device": self.device,
                    "compute_type": self.compute_type
                }
            )

            start_time = time.time()

            # Load model (downloads if needed)
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                cpu_threads=self.cpu_threads,
                num_workers=self.num_workers
            )

            load_time = time.time() - start_time

            self._logger.info(
                f"Faster-Whisper model loaded successfully",
                extra={"load_time": load_time}
            )

        except Exception as e:
            self._logger.error(
                "Failed to load Faster-Whisper model",
                extra={"error": str(e)}
            )
            raise ModelNotLoadedException(
                model_name=self.model_size,
                original_error=e
            )

    async def transcribe_file(
        self,
        file_path: str,
        language: Optional[str] = None,
        **kwargs
    ) -> TranscriptionResponse:
        """
        Transcribe audio file using Faster-Whisper.

        Args:
            file_path: Path to audio file
            language: Language code (ISO 639-1) or None for auto-detection
            **kwargs: Additional options (beam_size, vad_filter, etc.)

        Returns:
            TranscriptionResponse with transcription

        Raises:
            TranscriptionException: If transcription fails
            ModelNotLoadedException: If model is not loaded
        """
        start_time = time.time()

        try:
            # Ensure model is loaded
            if not self.model:
                raise ModelNotLoadedException(
                    model_name=self.model_size,
                    message="Model not initialized. Call initialize() first."
                )

            # Prepare transcription parameters
            transcribe_params = {
                "language": language if language and language != "auto" else None,
                "beam_size": kwargs.get("beam_size", 5),
                "vad_filter": kwargs.get("vad_filter", True),  # Voice Activity Detection
                "vad_parameters": kwargs.get("vad_parameters"),
                "temperature": kwargs.get("temperature", 0.0)
            }

            # Add prompt if provided (initial_prompt in faster-whisper)
            if "prompt" in kwargs and kwargs["prompt"]:
                transcribe_params["initial_prompt"] = kwargs["prompt"]

            self._logger.debug(
                "Transcribing with Faster-Whisper",
                extra={"file": file_path, "params": transcribe_params}
            )

            # Transcribe (returns segments generator and info)
            segments, info = self.model.transcribe(file_path, **transcribe_params)

            # Collect segments
            collected_segments = []
            full_text_parts = []

            for idx, segment in enumerate(segments):
                collected_segments.append(
                    TranscriptionSegment(
                        id=idx,
                        start=segment.start,
                        end=segment.end,
                        text=segment.text.strip(),
                        confidence=getattr(segment, "avg_logprob", None)
                    )
                )
                full_text_parts.append(segment.text.strip())

            # Combine all segments into full text
            full_text = " ".join(full_text_parts)

            processing_time = time.time() - start_time

            # Calculate average confidence
            avg_confidence = None
            if collected_segments:
                confidences = [
                    seg.confidence for seg in collected_segments
                    if seg.confidence is not None
                ]
                if confidences:
                    avg_confidence = sum(confidences) / len(confidences)

            transcription = TranscriptionResponse(
                text=full_text,
                language=info.language,
                duration=info.duration,
                segments=collected_segments,
                provider=self.provider_name,
                model=self.model_size,
                processing_time=processing_time,
                confidence=avg_confidence,
                metadata={
                    "device": self.device,
                    "compute_type": self.compute_type,
                    "language_probability": info.language_probability,
                    "vad_filter": transcribe_params["vad_filter"]
                }
            )

            self._logger.info(
                "Faster-Whisper transcription successful",
                extra={
                    "file": file_path,
                    "text_length": len(full_text),
                    "segments": len(collected_segments),
                    "processing_time": processing_time,
                    "language": info.language
                }
            )

            return transcription

        except ModelNotLoadedException:
            # Re-raise model not loaded exception
            raise

        except Exception as e:
            self._logger.error(
                "Faster-Whisper transcription failed",
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
        Transcribe audio from bytes using Faster-Whisper.

        Faster-Whisper requires a file, so we write to a temporary file.

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
                Path(temp_path).unlink()
            except Exception as e:
                self._logger.warning(
                    "Failed to delete temp file",
                    extra={"path": temp_path, "error": str(e)}
                )

    async def health_check(self) -> STTHealthCheck:
        """
        Check Faster-Whisper model health.

        Verifies that model is loaded and ready.

        Returns:
            STTHealthCheck with health status
        """
        start_time = time.time()

        try:
            # Check if model is loaded
            is_loaded = self.model is not None

            if not is_loaded:
                # Try to initialize
                await self.initialize()
                is_loaded = self.model is not None

            response_time = (time.time() - start_time) * 1000  # ms

            return STTHealthCheck(
                provider=self.provider_name,
                is_healthy=is_loaded,
                model_loaded=is_loaded,
                response_time_ms=response_time,
                last_error=None if is_loaded else "Model not loaded"
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000  # ms

            self._logger.error(
                "Faster-Whisper health check failed",
                extra={"error": str(e)}
            )

            return STTHealthCheck(
                provider=self.provider_name,
                is_healthy=False,
                model_loaded=False,
                response_time_ms=response_time,
                last_error=str(e)
            )

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        language: Optional[str] = None,
        sample_rate: int = 16000,
        **kwargs
    ) -> AsyncIterator[TranscriptionChunk]:
        """
        Transcribe audio stream in real-time using Faster-Whisper.

        This method processes audio chunks as they arrive, providing
        streaming transcription results.

        Args:
            audio_stream: Async iterator yielding audio chunks
            language: Language code or 'auto'
            sample_rate: Audio sample rate
            **kwargs: Additional options (vad_filter, beam_size, etc.)

        Yields:
            TranscriptionChunk with partial/final results

        Raises:
            TranscriptionException: If streaming fails
            ModelNotLoadedException: If model is not loaded
        """
        try:
            # Ensure model is loaded
            if not self.model:
                raise ModelNotLoadedException(
                    model_name=self.model_size,
                    message="Model not initialized for streaming"
                )

            self._logger.info(
                "Starting streaming transcription",
                extra={"language": language, "sample_rate": sample_rate}
            )

            # Create stream processor with VAD
            processor = AudioStreamProcessor(
                buffer_duration=30.0,
                sample_rate=sample_rate,
                enable_vad=kwargs.get("vad_filter", True),
                vad_threshold=kwargs.get("vad_threshold", 0.02)
            )

            sequence = 0

            # Process incoming audio chunks
            async for audio_chunk in audio_stream:
                # Process through VAD and buffer
                completed_segment = await processor.process_audio_chunk(audio_chunk)

                # If we have a completed speech segment, transcribe it
                if completed_segment:
                    self._logger.debug(
                        "Speech segment completed, transcribing",
                        extra={"size_bytes": len(completed_segment)}
                    )

                    # Write to temp file for faster-whisper
                    with tempfile.NamedTemporaryFile(
                        suffix=".wav",
                        delete=False
                    ) as temp_file:
                        temp_path = temp_file.name
                        temp_file.write(completed_segment)

                    try:
                        # Transcribe parameters
                        transcribe_params = {
                            "language": language if language and language != "auto" else None,
                            "beam_size": kwargs.get("beam_size", 5),
                            "vad_filter": False,  # Already filtered by processor
                            "temperature": kwargs.get("temperature", 0.0)
                        }

                        # Transcribe segment
                        segments, info = await asyncio.to_thread(
                            self.model.transcribe,
                            temp_path,
                            **transcribe_params
                        )

                        # Yield each word/segment as it comes
                        segment_start_time = time.time()

                        for seg_idx, segment in enumerate(segments):
                            # Yield interim results (not final)
                            if seg_idx < len(list(segments)) - 1:
                                yield TranscriptionChunk(
                                    text=segment.text.strip(),
                                    is_final=False,
                                    confidence=getattr(segment, "avg_logprob", None),
                                    start_time=segment.start,
                                    end_time=segment.end,
                                    sequence=sequence,
                                    language=info.language
                                )
                                sequence += 1

                        # Yield final result for this speech segment
                        if segments:
                            full_text = " ".join([seg.text.strip() for seg in segments])
                            yield TranscriptionChunk(
                                text=full_text,
                                is_final=True,
                                confidence=None,  # Average could be calculated
                                start_time=0,
                                end_time=info.duration if hasattr(info, "duration") else None,
                                sequence=sequence,
                                language=info.language
                            )
                            sequence += 1

                            self._logger.debug(
                                "Segment transcribed",
                                extra={
                                    "text": full_text[:50],
                                    "language": info.language,
                                    "duration": time.time() - segment_start_time
                                }
                            )

                    finally:
                        # Cleanup temp file
                        try:
                            Path(temp_path).unlink()
                        except Exception as e:
                            self._logger.warning(
                                "Failed to delete temp file",
                                extra={"error": str(e)}
                            )

            self._logger.info("Streaming transcription completed")

        except ModelNotLoadedException:
            raise

        except Exception as e:
            self._logger.error(
                "Streaming transcription failed",
                extra={"error": str(e), "type": type(e).__name__}
            )
            raise TranscriptionException(
                message="Streaming transcription failed",
                provider=self.provider_name,
                original_error=e
            )

    async def cleanup(self) -> None:
        """Cleanup model and resources."""
        if self.model:
            # Faster-Whisper doesn't have explicit cleanup
            # Just remove reference and let GC handle it
            self.model = None
            self._logger.info("Faster-Whisper model unloaded")

        await super().cleanup()
