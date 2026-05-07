"""Exercise repository."""

from datetime import datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.exercise import Exercise, ExerciseStatus
from app.repositories.base import BaseRepository


class ExerciseRepository(BaseRepository[Exercise]):
    """Repository for Exercise entity."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Exercise)

    async def get_by_student(
        self,
        student_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Exercise]:
        statement = (
            select(Exercise)
            .where(Exercise.student_id == student_id)
            .offset(skip)
            .limit(limit)
            .order_by(Exercise.created_at.desc())
        )
        result = await self.session.exec(statement)
        return list(result.all())

    async def get_by_status(self, status: ExerciseStatus) -> list[Exercise]:
        statement = select(Exercise).where(Exercise.status == status)
        result = await self.session.exec(statement)
        return list(result.all())

    async def get_due_exercises(self, student_id: int) -> list[Exercise]:
        now = datetime.utcnow()
        statement = select(Exercise).where(
            Exercise.student_id == student_id,
            Exercise.status == ExerciseStatus.assigned,
            Exercise.due_at >= now,
        )
        result = await self.session.exec(statement)
        return list(result.all())

    async def update_status(
        self,
        exercise_id: int,
        status: ExerciseStatus,
    ) -> Exercise | None:
        exercise = await self.get_by_id(exercise_id)
        if not exercise:
            return None
        exercise.status = status
        if status == ExerciseStatus.assigned:
            exercise.assigned_at = datetime.utcnow()
        elif status == ExerciseStatus.completed:
            exercise.completed_at = datetime.utcnow()
        exercise.updated_at = datetime.utcnow()
        self.session.add(exercise)
        await self.session.commit()
        await self.session.refresh(exercise)
        return exercise
