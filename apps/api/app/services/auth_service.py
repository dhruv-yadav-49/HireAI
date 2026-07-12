import hashlib
import uuid
from datetime import datetime, timezone, timedelta
import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    UserAlreadyExistsException,
    InvalidCredentialsException,
    AuthenticationException,
    LoginLockedException,
    RefreshTokenRevokedException,
)
from app.core.security import PasswordManager, TokenManager
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, SignupRequest, TokenResponse
from app.models.user import User
from app.models.user_role import UserRole
from app.models.user_session import UserSession


def parse_device_name(user_agent_str: str | None) -> str:
    if not user_agent_str:
        return "Unknown"
    ua = user_agent_str.lower()
    
    # OS detection
    os_name = "Unknown OS"
    if "windows" in ua:
        os_name = "Windows"
    elif "macintosh" in ua or "mac os" in ua:
        os_name = "macOS"
    elif "linux" in ua:
        os_name = "Linux"
    elif "iphone" in ua or "ipad" in ua:
        os_name = "iOS"
    elif "android" in ua:
        os_name = "Android"

    # Browser detection
    browser_name = "Unknown Browser"
    if "chrome" in ua and "safari" in ua and "edge" not in ua and "opr" not in ua:
        browser_name = "Chrome"
    elif "safari" in ua and "chrome" not in ua:
        browser_name = "Safari"
    elif "firefox" in ua:
        browser_name = "Firefox"
    elif "edge" in ua or "edg" in ua:
        browser_name = "Edge"
    elif "opr" in ua or "opera" in ua:
        browser_name = "Opera"
        
    return f"{os_name} / {browser_name}"

