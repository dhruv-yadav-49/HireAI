"""
app/repositories/user_session_repository.py

UserSessionRepository — all DB operations on the user_sessions table.

Named UserSession* (not Session*) because sessions are scoped to users.
This naming stays unambiguous when AI/Webhook/Scheduler sessions land later.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_session import UserSession


class UserSessionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        user_id: uuid.UUID,
        jti: str,
        token_hash: str,
        expires_at: datetime,
        device_name: str | None = None,
        user_agent: str | None = None,
        ip_address: str | None = None,
        last_ip: str | None = None,
        country: str | None = None,
        active_organization_id: uuid.UUID | None = None,
    ) -> UserSession:
        session = UserSession(
            user_id=user_id,
            jti=jti,
            token_hash=token_hash,
            expires_at=expires_at,
            device_name=device_name,
            user_agent=user_agent,
            ip_address=ip_address,
            last_ip=last_ip or ip_address,
            country=country,
            is_active=True,
            active_organization_id=active_organization_id,
        )
        self.db.add(session)
        await self.db.flush()
        return session

    async def get_by_id(self, session_id: uuid.UUID) -> UserSession | None:
        result = await self.db.execute(
            select(UserSession).where(UserSession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_by_jti(self, jti: str) -> UserSession | None:
        result = await self.db.execute(
            select(UserSession).where(UserSession.jti == jti)
        )
        return result.scalar_one_or_none()

    async def get_active_sessions_for_user(
        self, user_id: uuid.UUID
    ) -> list[UserSession]:
        result = await self.db.execute(
            select(UserSession).where(
                UserSession.user_id == user_id,
                UserSession.is_active.is_(True),
                UserSession.revoked_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def update_active_organization(
        self,
        session: UserSession,
        org_id: uuid.UUID | None,
    ) -> UserSession:
        """Switch the session's active org. Caller must manage the transaction."""
        session.active_organization_id = org_id  # type: ignore[assignment]
        self.db.add(session)
        await self.db.flush()
        return session

    async def revoke(self, session: UserSession) -> None:
        """Mark session as revoked. Caller must commit."""
        session.revoked_at = datetime.now(timezone.utc)  # type: ignore[assignment]
        session.is_active = False  # type: ignore[assignment]
        self.db.add(session)
        await self.db.flush()
