# services/booking_agent_service/utils/logger.py

"""
Structured logging for observability.
Staff Engineer principle: Proper logging for debugging, monitoring, and auditing.
"""

import logging
import sys
import json
from datetime import datetime
from typing import Any
from ..config import settings


class StructuredLogger:
    """
    Structured logger for JSON-formatted logs.

    Benefits:
    - Machine-readable logs
    - Easy to parse and analyze
    - Better for log aggregation tools (ELK, Splunk)
    """

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, settings.LOG_LEVEL))

        # Console handler
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(getattr(logging, settings.LOG_LEVEL))

        if settings.LOG_FORMAT == "json":
            formatter = JsonFormatter()
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )

        handler.setFormatter(formatter)

        # Clear existing handlers to avoid duplicates
        self.logger.handlers.clear()
        self.logger.addHandler(handler)

    def _log(self, level: str, message: str, **kwargs):
        """Internal log method with structured data"""
        extra = {
            'extra_data': kwargs,
            'timestamp': datetime.utcnow().isoformat()
        }
        getattr(self.logger, level)(message, extra=extra)

    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self._log('debug', message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message"""
        self._log('info', message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self._log('warning', message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message"""
        self._log('error', message, **kwargs)

    def critical(self, message: str, **kwargs):
        """Log critical message"""
        self._log('critical', message, **kwargs)

    def audit(self, action: str, user_id: str = None, resource_id: str = None, **kwargs):
        """
        Special audit log for security and compliance.

        Args:
            action: Action performed (e.g., "APPOINTMENT_CREATED")
            user_id: User identifier (phone number, customer_id)
            resource_id: Resource identifier (appointment_id)
        """
        self.info(
            f"AUDIT: {action}",
            action=action,
            user_id=user_id,
            resource_id=resource_id,
            **kwargs
        )


class JsonFormatter(logging.Formatter):
    """Custom JSON formatter for structured logs"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }

        # Add extra data if available
        if hasattr(record, 'extra_data'):
            log_data['extra'] = record.extra_data

        # Add exception info if available
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


# Global logger instance
def get_logger(name: str) -> StructuredLogger:
    """
    Get or create a logger instance.

    Args:
        name: Logger name (usually module name)

    Returns:
        Configured StructuredLogger instance
    """
    return StructuredLogger(name)
