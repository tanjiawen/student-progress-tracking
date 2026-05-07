import hashlib
import re
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, status
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.dependencies import get_current_user, get_raw_token
from app.core.exceptions import BadRequestException, UnauthorizedException
from app.core.redis_client import redis_client
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
)
from app.models.user import User, UserRole
from app.repositories.user import UserRepository
from app.schemas.user import Token, UserCreate, UserRead

router = APIRouter()


def validate_password(password: str) -> None:
    """密码策略：最小 8 位，包含大小写+数字."""
    if len(password) < 8:
        raise BadRequestException("密码至少需要 8 位字符")
    if not re.search(r"[A-Z]", password):
        raise BadRequestException("密码需要包含至少一个大写字母")
    if not re.search(r"[a-z]", password):
        raise BadRequestException("密码需要包含至少一个小写字母")
    if not re.search(r"\d", password):
        raise BadRequestException("密码需要包含至少一个数字")


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(
    data: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> Any:
    repo = UserRepository(session)
    user = await repo.authenticate(data.username, data.password)
    if not user:
        raise UnauthorizedException("Incorrect username or password")
    if not user.is_active:
        raise UnauthorizedException("User is inactive")

    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": UserRead(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.real_name,
            phone=user.phone,
            avatar_url=user.avatar_url,
            is_active=user.is_active,
            is_superuser=getattr(user, "is_superuser", False),
            role=user.role.value,
            tier=getattr(user, "tier", "default"),
            created_at=user.created_at,
            updated_at=user.updated_at,
        ),
    }


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserCreate,
    session: AsyncSession = Depends(get_session),
) -> Any:
    validate_password(user_in.password)

    repo = UserRepository(session)

    if await repo.get_by_username(user_in.username):
        raise BadRequestException("Username already registered")
    if await repo.get_by_email(user_in.email):
        raise BadRequestException("Email already registered")

    db_user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        real_name=user_in.full_name,
        phone=user_in.phone,
        avatar_url=user_in.avatar_url,
        role=UserRole(user_in.role),
        is_active=user_in.is_active,
    )
    await repo.create(db_user)

    return UserRead(
        id=db_user.id,
        username=db_user.username,
        email=db_user.email,
        full_name=db_user.real_name,
        phone=db_user.phone,
        avatar_url=db_user.avatar_url,
        is_active=db_user.is_active,
        is_superuser=False,
        role=db_user.role.value,
        tier=getattr(db_user, "tier", "default"),
        created_at=db_user.created_at,
        updated_at=db_user.updated_at,
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token_str: str = Body(...),
    session: AsyncSession = Depends(get_session),
) -> Any:
    payload = decode_token(refresh_token_str)
    if not payload or payload.get("type") != "refresh":
        raise UnauthorizedException("Invalid refresh token")

    token_hash = hashlib.sha256(refresh_token_str.encode()).hexdigest()
    if await redis_client.get(f"blacklist:{token_hash}"):
        raise UnauthorizedException("Token has been revoked")

    user_id = int(payload["sub"])
    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if not user or not user.is_active:
        raise UnauthorizedException("User not found or inactive")

    access_token = create_access_token(subject=user.id)
    new_refresh_token = create_refresh_token(subject=user.id)

    # Blacklist the old refresh token
    exp = payload.get("exp")
    if exp:
        ttl = int(exp - datetime.now(UTC).timestamp())
        if ttl > 0:
            await redis_client.setex(f"blacklist:{token_hash}", ttl, "1")

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.get("/me", response_model=UserRead)
async def get_me(current_user: UserRead = Depends(get_current_user)) -> Any:
    return current_user


@router.post("/logout")
async def logout(
    access_token: str | None = Depends(get_raw_token),
    refresh_token: str | None = Body(None),
) -> dict[str, str]:
    now = datetime.now(UTC).timestamp()

    if access_token:
        payload = decode_token(access_token)
        if payload:
            exp = payload.get("exp")
            if exp:
                ttl = int(exp - now)
                if ttl > 0:
                    token_hash = hashlib.sha256(access_token.encode()).hexdigest()
                    await redis_client.setex(f"blacklist:{token_hash}", ttl, "1")

    if refresh_token:
        payload = decode_token(refresh_token)
        if payload:
            exp = payload.get("exp")
            if exp:
                ttl = int(exp - now)
                if ttl > 0:
                    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
                    await redis_client.setex(f"blacklist:{token_hash}", ttl, "1")

    return {"message": "Successfully logged out"}
