"""Submission repository."""

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.submission import Submission
from app.repositories.base import BaseRepository


class SubmissionRepository(BaseRepository[Submission]):
    """Repository for Submission entity."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Submission)

    async def get_by_exam_and_student(
        self, exam_id: int, student_id: int
    ) -> Submission | None:
        statement = select(Submission).where(
            Submission.exam_id == exam_id,
            Submission.student_id == student_id,
        )
        result = await self.session.exec(statement)
        return result.first()

    async def get_by_student(self, student_id: int) -> list[Submission]:
        statement = select(Submission).where(Submission.student_id == student_id)
        result = await self.session.exec(statement)
        return list(result.all())

    async def get_pending_grading(self) -> list[Submission]:
        statement = select(Submission).where(Submission.grading_status == "pending")
        result = await self.session.exec(statement)
        return list(result.all())
