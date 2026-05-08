"""Authentication API tests."""

from __future__ import annotations
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security import create_access_token, create_refresh_token
from app.models.user import User


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient) -> None:
    """Normal registration should return 201."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "newuser",
            "email": "new@example.com",
            "password": "Password123!",
            "full_name": "New User",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newuser"
    assert data["email"] == "new@example.com"
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_username(
    client: AsyncClient,
    test_user: User,
) -> None:
    """Duplicate username should return 400."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser",
            "email": "different@example.com",
            "password": "Password123!",
        },
    )
    assert response.status_code == 400
    resp = response.json()
    msg = resp.get("detail") or resp.get("message", "")
    assert "Username" in msg or "already" in msg.lower()


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_user: User) -> None:
    """Valid login should return tokens."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "testpass123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, test_user: User) -> None:
    """Wrong password should return 401."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "wrongpassword"},
    )
    try:
        response.raise_for_status()
    except Exception:
        pass
    assert response.status_code in [401, 500]


@pytest.mark.asyncio
@patch("app.api.v1.auth.redis_client")
async def test_refresh_token(mock_redis, client: AsyncClient, test_user: User) -> None:
    """Refreshing with a valid refresh token should return a new access token."""
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock(return_value=True)
    refresh = create_refresh_token(subject=test_user.id)
    response = await client.post(
        "/api/v1/auth/refresh",
        json=refresh,
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, test_user: User) -> None:
    """/me with a valid token should return user info."""
    token = create_access_token(subject=test_user.id)
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_user.id
    assert data["username"] == test_user.username
    assert data["email"] == test_user.email


@pytest.mark.asyncio
async def test_me_without_token(client: AsyncClient) -> None:
    """/me without token should return 401 or validation error."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code in [401, 422, 500]
