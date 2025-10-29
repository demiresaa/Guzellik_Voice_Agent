"""
shared/security/validator.py

Input Validation & Sanitization

Protects against:
- XSS (Cross-Site Scripting)
- SQL Injection
- NoSQL Injection
- Command Injection
- Path Traversal
"""

import re
from typing import Optional
from html import escape

from shared.common.exceptions import ValidationException
from shared.common.logging import get_logger

logger = get_logger(__name__)


# Dangerous patterns (security threats)
DANGEROUS_PATTERNS = [
    # SQL Injection
    (r"(\bUNION\b.*\bSELECT\b)", "SQL_INJECTION"),
    (r"(\bDROP\b.*\bTABLE\b)", "SQL_INJECTION"),
    (r"(;\s*DROP\b)", "SQL_INJECTION"),
    (r"(--\s*$)", "SQL_COMMENT"),
    (r"(/\*.*\*/)", "SQL_COMMENT"),

    # XSS
    (r"(<script[^>]*>.*</script>)", "XSS"),
    (r"(<iframe[^>]*>)", "XSS"),
    (r"(<object[^>]*>)", "XSS"),
    (r"(javascript:)", "XSS"),
    (r"(on\w+\s*=)", "XSS"),  # event handlers

    # NoSQL Injection
    (r"(\$ne\b|\$gt\b|\$lt\b)", "NOSQL_INJECTION"),
    (r"(\{\s*\$where)", "NOSQL_INJECTION"),

    # Command Injection
    (r"(;\s*(ls|cat|rm|wget|curl)\b)", "COMMAND_INJECTION"),
    (r"(\||&&|`)", "COMMAND_INJECTION"),

    # Path Traversal
    (r"(\.\./|\.\.\\)", "PATH_TRAVERSAL"),
]

# Compile patterns for performance
COMPILED_PATTERNS = [(re.compile(pattern, re.IGNORECASE), threat) for pattern, threat in DANGEROUS_PATTERNS]


def is_safe_string(text: str, allow_html: bool = False) -> bool:
    """
    Check if string is safe (no injection attempts).

    Args:
        text: Input string to validate
        allow_html: Whether to allow HTML tags

    Returns:
        True if safe, False if potentially malicious
    """
    if not isinstance(text, str):
        return False

    # Check dangerous patterns
    for pattern, threat_type in COMPILED_PATTERNS:
        if pattern.search(text):
            logger.warning("Dangerous pattern detected", extra={
                "threat_type": threat_type,
                "pattern": pattern.pattern
            })
            return False

    # Check HTML if not allowed
    if not allow_html and ("<" in text or ">" in text):
        logger.warning("HTML tags detected in non-HTML field")
        return False

    return True


def sanitize_input(
    text: str,
    allow_html: bool = False,
    max_length: Optional[int] = None,
    strip: bool = True
) -> str:
    """
    Sanitize user input.

    Args:
        text: Input text
        allow_html: Whether to allow HTML (default: escape HTML)
        max_length: Maximum length (truncate if exceeded)
        strip: Strip whitespace

    Returns:
        Sanitized text

    Raises:
        ValidationException: If input contains dangerous patterns
    """
    if not isinstance(text, str):
        raise ValidationException("Input must be a string")

    # Strip whitespace
    if strip:
        text = text.strip()

    # Check safety
    if not is_safe_string(text, allow_html):
        raise ValidationException(
            "Input contains potentially malicious content",
            details={"hint": "Remove special characters or SQL/script syntax"}
        )

    # Escape HTML if not allowed
    if not allow_html:
        text = escape(text)

    # Truncate if needed
    if max_length and len(text) > max_length:
        text = text[:max_length]
        logger.debug("Input truncated", extra={"max_length": max_length})

    return text


def validate_phone_number(phone: str) -> str:
    """
    Validate and normalize Turkish phone number.

    Args:
        phone: Phone number

    Returns:
        Normalized phone number (05XXXXXXXXX)

    Raises:
        ValidationException: If phone number is invalid
    """
    if not phone:
        raise ValidationException("Phone number is required", field="phone_number")

    # Remove spaces, dashes, parentheses
    cleaned = re.sub(r"[\s\-\(\)]", "", phone)

    # Check format: 05XXXXXXXXX (11 digits starting with 05)
    if not re.match(r"^05\d{9}$", cleaned):
        raise ValidationException(
            "Invalid Turkish phone number format",
            field="phone_number",
            details={"expected_format": "05XXXXXXXXX", "example": "05321234567"}
        )

    return cleaned


