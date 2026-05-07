"""
AI 客户端基类与统一接口
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class OCRResult:
    """OCR 识别结果"""

    def __init__(
        self,
        text: str = "",
        latex: str = "",
        confidence: float = 0.0,
        bbox: Optional[Dict[str, float]] = None,
        raw_response: Optional[Dict] = None,
    ):
        self.text = text
        self.latex = latex
        self.confidence = confidence
        self.bbox = bbox or {}
        self.raw_response = raw_response or {}


class BaseOCRClient(ABC):
    """OCR 客户端基类"""

    @abstractmethod
    async def recognize(
        self,
        image_bytes: bytes,
        prompt: Optional[str] = None,
    ) -> OCRResult:
        """识别单张图片"""
        pass

    @abstractmethod
    async def batch_recognize(
        self,
        image_bytes_list: List[bytes],
        prompt: Optional[str] = None,
    ) -> List[OCRResult]:
        """批量识别"""
        pass


class BaseLLMClient(ABC):
    """LLM 客户端基类"""

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None,
    ) -> str:
        """对话请求"""
        pass

    @abstractmethod
    async def chat_with_image(
        self,
        image_bytes: bytes,
        text_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """多模态对话（图片+文本）"""
        pass
