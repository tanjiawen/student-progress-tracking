"""Error book item repository."""

from datetime import datetime, timedelta

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.error_book_item import ErrorBookItem
from app.repositories.base import BaseRepository


class ErrorBookItemRepository(BaseRepository[ErrorBookItem]):
    """Repository for ErrorBookItem entity."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ErrorBookItem)

    async def get_by_student(self, student_id: int) -> list[ErrorBookItem]:
        statement = select(ErrorBookItem).where(ErrorBookItem.student_id == student_id)
        result = await self.session.exec(statement)
        return list(result.all())

    async def get_due_for_review(self) -> list[ErrorBookItem]:
        now = datetime.utcnow()
        statement = select(ErrorBookItem).where(
            ErrorBookItem.is_resolved.is_(False),
            ErrorBookItem.next_review_at <= now,
        )
        result = await self.session.exec(statement)
        return list(result.all())

    async def get_by_knowledge_point(
        self, knowledge_point_id: int
    ) -> list[ErrorBookItem]:
        """Get error book items by knowledge point via question_template proxy."""
        statement = select(ErrorBookItem).where(
            ErrorBookItem.question_template_id == knowledge_point_id
        )
        result = await self.session.exec(statement)
        return list(result.all())

    async def increment_error_count(self, item_id: int) -> ErrorBookItem | None:
        item = await self.get_by_id(item_id)
        if not item:
            return None
        item.error_count += 1
        item.is_resolved = False
        days = min(2 ** (item.error_count - 1), 30)
        item.next_review_at = datetime.utcnow() + timedelta(days=days)
        item.updated_at = datetime.utcnow()
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def mark_resolved(self, item_id: int) -> ErrorBookItem | None:
        item = await self.get_by_id(item_id)
        if not item:
            return None
        item.is_resolved = True
        item.resolved_at = datetime.utcnow()
        item.updated_at = datetime.utcnow()
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item
