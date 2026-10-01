from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import LoginRequest, RegisterRequest, TokenResponse
from app.common.rate_limit import enforce_rate_limit
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import Cart, User
from app.db.session import get_session

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    body: RegisterRequest, session: Annotated[AsyncSession, Depends(get_session)]
) -> TokenResponse:
    if await session.scalar(select(User).where(User.email == body.email.lower())):
        raise AppError("email_exists", "An account with this email already exists", 409)
    user = User(email=body.email.lower(), password_hash=hash_password(body.password))
    session.add(user)
    await session.flush()
    session.add(Cart(user_id=user.id))
    await session.commit()
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request, body: LoginRequest, session: Annotated[AsyncSession, Depends(get_session)]
) -> TokenResponse:
    await enforce_rate_limit(request, "login", get_settings().login_rate_limit)
    user = await session.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise AppError("invalid_credentials", "Invalid email or password", 401)
    return TokenResponse(access_token=create_access_token(str(user.id)))
