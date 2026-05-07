"""Notification setting repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.notification_setting import NotificationSetting
from app.repositories.base import BaseRepository


class NotificationSettingRepository(BaseRepository[NotificationSetting]):
    """Repository for NotificationSetting entity."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, NotificationSetting)

    async def get_by_user_id(self, user_id: int) -> NotificationSetting | None:
        statement = select(NotificationSetting).where(
            NotificationSetting.user_id == user_id
        )
        result = await self.session.exec(statement)
        return result.first()
