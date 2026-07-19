"""
app/security/api_key_manager.py

API Key generation, hashing, verification, and scope validation.

ADR-021: Secret Abstraction — raw keys are never stored. Only the SHA-256
hash is persisted. The 8-char prefix is stored in plaintext for O(1) lookup
before the expensive hash comparison.

Key format: hireai_<8-char-prefix>_<64-char-random-hex>
"""
import hashlib
import hmac
import os
import secrets
from typing import Optional


_KEY_RANDOM_BYTES = 32  # 64 hex chars
_PREFIX_LENGTH = 8


class APIKeyManager:
    """Stateless helpers for API key lifecycle management."""

    @staticmethod
    def generate_key() -> tuple[str, str, str]:
        """Generate a new API key.

        Returns:
            (raw_key, prefix, hashed_key)
            - raw_key: returned to the caller ONCE — never stored
            - prefix: stored in plaintext for fast prefix-based lookup
            - hashed_key: SHA-256 hex digest — stored in DB
        """
        random_hex = secrets.token_hex(_KEY_RANDOM_BYTES)
        prefix = random_hex[:_PREFIX_LENGTH]
        raw_key = f"hireai_{prefix}_{random_hex}"
        hashed = APIKeyManager.hash_key(raw_key)
        return raw_key, prefix, hashed

    @staticmethod
    def hash_key(raw_key: str) -> str:
        """SHA-256 hex digest of a raw API key."""
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    @staticmethod
    def verify_key(raw_key: str, hashed_key: str) -> bool:
        """Constant-time comparison — prevents timing oracle attacks."""
        candidate = APIKeyManager.hash_key(raw_key)
        return hmac.compare_digest(candidate, hashed_key)

    @staticmethod
    def extract_prefix(raw_key: str) -> Optional[str]:
        """Extract the prefix from a raw key for DB lookup.

        Returns None if the key format is invalid.
        """
        parts = raw_key.split("_")
        if len(parts) >= 3 and parts[0] == "hireai":
            return parts[1]
        return None

    @staticmethod
    def validate_scope(key_scopes: list[str], required_scope: str) -> bool:
        """Check whether a key's scopes satisfy a required scope.

        Supports wildcard: "jobs:*" satisfies "jobs:read" and "jobs:write".
        """
        if "*" in key_scopes:
            return True
        if required_scope in key_scopes:
            return True
        # Wildcard namespace: "jobs:*" satisfies "jobs:read"
        if ":" in required_scope:
            ns = required_scope.split(":")[0]
            if f"{ns}:*" in key_scopes:
                return True
        return False

    @staticmethod
    def is_expired(expires_at) -> bool:
        """Check whether the key's expiry has passed."""
        if expires_at is None:
            return False
        from datetime import datetime, timezone
        return datetime.now(timezone.utc) > expires_at
