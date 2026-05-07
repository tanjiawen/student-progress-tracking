"""Student repository."""

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.student import Student
from app.repositories.base import BaseRepository


class StudentRepository(BaseRepository[Student]):
    """Repository for Student entity."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Student)

    async def get_by_user_id(self, user_id: int) -> Student | None:
        statement = select(Student).where(Student.user_id == user_id)
        result = await self.session.exec(statement)
        return result.first()

    async def get_by_student_number(self, student_number: str) -> Student | None:
        statement = select(Student).where(Student.student_number == student_number)
        result = await self.session.exec(statement)
        return result.first()

    async def get_by_class(self, class_id: int) -> list[Student]:
        statement = select(Student).where(Student.class_id == class_id)
        result = await self.session.exec(statement)
        return list(result.all())

    async def get_classmates(self, student_id: int) -> list[Student]:
        student = await self.get_by_id(student_id)
        if not student or student.class_id is None:
            return []
        statement = select(Student).where(
            Student.class_id == student.class_id,
            Student.id != student_id,
        )
        result = await self.session.exec(statement)
        return list(result.all())
