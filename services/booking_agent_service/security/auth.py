# services/booking_agent_service/security/auth.py

"""
API Authentication and Authorization.
Staff Engineer principle: Defense in depth, secure by default.

Security Features:
- API Key authentication for agent-to-agent communication
- Constant-time comparison to prevent timing attacks
- Secure token generation
- IP whitelisting support
"""

from fastapi import Security, HTTPException, status, Request
from fastapi.security import APIKeyHeader
from typing import Optional
import secrets
import hmac
from ..config import settings
from ..utils.logger import get_logger

logger = get_logger(__name__)

# API Key header name
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def verify_api_key(api_key: str) -> bool:
    """
    Verify API key using constant-time comparison.

    Security: Prevents timing attacks by using hmac.compare_digest
    which takes the same time regardless of where strings differ.

    Args:
        api_key: API key to verify

    Returns:
        True if valid, False otherwise
    """
    if not api_key:
        return False

    # Constant-time comparison to prevent timing attacks
    expected_key = settings.API_KEY.encode('utf-8')
    provided_key = api_key.encode('utf-8')

    return hmac.compare_digest(expected_key, provided_key)


async def get_api_key(
    request: Request,
    api_key_header: str = Security(api_key_header)
) -> str:
    """
    FastAPI dependency for API key authentication.

    Usage:
        @app.get("/protected", dependencies=[Depends(get_api_key)])
        async def protected_route():
            return {"message": "Authenticated"}

    Security Features:
    - Logs authentication attempts (audit trail)
    - IP-based tracking
    - Failed attempt monitoring

    Args:
        request: FastAPI request object
        api_key_header: API key from header

    Returns:
        Validated API key

    Raises:
        HTTPException: If authentication fails
    """
    client_ip = request.client.host if request.client else "unknown"

    # Check if API key is provided
    if not api_key_header:
        logger.warning(
            "Authentication failed: Missing API key",
            ip=client_ip,
            endpoint=request.url.path
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "UnauthorizedError",
                "message": "API key is required for authentication",
                "hint": "Include X-API-Key header in your request"
            },
            headers={"WWW-Authenticate": "ApiKey"}
        )

    # Verify API key
    if not verify_api_key(api_key_header):
        logger.warning(
            "Authentication failed: Invalid API key",
            ip=client_ip,
            endpoint=request.url.path,
            key_prefix=api_key_header[:8] if api_key_header else None
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "UnauthorizedError",
                "message": "Invalid API key",
                "hint": "Check your API key and try again"
            },
            headers={"WWW-Authenticate": "ApiKey"}
        )

    # Success - log for audit
    logger.audit(
        action="API_KEY_AUTHENTICATED",
        ip=client_ip,
        endpoint=request.url.path
    )

    return api_key_header


def generate_api_key(length: int = 32) -> str:
    """
    Generate a cryptographically secure API key.

    Usage:
        >>> new_key = generate_api_key()
        >>> print(f"Your new API key: {new_key}")

    Security: Uses secrets module for cryptographic randomness.

    Args:
        length: Key length in bytes (default 32 = 256 bits)

    Returns:
        Hexadecimal API key string
    """
    return secrets.token_hex(length)


class IPWhitelist:
    """
    IP whitelist for additional security layer.

    Usage:
        whitelist = IPWhitelist(["127.0.0.1", "192.168.1.0/24"])
        if not whitelist.is_allowed(client_ip):
            raise HTTPException(403, "IP not whitelisted")
    """

    def __init__(self, allowed_ips: Optional[list[str]] = None):
        """
        Initialize IP whitelist.

        Args:
            allowed_ips: List of allowed IP addresses or CIDR ranges
        """
        self.allowed_ips = set(allowed_ips or [])
        self.enabled = bool(allowed_ips)

    def is_allowed(self, ip: str) -> bool:
        """
        Check if IP is whitelisted.

        Args:
            ip: IP address to check

        Returns:
            True if allowed or whitelist disabled, False otherwise
        """
        if not self.enabled:
            return True

        # Exact match
        if ip in self.allowed_ips:
            return True

        # TODO: Add CIDR range matching if needed
        # For now, exact match only

        return False

    def add_ip(self, ip: str):
        """Add IP to whitelist"""
        self.allowed_ips.add(ip)
        self.enabled = True

    def remove_ip(self, ip: str):
        """Remove IP from whitelist"""
        self.allowed_ips.discard(ip)


async def verify_agent_identity(
    request: Request,
    api_key: str = Security(get_api_key)
) -> dict:
    """
    Verify agent identity and return agent info.

    This is an enhanced authentication that returns agent metadata.

    Args:
        request: FastAPI request
        api_key: Validated API key

    Returns:
        Agent identity information
    """
    client_ip = request.client.host if request.client else "unknown"

    # In production, you would:
    # 1. Query database for API key metadata
    # 2. Return agent permissions, rate limits, etc.
    # 3. Track agent usage

    agent_info = {
        "authenticated": True,
        "ip": client_ip,
        "agent_type": "conversation_agent",  # Could be determined from key
        "permissions": ["read", "write"],     # Permission set
        "rate_limit_tier": "standard"         # Rate limit tier
    }

    logger.info(
        "Agent authenticated",
        agent_type=agent_info["agent_type"],
        ip=client_ip
    )

    return agent_info


# Future: JWT Token Authentication
class JWTAuth:
    """
    JWT-based authentication for future use.

    When scaling to multiple agents or web clients,
    use JWT for stateless authentication.
    """

    def __init__(self, secret_key: str):
        self.secret_key = secret_key

    def create_token(self, payload: dict) -> str:
        """Create JWT token"""
        # TODO: Implement JWT creation
        raise NotImplementedError("JWT auth not yet implemented")

    def verify_token(self, token: str) -> dict:
        """Verify and decode JWT token"""
        # TODO: Implement JWT verification
        raise NotImplementedError("JWT auth not yet implemented")
