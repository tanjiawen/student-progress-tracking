"""Question template repository."""

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.question_template import QuestionTemplate
from app.repositories.base import BaseRepository


class QuestionTemplateRepository(BaseRepository[QuestionTemplate]):
    """Repository for QuestionTemplate entity."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, QuestionTemplate)

    async def get_by_subject(self, subject_id: int) -> list[QuestionTemplate]:
        statement = select(QuestionTemplate).where(
            QuestionTemplate.subject_id == subject_id
        )
        result = await self.session.exec(statement)
        return list(result.all())

    async def get_by_knowledge_point(self, knowledge_point_id: int) -> list[QuestionTemplate]:
        statement = select(QuestionTemplate).where(
            QuestionTemplate.knowledge_point_ids.contains([knowledge_point_id])
        )
        result = await self.session.exec(statement)
        return list(result.all())

    async def get_by_difficulty(self, difficulty: int) -> list[QuestionTemplate]:
        statement = select(QuestionTemplate).where(
            QuestionTemplate.difficulty == difficulty
        )
        result = await self.session.exec(statement)
        return list(result.all())

    async def search_by_content(self, keyword: str) -> list[QuestionTemplate]:
        statement = select(QuestionTemplate).where(
            QuestionTemplate.content.ilike(f"%{keyword}%")
        )
        result = await self.session.exec(statement)
        return list(result.all())
