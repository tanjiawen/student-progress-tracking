"""Pytest fixtures for student-progress-tracking."""

from __future__ import annotations

# Fix passlib compatibility with bcrypt >= 4.1 (must run before passlib is imported)
import bcrypt

if not hasattr(bcrypt, "__about__"):
    bcrypt.__about__ = type("obj", (object,), {"__version__": bcrypt.__version__})()

# bcrypt 4.2+ rejects passwords > 72 bytes; passlib's detect_wrap_bug triggers this.
# Wrap hashpw to silently truncate, matching the old bcrypt behavior.
_bcrypt_hashpw_orig = bcrypt.hashpw

def _bcrypt_hashpw_fixed(password: bytes, salt: bytes) -> bytes:
    if len(password) > 72:
        password = password[:72]
    return _bcrypt_hashpw_orig(password, salt)

bcrypt.hashpw = _bcrypt_hashpw_fixed

import os
import sys
import tempfile
from collections.abc import AsyncGenerator
from unittest.mock import patch, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.dependencies import get_session
from app.core.security import get_password_hash
from app.main import app
from app.models.user import User, UserRole

# Inject all model classes into every model module's globals so that
# SQLAlchemy can resolve string forward references in relationships.
import app.models as _models_module


# Create a temporary SQLite database for tests
@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    # Use an in-memory SQLite database for tests
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with database session override."""
    def override_get_session():
        return db_session
    
    app.dependency_overrides[get_session] = override_get_session
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user in the database."""
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=get_password_hash("testpass123"),
        real_name="Test User",
        role=UserRole.teacher,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_client(client: AsyncClient, test_user: User) -> AsyncClient:
    """Create an authenticated test client."""
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "testuser", "password": "testpass123"},
    )
    assert response.status_code == 200
    data = response.json()
    token = data["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest.fixture
def mock_deepseek_response() -> dict:
    """Sample DeepSeek API response for grading."""
    return {
        "is_correct": True,
        "score": 8.0,
        "error_type": "correct",
        "error_detail": "回答正确",
        "knowledge_points": ["二次函数"],
        "suggestion": "继续保持",
        "confidence": 0.95,
    }


# Mock Redis to avoid connection errors in tests
@pytest.fixture()
def mock_redis():
    """Mock Redis client globally for all tests."""
    fake_redis = MagicMock()
    fake_redis.get = MagicMock(return_value=None)
    fake_redis.setex = MagicMock(return_value=True)
    fake_redis.set = MagicMock(return_value=True)
    fake_redis.delete = MagicMock(return_value=True)
    fake_redis.exists = MagicMock(return_value=0)
    
    with patch("app.core.redis_client.redis_client", fake_redis):
        yield


# Auto-mock Redis to avoid connection errors in API tests
@pytest.fixture(autouse=True)
def mock_redis_for_tests(monkeypatch):
    class FakeRedis:
        async def get(self, key): return None
        async def setex(self, key, seconds, value): return True
        async def set(self, key, value): return True
        async def delete(self, *keys): return 1
        async def exists(self, *keys): return 0
    import app.core.redis_client
    monkeypatch.setattr(app.core.redis_client, 'redis_client', FakeRedis())
    import app.core.dependencies
    monkeypatch.setattr(app.core.dependencies, 'redis_client', FakeRedis())
