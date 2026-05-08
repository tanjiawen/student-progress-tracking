"""事件消费者 —— 从Redis队列消费通知并推送到WebSocket (Security fix A-003).

在应用启动时作为后台任务运行，持续消费Celery任务发布的通知事件。
"""

from __future__ import annotations

import asyncio
import json
import logging

from app.core.redis_client import redis_client
from app.core.websocket_manager import manager

logger = logging.getLogger(__name__)

NOTIFICATION_QUEUE_KEY = "notification:queue"
CONSUMER_STOP_EVENT: asyncio.Event | None = None


async def consume_notifications() -> None:
    """Continuously consume notifications from Redis and push to WebSocket clients."""
    global CONSUMER_STOP_EVENT
    CONSUMER_STOP_EVENT = asyncio.Event()
    logger.info("notification_consumer_started")

    while not CONSUMER_STOP_EVENT.is_set():
        try:
            # Use BRPOP with timeout to allow graceful shutdown checking
            result = await redis_client.brpop(NOTIFICATION_QUEUE_KEY, timeout=1)
            if result is None:
                continue

            # result is a tuple (key, value) from BRPOP
            _, message_json = result
            message = json.loads(message_json)

            user_id = str(message.get("user_id", ""))
            msg_type = message.get("type", "unknown")
            data = message.get("data", {})

            if user_id:
                await manager.send_to_user(
                    user_id,
                    manager.build_message(msg_type, data),
                )
                logger.debug(
                    "notification_pushed",
                    user_id=user_id,
                    msg_type=msg_type,
                )
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.exception("notification_consumer_error", error=str(exc))

    logger.info("notification_consumer_stopped")


async def start_consumer() -> None:
    """Start the notification consumer as a background task."""
    asyncio.create_task(consume_notifications(), name="notification_consumer")


def stop_consumer() -> None:
    """Signal the consumer to stop."""
    global CONSUMER_STOP_EVENT
    if CONSUMER_STOP_EVENT is not None:
        CONSUMER_STOP_EVENT.set()
