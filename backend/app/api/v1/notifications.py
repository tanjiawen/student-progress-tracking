"""Notification API routes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_current_user
from app.core.exceptions import NotFoundException
from app.models.notification_setting import NotificationSetting
from app.repositories.notification import NotificationRepository
from app.repositories.notification_setting import NotificationSettingRepository
from app.schemas.common import BaseResponse
from app.schemas.notification import (
    NotificationRead,
    NotificationSettingsRead,
    NotificationSettingsUpdate,
)
from app.schemas.user import UserRead
from app.services.notification_service import notification_service

router = APIRouter()


@router.get("/", response_model=BaseResponse)
async def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    current_user: UserRead = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Any:
    repo = NotificationRepository(session)
    skip = (page - 1) * page_size
    if unread_only:
        items = await repo.get_unread_by_user(current_user.id)
        total = len(items)
    else:
        items = await repo.get_by_user(current_user.id, skip=skip, limit=page_size)
        total = await repo.count_by_user(current_user.id)
    return BaseResponse(
        data={
            "items": [NotificationRead(**n.model_dump()) for n in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.get("/unread-count", response_model=BaseResponse)
async def get_unread_count(
    current_user: UserRead = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Any:
    count = await notification_service.get_unread_count(session, current_user.id)
    return BaseResponse(data={"unread_count": count})


@router.post("/{notification_id}/read", response_model=BaseResponse)
async def mark_as_read(
    notification_id: int,
    current_user: UserRead = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Any:
    notification = await notification_service.mark_as_read(session, notification_id)
    if not notification:
        raise NotFoundException("Notification not found")
    return BaseResponse(
        data=NotificationRead(**notification.model_dump()),
    )


@router.post("/read-all", response_model=BaseResponse)
async def mark_all_as_read(
    current_user: UserRead = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Any:
    count = await notification_service.mark_all_as_read(session, current_user.id)
    return BaseResponse(data={"marked_count": count})


@router.delete("/{notification_id}", response_model=BaseResponse)
async def delete_notification(
    notification_id: int,
    current_user: UserRead = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Any:
    repo = NotificationRepository(session)
    notification = await repo.get_by_id(notification_id)
    if not notification:
        raise NotFoundException("Notification not found")
    await repo.delete(notification_id)
    return BaseResponse(data={"deleted": True})


@router.get("/settings", response_model=BaseResponse)
async def get_notification_settings(
    current_user: UserRead = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Any:
    repo = NotificationSettingRepository(session)
    setting = await repo.get_by_user_id(current_user.id)
    if not setting:
        # 返回默认设置
        return BaseResponse(
            data=NotificationSettingsRead(
                user_id=current_user.id,
                enable_web_socket=True,
                enable_webhook=False,
                webhook_url=None,
                webhook_type=None,
                notify_system=True,
                notify_exam=True,
                notify_exercise=True,
                notify_error_book=True,
            )
        )
    return BaseResponse(data=NotificationSettingsRead(**setting.model_dump()))


@router.put("/settings", response_model=BaseResponse)
async def update_notification_settings(
    update: NotificationSettingsUpdate,
    current_user: UserRead = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Any:
    repo = NotificationSettingRepository(session)
    setting = await repo.get_by_user_id(current_user.id)
    if not setting:
        setting = NotificationSetting(user_id=current_user.id)
        session.add(setting)
        await session.commit()
        await session.refresh(setting)

    update_data = update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "user_id":
            continue
        setattr(setting, key, value)
    setting.updated_at = datetime.now(UTC)
    session.add(setting)
    await session.commit()
    await session.refresh(setting)
    return BaseResponse(data=NotificationSettingsRead(**setting.model_dump()))
