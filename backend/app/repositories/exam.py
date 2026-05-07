"""Exam repository."""

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.exam import Exam
from app.repositories.base import BaseRepository


class ExamRepository(BaseRepository[Exam]):
    """Repository for Exam entity."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Exam)

    async def get_by_class(self, class_id: int) -> list[Exam]:
        statement = select(Exam).where(Exam.class_id == class_id)
        result = await self.session.exec(statement)
        return list(result.all())

    async def get_by_subject(self, subject_id: int) -> list[Exam]:
        statement = select(Exam).where(Exam.subject_id == subject_id)
        result = await self.session.exec(statement)
        return list(result.all())

    async def get_by_status(self, status: str) -> list[Exam]:
        statement = select(Exam).where(Exam.status == status)
        result = await self.session.exec(statement)
        return list(result.all())

    async def update_status(self, exam_id: int, status: str) -> Exam | None:
        return await self.update(exam_id, {"status": status})
