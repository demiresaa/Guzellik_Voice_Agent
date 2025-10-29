# services/booking_agent_service/security/__init__.py

"""
Security layer for Booking Agent Service.

Components:
- Authentication: API key verification
- Rate Limiting: DDoS and abuse prevention
- Input Validation: Injection attack prevention
"""

from .auth import (
    get_api_key,
    verify_api_key,
    verify_agent_identity,
    generate_api_key,
    IPWhitelist
)

from .rate_limiter import (
    RateLimiter,
    rate_limiter,
    rate_limit_middleware
)

from .validator import (
    InputValidator,
    validation_middleware,
    validate_date_format,
    validate_time_format,
    validate_appointment_id,
    sanitize_search_query
)

__all__ = [
    # Auth
    'get_api_key',
    'verify_api_key',
    'verify_agent_identity',
    'generate_api_key',
    'IPWhitelist',

    # Rate Limiting
    'RateLimiter',
    'rate_limiter',
    'rate_limit_middleware',

    # Validation
    'InputValidator',
    'validation_middleware',
    'validate_date_format',
    'validate_time_format',
    'validate_appointment_id',
    'sanitize_search_query'
]
