"""Webhook service for Feishu/DingTalk integration."""

from __future__ import annotations

import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)


class WebhookService:
    """飞书/钉钉 Webhook 推送"""

    async def send_feishu_card(
        self,
        webhook_url: str,
        title: str,
        content: dict,
    ) -> bool:
        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "plain_text",
                            "content": str(content),
                        },
                    }
                ],
            },
        }
        return await self._post_with_retry(webhook_url, card)

    async def send_dingtalk_markdown(
        self,
        webhook_url: str,
        title: str,
        text: str,
    ) -> bool:
        payload = {
            "msgtype": "markdown",
            "markdown": {"title": title, "text": text},
        }
        return await self._post_with_retry(webhook_url, payload)

    async def notify_exam_graded(
        self,
        webhook_url: str,
        exam_title: str,
        class_name: str,
        graded_count: int,
        total_count: int,
    ) -> bool:
        markdown = (
            f"## ✅ 考试判卷完成\n\n"
            f"**考试名称:** {exam_title}\n\n"
            f"**班级:** {class_name}\n\n"
            f"**进度:** {graded_count}/{total_count}\n\n"
        )
        return await self.send_dingtalk_markdown(webhook_url, "考试判卷完成", markdown)

    async def _post_with_retry(
        self, url: str, payload: dict, max_retries: int = 3
    ) -> bool:
        for attempt in range(1, max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.post(url, json=payload)
                    response.raise_for_status()
                    return True
            except Exception as exc:
                logger.warning(
                    "Webhook attempt %s/%s failed: %s", attempt, max_retries, exc
                )
                if attempt < max_retries:
                    await asyncio.sleep(2**attempt)
                else:
                    logger.error(
                        "Webhook failed after %s retries: %s", max_retries, exc
                    )
        return False


webhook_service = WebhookService()
