"""Notification repository."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.notification import Notification
from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    """Repository for Notification entity."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Notification)

    async def get_by_user(
        self, user_id: int, skip: int = 0, limit: int = 50
    ) -> list[Notification]:
        statement = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.exec(statement)
        return list(result.all())

    async def get_unread_by_user(self, user_id: int) -> list[Notification]:
        statement = (
            select(Notification)
            .where(Notification.user_id == user_id, Notification.is_read.is_(False))
            .order_by(Notification.created_at.desc())
        )
        result = await self.session.exec(statement)
        return list(result.all())

    async def count_by_user(self, user_id: int) -> int:
        statement = select(func.count(Notification.id)).where(
            Notification.user_id == user_id
        )
        result = await self.session.exec(statement)
        return result.one()

    async def count_unread_by_user(self, user_id: int) -> int:
        statement = select(func.count(Notification.id)).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        result = await self.session.exec(statement)
        return result.one()
