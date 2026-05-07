"""作答提交服务 — 负责提交创建、判卷触发及结果查询."""

from __future__ import annotations

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.submission import GradingStatus, Submission
from app.repositories.grading_result import GradingResultRepository
from app.repositories.submission import SubmissionRepository
from app.tasks.grading import grade_submission as grade_submission_task


class SubmissionService:
    """作答提交业务服务，编排提交与判卷流程."""

    def __init__(self, session: AsyncSession) -> None:
        self.submission_repo = SubmissionRepository(session)
        self.grading_result_repo = GradingResultRepository(session)
        self.session = session

    async def submit_answer(self, data: dict) -> dict:
        """创建 submission 并触发判卷任务.

        Args:
            data: 提交数据，需包含 exam_id, student_id, exam_question_id 等

        Returns:
            dict: 提交结果及判卷任务 ID
        """
        exam_id = data.get("exam_id")
        student_id = data.get("student_id")
        exam_question_id = data.get("exam_question_id")

        if not all([exam_id, student_id, exam_question_id]):
            raise BadRequestException(
                "exam_id, student_id, exam_question_id 为必填字段"
            )

        submission = Submission(
            exam_id=int(exam_id),
            student_id=int(student_id),
            exam_question_id=int(exam_question_id),
            answer_text=data.get("answer_text"),
            answer_latex=data.get("answer_latex"),
            answer_image_urls=data.get("answer_image_urls"),
            grading_status=GradingStatus.PENDING,
        )
        created = await self.submission_repo.create(submission)

        # 触发异步判卷任务
        task = grade_submission_task.delay(created.id)

        return {
            "submission_id": created.id,
            "exam_id": created.exam_id,
            "student_id": created.student_id,
            "grading_status": created.grading_status.value,
            "task_id": task.id,
            "message": "判卷任务已提交",
        }

    async def get_submission_with_grading(self, submission_id: int) -> dict:
        """获取 submission 及其判卷结果.

        Args:
            submission_id: 提交 ID

        Returns:
            dict: 提交详情与判卷结果
        """
        submission = await self.submission_repo.get_by_id(submission_id)
        if not submission:
            raise NotFoundException(f"提交记录 {submission_id} 不存在")

        grading = await self.grading_result_repo.get_by_submission(submission_id)

        return {
            "submission": {
                "id": submission.id,
                "exam_id": submission.exam_id,
                "student_id": submission.student_id,
                "exam_question_id": submission.exam_question_id,
                "answer_text": submission.answer_text,
                "answer_latex": submission.answer_latex,
                "answer_image_urls": submission.answer_image_urls,
                "grading_status": submission.grading_status.value,
                "submitted_at": submission.submitted_at,
            },
            "grading": (
                {
                    "id": grading.id,
                    "is_correct": grading.is_correct,
                    "score": float(grading.score),
                    "max_score": float(grading.max_score),
                    "error_type": grading.error_type.value,
                    "error_type_detail": grading.error_type_detail,
                    "knowledge_point_ids": grading.knowledge_point_ids,
                    "suggestion": grading.suggestion,
                    "confidence": grading.confidence,
                    "ai_model": grading.ai_model,
                }
                if grading
                else None
            ),
        }
