"""
shared/security/rate_limiter.py

Advanced Rate Limiting

Token bucket algorithm with Redis backend for distributed rate limiting.
Supports multiple limit types: global, per-IP, per-user, per-phone.

Security Features:
- DDoS protection
- SMS bombing prevention
- API abuse prevention
- Distributed rate limiting (Redis)
"""

import time
import asyncio
from typing import Optional, Dict, Literal
from datetime import datetime, timedelta
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from shared.common.exceptions import RateLimitException
from shared.common.logging import get_logger
from shared.common.constants import (
    RATE_LIMIT_GLOBAL,
    RATE_LIMIT_PER_IP,
    RATE_LIMIT_PER_USER,
    RATE_LIMIT_SMS
)

logger = get_logger(__name__)


class TokenBucket:
    """
    Token bucket rate limiter (in-memory).

    Algorithm:
    - Bucket starts with max_tokens
    - Tokens refill at constant rate
    - Request consumes 1 token
    - Request blocked if no tokens available
    """

    def __init__(self, rate: int, per: int = 60):
        """
        Initialize token bucket.

        Args:
            rate: Number of tokens (requests)
            per: Time period in seconds (default 60 = per minute)
        """
        self.rate = rate
        self.per = per
        self.allowance = float(rate)
        self.last_check = time.time()

    def is_allowed(self) -> bool:
        """
        Check if request is allowed.

        Returns:
            True if request allowed, False if rate limited
        """
        current = time.time()
        time_passed = current - self.last_check
        self.last_check = current

        # Refill tokens based on time passed
        self.allowance += time_passed * (self.rate / self.per)

        # Cap at maximum rate
        if self.allowance > self.rate:
            self.allowance = self.rate

        # Check if we have tokens
        if self.allowance < 1.0:
            return False

        # Consume one token
        self.allowance -= 1.0
        return True

    def get_retry_after(self) -> int:
        """Get seconds until next token available."""
        if self.allowance >= 1.0:
            return 0

        tokens_needed = 1.0 - self.allowance
        seconds_per_token = self.per / self.rate
        return int(tokens_needed * seconds_per_token) + 1


