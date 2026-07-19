import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt

try:
    from pwdlib import PasswordHash
    _password_hasher = PasswordHash.recommended()

    class PasswordManager:
        """Stateless helpers for hashing and verifying passwords."""

        @staticmethod
        def hash(plain_password: str) -> str:
            return _password_hasher.hash(plain_password)

        @staticmethod
        def verify(plain_password: str, hashed_password: str) -> bool:
            return _password_hasher.verify(plain_password, hashed_password)
except ImportError:
    try:
        from passlib.context import CryptContext
        _pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        class PasswordManager:
            """Stateless helpers for hashing and verifying passwords (passlib fallback)."""

            @staticmethod
            def hash(plain_password: str) -> str:
                return _pwd_context.hash(plain_password)

            @staticmethod
            def verify(plain_password: str, hashed_password: str) -> bool:
                return _pwd_context.verify(plain_password, hashed_password)
    except ImportError:
        import hashlib
        import hmac

        class PasswordManager:
            """Stateless helpers for hashing and verifying passwords (hashlib fallback)."""

            @staticmethod
            def hash(plain_password: str) -> str:
                return hashlib.sha256(plain_password.encode("utf-8")).hexdigest()

            @staticmethod
            def verify(plain_password: str, hashed_password: str) -> bool:
                computed = hashlib.sha256(plain_password.encode("utf-8")).hexdigest()
                return hmac.compare_digest(computed, hashed_password)


class TokenManager:
    """Create and decode access / refresh JWTs.

    JWT payload (ADR-001):
      sub  — user_id (UUID string)
      sid  — UserSession.id (UUID string) — Sprint 2C+
      type — "access" | "refresh"
      jti  — unique token ID
      iat  — issued at
      exp  — expiry

    Intentionally EXCLUDED (ADR-001):
      role — stale after role change; always resolved at runtime from membership
      org  — stale after org switch; always resolved from session.active_organization_id
    """

    @staticmethod
    def _create_token(
        subject: str,
        session_id: str | None,
        token_type: Literal["access", "refresh"],
        expires_delta: timedelta,
        secret: str,
    ) -> tuple[str, str]:
        now = datetime.now(timezone.utc)
        jti = str(uuid.uuid4())
        payload: dict = {
            "sub": subject,
            "type": token_type,
            "jti": jti,
            "iat": now,
            "exp": now + expires_delta,
        }
        if session_id is not None:
            payload["sid"] = session_id  # UserSession.id for context resolution
        encoded = jwt.encode(payload, secret, algorithm=settings.ALGORITHM)
        return encoded, jti

    @staticmethod
    def create_access_token(
        subject: str,
        session_id: str | None = None,
    ) -> tuple[str, str]:
        return TokenManager._create_token(
            subject=subject,
            session_id=session_id,
            token_type="access",
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
            secret=settings.SECRET_KEY,
        )

    @staticmethod
    def create_refresh_token(
        subject: str,
        session_id: str | None = None,
    ) -> tuple[str, str]:
        return TokenManager._create_token(
            subject=subject,
            session_id=session_id,
            token_type="refresh",
            expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            secret=settings.REFRESH_SECRET_KEY,
        )

    @staticmethod
    def decode_access_token(token: str) -> dict:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

    @staticmethod
    def decode_refresh_token(token: str) -> dict:
        return jwt.decode(token, settings.REFRESH_SECRET_KEY, algorithms=[settings.ALGORITHM])

    @staticmethod
    def hash_token(raw_token: str) -> str:
        """SHA-256 hex digest — used for storing refresh tokens and session tokens."""
        return hashlib.sha256(raw_token.encode()).hexdigest()
