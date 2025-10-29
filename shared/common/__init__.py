"""
Common Shared Module

Provides base functionality used across all services:
- Configuration
- Logging
- Exceptions
- Base models
"""

from .config import BaseSettings, get_settings
from .logging import get_logger, setup_logging
from .exceptions import (
    BaseAppException,
    ValidationException,
    AuthenticationException,
    NotFoundException,
    RateLimitException
)

__all__ = [
    "BaseSettings",
    "get_settings",
    "get_logger",
    "setup_logging",
    "BaseAppException",
    "ValidationException",
    "AuthenticationException",
    "NotFoundException",
    "RateLimitException",
]
