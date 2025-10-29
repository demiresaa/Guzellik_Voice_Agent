"""
shared/common/constants.py

System-Wide Constants

Centralized constants used across all services.
"""

from enum import Enum


class ServiceName(str, Enum):
    """Service names for identification."""
    VOICE_INTERFACE = "voice-interface-client"
    CONVERSATION_AGENT = "conversation-agent"
    BOOKING_AGENT = "booking-agent"
    API_GATEWAY = "api-gateway"


class Environment(str, Enum):
    """Deployment environments."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """Logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class HTTPMethod(str, Enum):
    """HTTP methods."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    OPTIONS = "OPTIONS"
    HEAD = "HEAD"


class HeaderName(str, Enum):
    """Standard HTTP header names."""
    AUTHORIZATION = "Authorization"
    CONTENT_TYPE = "Content-Type"
    USER_AGENT = "User-Agent"
    X_API_KEY = "X-API-Key"
    X_REQUEST_ID = "X-Request-ID"
    X_TRACE_ID = "X-Trace-ID"
    X_USER_ID = "X-User-ID"
    X_FORWARDED_FOR = "X-Forwarded-For"


class ContentType(str, Enum):
    """Content type values."""
    JSON = "application/json"
    TEXT = "text/plain"
    HTML = "text/html"
    FORM = "application/x-www-form-urlencoded"
    MULTIPART = "multipart/form-data"
    EVENT_STREAM = "text/event-stream"
    OCTET_STREAM = "application/octet-stream"


class CacheKey(str, Enum):
    """Redis cache key prefixes."""
    SESSION = "session:"
    USER = "user:"
    RATE_LIMIT = "rate_limit:"
    CONVERSATION = "conversation:"
    APPOINTMENT = "appointment:"
    AVAILABILITY = "availability:"


class RateLimitBucket(str, Enum):
    """Rate limit bucket types."""
    GLOBAL = "global"
    IP = "ip"
    USER = "user"
    PHONE = "phone"
    ENDPOINT = "endpoint"


class MessageType(str, Enum):
    """SSE message types."""
    TOKEN = "token"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    STATUS = "status"
    ERROR = "error"
    DONE = "done"
    HEARTBEAT = "heartbeat"


class ToolName(str, Enum):
    """Available tool names."""
    GET_CUSTOMER_INFO = "get_customer_info"
    CREATE_CUSTOMER = "create_or_update_customer"
    CHECK_AVAILABILITY = "check_availability"
    CREATE_APPOINTMENT = "create_appointment"
    CANCEL_APPOINTMENT = "cancel_appointment"
    GET_SUGGESTIONS = "get_service_suggestions"
    GET_CAMPAIGNS = "get_active_campaigns"
    SEND_SMS = "send_sms_notification"
    REQUEST_PREPAYMENT = "request_prepayment"



class FeatureFlag(str, Enum):
    """
    Feature flags for enabling/disabling features dynamically.
    Allows for Canary Releases or A/B testing without redeployment.
    """
    USE_GEMINI_FLASH_MODEL = "use-gemini-flash-model"
    ENABLE_PREPAYMENT_FEATURE = "enable-prepayment-feature"
    NEW_APPOINTMENT_UI = "new-appointment-ui-enabled"
    ASYNC_SMS_NOTIFICATION = "async-sms-notification"


class ErrorCode(str, Enum):
    """
    Standardized API error codes for consistent client-side error handling.
    """
    # Genel Hatalar (1000-1999)
    VALIDATION_ERROR = "1001"
    UNAUTHENTICATED = "1002"
    PERMISSION_DENIED = "1003"
    RESOURCE_NOT_FOUND = "1004"
    RATE_LIMIT_EXCEEDED = "1005"
    INTERNAL_SERVER_ERROR = "1006"

    # Randevu Hataları (2000-2999)
    APPOINTMENT_SLOT_TAKEN = "2001"
    INVALID_APPOINTMENT_TIME = "2002"
    CANCELLATION_WINDOW_EXPIRED = "2003"
    CUSTOMER_NOT_FOUND = "2004"

    # Ödeme Hataları (3000-3999)
    PAYMENT_FAILED = "3001"
    PREPAYMENT_REQUIRED = "3002"


# Timing constants (seconds)
DEFAULT_TIMEOUT = 30
LONG_TIMEOUT = 120
SHORT_TIMEOUT = 10

# Session TTL (seconds)
SESSION_TTL = 1800  # 30 minutes
CACHE_TTL = 300     # 5 minutes

# Rate limiting
RATE_LIMIT_GLOBAL = 10000    # requests per minute
RATE_LIMIT_PER_IP = 100      # requests per minute
RATE_LIMIT_PER_USER = 60     # requests per minute
RATE_LIMIT_SMS = 10          # SMS per hour per phone

# Retry configuration
MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 2  # Exponential backoff: 1s, 2s, 4s

# Database
DB_POOL_SIZE = 10
DB_MAX_OVERFLOW = 20
DB_POOL_TIMEOUT = 30

# API versioning
API_VERSION = "v2"
API_PREFIX = f"/api/{API_VERSION}"

# Health check
HEALTH_CHECK_INTERVAL = 30  # seconds

# Security
MIN_API_KEY_LENGTH = 32
MIN_PASSWORD_LENGTH = 8
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_MINUTES = 30

# Business rules
APPOINTMENT_DURATION_MINUTES = 60
CANCELLATION_WINDOW_HOURS = 24
PREPAYMENT_THRESHOLD_TRY = 500.0
WORKING_HOURS_START = 9   # 09:00
WORKING_HOURS_END = 18    # 18:00

# LLM configuration
MAX_TOKENS = 2048
TEMPERATURE = 0.7
MAX_CONTEXT_MESSAGES = 20  # Keep last 20 messages in context

# File upload
MAX_UPLOAD_SIZE_MB = 10
ALLOWED_AUDIO_FORMATS = ["wav", "mp3", "ogg", "flac"]

# Monitoring
METRICS_PORT = 9090
HEALTH_CHECK_PATH = "/health"
METRICS_PATH = "/metrics"
READY_CHECK_PATH = "/ready"
LIVE_CHECK_PATH = "/live"

