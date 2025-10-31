"""
shared/common/config.py

Base Configuration Management

Provides base settings class with security-focused defaults.
All service-specific settings inherit from BaseSettings.
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings as PydanticBaseSettings
from typing import Literal, Optional
import os
from functools import lru_cache


class BaseSettings(PydanticBaseSettings):
    """
    Base configuration class for all services.

    Security Features:
    - Environment-based configuration
    - Validation on load
    - No secrets in code
    - Type safety
    """

    # Service Identity
    SERVICE_NAME: str = Field(default="base-service", description="Service name for logging and tracing")
    SERVICE_VERSION: str = Field(default="2.0.0", description="Service version")

    # Environment
    ENVIRONMENT: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Deployment environment"
    )

    # Logging
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level"
    )
    LOG_FORMAT: Literal["json", "text"] = Field(
        default="json",
        description="Log output format (json for production)"
    )

    # Security
    API_KEY: Optional[str] = Field(
        default=None,
        description="API key for service authentication (min 32 chars)"
    )
    JWT_SECRET: Optional[str] = Field(
        default=None,
        description="JWT signing secret (min 32 chars)"
    )
    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="JWT signing algorithm"
    )
    JWT_EXPIRATION_MINUTES: int = Field(
        default=30,
        description="JWT token expiration time in minutes"
    )

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = Field(default=True, description="Enable rate limiting")
    RATE_LIMIT_PER_MINUTE: int = Field(
        default=60,
        ge=1,
        le=10000,
        description="Max requests per minute per client"
    )

    # CORS
    ALLOWED_ORIGINS: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        description="Allowed CORS origins"
    )

    # Database (optional, not all services use it)
    DATABASE_URL: Optional[str] = Field(
        default=None,
        description="PostgreSQL connection URL"
    )
    DATABASE_POOL_SIZE: int = Field(default=10, ge=1, le=100)
    DATABASE_MAX_OVERFLOW: int = Field(default=20, ge=0, le=100)

    # Redis (optional)
    REDIS_URL: Optional[str] = Field(
        default=None,
        description="Redis connection URL for caching and sessions"
    )
    REDIS_TTL_SECONDS: int = Field(
        default=1800,  # 30 minutes
        ge=60,
        description="Default Redis key TTL"
    )

    # Health Check
    HEALTH_CHECK_INTERVAL_SECONDS: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Health check interval"
    )

    # Timeouts
    DEFAULT_TIMEOUT_SECONDS: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Default HTTP request timeout"
    )

    # Observability
    ENABLE_METRICS: bool = Field(default=True, description="Enable Prometheus metrics")
    ENABLE_TRACING: bool = Field(default=False, description="Enable OpenTelemetry tracing")
    JAEGER_ENDPOINT: Optional[str] = Field(
        default=None,
        description="Jaeger collector endpoint"
    )

    @field_validator("API_KEY")
    @classmethod
    def validate_api_key(cls, v: Optional[str]) -> Optional[str]:
        """Validate API key length for security."""
        if v is not None and len(v) < 32:
            raise ValueError("API_KEY must be at least 32 characters for security")
        return v

    @field_validator("JWT_SECRET")
    @classmethod
    def validate_jwt_secret(cls, v: Optional[str]) -> Optional[str]:
        """Validate JWT secret length for security."""
        if v is not None and len(v) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters for security")
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate database URL format."""
        if v is not None:
            if not v.startswith(("postgresql://", "postgresql+asyncpg://")):
                raise ValueError("DATABASE_URL must be a valid PostgreSQL URL")
        return v

    @field_validator("REDIS_URL")
    @classmethod
    def validate_redis_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate Redis URL format."""
        if v is not None:
            if not v.startswith(("redis://", "rediss://")):
                raise ValueError("REDIS_URL must be a valid Redis URL")
        return v

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENVIRONMENT == "development"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields not defined in model


@lru_cache()
def get_settings() -> BaseSettings:
    """
    Get cached settings instance.

    Returns cached instance for performance.
    Only loads once per application lifecycle.
    """
    return BaseSettings()


def get_service_config(service_name: str, settings_class: type[BaseSettings]) -> BaseSettings:
    """
    Factory function for service-specific settings.

    Args:
        service_name: Name of the service
        settings_class: Service-specific settings class

    Returns:
        Configured settings instance
    """
    os.environ["SERVICE_NAME"] = service_name
    return settings_class()
