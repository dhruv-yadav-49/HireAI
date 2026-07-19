"""
app/security/authentication_pipeline.py

Explicit authentication pipeline (CTO refinement #2).

Chain:
    HTTP Request
        │
    ┌───┴──────────────────────────┐
    │  Bearer token present?       │
    │  YES → JWT decode            │
    │  NO  → X-API-Key header?     │
    │         YES → API Key auth   │
    │         NO  → 401            │
    └─────────────────────────────┘
        │
    Identity resolved
        │
    SecurityContext built
        │
    Passed to AuthorizationEngine

ADR-021: Zero Trust — every request is authenticated independently.
ADR-021: Security by Composition — pipeline wraps business logic.
"""
import uuid
from typing import Optional, Tuple

import jwt
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import TokenManager
from app.models.enums import AuthMethod, OrganizationRole
from app.security.api_key_manager import APIKeyManager
from app.security.rbac_engine import RBACEngine
from app.security.security_context import SecurityContext, build_security_context


_API_KEY_HEADER = "X-API-Key"
_BEARER_PREFIX = "Bearer "


class AuthenticationError(Exception):
    """Raised when authentication fails at any stage in the pipeline."""
    def __init__(self, message: str, status_code: int = 401) -> None:
        super().__init__(message)
        self.status_code = status_code


class AuthenticationPipeline:
    """Resolves the caller's identity and builds a SecurityContext.

    Tries authentication methods in priority order:
        1. Bearer JWT (existing platform auth)
        2. X-API-Key header (new API key auth)

    OAuth and OIDC are resolved before this pipeline via their respective
    authorization flows, which ultimately issue JWTs.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def authenticate(self, request: Request) -> SecurityContext:
        """Authenticate the request and return an immutable SecurityContext.

        Raises AuthenticationError if no valid credentials are found.
        """
        ip_address = self._extract_ip(request)
        user_agent = request.headers.get("User-Agent", "")
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        correlation_id = request.headers.get("X-Correlation-ID", request_id)

        # ── Method 1: Bearer JWT ───────────────────────────────────────────────
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith(_BEARER_PREFIX):
            token = auth_header[len(_BEARER_PREFIX):]
            return await self._authenticate_jwt(
                token=token,
                request_id=request_id,
                correlation_id=correlation_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )

        # ── Method 2: API Key ──────────────────────────────────────────────────
        api_key_raw = request.headers.get(_API_KEY_HEADER, "")
        if api_key_raw:
            return await self._authenticate_api_key(
                raw_key=api_key_raw,
                request_id=request_id,
                correlation_id=correlation_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )

        raise AuthenticationError("No authentication credentials provided.")

    # ── Private methods ────────────────────────────────────────────────────────

    async def _authenticate_jwt(
        self,
        token: str,
        request_id: str,
        correlation_id: str,
        ip_address: Optional[str],
        user_agent: str,
    ) -> SecurityContext:
        """Validate JWT and resolve user + org → SecurityContext."""
        try:
            payload = TokenManager.decode_access_token(token)
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Access token has expired.", 401)
        except Exception:
            raise AuthenticationError("Invalid access token.", 401)

        if payload.get("type") != "access":
            raise AuthenticationError("Token is not an access token.", 401)

        user_id_str = payload.get("sub")
        if not user_id_str:
            raise AuthenticationError("Token payload missing subject.", 401)

        # Resolve user + membership for role/permissions
        from app.repositories.user_repository import UserRepository
        from app.repositories.user_session_repository import UserSessionRepository
        from app.repositories.organization_repository import OrganizationRepository

        user_repo = UserRepository(self._db)
        user = await user_repo.get_by_id(uuid.UUID(user_id_str))
        if not user or not user.is_active:
            raise AuthenticationError("User not found or deactivated.", 401)

        # Resolve session for org context
        sid = payload.get("sid")
        org_id: Optional[uuid.UUID] = None
        role = OrganizationRole.MEMBER

        if sid:
            session_repo = UserSessionRepository(self._db)
            session = await session_repo.get_by_id(uuid.UUID(sid))
            if session and session.active_organization_id:
                org_id = session.active_organization_id
                # Resolve membership role
                org_repo = OrganizationRepository(self._db)
                membership = await org_repo.get_active_membership(org_id, user.id)
                if membership:
                    role = membership.role

        permissions = RBACEngine.permissions_as_strings(role)

        return build_security_context(
            user_id=user.id,
            organization_id=org_id or uuid.UUID(int=0),
            roles={role.value},
            permissions=permissions,
            auth_method=AuthMethod.JWT,
            request_id=request_id,
            correlation_id=correlation_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def _authenticate_api_key(
        self,
        raw_key: str,
        request_id: str,
        correlation_id: str,
        ip_address: Optional[str],
        user_agent: str,
    ) -> SecurityContext:
        """Validate an API key and build SecurityContext from key metadata."""
        prefix = APIKeyManager.extract_prefix(raw_key)
        if not prefix:
            raise AuthenticationError("Malformed API key format.", 401)

        from app.repositories.security_repository import SecurityRepository
        repo = SecurityRepository(self._db)
        key_record = await repo.get_api_key_by_prefix(prefix)

        if key_record is None:
            raise AuthenticationError("API key not found.", 401)

        if not APIKeyManager.verify_key(raw_key, key_record.hashed_key):
            raise AuthenticationError("Invalid API key.", 401)

        if key_record.status.value != "ACTIVE":
            raise AuthenticationError(f"API key is {key_record.status.value}.", 401)

        if APIKeyManager.is_expired(key_record.expires_at):
            raise AuthenticationError("API key has expired.", 401)

        # Update last-used metadata
        await repo.touch_api_key(
            key_record.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # API keys have limited scopes — map to permission strings
        scopes = key_record.scopes_json or []
        permissions = frozenset(scopes)

        return build_security_context(
            user_id=key_record.user_id or uuid.UUID(int=0),
            organization_id=key_record.organization_id,
            roles={"api_key"},
            permissions=permissions,
            auth_method=AuthMethod.API_KEY,
            api_key_id=key_record.id,
            request_id=request_id,
            correlation_id=correlation_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    @staticmethod
    def _extract_ip(request: Request) -> Optional[str]:
        """Extract client IP, respecting X-Forwarded-For (reverse proxy)."""
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return None
