"""Knowledge relation repository."""

from sqlalchemy.orm import aliased
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.knowledge_relation import KnowledgeRelation
from app.repositories.base import BaseRepository


class KnowledgeRelationRepository(BaseRepository[KnowledgeRelation]):
    """Repository for KnowledgeRelation entity."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, KnowledgeRelation)

    async def get_relations_by_source(self, source_id: int) -> list[KnowledgeRelation]:
        statement = select(KnowledgeRelation).where(
            KnowledgeRelation.source_kp_id == source_id
        )
        result = await self.session.exec(statement)
        return list(result.all())

    async def get_relations_by_target(self, target_id: int) -> list[KnowledgeRelation]:
        statement = select(KnowledgeRelation).where(
            KnowledgeRelation.target_kp_id == target_id
        )
        result = await self.session.exec(statement)
        return list(result.all())

    async def get_prerequisites(self, target_id: int) -> list[int]:
        """Recursively get all prerequisite knowledge point IDs."""
        cte = (
            select(KnowledgeRelation.source_kp_id)
            .where(
                KnowledgeRelation.target_kp_id == target_id,
                KnowledgeRelation.relation_type == "prerequisite",
            )
            .cte(recursive=True)
        )
        cte_alias = aliased(KnowledgeRelation, cte)
        cte = cte.union_all(
            select(KnowledgeRelation.source_kp_id).where(
                KnowledgeRelation.target_kp_id == cte_alias.source_kp_id,
                KnowledgeRelation.relation_type == "prerequisite",
            )
        )
        statement = select(cte)
        result = await self.session.exec(statement)
        rows = result.all()
        return [row[0] for row in rows]
