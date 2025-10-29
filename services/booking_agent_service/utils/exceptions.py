# services/booking_agent_service/utils/exceptions.py

"""
Custom exception classes for proper error handling.
Staff Engineer principle: Explicit error types for better debugging and monitoring.
"""

from fastapi import HTTPException, status
from typing import Any, Optional


class BookingAgentException(Exception):
    """Base exception for all booking agent errors"""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(BookingAgentException):
    """Raised when input validation fails"""
    status_code = status.HTTP_400_BAD_REQUEST


class NotFoundError(BookingAgentException):
    """Raised when requested resource is not found"""
    status_code = status.HTTP_404_NOT_FOUND


class ConflictError(BookingAgentException):
    """Raised when there's a conflict (e.g., time slot already booked)"""
    status_code = status.HTTP_409_CONFLICT


class UnauthorizedError(BookingAgentException):
    """Raised when authentication fails"""
    status_code = status.HTTP_401_UNAUTHORIZED


class RateLimitExceeded(BookingAgentException):
    """Raised when rate limit is exceeded"""
    status_code = status.HTTP_429_TOO_MANY_REQUESTS


class ExternalServiceError(BookingAgentException):
    """Raised when external service (SMS, Payment) fails"""
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE


class DatabaseError(BookingAgentException):
    """Raised when database operation fails"""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR


def exception_to_http(exc: BookingAgentException) -> HTTPException:
    """
    Convert custom exception to HTTPException for FastAPI.

    Args:
        exc: Custom booking agent exception

    Returns:
        HTTPException with proper status code and details
    """
    return HTTPException(
        status_code=exc.status_code,
        detail={
            "error": exc.__class__.__name__,
            "message": exc.message,
            "details": exc.details
        }
    )