class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)

    def _hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    async def signup(
        self,
        data: SignupRequest,
        user_agent: str | None = None,
        ip_address: str | None = None,
        country: str | None = "Unknown",
    ) -> TokenResponse:
        # Check duplicate email
        existing_user = await self.user_repo.get_by_email(data.email)
        if existing_user:
            await self.user_repo.create_audit_log(
                email=data.email,
                ip_address=ip_address,
                event_type="failed",
            )
            await self.db.commit()
            raise UserAlreadyExistsException()

        # Decide role (first user is Owner, rest default to Viewer)
        total_users = await self.user_repo.count_users()
        role = UserRole.OWNER if total_users == 0 else UserRole.VIEWER

        # Hash password and create user
        hashed_password = PasswordManager.hash(data.password)
        user = await self.user_repo.create_user(
            email=data.email,
            password_hash=hashed_password,
            role=role,
            is_verified=False,  # Defaults to False, user onboarding can verify it later
        )

        # Create session and tokens atomically
        token_response = await self._issue_new_session(
            user=user,
            device_name=parse_device_name(user_agent),
            ip_address=ip_address,
            user_agent=user_agent,
            country=country,
        )

        # Write audit log
        await self.user_repo.create_audit_log(
            email=user.email,
            ip_address=ip_address,
            event_type="signup",
        )
        await self.db.commit()

        return token_response

    async def login(
        self,
        data: LoginRequest,
        user_agent: str | None = None,
        ip_address: str | None = None,
        country: str | None = "Unknown",
    ) -> TokenResponse:
        now_utc = datetime.now(timezone.utc)

        # Fetch user
        user = await self.user_repo.get_by_email(data.email)

        # 1. User Existence
        if not user:
            await self.user_repo.create_audit_log(
                email=data.email,
                ip_address=ip_address,
                event_type="failed",
            )
            await self.db.commit()
            raise InvalidCredentialsException()

        # 2. Lock check
        if user.locked_until:
            locked_until_tz = user.locked_until.replace(tzinfo=timezone.utc)
            if now_utc < locked_until_tz:
                await self.user_repo.create_audit_log(
                    email=user.email,
                    ip_address=ip_address,
                    event_type="locked",
                )
                await self.db.commit()
                raise LoginLockedException()
            else:
                # Lock expired, reset attempts
                user.failed_login_attempts = 0
                user.locked_until = None

        # 3. Active Status Check
        if not user.is_active or user.deleted_at is not None:
            await self.user_repo.create_audit_log(
                email=user.email,
                ip_address=ip_address,
                event_type="failed",
            )
            await self.db.commit()
            raise AuthenticationException("User account is deactivated.")

        # 4. Password verification
        if not PasswordManager.verify(data.password, user.password_hash):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                user.locked_until = now_utc + timedelta(minutes=15)
                event = "locked"
            else:
                event = "failed"
            
            await self.user_repo.create_audit_log(
                email=user.email,
                ip_address=ip_address,
                event_type=event,
            )
            self.db.add(user)
            await self.db.commit()
            raise InvalidCredentialsException()

        # 5. Success Logic
        user.failed_login_attempts = 0
        user.locked_until = None
        self.db.add(user)

        # Create session and tokens atomically
        token_response = await self._issue_new_session(
            user=user,
            device_name=parse_device_name(user_agent),
            ip_address=ip_address,
            user_agent=user_agent,
            country=country,
        )

        # Write audit log
        await self.user_repo.create_audit_log(
            email=user.email,
            ip_address=ip_address,
            event_type="login",
        )
        await self.db.commit()

        return token_response

    async def refresh(
        self,
        refresh_token: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> TokenResponse:
        try:
            payload = TokenManager.decode_refresh_token(refresh_token)
        except Exception:
            raise RefreshTokenRevokedException()

        if payload.get("type") != "refresh":
            raise RefreshTokenRevokedException()

        token_hash = self._hash_token(refresh_token)
        db_token = await self.user_repo.get_refresh_token_by_hash(token_hash)
        if not db_token:
            raise RefreshTokenRevokedException()

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if db_token.expires_at < now or db_token.revoked_at is not None:
            raise RefreshTokenRevokedException()

        user_id = payload.get("sub")
        user = await self.user_repo.get_by_id(uuid.UUID(user_id))
        if not user or not user.is_active or user.deleted_at is not None:
            raise RefreshTokenRevokedException()

        # Generate new tokens
        new_access_token, _ = TokenManager.create_access_token(
            subject=user_id,
            org_id=str(user.org_id) if user.org_id else None,
            role=user.role.value,
        )
        new_refresh_token, new_jti = TokenManager.create_refresh_token(
            subject=user_id,
            org_id=str(user.org_id) if user.org_id else None,
            role=user.role.value,
        )

        new_payload = TokenManager.decode_refresh_token(new_refresh_token)
        new_expires_at = datetime.fromtimestamp(new_payload["exp"], tz=timezone.utc).replace(tzinfo=None)
        new_token_hash = self._hash_token(new_refresh_token)

        # Revoke old refresh token & set replaced_by
        await self.user_repo.revoke_refresh_token(db_token, replaced_by_hash=new_token_hash)

        # Save new refresh token
        device_name = parse_device_name(user_agent)
        await self.user_repo.create_refresh_token(
            user_id=db_token.user_id,
            jti=new_jti,
            token_hash=new_token_hash,
            expires_at=new_expires_at,
            device_name=device_name,
            ip_address=ip_address,
        )

        # Audit refresh log
        await self.user_repo.create_audit_log(
            email=user.email,
            ip_address=ip_address,
            event_type="refresh",
        )
        await self.db.commit()

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
        )

    async def logout(
        self,
        refresh_token: str,
        ip_address: str | None = None,
    ) -> None:
        try:
            payload = TokenManager.decode_refresh_token(refresh_token)
        except Exception:
            return  # Fail silently or ignore invalid token on logout

        token_hash = self._hash_token(refresh_token)
        db_token = await self.user_repo.get_refresh_token_by_hash(token_hash)
        if db_token:
            await self.user_repo.revoke_refresh_token(db_token)
            
            user_id = payload.get("sub")
            user = await self.user_repo.get_by_id(uuid.UUID(user_id))
            if user:
                await self.user_repo.create_audit_log(
                    email=user.email,
                    ip_address=ip_address,
                    event_type="logout",
                )
            await self.db.commit()

    async def _issue_new_session(
        self,
        user: User,
        device_name: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        country: str | None = None,
    ) -> TokenResponse:
        session_id = uuid.uuid4()

        access_token, _ = TokenManager.create_access_token(
            subject=str(user.id), session_id=str(session_id)
        )
        refresh_token, refresh_jti = TokenManager.create_refresh_token(
            subject=str(user.id), session_id=str(session_id)
        )

        session = UserSession(
            id=session_id,
            user_id=user.id,
            jti=refresh_jti,
            token_hash=self._hash_token(refresh_token),
            device_name=device_name,
            user_agent=user_agent,
            ip_address=ip_address,
            last_ip=ip_address,
            country=country,
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        self.db.add(session)

        return TokenResponse(access_token=access_token, refresh_token=refresh_token)

    def _rotate_session_tokens(self, user: User, session: UserSession) -> TokenResponse:
        access_token, _ = TokenManager.create_access_token(
            subject=str(user.id), session_id=str(session.id)
        )
        refresh_token, refresh_jti = TokenManager.create_refresh_token(
            subject=str(user.id), session_id=str(session.id)
        )

        session.jti = refresh_jti
        session.token_hash = self._hash_token(refresh_token)
        session.expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

        return TokenResponse(access_token=access_token, refresh_token=refresh_token)
