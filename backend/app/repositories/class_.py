"""Class repository."""

from datetime import datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.class_ import Class
from app.repositories.base import BaseRepository


class ClassRepository(BaseRepository[Class]):
    """Repository for Class entity."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Class)

    async def get_by_teacher(self, teacher_id: int) -> list[Class]:
        statement = select(Class).where(Class.teacher_id == teacher_id)
        result = await self.session.exec(statement)
        return list(result.all())

    async def get_by_grade(self, grade: str) -> list[Class]:
        statement = select(Class).where(Class.grade == grade)
        result = await self.session.exec(statement)
        return list(result.all())

    async def get_current_semester_classes(self) -> list[Class]:
        now = datetime.utcnow()
        semester = "spring" if now.month < 7 else "autumn"
        current_year = now.year
        statement = select(Class).where(
            Class.semester == semester,
            Class.academic_year.ilike(f"%{current_year}%"),
        )
        result = await self.session.exec(statement)
        return list(result.all())
