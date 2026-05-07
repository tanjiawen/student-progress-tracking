"""Notification service."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.websocket_manager import manager
from app.models.notification import Notification
from app.models.notification_setting import NotificationSetting
from app.models.student import Student
from app.services.webhook_service import webhook_service

logger = logging.getLogger(__name__)


class NotificationService:
    """系统通知服务"""

    async def send_notification(
        self,
        session: AsyncSession,
        user_id: int,
        title: str,
        content: str,
        notification_type: str,
        data: dict | None = None,
    ) -> Notification:
        # 1. 写入数据库
        notification = Notification(
            user_id=user_id,
            title=title,
            content=content,
            notification_type=notification_type,
            data=data,
            is_read=False,
            read_at=None,
        )
        session.add(notification)
        await session.commit()
        await session.refresh(notification)

        # 2. WebSocket 推送（如果用户在线）
        message = manager.build_message(
            notification_type,
            {
                "id": notification.id,
                "title": title,
                "content": content,
                "data": data,
                "is_read": False,
            },
        )
        await manager.send_to_user(str(user_id), message)

        # 3. Webhook 推送（如果配置了）
        await self._maybe_send_webhook(
            session, user_id, title, content, notification_type
        )

        return notification

    async def broadcast_to_class(
        self,
        session: AsyncSession,
        class_id: int,
        title: str,
        content: str,
        notification_type: str,
        data: dict | None = None,
    ) -> None:
        statement = select(Student).where(Student.class_id == class_id)
        result = await session.exec(statement)
        students = list(result.all())
        for student in students:
            if student.user_id:
                await self.send_notification(
                    session,
                    student.user_id,
                    title,
                    content,
                    notification_type,
                    data,
                )

    async def mark_as_read(
        self, session: AsyncSession, notification_id: int
    ) -> Notification | None:
        notification = await session.get(Notification, notification_id)
        if not notification:
            return None
        notification.is_read = True
        notification.read_at = datetime.now(UTC)
        session.add(notification)
        await session.commit()
        await session.refresh(notification)
        return notification

    async def mark_all_as_read(
        self, session: AsyncSession, user_id: int
    ) -> int:
        statement = select(Notification).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        result = await session.exec(statement)
        notifications = list(result.all())
        count = 0
        for n in notifications:
            n.is_read = True
            n.read_at = datetime.now(UTC)
            session.add(n)
            count += 1
        if count:
            await session.commit()
        return count

    async def get_unread_count(
        self, session: AsyncSession, user_id: int
    ) -> int:
        from sqlalchemy import func

        statement = select(func.count(Notification.id)).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        result = await session.exec(statement)
        return result.one()

    async def _maybe_send_webhook(
        self,
        session: AsyncSession,
        user_id: int,
        title: str,
        content: str,
        notification_type: str,
    ) -> None:
        statement = select(NotificationSetting).where(
            NotificationSetting.user_id == user_id
        )
        result = await session.exec(statement)
        setting = result.first()
        if not setting or not setting.enable_webhook or not setting.webhook_url:
            return

        # 按类型过滤
        type_prefix = notification_type.split(".")[0] if "." in notification_type else notification_type
        type_map = {
            "system": "notify_system",
            "exam": "notify_exam",
            "exercise": "notify_exercise",
            "error_book": "notify_error_book",
        }
        type_key = type_map.get(type_prefix)
        if type_key and hasattr(setting, type_key) and not getattr(setting, type_key):
            return

        if setting.webhook_type == "feishu":
            await webhook_service.send_feishu_card(
                setting.webhook_url, title, {"content": content}
            )
        elif setting.webhook_type == "dingtalk":
            await webhook_service.send_dingtalk_markdown(
                setting.webhook_url, title, content
            )


notification_service = NotificationService()