class RateLimiter:
    """
    Distributed rate limiter with Redis backend.

    Supports fallback to in-memory if Redis unavailable.
    """

    def __init__(self, redis_client=None):
        """
        Initialize rate limiter.

        Args:
            redis_client: Optional Redis client (async) for distributed limiting
        """
        self.redis = redis_client
        self.memory_buckets: Dict[str, TokenBucket] = {}
        self.use_redis = redis_client is not None

        if self.use_redis:
            logger.info("Rate limiter initialized with Redis backend")
        else:
            logger.warning("Rate limiter using in-memory backend (not distributed)")

    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int = 60
    ) -> tuple[bool, Optional[int]]:
        """
        Check if request is within rate limit.

        Args:
            key: Rate limit key (e.g., "ip:1.2.3.4", "user:123")
            limit: Maximum requests allowed
            window_seconds: Time window in seconds

        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        if self.use_redis:
            return await self._check_redis(key, limit, window_seconds)
        else:
            return self._check_memory(key, limit, window_seconds)

    async def _check_redis(
        self,
        key: str,
        limit: int,
        window_seconds: int
    ) -> tuple[bool, Optional[int]]:
        """Check rate limit using Redis."""
        try:
            # Redis key with namespace
            redis_key = f"rate_limit:{key}"

            # Get current count
            current = await self.redis.get(redis_key)

            if current is None:
                # First request, set count to 1 with expiration
                await self.redis.setex(redis_key, window_seconds, 1)
                return True, None

            current_count = int(current)

            if current_count >= limit:
                # Rate limit exceeded
                ttl = await self.redis.ttl(redis_key)
                retry_after = max(ttl, 1)

                logger.warning("Rate limit exceeded", extra={
                    "key": key,
                    "limit": limit,
                    "count": current_count,
                    "retry_after": retry_after
                })

                return False, retry_after

            # Increment count
            await self.redis.incr(redis_key)
            return True, None

        except Exception as e:
            logger.error("Redis rate limit check failed, falling back to memory", extra={
                "error": str(e)
            })
            # Fallback to memory on Redis failure
            return self._check_memory(key, limit, window_seconds)

    def _check_memory(
        self,
        key: str,
        limit: int,
        window_seconds: int
    ) -> tuple[bool, Optional[int]]:
        """Check rate limit using in-memory buckets."""
        # Get or create bucket
        if key not in self.memory_buckets:
            self.memory_buckets[key] = TokenBucket(rate=limit, per=window_seconds)

        bucket = self.memory_buckets[key]

        if bucket.is_allowed():
            return True, None
        else:
            retry_after = bucket.get_retry_after()
            logger.warning("Rate limit exceeded (memory)", extra={
                "key": key,
                "limit": limit,
                "retry_after": retry_after
            })
            return False, retry_after

    async def check_ip_limit(
        self,
        ip_address: str,
        limit: int = RATE_LIMIT_PER_IP
    ) -> tuple[bool, Optional[int]]:
        """Check rate limit for IP address."""
        return await self.check_rate_limit(f"ip:{ip_address}", limit, 60)

    async def check_user_limit(
        self,
        user_id: str,
        limit: int = RATE_LIMIT_PER_USER
    ) -> tuple[bool, Optional[int]]:
        """Check rate limit for user."""
        return await self.check_rate_limit(f"user:{user_id}", limit, 60)

    async def check_phone_limit(
        self,
        phone_number: str,
        limit: int = RATE_LIMIT_SMS,
        window_seconds: int = 3600  # 1 hour
    ) -> tuple[bool, Optional[int]]:
        """
        Check rate limit for phone number (SMS bombing prevention).

        Args:
            phone_number: Phone number
            limit: Max SMS per window (default 10)
            window_seconds: Window size (default 3600 = 1 hour)

        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        return await self.check_rate_limit(f"phone:{phone_number}", limit, window_seconds)

    async def check_global_limit(
        self,
        limit: int = RATE_LIMIT_GLOBAL
    ) -> tuple[bool, Optional[int]]:
        """Check global rate limit (DDoS protection)."""
        return await self.check_rate_limit("global", limit, 60)

    async def reset_limit(self, key: str) -> None:
        """
        Reset rate limit for key.

        Args:
            key: Rate limit key
        """
        if self.use_redis:
            try:
                redis_key = f"rate_limit:{key}"
                await self.redis.delete(redis_key)
                logger.info("Rate limit reset", extra={"key": key})
            except Exception as e:
                logger.error("Failed to reset rate limit", extra={"key": key, "error": str(e)})
        else:
            if key in self.memory_buckets:
                del self.memory_buckets[key]
                logger.info("Rate limit reset (memory)", extra={"key": key})


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def init_rate_limiter(redis_client=None) -> None:
    """
    Initialize global rate limiter.

    Args:
        redis_client: Optional Redis client for distributed rate limiting
    """
    global _rate_limiter
    _rate_limiter = RateLimiter(redis_client)
    logger.info("Global rate limiter initialized")


def get_rate_limiter() -> RateLimiter:
    """
    Get global rate limiter instance.

    Returns:
        RateLimiter instance

    Raises:
        RuntimeError: If rate limiter not initialized
    """
    if _rate_limiter is None:
        # Auto-initialize with memory backend
        init_rate_limiter()

    return _rate_limiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for automatic rate limiting.

    Applies IP-based rate limiting to all requests.
    """

    def __init__(self, app, rate_limiter: Optional[RateLimiter] = None):
        super().__init__(app)
        self.rate_limiter = rate_limiter or get_rate_limiter()

    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""

        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/ready", "/live", "/metrics"]:
            return await call_next(request)

        # Get client IP
        client_ip = request.client.host

        # Check IP rate limit
        is_allowed, retry_after = await self.rate_limiter.check_ip_limit(client_ip)

        if not is_allowed:
            logger.warning("Request blocked by rate limiter", extra={
                "ip": client_ip,
                "path": request.url.path,
                "retry_after": retry_after
            })

            # Return 429 Too Many Requests
            return Response(
                content='{"success": false, "error": {"code": "RATE_LIMIT_EXCEEDED", '
                        '"message": "Too many requests"}}',
                status_code=429,
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(RATE_LIMIT_PER_IP),
                    "X-RateLimit-Remaining": "0",
                    "Content-Type": "application/json"
                }
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(RATE_LIMIT_PER_IP)

        return response


async def rate_limit_middleware(request: Request, call_next):
    """
    Standalone rate limit middleware function.

    Usage:
        app.middleware("http")(rate_limit_middleware)
    """
    middleware = RateLimitMiddleware(None)
    return await middleware.dispatch(request, call_next)
