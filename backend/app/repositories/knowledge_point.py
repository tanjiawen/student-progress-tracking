"""Knowledge point repository."""

from sqlalchemy.orm import aliased
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.knowledge_point import KnowledgePoint
from app.repositories.base import BaseRepository


class KnowledgePointRepository(BaseRepository[KnowledgePoint]):
    """Repository for KnowledgePoint entity."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, KnowledgePoint)

    async def get_by_subject(self, subject_id: int) -> list[KnowledgePoint]:
        statement = select(KnowledgePoint).where(KnowledgePoint.subject_id == subject_id)
        result = await self.session.exec(statement)
        return list(result.all())

    async def get_children(self, parent_id: int) -> list[KnowledgePoint]:
        statement = select(KnowledgePoint).where(KnowledgePoint.parent_id == parent_id)
        result = await self.session.exec(statement)
        return list(result.all())

    async def get_tree_by_subject(self, subject_id: int) -> list[KnowledgePoint]:
        statement = (
            select(KnowledgePoint)
            .where(KnowledgePoint.subject_id == subject_id)
            .order_by(KnowledgePoint.level, KnowledgePoint.id)
        )
        result = await self.session.exec(statement)
        return list(result.all())

    async def get_path_to_root(self, kp_id: int) -> list[KnowledgePoint]:
        """Get path from knowledge point to root using recursive CTE."""
        cte = (
            select(KnowledgePoint)
            .where(KnowledgePoint.id == kp_id)
            .cte(recursive=True)
        )
        cte_alias = aliased(KnowledgePoint, cte)
        cte = cte.union_all(
            select(KnowledgePoint).where(KnowledgePoint.id == cte_alias.parent_id)
        )
        statement = select(cte)
        result = await self.session.exec(statement)
        return list(result.all())

    async def get_by_code(self, code: str) -> KnowledgePoint | None:
        statement = select(KnowledgePoint).where(KnowledgePoint.code == code)
        result = await self.session.exec(statement)
        return result.first()
