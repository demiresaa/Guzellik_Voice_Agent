"""
services/conversation_agent_service/config.py

Conversation Agent Service Configuration

Service-specific settings extending shared BaseSettings.
"""

from pydantic import Field, field_validator
from typing import Optional, Literal
from shared.common.config import BaseSettings


class ConversationAgentSettings(BaseSettings):
    """
    Conversation Agent Service configuration.

    Extends BaseSettings with service-specific settings.
    """

    # Service Identity (override defaults)
    SERVICE_NAME: str = Field(
        default="conversation-agent",
        description="Service name"
    )
    SERVICE_VERSION: str = Field(default="2.0.0")

    # Server
    HOST: str = Field(default="0.0.0.0", description="Server host")
    PORT: int = Field(default=8002, ge=1024, le=65535, description="Server port")

    # Gemini LLM
    GEMINI_API_KEY: str = Field(
        ...,
        description="Google Gemini API key (required)"
    )
    GEMINI_MODEL: str = Field(
        default="gemini-2.0-flash-exp",
        description="Gemini model name"
    )
    GEMINI_TEMPERATURE: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="LLM temperature (0=deterministic, 1=creative)"
    )
    GEMINI_MAX_TOKENS: int = Field(
        default=2048,
        ge=128,
        le=8192,
        description="Max tokens per response"
    )
    GEMINI_TIMEOUT_SECONDS: int = Field(
        default=30,
        ge=5,
        le=120,
        description="LLM request timeout"
    )

    # Booking Agent Service (for tool calls)
    BOOKING_AGENT_URL: str = Field(
        default="http://localhost:8001",
        description="Booking Agent Service base URL"
    )
    BOOKING_AGENT_TIMEOUT: int = Field(
        default=30,
        ge=5,
        le=120,
        description="Booking Agent request timeout"
    )

    # Session Management
    SESSION_TTL_SECONDS: int = Field(
        default=1800,  # 30 minutes
        ge=300,
        le=7200,
        description="Session TTL in Redis"
    )
    MAX_CONTEXT_MESSAGES: int = Field(
        default=20,
        ge=5,
        le=50,
        description="Max conversation messages to keep in context"
    )

    # SSE Configuration
    SSE_RETRY_TIMEOUT_MS: int = Field(
        default=3000,
        description="SSE client retry timeout (milliseconds)"
    )
    SSE_HEARTBEAT_INTERVAL_SECONDS: int = Field(
        default=15,
        ge=5,
        le=60,
        description="SSE heartbeat interval to keep connection alive"
    )

    # Tool Calling
    TOOL_CALL_MAX_ITERATIONS: int = Field(
        default=6,
        ge=1,
        le=7,
        description="Max tool call iterations per conversation"
    )
    TOOL_CALL_TIMEOUT_SECONDS: int = Field(
        default=30,
        ge=5,
        le=120,
        description="Individual tool call timeout"
    )

    # Database (required for conversation history)
    DATABASE_URL: str = Field(
        ...,
        description="PostgreSQL connection URL (required)"
    )

    # Redis (required for session management)
    REDIS_URL: str = Field(
        ...,
        description="Redis connection URL (required)"
    )

    # Security (required)
    API_KEY: str = Field(
        ...,
        description="API key for service authentication"
    )
    JWT_SECRET: Optional[str] = Field(
        default=None,
        description="JWT secret for token verification (optional)"
    )

    # CORS
    ALLOWED_ORIGINS: list[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:8000",
            "http://localhost:8002"
        ],
        description="Allowed CORS origins"
    )

    # Logging
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO"
    )
    LOG_FORMAT: Literal["json", "text"] = Field(
        default="json",
        description="json for production, text for development"
    )

    @field_validator("GEMINI_API_KEY")
    @classmethod
    def validate_gemini_api_key(cls, v: str) -> str:
        """Validate Gemini API key is not empty."""
        if not v or v == "your_gemini_api_key_here":
            raise ValueError("GEMINI_API_KEY must be set to a valid API key")
        return v

    @field_validator("BOOKING_AGENT_URL")
    @classmethod
    def validate_booking_agent_url(cls, v: str) -> str:
        """Validate Booking Agent URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("BOOKING_AGENT_URL must start with http:// or https://")
        # Remove trailing slash
        return v.rstrip("/")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Global settings instance
_settings: Optional[ConversationAgentSettings] = None


def get_settings() -> ConversationAgentSettings:
    """
    Get conversation agent settings (singleton).

    Returns:
        ConversationAgentSettings instance
    """
    global _settings
    if _settings is None:
        _settings = ConversationAgentSettings()
    return _settings
