"""考试服务 — 负责考试的创建、文件上传、OCR 触发及查询."""

from __future__ import annotations

import datetime
from uuid import uuid4

from fastapi import UploadFile
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.exam import Exam, ExamStatus, ExamType
from app.repositories.exam import ExamRepository
from app.repositories.exam_question import ExamQuestionRepository
from app.schemas.exam import ExamCreate, ExamRead
from app.services.storage_service import storage_service
from app.tasks.ocr import process_exam_ocr


class ExamService:
    """考试业务服务，编排考试相关的 Repository 与外部服务."""

    def __init__(self, session: AsyncSession) -> None:
        self.exam_repo = ExamRepository(session)
        self.exam_question_repo = ExamQuestionRepository(session)
        self.session = session

    async def create_exam(self, data: ExamCreate, creator_id: int) -> ExamRead:
        """创建考试记录.

        Args:
            data: 考试创建数据（schema 中未显式定义的 class_id / subject_id 可通过 model_dump 扩展传入）
            creator_id: 创建人用户 ID

        Returns:
            ExamRead: 创建后的考试数据
        """
        payload = data.model_dump()

        class_id = payload.get("class_id")
        subject_id = payload.get("subject_id")
        if class_id is None:
            raise BadRequestException("class_id 为必填字段")
        if subject_id is None:
            raise BadRequestException("subject_id 为必填字段")

        exam_type_str = payload.get("exam_type", "quiz")
        try:
            exam_type = ExamType(exam_type_str)
        except ValueError as exc:
            raise BadRequestException(f"无效的考试类型: {exam_type_str}") from exc

        status_str = payload.get("status", "draft")
        try:
            status = ExamStatus(status_str)
        except ValueError:
            status = ExamStatus.DRAFT

        exam = Exam(
            title=payload.get("title", "未命名考试"),
            subject_id=int(subject_id),
            class_id=int(class_id),
            exam_type=exam_type,
            total_score=payload.get("total_score", 100.0),
            status=status,
            exam_date=payload.get("exam_date")
            or datetime.datetime.now(datetime.timezone.utc),
            created_by=creator_id,
        )

        created = await self.exam_repo.create(exam)

        return ExamRead(
            id=created.id,
            title=created.title,
            description=payload.get("description"),
            subject=str(created.subject_id),
            grade_level=payload.get("grade_level"),
            total_score=float(created.total_score),
            duration_minutes=payload.get("duration_minutes"),
            exam_date=created.exam_date,
            status=created.status.value,
            created_by=created.created_by,
            created_at=created.created_at,
            updated_at=created.updated_at,
        )

    async def upload_exam_files(self, exam_id: int, files: list[UploadFile]) -> dict:
        """上传 PDF/图片到 MinIO，路径: exams/{exam_id}/images/{filename}.

        Args:
            exam_id: 考试 ID
            files: 上传文件列表

        Returns:
            dict: 上传结果，包含 object_names 列表
        """
        exam = await self.exam_repo.get_by_id(exam_id)
        if not exam:
            raise NotFoundException(f"考试 {exam_id} 不存在")

        object_names = []
        for file in files:
            contents = await file.read()
            if not contents:
                raise BadRequestException(f"文件 {file.filename} 为空")

            ext = (
                file.filename.split(".")[-1].lower()
                if "." in file.filename
                else "bin"
            )
            object_name = f"exams/{exam_id}/images/{uuid4().hex}.{ext}"
            content_type = file.content_type or "application/octet-stream"

            storage_service.upload_file(
                file_data=contents,
                filename=file.filename,
                content_type=content_type,
                folder=f"exams/{exam_id}/images",
            )
            object_names.append(object_name)

        return {
            "exam_id": exam_id,
            "uploaded_count": len(object_names),
            "object_names": object_names,
        }

    async def start_ocr(self, exam_id: int) -> dict:
        """更新 exam.status = processing 并触发 Celery OCR 任务.

        Args:
            exam_id: 考试 ID

        Returns:
            dict: 任务触发结果
        """
        exam = await self.exam_repo.get_by_id(exam_id)
        if not exam:
            raise NotFoundException(f"考试 {exam_id} 不存在")

        if exam.status not in (ExamStatus.DRAFT, ExamStatus.READY):
            raise BadRequestException(
                f"当前状态 {exam.status.value} 不支持启动 OCR"
            )

        await self.exam_repo.update_status(exam_id, ExamStatus.PROCESSING.value)
        task = process_exam_ocr.delay(exam_id)

        return {
            "exam_id": exam_id,
            "task_id": task.id,
            "status": "processing",
            "message": "OCR 任务已提交",
        }

    async def get_exam_with_questions(self, exam_id: int) -> dict:
        """获取考试 + 所有题目.

        Args:
            exam_id: 考试 ID

        Returns:
            dict: 考试信息及题目列表
        """
        exam = await self.exam_repo.get_by_id(exam_id)
        if not exam:
            raise NotFoundException(f"考试 {exam_id} 不存在")

        questions = await self.exam_question_repo.get_by_exam_ordered(exam_id)

        return {
            "exam": ExamRead(
                id=exam.id,
                title=exam.title,
                subject=str(exam.subject_id),
                grade_level=None,
                total_score=float(exam.total_score),
                duration_minutes=None,
                exam_date=exam.exam_date,
                status=exam.status.value,
                created_by=exam.created_by,
                created_at=exam.created_at,
                updated_at=exam.updated_at,
            ),
            "questions": [
                {
                    "id": q.id,
                    "sequence_number": q.sequence_number,
                    "question_type": q.question_type.value,
                    "content": q.content,
                    "score": float(q.score),
                    "status": q.status.value,
                }
                for q in questions
            ],
        }

    async def list_exams_by_class(
        self, class_id: int, skip: int = 0, limit: int = 20
    ) -> list[ExamRead]:
        """按班级分页查询考试列表.

        Args:
            class_id: 班级 ID
            skip: 分页偏移
            limit: 每页数量

        Returns:
            list[ExamRead]: 考试列表
        """
        exams = await self.exam_repo.get_by_class(class_id)
        paginated = exams[skip : skip + limit]
        return [
            ExamRead(
                id=e.id,
                title=e.title,
                subject=str(e.subject_id),
                grade_level=None,
                total_score=float(e.total_score),
                duration_minutes=None,
                exam_date=e.exam_date,
                status=e.status.value,
                created_by=e.created_by,
                created_at=e.created_at,
                updated_at=e.updated_at,
            )
            for e in paginated
        ]
