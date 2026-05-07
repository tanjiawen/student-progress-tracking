import hashlib
from datetime import UTC, datetime

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.redis_client import redis_client
from app.core.security import decode_token
from app.models.user import UserRole
from app.repositories.user import UserRepository
from app.schemas.user import UserRead

security = HTTPBearer(auto_error=False)


async def _is_token_blacklisted(token: str) -> bool:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    result = await redis_client.get(f"blacklist:{token_hash}")
    return result is not None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> UserRead | None:
    if not credentials:
        return None

    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise UnauthorizedException("Invalid or expired token")

    if await _is_token_blacklisted(credentials.credentials):
        raise UnauthorizedException("Token has been revoked")

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedException("Invalid token payload")

    repo = UserRepository(session)
    user = await repo.get_by_id(int(user_id))
    if not user:
        raise UnauthorizedException("User not found")
    if not user.is_active:
        raise UnauthorizedException("User is inactive")

    return UserRead(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.real_name,
        phone=user.phone,
        avatar_url=user.avatar_url,
        is_active=user.is_active,
        is_superuser=False,
        role=user.role.value,
        tier=getattr(user, "tier", "default"),
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


async def get_current_active_user(
    current_user: UserRead = Depends(get_current_user),
) -> UserRead:
    return current_user


async def get_raw_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str | None:
    if not credentials:
        return None
    return credentials.credentials


def require_role(*roles: UserRole):
    allowed_roles = {role.value for role in roles}

    async def role_checker(
        current_user: UserRead = Depends(get_current_user),
    ) -> UserRead:
        if current_user.role not in allowed_roles:
            raise ForbiddenException(
                f"Required role: {', '.join(sorted(allowed_roles))}"
            )
        return current_user

    return role_checker


get_current_admin = require_role(UserRole.admin)
get_current_teacher_or_admin = require_role(UserRole.teacher, UserRole.admin)
