"""
Qwen-VL 多模态 OCR 客户端
支持阿里云 DashScope API 或本地 vLLM 部署
"""

import base64
import json
from typing import Any

import httpx

from app.ai.base import BaseLLMClient
from app.core.config import settings
from app.core.exceptions import BadRequestException


class QwenVLClient(BaseLLMClient):
    """Qwen-VL 多模态客户端"""

    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY or ""
        self.base_url = settings.DEEPSEEK_BASE_URL or "https://dashscope.aliyuncs.com/api/v1"
        self.model = "qwen-vl-max"
        self.timeout = 60.0

    def _encode_image(self, image_bytes: bytes) -> str:
        """将图片转为 base64"""
        return base64.b64encode(image_bytes).decode("utf-8")

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        response_format: dict | None = None,
    ) -> str:
        """纯文本对话"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/services/aigc/multimodal-generation/generation",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["output"]["choices"][0]["message"]["content"]

    async def chat_with_image(
        self,
        image_bytes: bytes,
        text_prompt: str,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """图片+文本多模态对话"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        b64_image = self._encode_image(image_bytes)

        messages = [
            {
                "role": "user",
                "content": [
                    {"image": f"data:image/png;base64,{b64_image}"},
                    {"text": text_prompt},
                ],
            }
        ]

        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/services/aigc/multimodal-generation/generation",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["output"]["choices"][0]["message"]["content"]

    async def recognize_exam_page(
        self,
        image_bytes: bytes,
        subject_hint: str = "数学",
    ) -> dict[str, Any]:
        """
        识别试卷页面，输出结构化版面分析结果

        返回:
            {
                "page_number": 1,
                "questions": [
                    {
                        "sequence": 1,
                        "type": "choice",
                        "content": "题干文本",
                        "content_latex": "LaTeX格式",
                        "options": {"A": "...", "B": "..."},
                        "score": 5,
                        "bbox": {"x": 0.1, "y": 0.1, "width": 0.8, "height": 0.15},
                        "answer_area": {"x": 0.1, "y": 0.3, "width": 0.8, "height": 0.1}
                    }
                ]
            }
        """
        prompt = f"""你是一位专业的试卷版面分析专家。请仔细分析这张{subject_hint}试卷图片，提取所有题目信息。

要求输出严格的 JSON 格式：
{{
    "page_number": 1,
    "questions": [
        {{
            "sequence": 1,
            "type": "choice",
            "content": "题目内容（保留LaTeX公式）",
            "content_latex": "纯LaTeX",
            "options": {{"A": "选项A", "B": "选项B", "C": "选项C", "D": "选项D"}},
            "score": 5,
            "bbox": {{"x": 0.0, "y": 0.0, "width": 1.0, "height": 0.1}},
            "answer_area": {{"x": 0.0, "y": 0.1, "width": 1.0, "height": 0.05}}
        }}
    ]
}}

type 只能是: choice(选择题), fill_blank(填空题), short_answer(简答题), calculation(计算题), proof(证明题)
bbox 和 answer_area 使用相对坐标 (0-1)
如果某题没有选项，options 为空对象 {{}}
"""

        try:
            result_text = await self.chat_with_image(
                image_bytes=image_bytes,
                text_prompt=prompt,
                temperature=0.1,
                max_tokens=4096,
            )

            # 提取 JSON
            json_str = self._extract_json(result_text)
            parsed = json.loads(json_str)
            parsed["_provider"] = "qwen-vl"
            return parsed

        except Exception as e:
            raise BadRequestException(f"Qwen-VL 识别失败: {e}") from e

    async def recognize_student_answer(
        self,
        image_bytes: bytes,
        question_content: str = "",
    ) -> str:
        """识别学生手写作答内容"""
        prompt = f"""请识别这张图片中的学生手写作答内容。

已知题目：{question_content or "未知"}

要求：
1. 将手写内容转为文本
2. 数学公式用 LaTeX 表示
3. 如果字迹不清，标注 [unclear]
4. 只输出识别结果，不要解释

学生答案："""

        result = await self.chat_with_image(
            image_bytes=image_bytes,
            text_prompt=prompt,
            temperature=0.1,
            max_tokens=2048,
        )
        return result.strip()

    @staticmethod
    def _extract_json(text: str) -> str:
        """从文本中提取 JSON"""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()
