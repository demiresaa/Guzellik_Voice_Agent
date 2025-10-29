# services/booking_agent_service/security/validator.py

"""
Input validation and sanitization middleware.
Staff Engineer principle: Never trust user input, defense in depth.

Protection Against:
- XSS (Cross-Site Scripting)
- SQL Injection
- NoSQL Injection
- Command Injection
- Path Traversal
- Malformed inputs
"""

from fastapi import Request, HTTPException, status
from typing import Any, Dict, List
import re
import json
from ..utils.logger import get_logger
from ..utils.exceptions import ValidationError

logger = get_logger(__name__)


class InputValidator:
    """
    Comprehensive input validation and sanitization.

    Multi-layer security:
    1. Pydantic schemas (type validation)
    2. This validator (content validation)
    3. Database ORM (parameterized queries)
    """

    # Dangerous patterns that indicate attacks
    DANGEROUS_PATTERNS = [
        # SQL Injection
        r"(\bUNION\b.*\bSELECT\b)",
        r"(\bINSERT\b.*\bINTO\b)",
        r"(\bUPDATE\b.*\bSET\b)",
        r"(\bDELETE\b.*\bFROM\b)",
        r"(\bDROP\b.*\b(TABLE|DATABASE)\b)",
        r"(--|#|/\*|\*/)",  # SQL comments

        # NoSQL Injection
        r"(\$where|\$ne|\$gt|\$lt|\$regex)",

        # Command Injection
        r"(;|\||&&|\$\(|\`)",

        # Path Traversal
        r"(\.\./|\.\.\\)",

        # XSS
        r"(<script|<iframe|<object|<embed|javascript:)",
        r"(on\w+\s*=)",  # Event handlers

        # Template Injection
        r"(\{\{.*\}\}|\{%.*%\})",
    ]

    # Compile patterns for performance
    _compiled_patterns = [re.compile(p, re.IGNORECASE) for p in DANGEROUS_PATTERNS]

    @classmethod
    def detect_attack_pattern(cls, value: str) -> tuple[bool, str]:
        """
        Detect malicious patterns in string input.

        Args:
            value: Input string to check

        Returns:
            Tuple of (is_malicious, pattern_description)
        """
        for i, pattern in enumerate(cls._compiled_patterns):
            if pattern.search(value):
                return True, f"Detected attack pattern: {cls.DANGEROUS_PATTERNS[i]}"
        return False, ""

    @classmethod
    def sanitize_string(cls, value: str, max_length: int = 1000) -> str:
        """
        Sanitize string input.

        Args:
            value: Input string
            max_length: Maximum allowed length

        Returns:
            Sanitized string

        Raises:
            ValidationError: If malicious content detected
        """
        if not isinstance(value, str):
            return value

        # Length check (DoS prevention)
        if len(value) > max_length:
            raise ValidationError(
                message=f"Input too long (max {max_length} characters)",
                details={"length": len(value), "max_length": max_length}
            )

        # Detect attack patterns
        is_malicious, description = cls.detect_attack_pattern(value)
        if is_malicious:
            logger.warning(
                "Malicious input detected",
                pattern=description,
                input_sample=value[:100]
            )
            raise ValidationError(
                message="Invalid input detected",
                details={"reason": "Potentially malicious content"}
            )

        # Strip dangerous characters (but allow Turkish characters)
        # Remove null bytes
        value = value.replace('\x00', '')

        # Remove control characters except newline and tab
        value = ''.join(char for char in value if ord(char) >= 32 or char in '\n\t')

        return value.strip()

    @classmethod
    def validate_phone_number(cls, phone: str) -> str:
        """
        Validate and normalize Turkish phone number.

        Args:
            phone: Phone number string

        Returns:
            Normalized phone number (05XXXXXXXXX)

        Raises:
            ValidationError: If invalid format
        """
        # Remove all non-digits
        cleaned = re.sub(r'\D', '', phone)

        # Turkish mobile format: 05XXXXXXXXX (11 digits)
        if not re.match(r'^(05\d{9}|5\d{9})$', cleaned):
            raise ValidationError(
                message="Invalid Turkish phone number format",
                details={"expected": "05XXXXXXXXX", "received": phone}
            )

        # Normalize to 11 digits
        if len(cleaned) == 10 and cleaned.startswith('5'):
            cleaned = '0' + cleaned

        return cleaned

    @classmethod
    def validate_email(cls, email: str) -> str:
        """
        Validate email format.

        Args:
            email: Email address

        Returns:
            Validated email

        Raises:
            ValidationError: If invalid format
        """
        # Basic email regex (Pydantic also validates this)
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        if not re.match(email_pattern, email):
            raise ValidationError(
                message="Invalid email format",
                details={"email": email}
            )

        # Check for dangerous characters
        if cls.detect_attack_pattern(email)[0]:
            raise ValidationError(
                message="Invalid email format",
                details={"reason": "Contains invalid characters"}
            )

        return email.lower().strip()

    @classmethod
    def validate_dict(cls, data: Dict[str, Any], max_depth: int = 5) -> Dict[str, Any]:
        """
        Recursively validate dictionary input.

        Args:
            data: Dictionary to validate
            max_depth: Maximum nesting depth (DoS prevention)

        Returns:
            Validated dictionary

        Raises:
            ValidationError: If validation fails
        """
        def _validate_recursive(obj: Any, depth: int = 0) -> Any:
            if depth > max_depth:
                raise ValidationError(
                    message="Input too deeply nested",
                    details={"max_depth": max_depth}
                )

            if isinstance(obj, dict):
                return {
                    key: _validate_recursive(value, depth + 1)
                    for key, value in obj.items()
                }
            elif isinstance(obj, list):
                return [_validate_recursive(item, depth + 1) for item in obj]
            elif isinstance(obj, str):
                return cls.sanitize_string(obj)
            else:
                return obj

        return _validate_recursive(data)

    @classmethod
    def validate_json_size(cls, data: Dict[str, Any], max_size_kb: int = 100) -> bool:
        """
        Validate JSON payload size (DoS prevention).

        Args:
            data: JSON data
            max_size_kb: Maximum size in KB

        Returns:
            True if valid

        Raises:
            ValidationError: If too large
        """
        json_str = json.dumps(data)
        size_kb = len(json_str.encode('utf-8')) / 1024

        if size_kb > max_size_kb:
            raise ValidationError(
                message=f"Request payload too large (max {max_size_kb}KB)",
                details={"size_kb": round(size_kb, 2), "max_size_kb": max_size_kb}
            )

        return True


