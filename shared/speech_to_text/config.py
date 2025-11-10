"""
shared/speech_to_text/config.py

Speech-to-Text Configuration

Configuration settings for STT providers.
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from typing import Optional, Literal
from functools import lru_cache


class STTSettings(BaseSettings):
    """
    Configuration for Speech-to-Text service.

    Environment Variables:
    - STT_PROVIDER: Provider to use ("openai" or "faster-whisper")
    - STT_FALLBACK_ENABLED: Enable fallback to secondary provider
    - STT_FALLBACK_PROVIDER: Fallback provider name
    - OPENAI_API_KEY: OpenAI API key (for OpenAI provider)
    - STT_MODEL: Model name/size
    - STT_DEVICE: Device for local models ("cpu", "cuda", "auto")
    - STT_MAX_AUDIO_SIZE_MB: Maximum audio file size in MB
    - STT_DEFAULT_LANGUAGE: Default language code
    """

    # Provider Selection
    STT_PROVIDER: Literal["openai", "faster-whisper"] = Field(
        default="faster-whisper",
        description="Primary STT provider"
    )

    STT_FALLBACK_ENABLED: bool = Field(
        default=True,
        description="Enable fallback to secondary provider on failure"
    )

    STT_FALLBACK_PROVIDER: Optional[Literal["openai", "faster-whisper"]] = Field(
        default=None,
        description="Fallback provider (if different from primary)"
    )

    # OpenAI Whisper Settings
    OPENAI_API_KEY: Optional[str] = Field(
        default=None,
        description="OpenAI API key (required for OpenAI provider)"
    )

    OPENAI_WHISPER_MODEL: str = Field(
        default="whisper-1",
        description="OpenAI Whisper model name"
    )

    OPENAI_TIMEOUT: int = Field(
        default=30,
        ge=5,
        le=300,
        description="OpenAI API timeout in seconds"
    )

    OPENAI_MAX_RETRIES: int = Field(
        default=3,
        ge=0,
        le=10,
        description="OpenAI API max retries"
    )

    # Faster-Whisper Settings
    FASTER_WHISPER_MODEL: str = Field(
        default="small",
        description="Faster-Whisper model size (tiny, base, small, medium, large-v2, large-v3)"
    )

    FASTER_WHISPER_DEVICE: str = Field(
        default="auto",
        description="Device for Faster-Whisper (cpu, cuda, auto)"
    )

    FASTER_WHISPER_COMPUTE_TYPE: str = Field(
        default="auto",
        description="Compute type (int8, float16, float32, auto)"
    )

    FASTER_WHISPER_CPU_THREADS: int = Field(
        default=4,
        ge=1,
        le=32,
        description="Number of CPU threads"
    )

    FASTER_WHISPER_NUM_WORKERS: int = Field(
        default=1,
        ge=1,
        le=8,
        description="Number of parallel workers"
    )

    # General Settings
    STT_DEFAULT_LANGUAGE: str = Field(
        default="auto",
        description="Default language code (ISO 639-1) or 'auto'"
    )

    STT_MAX_AUDIO_SIZE_MB: int = Field(
        default=25,
        ge=1,
        le=100,
        description="Maximum audio file size in MB"
    )

    STT_CACHE_ENABLED: bool = Field(
        default=False,
        description="Enable transcription caching (for identical audio)"
    )

    STT_CACHE_TTL_SECONDS: int = Field(
        default=3600,
        ge=60,
        description="Cache TTL in seconds"
    )

    # Performance
    STT_ENABLE_VAD: bool = Field(
        default=True,
        description="Enable Voice Activity Detection (faster-whisper)"
    )

    STT_BEAM_SIZE: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Beam size for faster-whisper"
    )

    STT_TEMPERATURE: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Sampling temperature (0.0 = deterministic)"
    )

    @field_validator("STT_FALLBACK_PROVIDER")
    @classmethod
    def validate_fallback_provider(cls, v, info):
        """Ensure fallback is different from primary."""
        if v is not None:
            primary = info.data.get("STT_PROVIDER")
            if v == primary:
                raise ValueError(
                    "STT_FALLBACK_PROVIDER must be different from STT_PROVIDER"
                )
        return v

    @field_validator("OPENAI_API_KEY")
    @classmethod
    def validate_openai_key(cls, v, info):
        """Validate OpenAI key if OpenAI provider is selected."""
        primary = info.data.get("STT_PROVIDER")
        fallback = info.data.get("STT_FALLBACK_PROVIDER")

        # Check if OpenAI is used (primary or fallback)
        uses_openai = (primary == "openai" or fallback == "openai")

        if uses_openai and not v:
            raise ValueError(
                "OPENAI_API_KEY is required when using OpenAI provider. "
                "Set the OPENAI_API_KEY environment variable."
            )

        return v

    @property
    def max_audio_size_bytes(self) -> int:
        """Get max audio size in bytes."""
        return self.STT_MAX_AUDIO_SIZE_MB * 1024 * 1024

    @property
    def is_openai_enabled(self) -> bool:
        """Check if OpenAI provider is enabled."""
        return (
            self.STT_PROVIDER == "openai" or
            self.STT_FALLBACK_PROVIDER == "openai"
        )

    @property
    def is_faster_whisper_enabled(self) -> bool:
        """Check if Faster-Whisper provider is enabled."""
        return (
            self.STT_PROVIDER == "faster-whisper" or
            self.STT_FALLBACK_PROVIDER == "faster-whisper"
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_stt_settings() -> STTSettings:
    """
    Get cached STT settings instance.

    Returns cached instance for performance.
    Only loads once per application lifecycle.
    """
    return STTSettings()
