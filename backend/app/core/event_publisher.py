"""事件发布模块 —— 用于Celery任务与WebSocket解耦 (Security fix A-003).

Celery任务通过Redis List发布通知事件，由后端事件消费者异步消费并推送到WebSocket。
这种解耦避免了Celery Worker直接处理实时通信层的职责。
"""

from __future__ import annotations

import json
from typing import Any

from app.core.redis_client import redis_client

NOTIFICATION_QUEUE_KEY = "notification:queue"


async def publish_notification(user_id: str, msg_type: str, data: dict[str, Any]) -> None:
    """Publish a notification event to the Redis queue.

    Args:
        user_id: Target user ID.
        msg_type: Message type (e.g. "grading_complete", "ocr_progress").
        data: Payload data.
    """
    message = json.dumps({
        "user_id": user_id,
        "type": msg_type,
        "data": data,
    })
    await redis_client.lpush(NOTIFICATION_QUEUE_KEY, message)


def publish_notification_sync(user_id: str, msg_type: str, data: dict[str, Any]) -> None:
    """Synchronous version for Celery tasks (uses async_to_sync bridge).

    Args:
        user_id: Target user ID.
        msg_type: Message type.
        data: Payload data.
    """
    from asgiref.sync import async_to_sync
    async_to_sync(publish_notification)(user_id, msg_type, data)
