"""
Shared Security Module

Provides security utilities across all services:
- Authentication (JWT, API Key)
- Authorization
- Rate limiting
- Encryption
- Input validation
"""

from .auth import (
    create_jwt_token,
    verify_jwt_token,
    verify_api_key,
    get_current_user,
    require_api_key
)
from .rate_limiter import (
    RateLimiter,
    get_rate_limiter,
    rate_limit_middleware
)
from .encryption import (
    encrypt_data,
    decrypt_data,
    hash_password,
    verify_password,
    generate_secure_token
)
from .validator import (
    sanitize_input,
    validate_phone_number,
    validate_email,
    is_safe_string
)

__all__ = [
    "create_jwt_token",
    "verify_jwt_token",
    "verify_api_key",
    "get_current_user",
    "require_api_key",
    "RateLimiter",
    "get_rate_limiter",
    "rate_limit_middleware",
    "encrypt_data",
    "decrypt_data",
    "hash_password",
    "verify_password",
    "generate_secure_token",
    "sanitize_input",
    "validate_phone_number",
    "validate_email",
    "is_safe_string",
]
