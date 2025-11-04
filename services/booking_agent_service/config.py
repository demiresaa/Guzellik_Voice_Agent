# services/booking_agent_service/config.py

"""
Configuration management using Pydantic BaseSettings.
Environment-based configuration for security and flexibility.
"""

from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import Optional
import os


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Security Best Practices:
    - Sensitive data loaded from .env
    - Validation on all fields
    - Type-safe configuration
    """

    # Application
    APP_NAME: str = "Güzellik Salonu Booking Agent"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = Field(default=False, description="Debug mode (never use in production)")

    # API Security
    API_KEY: str = Field(..., description="API key for agent-to-agent communication")
    ALLOWED_ORIGINS: list[str] = Field(
        default=["http://localhost:3000"],
        description="CORS allowed origins"
    )

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = Field(default=True, description="Enable rate limiting")
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, description="Max requests per minute per IP")

    # Database (Future: PostgreSQL/MongoDB)
    DATABASE_TYPE: str = Field(default="memory", description="Database type: memory, sqlite, postgres")
    DATABASE_URL: Optional[str] = Field(default=None, description="Database connection URL")

    # External Services
    SMS_PROVIDER_API_KEY: Optional[str] = Field(default=None, description="SMS provider API key")
    SMS_PROVIDER_URL: Optional[str] = Field(default=None, description="SMS provider endpoint")
    PAYMENT_PROVIDER_API_KEY: Optional[str] = Field(default=None, description="Payment provider API key")
    PAYMENT_PROVIDER_URL: Optional[str] = Field(default=None, description="Payment provider endpoint")

    # Logging
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    LOG_FORMAT: str = Field(default="json", description="Log format: json or text")

    # Business Rules
    APPOINTMENT_DURATION_MINUTES: int = Field(default=60, description="Default appointment duration")
    CANCELLATION_WINDOW_HOURS: int = Field(default=24, description="Minimum hours before appointment for cancellation")
    PREPAYMENT_THRESHOLD_TRY: float = Field(default=500.0, description="Services above this price require prepayment")


    @validator("LOG_LEVEL")
    def validate_log_level(cls, v):
        """Validate log level"""
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {allowed}")
        return v.upper()

    @validator("API_KEY")
    def validate_api_key(cls, v):
        """Ensure API key is strong enough"""
        if len(v) < 32:
            raise ValueError("API_KEY must be at least 32 characters for security")
        return v


# Global settings instance
settings = Settings()
