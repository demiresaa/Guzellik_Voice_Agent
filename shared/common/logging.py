"""
shared/common/logging.py

Structured Logging Infrastructure

Enterprise-grade logging with:
- JSON structured logs (production)
- Human-readable format (development)
- PII masking
- Trace correlation
- Security audit logging
"""

import logging
import sys
import json
import re
from datetime import datetime
from typing import Optional, Any, Dict
from contextvars import ContextVar
from functools import wraps
import traceback

# Context variables for request tracing
trace_id_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar("user_id", default=None)


class PII:
    """
    PII (Personally Identifiable Information) patterns for masking.

    Protects sensitive data in logs (GDPR/KVKK compliance).
    """

    PATTERNS = {
        "phone": re.compile(r"(05\d{2})(\d{3})(\d{4})"),  # Turkish phone
        "email": re.compile(r"([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"),
        "credit_card": re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
        "api_key": re.compile(r"(api[_-]?key|apikey|key)[\s:=]+['\"]?([a-zA-Z0-9]{32,})['\"]?", re.IGNORECASE),
        "password": re.compile(r"(password|passwd|pwd)[\s:=]+['\"]?([^\s'\"]+)['\"]?", re.IGNORECASE),
    }

    @classmethod
    def mask(cls, text: str) -> str:
        """
        Mask PII in text.

        Args:
            text: Text potentially containing PII

        Returns:
            Text with PII masked
        """
        if not isinstance(text, str):
            return text

        # Mask phone: 0532XXX5678
        text = cls.PATTERNS["phone"].sub(r"\1***\3", text)

        # Mask email: user***@domain.com
        text = cls.PATTERNS["email"].sub(r"\1***@\2", text)

        # Mask credit card: ****-****-****-1234
        text = cls.PATTERNS["credit_card"].sub("****-****-****-****", text)

        # Mask API keys
        text = cls.PATTERNS["api_key"].sub(r"\1: ***", text)

        # Mask passwords
        text = cls.PATTERNS["password"].sub(r"\1: ***", text)

        return text


class JSONFormatter(logging.Formatter):
    """
    JSON log formatter for structured logging.

    Outputs logs in JSON format for easy parsing by log aggregators
    (ELK, Splunk, CloudWatch, etc.)
    """

    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "service": self.service_name,
            "level": record.levelname,
            "logger": record.name,
            "message": PII.mask(record.getMessage()),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add trace context
        trace_id = trace_id_var.get()
        user_id = user_id_var.get()

        if trace_id:
            log_data["trace_id"] = trace_id
        if user_id:
            log_data["user_id"] = PII.mask(user_id)

        # Add extra fields from record
        if hasattr(record, "extra"):
            log_data.update(record.extra)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": PII.mask(str(record.exc_info[1])),
                "traceback": PII.mask("".join(traceback.format_exception(*record.exc_info)))
            }

        return json.dumps(log_data, ensure_ascii=False)


class HumanReadableFormatter(logging.Formatter):
    """
    Human-readable formatter for development.

    Colorized output with timestamp and context.
    """

    COLORS = {
        "DEBUG": "\033[36m",      # Cyan
        "INFO": "\033[32m",       # Green
        "WARNING": "\033[33m",    # Yellow
        "ERROR": "\033[31m",      # Red
        "CRITICAL": "\033[35m",   # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        color = self.COLORS.get(record.levelname, self.RESET)
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        message = PII.mask(record.getMessage())

        log_line = (
            f"{color}[{timestamp}] [{record.levelname}] "
            f"{record.name}:{record.lineno}{self.RESET} - {message}"
        )

        # Add trace context if available
        trace_id = trace_id_var.get()
        if trace_id:
            log_line += f" [trace_id={trace_id}]"

        # Add exception if present
        if record.exc_info:
            log_line += "\n" + PII.mask("".join(traceback.format_exception(*record.exc_info)))

        return log_line


def setup_logging(
    service_name: str,
    log_level: str = "INFO",
    log_format: str = "json"
) -> None:
    """
    Setup logging for the service.

    Args:
        service_name: Name of the service
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Format (json or text)
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Set formatter
    if log_format == "json":
        formatter = JSONFormatter(service_name)
    else:
        formatter = HumanReadableFormatter()

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Suppress noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def set_trace_context(trace_id: Optional[str] = None, user_id: Optional[str] = None) -> None:
    """
    Set trace context for current request.

    Args:
        trace_id: Unique trace ID for request correlation
        user_id: User ID for user-specific logging
    """
    if trace_id:
        trace_id_var.set(trace_id)
    if user_id:
        user_id_var.set(user_id)


def clear_trace_context() -> None:
    """Clear trace context after request."""
    trace_id_var.set(None)
    user_id_var.set(None)


def log_function_call(logger: logging.Logger):
    """
    Decorator to log function calls with timing.

    Usage:
        @log_function_call(logger)
        async def my_function(arg1, arg2):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = datetime.utcnow()
            logger.info(f"Calling {func.__name__}", extra={
                "function": func.__name__,
                "args_count": len(args),
                "kwargs": list(kwargs.keys())
            })

            try:
                result = await func(*args, **kwargs)
                duration = (datetime.utcnow() - start_time).total_seconds() * 1000

                logger.info(f"Completed {func.__name__}", extra={
                    "function": func.__name__,
                    "duration_ms": duration,
                    "success": True
                })

                return result

            except Exception as e:
                duration = (datetime.utcnow() - start_time).total_seconds() * 1000

                logger.error(f"Failed {func.__name__}", extra={
                    "function": func.__name__,
                    "duration_ms": duration,
                    "success": False,
                    "error": str(e)
                }, exc_info=True)

                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = datetime.utcnow()
            logger.info(f"Calling {func.__name__}", extra={
                "function": func.__name__,
                "args_count": len(args),
                "kwargs": list(kwargs.keys())
            })

            try:
                result = func(*args, **kwargs)
                duration = (datetime.utcnow() - start_time).total_seconds() * 1000

                logger.info(f"Completed {func.__name__}", extra={
                    "function": func.__name__,
                    "duration_ms": duration,
                    "success": True
                })

                return result

            except Exception as e:
                duration = (datetime.utcnow() - start_time).total_seconds() * 1000

                logger.error(f"Failed {func.__name__}", extra={
                    "function": func.__name__,
                    "duration_ms": duration,
                    "success": False,
                    "error": str(e)
                }, exc_info=True)

                raise

        # Return appropriate wrapper based on function type
        if hasattr(func, "__code__") and func.__code__.co_flags & 0x0080:  # CO_COROUTINE
            return async_wrapper
        return sync_wrapper

    return decorator
