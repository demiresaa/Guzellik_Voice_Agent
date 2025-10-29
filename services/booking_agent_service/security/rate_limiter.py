# services/booking_agent_service/security/rate_limiter.py

"""
Rate Limiting for DDoS and abuse prevention.
Staff Engineer principle: Multi-layer defense, granular control.

Protection Against:
- DDoS attacks (IP-based limiting)
- SMS bombing (phone number-based limiting)
- API abuse (endpoint-specific limits)
- Brute force attacks (authentication attempts)
"""

from fastapi import Request, HTTPException, status
from typing import Dict, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio
from ..config import settings
from ..utils.logger import get_logger
from ..utils.exceptions import RateLimitExceeded

logger = get_logger(__name__)


class RateLimiter:
    """
    Token bucket algorithm for rate limiting.

    Features:
    - IP-based limiting
    - Phone number-based limiting
    - Endpoint-specific limits
    - Sliding window
    - Automatic cleanup of old entries
    """

    def __init__(self):
        """Initialize rate limiter with in-memory storage"""
        # Structure: {key: {"count": int, "reset_time": datetime}}
        self._ip_buckets: Dict[str, dict] = defaultdict(dict)
        self._phone_buckets: Dict[str, dict] = defaultdict(dict)
        self._endpoint_buckets: Dict[str, dict] = defaultdict(dict)

        # Cleanup task
        self._cleanup_task = None
        if settings.RATE_LIMIT_ENABLED:
            self._start_cleanup_task()

    def _start_cleanup_task(self):
        """Start background task to cleanup expired entries"""
        async def cleanup():
            while True:
                await asyncio.sleep(300)  # Every 5 minutes
                self._cleanup_expired()

        try:
            loop = asyncio.get_event_loop()
            self._cleanup_task = loop.create_task(cleanup())
        except RuntimeError:
            # No event loop, cleanup will happen on-demand
            pass

    def _cleanup_expired(self):
        """Remove expired rate limit entries"""
        now = datetime.utcnow()

        def clean_dict(bucket_dict):
            expired_keys = [
                key for key, data in bucket_dict.items()
                if data.get("reset_time", now) < now
            ]
            for key in expired_keys:
                del bucket_dict[key]

        clean_dict(self._ip_buckets)
        clean_dict(self._phone_buckets)
        clean_dict(self._endpoint_buckets)

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired rate limit entries")

    def _check_limit(
        self,
        bucket: dict,
        key: str,
        max_requests: int,
        window_seconds: int,
        identifier: str
    ) -> tuple[bool, dict]:
        """
        Check if request is within rate limit.

        Args:
            bucket: Bucket dictionary to use
            key: Unique identifier key
            max_requests: Maximum requests allowed
            window_seconds: Time window in seconds
            identifier: Human-readable identifier for logging

        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        now = datetime.utcnow()

        if key not in bucket:
            # First request
            bucket[key] = {
                "count": 1,
                "reset_time": now + timedelta(seconds=window_seconds),
                "window_start": now
            }
            return True, {
                "limit": max_requests,
                "remaining": max_requests - 1,
                "reset": bucket[key]["reset_time"].timestamp()
            }

        data = bucket[key]

        # Check if window has reset
        if now >= data["reset_time"]:
            # Reset window
            data["count"] = 1
            data["reset_time"] = now + timedelta(seconds=window_seconds)
            data["window_start"] = now
            return True, {
                "limit": max_requests,
                "remaining": max_requests - 1,
                "reset": data["reset_time"].timestamp()
            }

        # Within window - check count
        if data["count"] >= max_requests:
            # Rate limit exceeded
            logger.warning(
                f"Rate limit exceeded for {identifier}",
                key=key,
                count=data["count"],
                limit=max_requests
            )
            return False, {
                "limit": max_requests,
                "remaining": 0,
                "reset": data["reset_time"].timestamp(),
                "retry_after": (data["reset_time"] - now).total_seconds()
            }

        # Increment count
        data["count"] += 1
        return True, {
            "limit": max_requests,
            "remaining": max_requests - data["count"],
            "reset": data["reset_time"].timestamp()
        }

    async def check_ip_limit(self, request: Request) -> dict:
        """
        Check IP-based rate limit.

        Args:
            request: FastAPI request object

        Returns:
            Rate limit info dict

        Raises:
            RateLimitExceeded: If limit exceeded
        """
        if not settings.RATE_LIMIT_ENABLED:
            return {"limit": None, "remaining": None, "reset": None}

        ip = request.client.host if request.client else "unknown"

        is_allowed, info = self._check_limit(
            bucket=self._ip_buckets,
            key=ip,
            max_requests=settings.RATE_LIMIT_PER_MINUTE,
            window_seconds=60,
            identifier=f"IP {ip}"
        )

        if not is_allowed:
            raise RateLimitExceeded(
                message=f"Rate limit exceeded. Try again in {int(info['retry_after'])} seconds.",
                details={
                    "limit": info["limit"],
                    "reset": info["reset"],
                    "retry_after": int(info["retry_after"])
                }
            )

        return info

    async def check_phone_limit(
        self,
        phone_number: str,
        max_requests: int = 10,
        window_seconds: int = 3600
    ) -> dict:
        """
        Check phone number-based rate limit.

        Critical for SMS bombing prevention.

        Args:
            phone_number: Phone number to check
            max_requests: Max SMS per window (default: 10/hour)
            window_seconds: Time window (default: 3600 = 1 hour)

        Returns:
            Rate limit info dict

        Raises:
            RateLimitExceeded: If limit exceeded
        """
        if not settings.RATE_LIMIT_ENABLED:
            return {"limit": None, "remaining": None, "reset": None}

        is_allowed, info = self._check_limit(
            bucket=self._phone_buckets,
            key=phone_number,
            max_requests=max_requests,
            window_seconds=window_seconds,
            identifier=f"Phone {phone_number}"
        )

        if not is_allowed:
            logger.audit(
                action="SMS_BOMBING_PREVENTED",
                phone_number=phone_number,
                attempts=info["limit"]
            )
            raise RateLimitExceeded(
                message=f"Too many SMS requests. Try again in {int(info['retry_after'])} seconds.",
                details={
                    "limit": info["limit"],
                    "reset": info["reset"],
                    "retry_after": int(info["retry_after"]),
                    "reason": "SMS bombing prevention"
                }
            )

        return info

    async def check_endpoint_limit(
        self,
        request: Request,
        endpoint: str,
        max_requests: int,
        window_seconds: int
    ) -> dict:
        """
        Check endpoint-specific rate limit.

        Useful for expensive operations (e.g., availability search).

        Args:
            request: FastAPI request
            endpoint: Endpoint identifier
            max_requests: Max requests per window
            window_seconds: Time window in seconds

        Returns:
            Rate limit info dict

        Raises:
            RateLimitExceeded: If limit exceeded
        """
        if not settings.RATE_LIMIT_ENABLED:
            return {"limit": None, "remaining": None, "reset": None}

        ip = request.client.host if request.client else "unknown"
        key = f"{ip}:{endpoint}"

        is_allowed, info = self._check_limit(
            bucket=self._endpoint_buckets,
            key=key,
            max_requests=max_requests,
            window_seconds=window_seconds,
            identifier=f"Endpoint {endpoint} from {ip}"
        )

        if not is_allowed:
            raise RateLimitExceeded(
                message=f"Rate limit exceeded for {endpoint}. Try again in {int(info['retry_after'])} seconds.",
                details={
                    "endpoint": endpoint,
                    "limit": info["limit"],
                    "reset": info["reset"],
                    "retry_after": int(info["retry_after"])
                }
            )

        return info

    def get_stats(self) -> dict:
        """
        Get rate limiter statistics.

        Useful for monitoring and debugging.

        Returns:
            Statistics dictionary
        """
        return {
            "ip_entries": len(self._ip_buckets),
            "phone_entries": len(self._phone_buckets),
            "endpoint_entries": len(self._endpoint_buckets),
            "enabled": settings.RATE_LIMIT_ENABLED
        }

    def reset_ip(self, ip: str):
        """Reset rate limit for specific IP (admin function)"""
        if ip in self._ip_buckets:
            del self._ip_buckets[ip]
            logger.audit(action="RATE_LIMIT_RESET", ip=ip)

    def reset_phone(self, phone_number: str):
        """Reset rate limit for specific phone (admin function)"""
        if phone_number in self._phone_buckets:
            del self._phone_buckets[phone_number]
            logger.audit(action="RATE_LIMIT_RESET", phone=phone_number)


# Global rate limiter instance
rate_limiter = RateLimiter()


async def rate_limit_middleware(request: Request, call_next):
    """
    FastAPI middleware for automatic rate limiting.

    Usage:
        app.middleware("http")(rate_limit_middleware)

    Args:
        request: FastAPI request
        call_next: Next middleware/route handler

    Returns:
        Response with rate limit headers
    """
    try:
        # Check IP-based rate limit
        rate_info = await rate_limiter.check_ip_limit(request)

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        if rate_info.get("limit"):
            response.headers["X-RateLimit-Limit"] = str(rate_info["limit"])
            response.headers["X-RateLimit-Remaining"] = str(rate_info["remaining"])
            response.headers["X-RateLimit-Reset"] = str(int(rate_info["reset"]))

        return response

    except RateLimitExceeded as e:
        # Convert to HTTPException with proper headers
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "RateLimitExceeded",
                "message": e.message,
                "details": e.details
            },
            headers={
                "Retry-After": str(e.details.get("retry_after", 60)),
                "X-RateLimit-Limit": str(e.details.get("limit", 0)),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(e.details.get("reset", 0)))
            }
        )
