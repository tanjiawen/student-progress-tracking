"""Student API tests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.student import Student
from app.models.user import User


@pytest.fixture
async def test_student(db_session: AsyncSession, test_user: User) -> Student:
    """Create a test student linked to the test user."""
    student = Student(
        user_id=test_user.id,
        student_number="S2026001",
        class_id=None,
        enrollment_year=2026,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(student)
    await db_session.commit()
    await db_session.refresh(student)
    return student


@pytest.mark.asyncio
async def test_list_students(auth_client: AsyncClient, test_student: Student) -> None:
    """Listing students should return items."""
    response = await auth_client.get("/api/v1/students")
    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_get_student_profile(auth_client: AsyncClient, test_student: Student) -> None:
    """Getting student profile should work."""
    response = await auth_client.get(f"/api/v1/students/{test_student.id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == test_student.id
    assert data["student_number"] == test_student.student_number


@pytest.mark.asyncio
async def test_get_student_knowledge_state(auth_client: AsyncClient, test_student: Student) -> None:
    """Getting student knowledge states should work."""
    response = await auth_client.get(
        f"/api/v1/students/{test_student.id}/knowledge-state",
        params={"page": 1, "page_size": 10},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_get_student_error_book(auth_client: AsyncClient, test_student: Student) -> None:
    """Getting student error book should work."""
    response = await auth_client.get(f"/api/v1/students/{test_student.id}/error-book")
    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data, list)
