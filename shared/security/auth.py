"""
shared/security/auth.py

Authentication & Authorization

Provides JWT and API key authentication with security best practices:
- Constant-time comparison (timing attack prevention)
- JWT with expiration
- Secure token generation
- FastAPI dependency injection
"""

import hmac
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import Header, HTTPException, status, Depends
from jose import JWTError, jwt
from pydantic import BaseModel

from shared.common.exceptions import AuthenticationException, AuthorizationException
from shared.common.logging import get_logger

logger = get_logger(__name__)


class TokenData(BaseModel):
    """JWT token payload data."""
    user_id: str
    phone_number: Optional[str] = None
    session_id: Optional[str] = None
    exp: Optional[datetime] = None


class JWTConfig:
    """JWT configuration."""
    def __init__(
        self,
        secret: str,
        algorithm: str = "HS256",
        expiration_minutes: int = 30
    ):
        if len(secret) < 32:
            raise ValueError("JWT secret must be at least 32 characters")

        self.secret = secret
        self.algorithm = algorithm
        self.expiration_minutes = expiration_minutes


# Global JWT config (initialized by service)
_jwt_config: Optional[JWTConfig] = None


def init_jwt_config(secret: str, algorithm: str = "HS256", expiration_minutes: int = 30) -> None:
    """
    Initialize JWT configuration.

    Must be called at service startup.

    Args:
        secret: JWT signing secret (min 32 chars)
        algorithm: Signing algorithm (default HS256)
        expiration_minutes: Token expiration time
    """
    global _jwt_config
    _jwt_config = JWTConfig(secret, algorithm, expiration_minutes)
    logger.info("JWT configuration initialized", extra={"algorithm": algorithm})


def get_jwt_config() -> JWTConfig:
    """Get JWT configuration (raises if not initialized)."""
    if _jwt_config is None:
        raise RuntimeError("JWT config not initialized. Call init_jwt_config() first.")
    return _jwt_config


def create_jwt_token(
    user_id: str,
    phone_number: Optional[str] = None,
    session_id: Optional[str] = None,
    additional_claims: Optional[Dict[str, Any]] = None
) -> str:
    """
    Create JWT token.

    Args:
        user_id: User identifier
        phone_number: User phone number (optional)
        session_id: Session identifier (optional)
        additional_claims: Additional JWT claims

    Returns:
        Encoded JWT token

    Raises:
        RuntimeError: If JWT config not initialized
    """
    config = get_jwt_config()

    # Calculate expiration
    expires_at = datetime.utcnow() + timedelta(minutes=config.expiration_minutes)

    # Build claims
    claims = {
        "user_id": user_id,
        "exp": expires_at,
        "iat": datetime.utcnow(),
        "jti": secrets.token_urlsafe(16),  # JWT ID for revocation
    }

    if phone_number:
        claims["phone_number"] = phone_number
    if session_id:
        claims["session_id"] = session_id
    if additional_claims:
        claims.update(additional_claims)

    # Encode token
    token = jwt.encode(claims, config.secret, algorithm=config.algorithm)

    logger.info("JWT token created", extra={
        "user_id": user_id,
        "expires_at": expires_at.isoformat()
    })

    return token


def verify_jwt_token(token: str) -> TokenData:
    """
    Verify and decode JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded token data

    Raises:
        AuthenticationException: If token is invalid or expired
    """
    config = get_jwt_config()

    try:
        # Decode and verify
        payload = jwt.decode(
            token,
            config.secret,
            algorithms=[config.algorithm]
        )

        # Extract data
        token_data = TokenData(
            user_id=payload.get("user_id"),
            phone_number=payload.get("phone_number"),
            session_id=payload.get("session_id"),
            exp=datetime.fromtimestamp(payload.get("exp"))
        )

        logger.debug("JWT token verified", extra={"user_id": token_data.user_id})

        return token_data

    except JWTError as e:
        logger.warning("JWT verification failed", extra={"error": str(e)})
        raise AuthenticationException(
            message="Invalid or expired token",
            details={"reason": str(e)}
        )


def verify_api_key(
    provided_key: str,
    expected_key: str
) -> bool:
    """
    Verify API key with constant-time comparison.

    Prevents timing attacks by comparing strings in constant time.

    Args:
        provided_key: API key from client
        expected_key: Expected API key from config

    Returns:
        True if keys match, False otherwise
    """
    if not provided_key or not expected_key:
        return False

    # Constant-time comparison (prevents timing attacks)
    return hmac.compare_digest(provided_key, expected_key)


async def require_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None)
) -> str:
    """
    FastAPI dependency to require API key.

    Checks X-API-Key header or Authorization: Bearer header.

    Args:
        x_api_key: X-API-Key header value
        authorization: Authorization header value

    Returns:
        Valid API key

    Raises:
        AuthenticationException: If API key is missing or invalid
    """
    from shared.common.config import get_settings
    settings = get_settings()

    if not settings.API_KEY:
        logger.warning("API_KEY not configured in settings")
        raise AuthenticationException("API authentication not configured")

    # Try X-API-Key header
    if x_api_key:
        if verify_api_key(x_api_key, settings.API_KEY):
            logger.debug("API key verified (X-API-Key header)")
            return x_api_key

    # Try Authorization: Bearer header
    if authorization and authorization.startswith("Bearer "):
        bearer_token = authorization[7:]  # Remove "Bearer " prefix
        if verify_api_key(bearer_token, settings.API_KEY):
            logger.debug("API key verified (Authorization header)")
            return bearer_token

    logger.warning("API key verification failed")
    raise AuthenticationException(
        message="Invalid or missing API key",
        details={"hint": "Provide API key via X-API-Key or Authorization header"}
    )


async def get_current_user(
    authorization: Optional[str] = Header(None)
) -> TokenData:
    """
    FastAPI dependency to get current authenticated user from JWT.

    Args:
        authorization: Authorization header (Bearer <token>)

    Returns:
        Token data with user information

    Raises:
        AuthenticationException: If token is missing or invalid
    """
    if not authorization:
        raise AuthenticationException("Missing authorization header")

    if not authorization.startswith("Bearer "):
        raise AuthenticationException("Invalid authorization header format. Use: Bearer <token>")

    token = authorization[7:]  # Remove "Bearer " prefix

    return verify_jwt_token(token)


async def require_permission(
    user: TokenData = Depends(get_current_user),
    required_permission: str = None
) -> TokenData:
    """
    FastAPI dependency to require specific permission.

    Args:
        user: Current user from JWT
        required_permission: Required permission string

    Returns:
        User token data if authorized

    Raises:
        AuthorizationException: If user lacks permission
    """
    # TODO: Implement permission checking logic
    # For now, just return user (all authenticated users have access)

    logger.debug("Permission check", extra={
        "user_id": user.user_id,
        "permission": required_permission
    })

    return user


def generate_api_key(length: int = 32) -> str:
    """
    Generate secure random API key.

    Args:
        length: Key length in bytes (default 32)

    Returns:
        Hex-encoded API key (64 characters for 32 bytes)
    """
    if length < 20:
        raise ValueError("API key length must be at least 16 bytes")

    return secrets.token_hex(length)


def hash_api_key(api_key: str) -> str:
    """
    Hash API key for storage.

    Args:
        api_key: Plain API key

    Returns:
        SHA-256 hash of API key
    """
    return hashlib.sha256(api_key.encode()).hexdigest()
