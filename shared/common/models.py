"""
shared/common/models.py

Shared Pydantic Models

Common request/response models used across services.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Any, Dict, List
from datetime import datetime
from enum import Enum


class HealthStatus(str, Enum):
    """Health check status."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"


class BaseResponse(BaseModel):
    """Base response model for all API responses."""

    success: bool = Field(..., description="Whether request succeeded")
    message: Optional[str] = Field(None, description="Human-readable message")
    data: Optional[Any] = Field(None, description="Response data")
    error: Optional[Dict[str, Any]] = Field(None, description="Error details if failed")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Operation completed successfully",
                "data": {"id": "123", "status": "active"}
            }
        }


class ErrorResponse(BaseModel):
    """Error response model."""

    success: bool = Field(default=False, description="Always false for errors")
    error: Dict[str, Any] = Field(..., description="Error details")

    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid input",
                    "details": {"field": "phone_number", "issue": "Invalid format"}
                }
            }
        }


class HealthCheckResponse(BaseModel):
    """Health check response."""

    status: HealthStatus = Field(..., description="Overall health status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    checks: Dict[str, Any] = Field(default_factory=dict, description="Individual health checks")
    uptime_seconds: Optional[float] = Field(None, description="Service uptime in seconds")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "service": "conversation-agent",
                "version": "2.0.0",
                "timestamp": "2025-10-29T12:00:00Z",
                "checks": {
                    "database": "healthy",
                    "redis": "healthy",
                    "llm": "healthy"
                },
                "uptime_seconds": 3600.5
            }
        }


class PaginationParams(BaseModel):
    """Pagination parameters."""

    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")

    @property
    def offset(self) -> int:
        """Calculate offset for database queries."""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Get limit for database queries."""
        return self.page_size


class PaginatedResponse(BaseModel):
    """Paginated response model."""

    items: List[Any] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there's a next page")
    has_prev: bool = Field(..., description="Whether there's a previous page")

    class Config:
        json_schema_extra = {
            "example": {
                "items": [{"id": "1"}, {"id": "2"}],
                "total": 50,
                "page": 1,
                "page_size": 20,
                "total_pages": 3,
                "has_next": True,
                "has_prev": False
            }
        }


class SSEMessage(BaseModel):
    """Server-Sent Event message."""

    event: str = Field(..., description="Event type (token, tool_call, status, error, done)")
    data: Dict[str, Any] = Field(..., description="Event data")
    id: Optional[str] = Field(None, description="Event ID for reconnection")

    def to_sse_format(self) -> str:
        """
        Convert to SSE format string.

        Returns:
            SSE formatted string: "event: <event>\ndata: <json>\n\n"
        """
        import json

        lines = []

        if self.id:
            lines.append(f"id: {self.id}")

        lines.append(f"event: {self.event}")
        lines.append(f"data: {json.dumps(self.data, ensure_ascii=False)}")
        lines.append("")  # Empty line terminates message

        return "\n".join(lines) + "\n"


class TokenMessage(SSEMessage):
    """SSE message for LLM token streaming."""

    event: str = Field(default="token", const=True)
    data: Dict[str, str] = Field(
        ...,
        description="Token data",
        json_schema_extra={"example": {"token": "Hello"}}
    )


class ToolCallMessage(SSEMessage):
    """SSE message for tool call notification."""

    event: str = Field(default="tool_call", const=True)
    data: Dict[str, Any] = Field(
        ...,
        description="Tool call data",
        json_schema_extra={
            "example": {
                "tool": "get_customer_info",
                "status": "running",
                "params": {"phone_number": "05321234567"}
            }
        }
    )


class StatusMessage(SSEMessage):
    """SSE message for status updates."""

    event: str = Field(default="status", const=True)
    data: Dict[str, str] = Field(
        ...,
        description="Status data",
        json_schema_extra={"example": {"message": "Checking availability..."}}
    )


class ErrorMessage(SSEMessage):
    """SSE message for errors."""

    event: str = Field(default="error", const=True)
    data: Dict[str, Any] = Field(
        ...,
        description="Error data",
        json_schema_extra={
            "example": {
                "code": "EXTERNAL_SERVICE_ERROR",
                "message": "Failed to call booking service"
            }
        }
    )


class DoneMessage(SSEMessage):
    """SSE message for conversation completion."""

    event: str = Field(default="done", const=True)
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Completion data"
    )


class PhoneNumber(BaseModel):
    """Turkish phone number model with validation."""

    number: str = Field(..., description="Phone number (05XXXXXXXXX format)")

    @field_validator("number")
    @classmethod
    def validate_turkish_phone(cls, v: str) -> str:
        """Validate Turkish phone number format."""
        import re

        # Remove spaces, dashes, parentheses
        cleaned = re.sub(r"[\s\-\(\)]", "", v)

        # Check format: 05XXXXXXXXX (11 digits starting with 05)
        if not re.match(r"^05\d{9}$", cleaned):
            raise ValueError(
                "Phone number must be in Turkish format: 05XXXXXXXXX (11 digits)"
            )

        return cleaned

    @property
    def formatted(self) -> str:
        """Get formatted phone number: 0532 123 4567"""
        return f"{self.number[:4]} {self.number[4:7]} {self.number[7:]}"

    @property
    def masked(self) -> str:
        """Get masked phone number: 0532***4567 (for logging/display)"""
        return f"{self.number[:4]}***{self.number[7:]}"


class SessionInfo(BaseModel):
    """User session information."""

    session_id: str = Field(..., description="Unique session ID")
    user_id: Optional[str] = Field(None, description="User ID if authenticated")
    phone_number: Optional[str] = Field(None, description="Phone number")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(..., description="Session expiration time")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional session data")

    @property
    def is_expired(self) -> bool:
        """Check if session is expired."""
        return datetime.utcnow() > self.expires_at

    @property
    def remaining_seconds(self) -> int:
        """Get remaining session time in seconds."""
        if self.is_expired:
            return 0
        return int((self.expires_at - datetime.utcnow()).total_seconds())


class MetricsSnapshot(BaseModel):
    """Metrics snapshot for monitoring."""

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    service: str = Field(..., description="Service name")
    metrics: Dict[str, float] = Field(..., description="Metric name -> value mapping")

    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2025-10-29T12:00:00Z",
                "service": "conversation-agent",
                "metrics": {
                    "requests_total": 1234,
                    "requests_per_second": 10.5,
                    "error_rate": 0.02,
                    "avg_latency_ms": 234.5,
                    "llm_tokens_used": 50000
                }
            }
        }