def validate_email(email: str) -> str:
    """
    Validate email address.

    Args:
        email: Email address

    Returns:
        Normalized email (lowercase)

    Raises:
        ValidationException: If email is invalid
    """
    if not email:
        raise ValidationException("Email is required", field="email")

    # Basic email regex
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

    if not re.match(pattern, email):
        raise ValidationException(
            "Invalid email format",
            field="email",
            details={"example": "user@example.com"}
        )

    return email.lower()


def validate_date(date_str: str) -> str:
    """
    Validate date string (YYYY-MM-DD).

    Args:
        date_str: Date string

    Returns:
        Validated date string

    Raises:
        ValidationException: If date format is invalid
    """
    if not date_str:
        raise ValidationException("Date is required", field="date")

    pattern = r"^\d{4}-\d{2}-\d{2}$"

    if not re.match(pattern, date_str):
        raise ValidationException(
            "Invalid date format",
            field="date",
            details={"expected_format": "YYYY-MM-DD", "example": "2025-10-29"}
        )

    return date_str


def validate_time(time_str: str) -> str:
    """
    Validate time string (HH:MM).

    Args:
        time_str: Time string

    Returns:
        Validated time string

    Raises:
        ValidationException: If time format is invalid
    """
    if not time_str:
        raise ValidationException("Time is required", field="time")

    pattern = r"^([01]\d|2[0-3]):([0-5]\d)$"

    if not re.match(pattern, time_str):
        raise ValidationException(
            "Invalid time format",
            field="time",
            details={"expected_format": "HH:MM", "example": "14:30"}
        )

    return time_str


def validate_appointment_code(code: str) -> str:
    """
    Validate appointment code format.

    Args:
        code: Appointment code

    Returns:
        Validated code

    Raises:
        ValidationException: If code format is invalid
    """
    if not code:
        raise ValidationException("Appointment code is required", field="appointment_code")

    # Format: APT-XXXXXXXX (APT- followed by 8 alphanumeric chars)
    pattern = r"^APT-[A-Z0-9]{8}$"

    if not re.match(pattern, code):
        raise ValidationException(
            "Invalid appointment code format",
            field="appointment_code",
            details={"expected_format": "APT-XXXXXXXX", "example": "APT-12AB34CD"}
        )

    return code


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename (prevent path traversal).

    Args:
        filename: Original filename

    Returns:
        Safe filename

    Raises:
        ValidationException: If filename is invalid
    """
    if not filename:
        raise ValidationException("Filename is required", field="filename")

    # Remove path separators and special chars
    safe_filename = re.sub(r"[^\w\.\-]", "_", filename)

    # Remove leading dots (prevent hidden files)
    safe_filename = safe_filename.lstrip(".")

    # Check for path traversal
    if ".." in safe_filename or "/" in safe_filename or "\\" in safe_filename:
        raise ValidationException(
            "Filename contains invalid characters",
            field="filename"
        )

    return safe_filename


def validate_url(url: str, allowed_schemes: Optional[list[str]] = None) -> str:
    """
    Validate URL.

    Args:
        url: URL string
        allowed_schemes: Allowed schemes (default: http, https)

    Returns:
        Validated URL

    Raises:
        ValidationException: If URL is invalid
    """
    if not url:
        raise ValidationException("URL is required", field="url")

    if allowed_schemes is None:
        allowed_schemes = ["http", "https"]

    # Basic URL validation
    pattern = r"^(https?|ftp)://[^\s/$.?#].[^\s]*$"

    if not re.match(pattern, url, re.IGNORECASE):
        raise ValidationException("Invalid URL format", field="url")

    # Check scheme
    scheme = url.split("://")[0].lower()
    if scheme not in allowed_schemes:
        raise ValidationException(
            f"URL scheme '{scheme}' not allowed",
            field="url",
            details={"allowed_schemes": allowed_schemes}
        )

    return url
