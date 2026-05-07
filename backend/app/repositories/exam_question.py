"""Exam question repository."""

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.exam_question import ExamQuestion
from app.repositories.base import BaseRepository


class ExamQuestionRepository(BaseRepository[ExamQuestion]):
    """Repository for ExamQuestion entity."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ExamQuestion)

    async def get_by_exam(self, exam_id: int) -> list[ExamQuestion]:
        statement = select(ExamQuestion).where(ExamQuestion.exam_id == exam_id)
        result = await self.session.exec(statement)
        return list(result.all())

    async def get_by_exam_ordered(self, exam_id: int) -> list[ExamQuestion]:
        statement = (
            select(ExamQuestion)
            .where(ExamQuestion.exam_id == exam_id)
            .order_by(ExamQuestion.sequence_number)
        )
        result = await self.session.exec(statement)
        return list(result.all())
