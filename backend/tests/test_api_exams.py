"""Exam API tests."""

from __future__ import annotations
from unittest.mock import patch

import io
from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch, MagicMock

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.class_ import Class
from app.models.exam import Exam, ExamStatus, ExamType
from app.models.subject import Subject
from app.repositories.exam import ExamRepository


@pytest.fixture
async def test_subject(db_session: AsyncSession) -> Subject:
    """Create a test subject in the database."""
    subject = Subject(name="数学", code="math", description="数学学科")
    db_session.add(subject)
    await db_session.commit()
    await db_session.refresh(subject)
    return subject


@pytest.fixture
async def test_class(db_session: AsyncSession, test_user: Any) -> Class:
    """Create a test class in the database."""
    class_ = Class(
        name="初三(1)班",
        grade="初三",
        academic_year=2026,
        semester="春季",
        teacher_id=test_user.id,
    )
    db_session.add(class_)
    await db_session.commit()
    await db_session.refresh(class_)
    return class_


@pytest.fixture
async def test_exam(
    db_session: AsyncSession,
    test_subject: Subject,
    test_class: Class,
    test_user: Any,
) -> Exam:
    """Create a test exam in the database."""
    exam = Exam(
        title="单元测试",
        subject_id=test_subject.id,
        class_id=test_class.id,
        exam_type=ExamType.QUIZ,
        total_score=100.0,
        status=ExamStatus.DRAFT,
        exam_date=datetime.now(timezone.utc),
        created_by=test_user.id,
    )
    repo = ExamRepository(db_session)
    created = await repo.create(exam)
    return created


@pytest.mark.asyncio
async def test_list_exams(auth_client: AsyncClient, test_exam: Exam) -> None:
    """Listing exams should return items."""
    response = await auth_client.get("/api/v1/exams")
    assert response.status_code == 200
    data = response.json()["data"]
    assert "items" in data
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_get_exam_detail(auth_client: AsyncClient, test_exam: Exam) -> None:
    """Getting exam detail should work."""
    response = await auth_client.get(f"/api/v1/exams/{test_exam.id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["exam"]["id"] == test_exam.id
    assert data["exam"]["title"] == test_exam.title


@pytest.mark.asyncio
async def test_upload_exam_file(
    auth_client: AsyncClient,
    test_subject: Subject,
    test_class: Class,
) -> None:
    """Uploading a PDF exam file should work."""
    pdf_bytes = b"%PDF-1.4 fake pdf content"
    files = {"file": ("test_exam.pdf", io.BytesIO(pdf_bytes), "application/pdf")}

    with patch("app.api.v1.exams.pdf_service.pdf_to_images") as mock_pdf:
        with patch("app.api.v1.exams.storage_service.upload_image") as mock_upload:
            mock_pdf.return_value = [(1, b"fake_image", "png")]
            mock_upload.return_value = "exams/1/images/page_001.png"

            response = await auth_client.post(
                "/api/v1/exams/upload",
                data={
                    "title": "上传测试",
                    "subject": test_subject.name,
                    "class_id": str(test_class.id),
                },
                files=files,
            )

    assert response.status_code == 201
    data = response.json()["data"]
    assert "id" in data


@pytest.mark.asyncio
async def test_upload_exam_image(
    auth_client: AsyncClient,
    test_subject: Subject,
    test_class: Class,
) -> None:
    """Uploading an image exam file should work."""
    # Generate a valid 1x1 PNG for testing
    from PIL import Image
    import io as io_module
    img = Image.new("RGB", (1, 1), color="red")
    png_buf = io_module.BytesIO()
    img.save(png_buf, format="PNG")
    img_bytes = png_buf.getvalue()
    files = {"file": ("test_exam.png", io.BytesIO(img_bytes), "image/png")}

    with patch("app.api.v1.exams.storage_service.upload_image") as mock_upload:
        mock_upload.return_value = "exams/1/images/page_001.png"

        response = await auth_client.post(
            "/api/v1/exams/upload",
            data={
                "title": "图片上传测试",
                "subject": test_subject.name,
                "class_id": str(test_class.id),
            },
            files=files,
        )

    assert response.status_code == 201
    data = response.json()["data"]
    assert "id" in data


@pytest.mark.asyncio
async def test_start_ocr(auth_client: AsyncClient, test_exam: Exam) -> None:
    """Starting OCR should enqueue a task."""
    with patch("app.tasks.ocr.process_exam_ocr.delay") as mock_task:
        mock_task.return_value.id = "fake-task-id"
        response = await auth_client.post(f"/api/v1/exams/{test_exam.id}/start-ocr")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["task_id"] == "fake-task-id"
    mock_task.assert_called_once_with(test_exam.id)
