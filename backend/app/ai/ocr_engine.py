"""
OCR 引擎统一入口
支持多 provider 切换 + 自动降级（fallback）策略
"""

from typing import Any, Dict, List, Optional

from app.ai.mathpix import MathpixClient
from app.ai.openai_vision import OpenAIVisionClient
from app.ai.qwen_vl import QwenVLClient
from app.core.config import settings
from app.core.exceptions import BadRequestException


class OCREngine:
    """
    OCR 引擎统一入口

    优先级策略：
    1. Qwen-VL / GPT-4V（多模态，版面分析最强）
    2. Mathpix（公式识别最准，作为补充）

    降级策略：
    - 如果主模型失败，自动尝试备用模型
    - 如果都失败，返回错误，标记为待人工处理
    """

    def __init__(self):
        self.qwen = QwenVLClient()
        self.gpt4v = OpenAIVisionClient()
        self.mathpix = MathpixClient()

        # 配置可用 provider
        self.providers = []
        if settings.OPENAI_API_KEY or settings.DEEPSEEK_API_KEY:
            self.providers.append("qwen-vl")
            self.providers.append("gpt-4o")
        if settings.MATHPIX_APP_ID and settings.MATHPIX_API_KEY:
            self.providers.append("mathpix")

    async def analyze_exam_page(
        self,
        image_bytes: bytes,
        subject_hint: str = "数学",
        preferred_provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        分析试卷页面，输出结构化题目

        Args:
            image_bytes: 页面图片
            subject_hint: 学科提示
            preferred_provider: 优先使用的模型

        Returns:
            {
                "success": True,
                "provider": "qwen-vl",
                "data": {"page_number": 1, "questions": [...]},
                "fallback_used": False
            }
        """
        providers_to_try = self._get_provider_order(preferred_provider)

        last_error = None
        for provider in providers_to_try:
            try:
                if provider in ("qwen-vl", "gpt-4o"):
                    client = self.qwen if provider == "qwen-vl" else self.gpt4v
                    result = await client.recognize_exam_page(
                        image_bytes=image_bytes,
                        subject_hint=subject_hint,
                    )
                    return {
                        "success": True,
                        "provider": provider,
                        "data": result,
                        "fallback_used": provider != providers_to_try[0],
                    }

                elif provider == "mathpix":
                    # Mathpix 只做文本/公式识别，不做版面分析
                    result = await self.mathpix.recognize(image_bytes)
                    # 将 Mathpix 结果包装为标准格式
                    return {
                        "success": True,
                        "provider": "mathpix",
                        "data": {
                            "page_number": 1,
                            "questions": [
                                {
                                    "sequence": 1,
                                    "type": "unknown",
                                    "content": result.get("text", ""),
                                    "content_latex": result.get("latex", ""),
                                    "options": {},
                                    "score": 0,
                                    "bbox": {},
                                    "answer_area": {},
                                    "ocr_confidence": result.get("confidence", 0),
                                }
                            ],
                        },
                        "fallback_used": provider != providers_to_try[0],
                        "warning": "Mathpix 仅提供文本识别，未进行版面分析，建议人工校对",
                    }

            except Exception as e:
                last_error = e
                continue

        # 全部失败
        raise BadRequestException(
            f"OCR 识别全部失败。已尝试: {providers_to_try}。最后错误: {last_error}"
        )

    async def recognize_student_answer(
        self,
        image_bytes: bytes,
        question_content: str = "",
        preferred_provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        识别学生手写作答

        Returns:
            {
                "success": True,
                "provider": "gpt-4o",
                "text": "学生答案文本",
                "latex": "LaTeX格式",
                "fallback_used": False
            }
        """
        providers_to_try = self._get_provider_order(preferred_provider)

        last_error = None
        for provider in providers_to_try:
            try:
                if provider in ("qwen-vl", "gpt-4o"):
                    client = self.qwen if provider == "qwen-vl" else self.gpt4v
                    text = await client.recognize_student_answer(
                        image_bytes=image_bytes,
                        question_content=question_content,
                    )
                    return {
                        "success": True,
                        "provider": provider,
                        "text": text,
                        "latex": "",  # TODO: extract latex from text
                        "fallback_used": provider != providers_to_try[0],
                    }

                elif provider == "mathpix":
                    result = await self.mathpix.recognize(image_bytes)
                    return {
                        "success": True,
                        "provider": "mathpix",
                        "text": result.get("text", ""),
                        "latex": result.get("latex", ""),
                        "fallback_used": provider != providers_to_try[0],
                    }

            except Exception as e:
                last_error = e
                continue

        raise BadRequestException(
            f"手写识别全部失败。已尝试: {providers_to_try}。最后错误: {last_error}"
        )

    async def recognize_formula(
        self,
        image_bytes: bytes,
    ) -> str:
        """专门识别公式，优先使用 Mathpix"""
        try:
            if settings.MATHPIX_APP_ID and settings.MATHPIX_API_KEY:
                return await self.mathpix.recognize_formula_only(image_bytes)
        except Exception:
            pass

        # fallback 到多模态模型
        try:
            result = await self.qwen.recognize_student_answer(
                image_bytes=image_bytes,
                question_content="请识别图片中的数学公式，只输出 LaTeX",
            )
            return result
        except Exception:
            pass

        return ""

    def _get_provider_order(
        self, preferred: Optional[str] = None
    ) -> List[str]:
        """确定 provider 尝试顺序"""
        order = []
        if preferred and preferred in self.providers:
            order.append(preferred)
        for p in self.providers:
            if p not in order:
                order.append(p)
        return order if order else ["qwen-vl"]


# 全局实例
ocr_engine = OCREngine()
