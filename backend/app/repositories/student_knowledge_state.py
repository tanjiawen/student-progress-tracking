"""Student knowledge state repository."""

from datetime import datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.student_knowledge_state import MasteryStatus, StudentKnowledgeState
from app.repositories.base import BaseRepository


class StudentKnowledgeStateRepository(BaseRepository[StudentKnowledgeState]):
    """Repository for StudentKnowledgeState entity."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, StudentKnowledgeState)

    async def get_by_student(self, student_id: int) -> list[StudentKnowledgeState]:
        statement = select(StudentKnowledgeState).where(
            StudentKnowledgeState.student_id == student_id
        )
        result = await self.session.exec(statement)
        return list(result.all())

    async def get_by_student_and_kp(
        self, student_id: int, knowledge_point_id: int
    ) -> StudentKnowledgeState | None:
        statement = select(StudentKnowledgeState).where(
            StudentKnowledgeState.student_id == student_id,
            StudentKnowledgeState.knowledge_point_id == knowledge_point_id,
        )
        result = await self.session.exec(statement)
        return result.first()

    async def get_weak_points(
        self, student_id: int, threshold: float = 0.5
    ) -> list[StudentKnowledgeState]:
        statement = select(StudentKnowledgeState).where(
            StudentKnowledgeState.student_id == student_id,
            StudentKnowledgeState.mastery_probability < threshold,
        )
        result = await self.session.exec(statement)
        return list(result.all())

    async def get_mastered_points(
        self, student_id: int, threshold: float = 0.8
    ) -> list[StudentKnowledgeState]:
        statement = select(StudentKnowledgeState).where(
            StudentKnowledgeState.student_id == student_id,
            StudentKnowledgeState.mastery_probability >= threshold,
        )
        result = await self.session.exec(statement)
        return list(result.all())

    async def update_mastery(
        self, student_id: int, knowledge_point_id: int, mastery_probability: float
    ) -> StudentKnowledgeState | None:
        """Atomically update mastery probability for a student-knowledge point pair."""
        state = await self.get_by_student_and_kp(student_id, knowledge_point_id)
        if not state:
            return None
        state.mastery_probability = mastery_probability
        if mastery_probability >= 0.8:
            state.status = MasteryStatus.mastered
        elif mastery_probability < 0.5:
            state.status = MasteryStatus.weak
        else:
            state.status = MasteryStatus.normal
        state.updated_at = datetime.utcnow()
        self.session.add(state)
        await self.session.commit()
        await self.session.refresh(state)
        return state
