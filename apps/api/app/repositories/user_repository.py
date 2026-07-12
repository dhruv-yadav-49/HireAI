import uuid
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.models.user_role import UserRole
from app.models.refresh_token import RefreshToken
from app.models.user_session import UserSession
from app.models.login_audit_log import LoginAuditLog

class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def count_users(self) -> int:
        result = await self.db.execute(select(func.count(User.id)))
        return result.scalar() or 0

    async def create_user(self, email: str, password_hash: str, role: UserRole, is_verified: bool) -> User:
        user = User(
            email=email,
            password_hash=password_hash,
            role=role,
            is_verified=is_verified,
        )
        self.db.add(user)
        await self.db.flush()
        return user

    async def create_refresh_token(
        self,
        user_id: uuid.UUID,
        jti: str,
        token_hash: str,
        expires_at: datetime,
        device_name: str | None = None,
        ip_address: str | None = None,
        replaced_by: str | None = None,
    ) -> RefreshToken:
        token = RefreshToken(
            user_id=user_id,
            jti=jti,
            token_hash=token_hash,
            expires_at=expires_at,
            device_name=device_name,
            ip_address=ip_address,
            replaced_by=replaced_by,
        )
        self.db.add(token)
        await self.db.flush()
        return token

    async def get_refresh_token_by_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked_at.is_(None)
            )
        )
        return result.scalar_one_or_none()

    async def revoke_refresh_token(self, token: RefreshToken, replaced_by_hash: str | None = None) -> None:
        token.revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)
        if replaced_by_hash:
            token.replaced_by = replaced_by_hash
        self.db.add(token)
        await self.db.flush()

    async def create_session(
        self,
        user_id: uuid.UUID,
        device_name: str | None,
        user_agent: str | None,
        last_ip: str | None,
        country: str | None,
    ) -> UserSession:
        session = UserSession(
            user_id=user_id,
            device_name=device_name,
            user_agent=user_agent,
            last_ip=last_ip,
            country=country,
            is_active=True,
        )
        self.db.add(session)
        await self.db.flush()
        return session

    async def create_audit_log(
        self,
        email: str,
        ip_address: str | None,
        event_type: str,
    ) -> LoginAuditLog:
        log = LoginAuditLog(
            email=email,
            ip_address=ip_address,
            event_type=event_type,
        )
        self.db.add(log)
        await self.db.flush()
        return log
