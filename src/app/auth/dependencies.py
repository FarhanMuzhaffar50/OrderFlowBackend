import uuid
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.security import decode_access_token
from app.db.models import Role, User
from app.db.session import get_session

bearer = HTTPBearer(auto_error=False)


async def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    if credentials is None:
        raise AppError("authentication_required", "Authentication required", 401)
    try:
        user_id = uuid.UUID(decode_access_token(credentials.credentials))
    except (jwt.InvalidTokenError, ValueError):
        raise AppError("invalid_token", "Invalid or expired access token", 401) from None
    user = await session.get(User, user_id)
    if user is None:
        raise AppError("invalid_token", "User no longer exists", 401)
    return user


async def admin_user(user: Annotated[User, Depends(current_user)]) -> User:
    if user.role != Role.ADMIN:
        raise AppError("forbidden", "Administrator role required", 403)
    return user


CurrentUser = Annotated[User, Depends(current_user)]
AdminUser = Annotated[User, Depends(admin_user)]
