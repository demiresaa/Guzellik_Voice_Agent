"""
shared/speech_to_text/schemas.py

Speech-to-Text Data Models

Pydantic schemas for STT requests, responses, and configurations.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal, Dict, Any
from datetime import datetime
from enum import Enum


class AudioFormat(str, Enum):
    """Supported audio formats."""
    WAV = "wav"
    MP3 = "mp3"
    M4A = "m4a"
    WEBM = "webm"
    OGG = "ogg"
    FLAC = "flac"
    OPUS = "opus"


class STTProvider(str, Enum):
    """Available STT providers."""
    OPENAI_WHISPER = "openai"
    FASTER_WHISPER = "faster-whisper"


class WhisperModel(str, Enum):
    """Faster-Whisper model sizes."""
    TINY = "tiny"
    TINY_EN = "tiny.en"
    BASE = "base"
    BASE_EN = "base.en"
    SMALL = "small"
    SMALL_EN = "small.en"
    MEDIUM = "medium"
    MEDIUM_EN = "medium.en"
    LARGE = "large-v2"
    LARGE_V3 = "large-v3"


class Language(str, Enum):
    """Supported languages (ISO 639-1 codes)."""
    TURKISH = "tr"
    ENGLISH = "en"
    AUTO = "auto"  # Auto-detect


class TranscriptionRequest(BaseModel):
    """
    Request model for transcription.

    Used when calling transcribe() method.
    """
    audio_path: Optional[str] = Field(
        default=None,
        description="Path to audio file on disk"
    )
    audio_data: Optional[bytes] = Field(
        default=None,
        description="Raw audio data as bytes"
    )
    language: Optional[str] = Field(
        default="auto",
        description="Language code (ISO 639-1) or 'auto' for auto-detection"
    )
    prompt: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional prompt to guide transcription (OpenAI only)"
    )
    temperature: Optional[float] = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Sampling temperature (0.0 = deterministic)"
    )

    @field_validator("audio_path", "audio_data")
    @classmethod
    def validate_audio_source(cls, v, info):
        """Ensure at least one audio source is provided."""
        # This will be called for each field separately
        # We'll validate in the model_validator instead
        return v

    @classmethod
    def model_validate(cls, *args, **kwargs):
        """Validate that exactly one audio source is provided."""
        instance = super().model_validate(*args, **kwargs)

        has_path = instance.audio_path is not None
        has_data = instance.audio_data is not None

        if not has_path and not has_data:
            raise ValueError("Either audio_path or audio_data must be provided")

        if has_path and has_data:
            raise ValueError("Only one of audio_path or audio_data should be provided")

        return instance

    class Config:
        json_schema_extra = {
            "example": {
                "audio_path": "/tmp/audio.wav",
                "language": "tr",
                "temperature": 0.0
            }
        }


class TranscriptionSegment(BaseModel):
    """
    A segment of transcribed text with timing.

    Used for word-level or sentence-level transcription.
    """
    id: int = Field(description="Segment ID (0-indexed)")
    start: float = Field(description="Start time in seconds")
    end: float = Field(description="End time in seconds")
    text: str = Field(description="Transcribed text for this segment")
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0-1.0) if available"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": 0,
                "start": 0.0,
                "end": 2.5,
                "text": "Merhaba, randevu almak istiyorum.",
                "confidence": 0.95
            }
        }


class TranscriptionResponse(BaseModel):
    """
    Response model for transcription.

    Returned by transcribe() method.
    """
    text: str = Field(description="Full transcribed text")
    language: Optional[str] = Field(
        default=None,
        description="Detected or specified language code"
    )
    duration: Optional[float] = Field(
        default=None,
        description="Audio duration in seconds"
    )
    segments: Optional[list[TranscriptionSegment]] = Field(
        default=None,
        description="Transcription segments with timing (if available)"
    )
    provider: str = Field(description="STT provider used")
    model: Optional[str] = Field(
        default=None,
        description="Model name/version used"
    )
    processing_time: Optional[float] = Field(
        default=None,
        description="Processing time in seconds"
    )
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Average confidence score (if available)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional provider-specific metadata"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Transcription timestamp (UTC)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "text": "Merhaba, yarın için randevu almak istiyorum.",
                "language": "tr",
                "duration": 3.5,
                "provider": "openai",
                "model": "whisper-1",
                "processing_time": 1.2,
                "confidence": 0.95,
                "timestamp": "2025-10-29T12:34:56Z"
            }
        }


class AudioValidationResult(BaseModel):
    """
    Result of audio file validation.

    Used internally for validation checks.
    """
    is_valid: bool = Field(description="Whether audio file is valid")
    format: Optional[str] = Field(
        default=None,
        description="Detected audio format"
    )
    size_bytes: Optional[int] = Field(
        default=None,
        description="File size in bytes"
    )
    duration: Optional[float] = Field(
        default=None,
        description="Audio duration in seconds (if available)"
    )
    mime_type: Optional[str] = Field(
        default=None,
        description="Detected MIME type"
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Validation errors (if any)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "is_valid": True,
                "format": "wav",
                "size_bytes": 524288,
                "duration": 5.0,
                "mime_type": "audio/wav",
                "errors": []
            }
        }


class STTHealthCheck(BaseModel):
    """
    Health check response for STT service.

    Used for monitoring and diagnostics.
    """
    provider: str = Field(description="STT provider name")
    is_healthy: bool = Field(description="Whether provider is healthy")
    model_loaded: Optional[bool] = Field(
        default=None,
        description="Whether model is loaded (faster-whisper only)"
    )
    api_reachable: Optional[bool] = Field(
        default=None,
        description="Whether API is reachable (OpenAI only)"
    )
    response_time_ms: Optional[float] = Field(
        default=None,
        description="Health check response time in milliseconds"
    )
    last_error: Optional[str] = Field(
        default=None,
        description="Last error message (if any)"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Health check timestamp (UTC)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "provider": "faster-whisper",
                "is_healthy": True,
                "model_loaded": True,
                "response_time_ms": 50.0,
                "timestamp": "2025-10-29T12:34:56Z"
            }
        }
