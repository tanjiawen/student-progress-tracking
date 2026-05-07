from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.config import settings
from app.core.exceptions import UnauthorizedException
from app.core.security import create_access_token, create_refresh_token, verify_password

router = APIRouter()


@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    # TODO: verify user from database
    # This is a placeholder implementation
    if form_data.username != "admin" or form_data.password != "admin":
        raise UnauthorizedException("Incorrect username or password")

    user_id = 1
    access_token = create_access_token(
        subject=user_id,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = create_refresh_token(subject=user_id)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "refresh_token": refresh_token,
        "user": {
            "id": user_id,
            "username": form_data.username,
            "real_name": "Admin",
            "role": "admin",
        },
    }


@router.post("/refresh")
async def refresh_token(refresh_token: str) -> Any:
    """
    Refresh access token.
    """
    # TODO: verify refresh token from database / redis
    from app.core.security import decode_token

    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise UnauthorizedException("Invalid refresh token")

    user_id = int(payload["sub"])
    new_access_token = create_access_token(subject=user_id)
    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.get("/me")
async def get_me() -> Any:
    """
    Get current user info.
    """
    # TODO: get from current_user dependency
    return {
        "id": 1,
        "username": "admin",
        "real_name": "Admin",
        "role": "admin",
        "email": "admin@school.com",
    }
