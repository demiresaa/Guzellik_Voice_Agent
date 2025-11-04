"""
services/voice_interface_service/config.py

Configuration for Voice Interface Service
"""

from pydantic import Field
from pydantic_settings import BaseSettings
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict # SettingsConfigDict'i import edin



class VoiceInterfaceSettings(BaseSettings):
    """
    Voice Interface Service Configuration.

    This service handles real-time voice interactions:
    - WebSocket audio streaming
    - Real-time STT (Speech-to-Text)
    - Conversation management
    - Optional TTS (Text-to-Speech)
    """

    # Service Identity
    SERVICE_NAME: str = Field(default="voice-interface-service")
    SERVICE_VERSION: str = Field(default="1.0.0")
    SERVICE_PORT: int = Field(default=8000)

    # Environment
    ENVIRONMENT: str = Field(default="development")

    # Conversation Agent URL
    CONVERSATION_AGENT_URL: str = Field(
        default="http://localhost:8002",
        description="URL of conversation agent service"
    )

    # Audio Settings
    AUDIO_SAMPLE_RATE: int = Field(
        default=16000,
        description="Audio sample rate (Hz)"
    )

    AUDIO_CHUNK_SIZE: int = Field(
        default=4096,
        description="Audio chunk size (bytes)"
    )

    AUDIO_CHANNELS: int = Field(
        default=1,
        description="Audio channels (1=mono, 2=stereo)"
    )

    # STT Settings (inherited from shared config)
    STT_PROVIDER: str = Field(
        default="faster-whisper",
        description="STT provider (openai, faster-whisper)"
    )

    STT_LANGUAGE: str = Field(
        default="tr",
        description="Default language for STT"
    )

    # Voice Activity Detection
    VAD_ENABLED: bool = Field(
        default=True,
        description="Enable Voice Activity Detection"
    )

    VAD_THRESHOLD: float = Field(
        default=0.02,
        description="VAD energy threshold"
    )

    VAD_MIN_SPEECH_MS: int = Field(
        default=250,
        description="Minimum speech duration (ms)"
    )

    VAD_MIN_SILENCE_MS: int = Field(
        default=500,
        description="Minimum silence duration to end speech (ms)"
    )

    # WebSocket Settings
    WS_PING_INTERVAL: int = Field(
        default=20,
        description="WebSocket ping interval (seconds)"
    )

    WS_PING_TIMEOUT: int = Field(
        default=10,
        description="WebSocket ping timeout (seconds)"
    )

    WS_MAX_SIZE: int = Field(
        default=10 * 1024 * 1024,  # 10MB
        description="Maximum WebSocket message size"
    )

    # Session Settings
    SESSION_TIMEOUT_SECONDS: int = Field(
        default=300,  # 5 minutes
        description="Session timeout for inactive connections"
    )

    MAX_CONCURRENT_SESSIONS: int = Field(
        default=100,
        description="Maximum concurrent voice sessions"
    )

    # Buffer Settings
    AUDIO_BUFFER_DURATION_SECONDS: float = Field(
        default=30.0,
        description="Audio buffer duration"
    )

    # Security
    API_KEY: str = Field(
        default="your-api-key-here",
        description="API key for service authentication"
    )

    RATE_LIMIT_PER_MINUTE: int = Field(
        default=100,
        description="Rate limit per client per minute"
    )

    # Logging
    LOG_LEVEL: str = Field(default="INFO")
    LOG_FORMAT: str = Field(default="json")

    # CORS
    ALLOWED_ORIGINS: list[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:8000",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8000"
        ]
    )

    # Observability
    ENABLE_METRICS: bool = Field(default=True)
    ENABLE_TRACING: bool = Field(default=False)


    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        case_sensitive=True, 
        extra='ignore'  # <- EN ÖNEMLİ KISIM BURASI
    )


@lru_cache()
def get_settings() -> VoiceInterfaceSettings:
    """Get cached settings instance."""
    return VoiceInterfaceSettings()
