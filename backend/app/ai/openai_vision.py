"""
OpenAI GPT-4V / GPT-4o 多模态客户端
兼容 OpenAI API 格式，也支持 DeepSeek 等兼容接口
"""

import base64
import json
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.core.exceptions import BadRequestException


class OpenAIVisionClient:
    """OpenAI 兼容的多模态视觉客户端"""

    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY or settings.DEEPSEEK_API_KEY or ""
        self.base_url = settings.DEEPSEEK_BASE_URL or "https://api.openai.com/v1"
        self.model = "gpt-4o"
        self.timeout = 60.0

    def _encode_image(self, image_bytes: bytes) -> str:
        return base64.b64encode(image_bytes).decode("utf-8")

    async def chat_with_image(
        self,
        image_bytes: bytes,
        text_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None,
    ) -> str:
        """多模态对话"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        b64_image = self._encode_image(image_bytes)

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{b64_image}",
                            "detail": "high",
                        },
                    },
                    {"type": "text", "text": text_prompt},
                ],
            }
        ]

        payload: Dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def recognize_exam_page(
        self,
        image_bytes: bytes,
        subject_hint: str = "数学",
    ) -> Dict[str, Any]:
        """识别试卷页面"""
        prompt = f"""你是一位专业的试卷版面分析专家。请仔细分析这张{subject_hint}试卷图片，提取所有题目信息。

必须输出严格的 JSON 格式，不要有任何其他文字：
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

type 只能是: choice, fill_blank, short_answer, calculation, proof
bbox 和 answer_area 使用相对坐标 (0-1)
"""

        try:
            result_text = await self.chat_with_image(
                image_bytes=image_bytes,
                text_prompt=prompt,
                temperature=0.1,
                max_tokens=4096,
            )

            json_str = self._extract_json(result_text)
            parsed = json.loads(json_str)
            parsed["_provider"] = "gpt-4o"
            return parsed

        except Exception as e:
            raise BadRequestException(f"GPT-4V 识别失败: {e}")

    async def recognize_student_answer(
        self,
        image_bytes: bytes,
        question_content: str = "",
    ) -> str:
        """识别学生手写作答"""
        prompt = f"""请识别图片中的学生手写作答内容。
题目：{question_content or "未知"}
要求：
1. 手写内容转文本
2. 数学公式用 LaTeX
3. 字迹不清处标注 [unclear]
4. 只输出识别结果"""

        result = await self.chat_with_image(
            image_bytes=image_bytes,
            text_prompt=prompt,
            temperature=0.1,
            max_tokens=2048,
        )
        return result.strip()

    @staticmethod
    def _extract_json(text: str) -> str:
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()
