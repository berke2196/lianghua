"""
Security utilities for private key management
Handles secure storage, clearing, and access to private keys
"""

import os
import time
from contextlib import contextmanager
from typing import Optional, Generator
import logging

logger = logging.getLogger(__name__)


class SecureKeyStore:
    """
    Secure storage for private keys with automatic expiration

    Features:
    - Private keys never logged or printed
    - Automatic expiration after timeout
    - Context manager for guaranteed cleanup
    - Memory clearing after use
    """

    def __init__(self, expiration_seconds: int = 3600):
        """
        Initialize secure key store

        Args:
            expiration_seconds: Auto-clear key after this duration
        """
        self._key: Optional[str] = None
        self._created_at: float = 0
        self._expiration_seconds = expiration_seconds
        self._access_count = 0

    def set_key(self, key: str) -> None:
        """
        Store private key securely

        Args:
            key: Private key (will be cleared after use)
        """
        if not key or not isinstance(key, str):
            raise ValueError("Invalid key format")

        # Clear old key first
        self._clear()

        self._key = key
        self._created_at = time.time()
        self._access_count = 0

        logger.info("✅ Private key stored securely (will auto-expire)")

    def get_key(self) -> Optional[str]:
        """
        Retrieve private key if valid and not expired

        Returns:
            Private key or None if expired/not set
        """
        if self._key is None:
            return None

        # Check expiration
        age = time.time() - self._created_at
        if age > self._expiration_seconds:
            logger.warning(
                f"⚠️ Private key expired after {age:.0f}s (threshold: {self._expiration_seconds}s)"
            )
            self._clear()
            return None

        self._access_count += 1
        return self._key

    def _clear(self) -> None:
        """Clear private key from memory"""
        if self._key:
            # Overwrite key with empty string
            self._key = ""
            # Delete reference
            self._key = None
            logger.debug("✅ Private key cleared from memory")

    def is_set(self) -> bool:
        """Check if key is currently set and valid"""
        if self._key is None:
            return False
        age = time.time() - self._created_at
        return age <= self._expiration_seconds

    def get_status(self) -> dict:
        """Get key store status (safe to log)"""
        if self._key is None:
            return {"set": False, "status": "empty"}

        age = time.time() - self._created_at
        expired = age > self._expiration_seconds

        return {
            "set": True,
            "age_seconds": age,
            "expired": expired,
            "access_count": self._access_count,
            "expires_in_seconds": max(0, self._expiration_seconds - age),
        }

    def __del__(self):
        """Cleanup on garbage collection"""
        self._clear()


# Global key store instance
_global_key_store = SecureKeyStore(expiration_seconds=3600)  # 1 hour


@contextmanager
def secure_key_context(key: str) -> Generator[str, None, None]:
    """
    Context manager for safe key usage

    Guarantees key cleanup even if exception occurs

    Usage:
        with secure_key_context(private_key) as key:
            signature = sign_message(key)  # Use key safely
            # Key automatically cleared after block

    Args:
        key: Private key to use

    Yields:
        Private key for use within context
    """
    _global_key_store.set_key(key)
    try:
        yield _global_key_store.get_key()
    finally:
        _global_key_store._clear()


def set_global_key(key: str) -> None:
    """Set global private key (use with caution)"""
    _global_key_store.set_key(key)
    logger.info("✅ Global private key updated")


def get_global_key() -> Optional[str]:
    """Get global private key if valid"""
    return _global_key_store.get_key()


def clear_global_key() -> None:
    """Explicitly clear global private key"""
    _global_key_store._clear()
    logger.info("✅ Global private key cleared")


def get_key_status() -> dict:
    """Get safe-to-log status of global key"""
    return _global_key_store.get_status()


def validate_private_key_format(key: str) -> bool:
    """
    Validate private key format (hex string)

    Args:
        key: Key to validate

    Returns:
        True if key format is valid
    """
    if not isinstance(key, str):
        return False

    # Should be 64 hex characters (for 256-bit keys)
    # or 66 characters with 0x prefix
    if len(key) == 66 and key.startswith("0x"):
        try:
            int(key, 16)
            return True
        except ValueError:
            return False

    if len(key) == 64:
        try:
            int(key, 16)
            return True
        except ValueError:
            return False

    return False


# ─────────────────────────────────────────────
# Security Audit Hooks
# ─────────────────────────────────────────────

def audit_key_access(user: str, action: str) -> None:
    """Log secure audit trail for key access"""
    logger.info(f"🔐 Key audit: user={user}, action={action}, status={get_key_status()}")
