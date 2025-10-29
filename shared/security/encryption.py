"""
shared/security/encryption.py

Encryption & Hashing Utilities

Provides secure encryption, hashing, and token generation.
"""

import secrets
import hashlib
import base64
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
import bcrypt

from shared.common.logging import get_logger

logger = get_logger(__name__)


class EncryptionService:
    """
    Encryption service using Fernet (symmetric encryption).

    Uses AES-128 in CBC mode with PKCS7 padding.
    """

    def __init__(self, key: Optional[bytes] = None):
        """
        Initialize encryption service.

        Args:
            key: 32-byte encryption key (auto-generated if not provided)
        """
        if key is None:
            key = Fernet.generate_key()
        self.cipher = Fernet(key)
        self.key = key

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext.

        Args:
            plaintext: Text to encrypt

        Returns:
            Base64-encoded ciphertext
        """
        ciphertext = self.cipher.encrypt(plaintext.encode())
        return base64.urlsafe_b64encode(ciphertext).decode()

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt ciphertext.

        Args:
            ciphertext: Base64-encoded ciphertext

        Returns:
            Decrypted plaintext

        Raises:
            ValueError: If decryption fails
        """
        try:
            decoded = base64.urlsafe_b64decode(ciphertext.encode())
            plaintext = self.cipher.decrypt(decoded)
            return plaintext.decode()
        except Exception as e:
            logger.error("Decryption failed", extra={"error": str(e)})
            raise ValueError("Failed to decrypt data")


# Global encryption service
_encryption_service: Optional[EncryptionService] = None


def init_encryption_service(key: Optional[bytes] = None) -> None:
    """
    Initialize global encryption service.

    Args:
        key: Encryption key (generated if not provided)
    """
    global _encryption_service
    _encryption_service = EncryptionService(key)
    logger.info("Encryption service initialized")


def get_encryption_service() -> EncryptionService:
    """Get global encryption service (auto-initialize if needed)."""
    if _encryption_service is None:
        init_encryption_service()
    return _encryption_service


def encrypt_data(plaintext: str) -> str:
    """
    Encrypt data using global encryption service.

    Args:
        plaintext: Text to encrypt

    Returns:
        Encrypted ciphertext
    """
    service = get_encryption_service()
    return service.encrypt(plaintext)


def decrypt_data(ciphertext: str) -> str:
    """
    Decrypt data using global encryption service.

    Args:
        ciphertext: Encrypted text

    Returns:
        Decrypted plaintext
    """
    service = get_encryption_service()
    return service.decrypt(ciphertext)


def hash_password(password: str) -> str:
    """
    Hash password using bcrypt.

    Args:
        password: Plain password

    Returns:
        Hashed password (bcrypt format)
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode(), salt)
    return hashed.decode()


def verify_password(password: str, hashed: str) -> bool:
    """
    Verify password against bcrypt hash.

    Args:
        password: Plain password
        hashed: Bcrypt hashed password

    Returns:
        True if password matches, False otherwise
    """
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception as e:
        logger.error("Password verification failed", extra={"error": str(e)})
        return False


def generate_secure_token(length: int = 32) -> str:
    """
    Generate cryptographically secure random token.

    Args:
        length: Token length in bytes

    Returns:
        URL-safe base64-encoded token
    """
    return secrets.token_urlsafe(length)


def hash_sha256(data: str) -> str:
    """
    Hash data using SHA-256.

    Args:
        data: Data to hash

    Returns:
        Hex-encoded hash
    """
    return hashlib.sha256(data.encode()).hexdigest()


def derive_key_from_password(password: str, salt: Optional[bytes] = None) -> tuple[bytes, bytes]:
    """
    Derive encryption key from password using PBKDF2.

    Args:
        password: Password to derive key from
        salt: Salt (generated if not provided)

    Returns:
        Tuple of (derived_key, salt)
    """
    if salt is None:
        salt = secrets.token_bytes(16)

    kdf = PBKDF2(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )

    key = kdf.derive(password.encode())
    return key, salt
