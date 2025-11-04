"""
shared/speech_to_text/streaming.py

Real-Time Audio Streaming Infrastructure

Handles real-time audio streaming, buffering, and Voice Activity Detection (VAD)
for live transcription.
"""

import asyncio
from typing import Optional, AsyncIterator, Callable
from dataclasses import dataclass, field
from enum import Enum
import time
from collections import deque

from shared.common.logging import get_logger

logger = get_logger(__name__)


class StreamState(str, Enum):
    """Audio stream state."""
    IDLE = "idle"
    LISTENING = "listening"
    SPEAKING = "speaking"
    PROCESSING = "processing"
    PAUSED = "paused"
    CLOSED = "closed"


@dataclass
class AudioChunk:
    """
    Represents a chunk of audio data.

    Used for streaming audio processing.
    """
    data: bytes
    timestamp: float
    sequence: int
    sample_rate: int = 16000  # Default: 16kHz
    channels: int = 1  # Default: mono

    def __len__(self) -> int:
        """Get chunk size in bytes."""
        return len(self.data)

    @property
    def duration_ms(self) -> float:
        """Calculate chunk duration in milliseconds."""
        # bytes → samples → seconds → milliseconds
        samples = len(self.data) // (2 * self.channels)  # 2 bytes per sample (int16)
        seconds = samples / self.sample_rate
        return seconds * 1000


@dataclass
class TranscriptionChunk:
    """
    Represents a partial transcription result.

    Returned during streaming transcription.
    """
    text: str
    is_final: bool  # True if this is the final result for this segment
    confidence: Optional[float] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    sequence: int = 0
    language: Optional[str] = None


class AudioBuffer:
    """
    Thread-safe audio buffer for streaming.

    Manages incoming audio chunks with automatic overflow protection.
    """

    def __init__(
        self,
        max_duration_seconds: float = 30.0,
        sample_rate: int = 16000
    ):
        """
        Initialize audio buffer.

        Args:
            max_duration_seconds: Maximum buffer duration
            sample_rate: Audio sample rate
        """
        self.max_duration_seconds = max_duration_seconds
        self.sample_rate = sample_rate
        self.max_bytes = int(max_duration_seconds * sample_rate * 2)  # 2 bytes per sample

        self._buffer: deque[AudioChunk] = deque()
        self._total_bytes = 0
        self._sequence = 0
        self._lock = asyncio.Lock()

        logger.debug(
            "Audio buffer initialized",
            extra={
                "max_duration": max_duration_seconds,
                "max_bytes": self.max_bytes,
                "sample_rate": sample_rate
            }
        )

    async def add_chunk(self, data: bytes, timestamp: Optional[float] = None) -> AudioChunk:
        """
        Add audio chunk to buffer.

        Args:
            data: Raw audio data
            timestamp: Chunk timestamp (default: current time)

        Returns:
            Created AudioChunk
        """
        async with self._lock:
            chunk = AudioChunk(
                data=data,
                timestamp=timestamp or time.time(),
                sequence=self._sequence,
                sample_rate=self.sample_rate
            )

            self._buffer.append(chunk)
            self._total_bytes += len(data)
            self._sequence += 1

            # Remove old chunks if buffer is full
            while self._total_bytes > self.max_bytes and len(self._buffer) > 1:
                removed = self._buffer.popleft()
                self._total_bytes -= len(removed.data)
                logger.debug(
                    "Buffer overflow, removed chunk",
                    extra={"sequence": removed.sequence}
                )

            return chunk

    async def get_all_data(self) -> bytes:
        """
        Get all buffered audio data.

        Returns:
            Combined audio data
        """
        async with self._lock:
            return b"".join(chunk.data for chunk in self._buffer)

    async def get_recent_data(self, duration_seconds: float) -> bytes:
        """
        Get recent audio data.

        Args:
            duration_seconds: How many seconds of recent audio to get

        Returns:
            Recent audio data
        """
        async with self._lock:
            target_bytes = int(duration_seconds * self.sample_rate * 2)

            # Collect from newest to oldest
            chunks = []
            total = 0

            for chunk in reversed(self._buffer):
                chunks.insert(0, chunk.data)
                total += len(chunk.data)
                if total >= target_bytes:
                    break

            return b"".join(chunks)

    async def clear(self) -> None:
        """Clear buffer."""
        async with self._lock:
            self._buffer.clear()
            self._total_bytes = 0
            logger.debug("Buffer cleared")

    @property
    def size_bytes(self) -> int:
        """Get buffer size in bytes."""
        return self._total_bytes

    @property
    def duration_seconds(self) -> float:
        """Get buffer duration in seconds."""
        samples = self._total_bytes // 2
        return samples / self.sample_rate


