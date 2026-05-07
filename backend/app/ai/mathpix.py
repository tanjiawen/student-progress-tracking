"""
Mathpix API 客户端 - 公式识别（LaTeX 转换）
适合识别印刷体公式和清晰的手写公式
"""

import base64
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import BadRequestException


class MathpixClient:
    """Mathpix OCR 客户端"""

    API_URL = "https://api.mathpix.com/v3/text"

    def __init__(self):
        self.app_id = settings.MATHPIX_APP_ID or ""
        self.api_key = settings.MATHPIX_API_KEY or ""
        self.timeout = 30.0

    def _get_headers(self) -> dict[str, str]:
        return {
            "app_id": self.app_id,
            "app_key": self.api_key,
            "Content-Type": "application/json",
        }

    async def recognize(
        self,
        image_bytes: bytes,
        include_latex: bool = True,
        include_text: bool = True,
    ) -> dict[str, Any]:
        """
        识别图片中的公式和文本

        Returns:
            {
                "text": "纯文本",
                "latex": "LaTeX格式",
                "confidence": 0.95,
                "lines": [...],
                "words": [...]
            }
        """
        if not self.app_id or not self.api_key:
            raise BadRequestException("Mathpix API 密钥未配置") from None

        b64_image = base64.b64encode(image_bytes).decode("utf-8")

        payload = {
            "src": f"data:image/png;base64,{b64_image}",
            "formats": ["text", "latex_styled"] if include_latex else ["text"],
            "math_inline_delimiters": ["$", "$"],
            "rm_spaces": True,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self.API_URL,
                headers=self._get_headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            return {
                "text": data.get("text", ""),
                "latex": data.get("latex_styled", ""),
                "confidence": data.get("confidence", 0.0),
                "lines": data.get("lines", []),
                "words": data.get("words", []),
                "raw": data,
                "_provider": "mathpix",
            }

    async def batch_recognize(
        self,
        image_bytes_list: list[bytes],
    ) -> list[dict[str, Any]]:
        """批量识别"""
        results = []
        for img_bytes in image_bytes_list:
            try:
                result = await self.recognize(img_bytes)
                results.append(result)
            except Exception as e:
                results.append({"error": str(e), "_provider": "mathpix"})
        return results

    async def recognize_formula_only(
        self,
        image_bytes: bytes,
    ) -> str:
        """仅识别公式，返回 LaTeX"""
        result = await self.recognize(image_bytes, include_text=False)
        return result.get("latex", "")