async def validation_middleware(request: Request, call_next):
    """
    FastAPI middleware for automatic input validation.

    Usage:
        app.middleware("http")(validation_middleware)

    Args:
        request: FastAPI request
        call_next: Next middleware/route handler

    Returns:
        Response
    """
    try:
        # Only validate POST/PUT/PATCH requests with JSON body
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("content-type", "")

            if "application/json" in content_type:
                # Read body
                body = await request.body()

                # Size check (DoS prevention)
                if len(body) > 100 * 1024:  # 100KB limit
                    raise ValidationError(
                        message="Request body too large (max 100KB)",
                        details={"size_bytes": len(body)}
                    )

                # Parse JSON
                try:
                    data = json.loads(body)
                except json.JSONDecodeError as e:
                    raise ValidationError(
                        message="Invalid JSON format",
                        details={"error": str(e)}
                    )

                # Validate recursively
                if isinstance(data, dict):
                    InputValidator.validate_dict(data)
                    InputValidator.validate_json_size(data)

        # Process request
        response = await call_next(request)
        return response

    except ValidationError as e:
        logger.warning(
            "Input validation failed",
            error=e.message,
            details=e.details,
            ip=request.client.host if request.client else "unknown"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ValidationError",
                "message": e.message,
                "details": e.details
            }
        )


# Utility functions for common validations

def validate_date_format(date_str: str) -> bool:
    """Validate YYYY-MM-DD format"""
    return bool(re.match(r'^\d{4}-\d{2}-\d{2}$', date_str))


def validate_time_format(time_str: str) -> bool:
    """Validate HH:MM format"""
    return bool(re.match(r'^([01]\d|2[0-3]):([0-5]\d)$', time_str))


def validate_appointment_id(appointment_id: str) -> bool:
    """Validate appointment ID format (APT-XXXXXXXX)"""
    return bool(re.match(r'^APT-[A-Z0-9]{8}$', appointment_id, re.IGNORECASE))


def sanitize_search_query(query: str) -> str:
    """
    Sanitize search query for database operations.

    Args:
        query: Search query string

    Returns:
        Sanitized query
    """
    # Remove special characters that could be used for injection
    query = re.sub(r'[^\w\sğüşıöçĞÜŞİÖÇ\-]', '', query)

    # Limit length
    if len(query) > 100:
        query = query[:100]

    return query.strip()
