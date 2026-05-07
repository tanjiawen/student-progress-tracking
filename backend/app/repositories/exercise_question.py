"""Exercise question repository."""

from datetime import datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.exercise_question import ExerciseQuestion
from app.repositories.base import BaseRepository


class ExerciseQuestionRepository(BaseRepository[ExerciseQuestion]):
    """Repository for ExerciseQuestion entity."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ExerciseQuestion)

    async def get_by_exercise(self, exercise_id: int) -> list[ExerciseQuestion]:
        statement = (
            select(ExerciseQuestion)
            .where(ExerciseQuestion.exercise_id == exercise_id)
            .order_by(ExerciseQuestion.sequence_number)
        )
        result = await self.session.exec(statement)
        return list(result.all())

    async def submit_answer(
        self,
        exercise_question_id: int,
        answer: str,
    ) -> ExerciseQuestion | None:
        eq = await self.get_by_id(exercise_question_id)
        if not eq:
            return None
        eq.student_answer = answer
        eq.updated_at = datetime.utcnow()
        self.session.add(eq)
        await self.session.commit()
        await self.session.refresh(eq)
        return eq

    async def update_grading_result(
        self,
        exercise_question_id: int,
        is_correct: bool,
        score: float,
        ai_explanation: str | None = None,
    ) -> ExerciseQuestion | None:
        eq = await self.get_by_id(exercise_question_id)
        if not eq:
            return None
        eq.is_correct = is_correct
        eq.score = score
        if ai_explanation is not None:
            eq.ai_explanation = ai_explanation
        eq.updated_at = datetime.utcnow()
        self.session.add(eq)
        await self.session.commit()
        await self.session.refresh(eq)
        return eq
