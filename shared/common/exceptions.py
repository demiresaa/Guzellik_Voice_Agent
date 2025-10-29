"""
shared/common/exceptions.py

Custom Exception Hierarchy

Provides structured exceptions with HTTP status codes for API responses.
All application exceptions inherit from BaseAppException.
"""

from typing import Optional, Dict, Any
from fastapi import HTTPException, status


class BaseAppException(Exception):
    """
    Base exception for all application errors.

    Attributes:
        message: Human-readable error message
        status_code: HTTP status code
        error_code: Machine-readable error code
        details: Additional error details
    """

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON response."""
        return {
            "success": False,
            "error": {
                "code": self.error_code,
                "message": self.message,
                "details": self.details
            }
        }

    def to_http_exception(self) -> HTTPException:
        """Convert to FastAPI HTTPException."""
        return HTTPException(
            status_code=self.status_code,
            detail=self.to_dict()
        )


class ValidationException(BaseAppException):
    """
    Validation error (400 Bad Request).

    Raised when request data fails validation.
    """

    def __init__(
        self,
        message: str = "Validation failed",
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if field:
            error_details["field"] = field

        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="VALIDATION_ERROR",
            details=error_details
        )


class AuthenticationException(BaseAppException):
    """
    Authentication error (401 Unauthorized).

    Raised when authentication credentials are missing or invalid.
    """

    def __init__(
        self,
        message: str = "Authentication failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="AUTHENTICATION_ERROR",
            details=details
        )


class AuthorizationException(BaseAppException):
    """
    Authorization error (403 Forbidden).

    Raised when user doesn't have permission to access resource.
    """

    def __init__(
        self,
        message: str = "Access forbidden",
        resource: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if resource:
            error_details["resource"] = resource

        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="AUTHORIZATION_ERROR",
            details=error_details
        )


class NotFoundException(BaseAppException):
    """
    Resource not found (404 Not Found).

    Raised when requested resource doesn't exist.
    """

    def __init__(
        self,
        resource_type: str,
        resource_id: Optional[str] = None,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        if message is None:
            message = f"{resource_type} not found"
            if resource_id:
                message += f": {resource_id}"

        error_details = details or {}
        error_details["resource_type"] = resource_type
        if resource_id:
            error_details["resource_id"] = resource_id

        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="NOT_FOUND",
            details=error_details
        )


class ConflictException(BaseAppException):
    """
    Resource conflict (409 Conflict).

    Raised when operation conflicts with current state
    (e.g., duplicate booking).
    """

    def __init__(
        self,
        message: str = "Resource conflict",
        conflict_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if conflict_type:
            error_details["conflict_type"] = conflict_type

        super().__init__(
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            error_code="CONFLICT_ERROR",
            details=error_details
        )


class RateLimitException(BaseAppException):
    """
    Rate limit exceeded (429 Too Many Requests).

    Raised when client exceeds rate limit.
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        limit: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if retry_after:
            error_details["retry_after_seconds"] = retry_after
        if limit:
            error_details["rate_limit"] = limit

        super().__init__(
            message=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error_code="RATE_LIMIT_EXCEEDED",
            details=error_details
        )


class ExternalServiceException(BaseAppException):
    """
    External service error (502 Bad Gateway).

    Raised when external service (LLM, SMS provider, etc.) fails.
    """

    def __init__(
        self,
        service_name: str,
        message: Optional[str] = None,
        original_error: Optional[Exception] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        if message is None:
            message = f"External service '{service_name}' failed"

        error_details = details or {}
        error_details["service_name"] = service_name
        if original_error:
            error_details["original_error"] = str(original_error)

        super().__init__(
            message=message,
            status_code=status.HTTP_502_BAD_GATEWAY,
            error_code="EXTERNAL_SERVICE_ERROR",
            details=error_details
        )


class ServiceUnavailableException(BaseAppException):
    """
    Service temporarily unavailable (503 Service Unavailable).

    Raised when service is overloaded or undergoing maintenance.
    """

    def __init__(
        self,
        message: str = "Service temporarily unavailable",
        retry_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if retry_after:
            error_details["retry_after_seconds"] = retry_after

        super().__init__(
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="SERVICE_UNAVAILABLE",
            details=error_details
        )


class DatabaseException(BaseAppException):
    """
    Database operation error (500 Internal Server Error).

    Raised when database operations fail.
    """

    def __init__(
        self,
        message: str = "Database operation failed",
        operation: Optional[str] = None,
        original_error: Optional[Exception] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if operation:
            error_details["operation"] = operation
        if original_error:
            error_details["original_error"] = str(original_error)

        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="DATABASE_ERROR",
            details=error_details
        )


class BusinessLogicException(BaseAppException):
    """
    Business logic violation (422 Unprocessable Entity).

    Raised when request is valid but violates business rules.
    """

    def __init__(
        self,
        message: str,
        rule: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if rule:
            error_details["violated_rule"] = rule

        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="BUSINESS_LOGIC_ERROR",
            details=error_details
        )


# Convenience functions for common errors

def not_found(resource_type: str, resource_id: Optional[str] = None) -> NotFoundException:
    """Create NotFoundException with standard message."""
    return NotFoundException(resource_type, resource_id)


def invalid_input(message: str, field: Optional[str] = None) -> ValidationException:
    """Create ValidationException with standard message."""
    return ValidationException(message, field)


def unauthorized(message: str = "Invalid credentials") -> AuthenticationException:
    """Create AuthenticationException with standard message."""
    return AuthenticationException(message)


def forbidden(resource: Optional[str] = None) -> AuthorizationException:
    """Create AuthorizationException with standard message."""
    return AuthorizationException(resource=resource)


def rate_limited(retry_after: int = 60) -> RateLimitException:
    """Create RateLimitException with retry_after."""
    return RateLimitException(retry_after=retry_after)


def external_service_error(service_name: str, error: Optional[Exception] = None) -> ExternalServiceException:
    """Create ExternalServiceException for failed external call."""
    return ExternalServiceException(service_name, original_error=error)
