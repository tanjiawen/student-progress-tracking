"""Report repository."""

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.report import Report
from app.repositories.base import BaseRepository


class ReportRepository(BaseRepository[Report]):
    """Repository for Report entity."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Report)

    async def get_by_student(self, student_id: int) -> list[Report]:
        statement = select(Report).where(Report.student_id == student_id)
        result = await self.session.exec(statement)
        return list(result.all())

    async def get_latest_by_student(self, student_id: int) -> Report | None:
        statement = (
            select(Report)
            .where(Report.student_id == student_id)
            .order_by(Report.created_at.desc())
            .limit(1)
        )
        result = await self.session.exec(statement)
        return result.first()
