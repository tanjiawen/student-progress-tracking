"""Grading result repository."""

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.grading_result import ErrorType, GradingResult
from app.models.submission import Submission
from app.repositories.base import BaseRepository


class GradingResultRepository(BaseRepository[GradingResult]):
    """Repository for GradingResult entity."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, GradingResult)

    async def get_by_submission(self, submission_id: int) -> GradingResult | None:
        statement = select(GradingResult).where(
            GradingResult.submission_id == submission_id
        )
        result = await self.session.exec(statement)
        return result.first()

    async def get_by_exam(self, exam_id: int) -> list[GradingResult]:
        statement = (
            select(GradingResult)
            .join(Submission, GradingResult.submission_id == Submission.id)
            .where(Submission.exam_id == exam_id)
        )
        result = await self.session.exec(statement)
        return list(result.all())

    async def get_by_student(self, student_id: int) -> list[GradingResult]:
        statement = (
            select(GradingResult)
            .join(Submission, GradingResult.submission_id == Submission.id)
            .where(Submission.student_id == student_id)
        )
        result = await self.session.exec(statement)
        return list(result.all())

    async def get_error_stats(self, exam_id: int) -> list[GradingResult]:
        statement = (
            select(GradingResult)
            .join(Submission, GradingResult.submission_id == Submission.id)
            .where(
                Submission.exam_id == exam_id,
                GradingResult.error_type != ErrorType.CORRECT,
            )
        )
        result = await self.session.exec(statement)
        return list(result.all())
