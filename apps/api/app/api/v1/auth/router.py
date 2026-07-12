from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
    LogoutRequest,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/signup", response_model=TokenResponse, status_code=201)
async def signup(data: SignupRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user_agent = request.headers.get("user-agent")
    ip = request.client.host if request.client else None
    return await AuthService(db).signup(data, user_agent=user_agent, ip_address=ip)

@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user_agent = request.headers.get("user-agent")
    ip = request.client.host if request.client else None
    return await AuthService(db).login(data, user_agent=user_agent, ip_address=ip)

@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user_agent = request.headers.get("user-agent")
    ip = request.client.host if request.client else None
    return await AuthService(db).refresh(data.refresh_token, user_agent=user_agent, ip_address=ip)

@router.post("/logout", status_code=204)
async def logout(data: LogoutRequest, request: Request, db: AsyncSession = Depends(get_db)):
    ip = request.client.host if request.client else None
    await AuthService(db).logout(data.refresh_token, ip_address=ip)

@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