class VoiceActivityDetector:
    """
    Simple Voice Activity Detection (VAD).

    Detects when speech starts and stops based on audio energy.
    """

    def __init__(
        self,
        threshold: float = 0.02,
        min_speech_duration_ms: float = 250,
        min_silence_duration_ms: float = 500,
        sample_rate: int = 16000
    ):
        """
        Initialize VAD.

        Args:
            threshold: Energy threshold for speech detection
            min_speech_duration_ms: Minimum speech duration to trigger
            min_silence_duration_ms: Minimum silence to end speech
            sample_rate: Audio sample rate
        """
        self.threshold = threshold
        self.min_speech_duration_ms = min_speech_duration_ms
        self.min_silence_duration_ms = min_silence_duration_ms
        self.sample_rate = sample_rate

        self.is_speaking = False
        self.speech_start_time: Optional[float] = None
        self.last_speech_time: Optional[float] = None

        logger.debug(
            "VAD initialized",
            extra={
                "threshold": threshold,
                "min_speech_ms": min_speech_duration_ms,
                "min_silence_ms": min_silence_duration_ms
            }
        )

    def _calculate_energy(self, audio_data: bytes) -> float:
        """
        Calculate audio energy (RMS).

        Args:
            audio_data: Raw audio bytes

        Returns:
            Normalized energy (0.0 - 1.0)
        """
        import numpy as np

        # Convert bytes to int16 array
        audio_array = np.frombuffer(audio_data, dtype=np.int16)

        # Calculate RMS
        if len(audio_array) == 0:
            return 0.0

        rms = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))

        # Normalize (int16 max is 32768)
        normalized = rms / 32768.0

        return normalized

    def process_chunk(self, chunk: AudioChunk) -> tuple[bool, bool]:
        """
        Process audio chunk for VAD.

        Args:
            chunk: Audio chunk to process

        Returns:
            Tuple of (is_speaking, speech_ended)
            - is_speaking: True if currently speaking
            - speech_ended: True if speech just ended
        """
        current_time = chunk.timestamp
        energy = self._calculate_energy(chunk.data)

        is_speech = energy > self.threshold
        speech_ended = False

        if is_speech:
            # Speech detected
            if not self.is_speaking:
                # Speech just started
                if self.speech_start_time is None:
                    self.speech_start_time = current_time

                # Check if minimum duration reached
                duration_ms = (current_time - self.speech_start_time) * 1000
                if duration_ms >= self.min_speech_duration_ms:
                    self.is_speaking = True
                    logger.debug("Speech started", extra={"energy": energy})

            self.last_speech_time = current_time

        else:
            # Silence detected
            if self.is_speaking and self.last_speech_time:
                # Check if minimum silence duration reached
                silence_duration_ms = (current_time - self.last_speech_time) * 1000
                if silence_duration_ms >= self.min_silence_duration_ms:
                    self.is_speaking = False
                    speech_ended = True
                    self.speech_start_time = None
                    logger.debug(
                        "Speech ended",
                        extra={"silence_duration_ms": silence_duration_ms}
                    )

        return self.is_speaking, speech_ended

    def reset(self) -> None:
        """Reset VAD state."""
        self.is_speaking = False
        self.speech_start_time = None
        self.last_speech_time = None


class AudioStreamProcessor:
    """
    High-level audio stream processor.

    Combines buffer management, VAD, and transcription coordination.
    """

    def __init__(
        self,
        buffer_duration: float = 30.0,
        sample_rate: int = 16000,
        enable_vad: bool = True,
        vad_threshold: float = 0.02
    ):
        """
        Initialize stream processor.

        Args:
            buffer_duration: Buffer duration in seconds
            sample_rate: Audio sample rate
            enable_vad: Enable Voice Activity Detection
            vad_threshold: VAD energy threshold
        """
        self.buffer = AudioBuffer(
            max_duration_seconds=buffer_duration,
            sample_rate=sample_rate
        )

        self.vad = VoiceActivityDetector(
            threshold=vad_threshold,
            sample_rate=sample_rate
        ) if enable_vad else None

        self.state = StreamState.IDLE
        self.sample_rate = sample_rate

        # Callbacks
        self.on_speech_start: Optional[Callable] = None
        self.on_speech_end: Optional[Callable] = None

        logger.info(
            "Audio stream processor initialized",
            extra={
                "buffer_duration": buffer_duration,
                "sample_rate": sample_rate,
                "vad_enabled": enable_vad
            }
        )

    async def process_audio_chunk(self, data: bytes) -> Optional[bytes]:
        """
        Process incoming audio chunk.

        Args:
            data: Raw audio data

        Returns:
            Audio data to transcribe (if speech segment completed)
        """
        # Add to buffer
        chunk = await self.buffer.add_chunk(data)

        # Run VAD if enabled
        if self.vad:
            is_speaking, speech_ended = self.vad.process_chunk(chunk)

            # Update state
            if is_speaking and self.state != StreamState.SPEAKING:
                self.state = StreamState.SPEAKING
                if self.on_speech_start:
                    await self.on_speech_start()

            # Speech segment completed
            if speech_ended:
                self.state = StreamState.PROCESSING

                # Get buffered audio
                audio_data = await self.buffer.get_all_data()

                # Clear buffer for next segment
                await self.buffer.clear()

                if self.on_speech_end:
                    await self.on_speech_end()

                self.state = StreamState.LISTENING

                return audio_data

        return None

    async def get_current_audio(self) -> bytes:
        """Get current buffered audio."""
        return await self.buffer.get_all_data()

    async def reset(self) -> None:
        """Reset processor state."""
        await self.buffer.clear()
        if self.vad:
            self.vad.reset()
        self.state = StreamState.IDLE
