"""Subject repository."""

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.subject import Subject
from app.repositories.base import BaseRepository


class SubjectRepository(BaseRepository[Subject]):
    """Repository for Subject entity."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Subject)

    async def get_by_code(self, code: str) -> Subject | None:
        statement = select(Subject).where(Subject.code == code)
        result = await self.session.exec(statement)
        return result.first()
