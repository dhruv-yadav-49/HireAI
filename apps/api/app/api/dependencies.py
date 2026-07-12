"""
app/api/dependencies.py

FastAPI dependency chain:
    get_db()
        └─ get_current_user()         ← validate JWT sub
            └─ get_current_session() ← validate JWT sid → UserSession
                └─ get_request_context() ← build RequestContext (cached per request)
"""

import uuid
import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext, build_request_context
from app.core.security import TokenManager
from app.db.session import get_db
from app.models.user import User
from app.models.user_session import UserSession
from app.repositories.user_repository import UserRepository
from app.repositories.user_session_repository import UserSessionRepository
from app.core.exceptions import (
    AuthenticationException,
    TokenExpiredException,
    EmailNotVerifiedException,
)

_bearer_scheme = HTTPBearer()


# ── Step 1: Validate JWT, return User ─────────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    repo = UserRepository(db)
    try:
        payload = TokenManager.decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise TokenExpiredException()
    except Exception:
        raise AuthenticationException("Invalid or expired access token.")

    if payload.get("type") != "access":
        raise AuthenticationException("Token is not an access token.")

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationException("Token payload missing subject.")

    user = await repo.get_by_id(uuid.UUID(user_id))
    if user is None:
        raise AuthenticationException("User no longer exists.")

    if not user.is_active or getattr(user, "deleted_at", None) is not None:
        raise AuthenticationException("User account is deactivated.")

    return user


# ── Step 2: Validate session via JWT sid claim ─────────────────────────────────

async def get_current_session(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> UserSession:
    """
    Decodes the access JWT, extracts the `sid` (session_id) claim,
    fetches the UserSession, and validates:
      - Session is not revoked (revoked_at is None)
      - Session is not expired
      - session.user_id matches JWT.sub  ← SECURITY: prevents forged sid attack
    """
    try:
        payload = TokenManager.decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise TokenExpiredException()
    except Exception:
        raise AuthenticationException("Invalid or expired access token.")

    sid = payload.get("sid")
    if not sid:
        # Pre-Sprint-2C token without sid — force re-authentication.
        raise TokenExpiredException(
            "Session context required. Please log in again."
        )

    sub = payload.get("sub")
    if not sub:
        raise AuthenticationException("Token payload missing subject.")

    repo = UserSessionRepository(db)
    session = await repo.get_by_id(uuid.UUID(sid))

    if session is None:
        raise AuthenticationException("Session not found.")

    # SECURITY: prevents a forged sid from accessing another user's session
    if str(session.user_id) != sub:
        raise AuthenticationException("Session does not belong to this user.")

    if session.revoked_at is not None:
        raise AuthenticationException("Session has been revoked. Please log in again.")

    from datetime import datetime, timezone
    if session.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        raise TokenExpiredException("Session has expired. Please log in again.")

    return session


# ── Step 3: Build RequestContext (cached per request) ─────────────────────────

async def get_request_context(
    request: Request,
    user: User = Depends(get_current_user),
    session: UserSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> RequestContext:
    """
    Assembles and caches the RequestContext for the current request.
    Subsequent uses of this dependency in the same request hit the cache.
    """
    return await build_request_context(request, user, session, db)


# ── Shortcut: verified user only (email must be confirmed) ────────────────────

async def get_verified_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Enforce email verification on business-critical routes."""
    if not current_user.is_verified:
        raise EmailNotVerifiedException()
    return current_user
