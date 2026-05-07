"""文本 Embedding 服务."""

import os
import warnings

import httpx
import numpy as np

from app.core.config import settings
from app.models.question_template import QuestionTemplate


class EmbeddingService:
    """文本 Embedding 服务.

    优先使用 OpenAI Embedding API；无 API Key 时 fallback 到随机向量（仅用于测试）.
    """

    def __init__(self) -> None:
        self.model = settings.EMBEDDING_MODEL
        self.dimension = settings.EMBEDDING_DIMENSION
        self.api_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
        self.base_url = "https://api.openai.com/v1"
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=60.0,
            )
        return self._client

    async def embed_text(self, text: str) -> list[float]:
        """单文本 Embedding.

        Args:
            text: 待嵌入文本

        Returns:
            1536 维浮点向量
        """
        if not self.api_key:
            warnings.warn(
                "OPENAI_API_KEY 未设置，使用随机向量作为 fallback（仅测试用途）",
                stacklevel=2,
            )
            return self._random_vector()

        response = await self.client.post(
            "/embeddings",
            json={"model": self.model, "input": text},
        )
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量文本 Embedding.

        Args:
            texts: 待嵌入文本列表

        Returns:
            向量列表
        """
        if not texts:
            return []

        if not self.api_key:
            warnings.warn(
                "OPENAI_API_KEY 未设置，使用随机向量作为 fallback（仅测试用途）",
                stacklevel=2,
            )
            return [self._random_vector() for _ in texts]

        response = await self.client.post(
            "/embeddings",
            json={"model": self.model, "input": texts},
        )
        response.raise_for_status()
        data = response.json()
        sorted_data = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in sorted_data]

    async def embed_question(self, question: QuestionTemplate) -> list[float]:
        """将题目内容拼接后 Embedding.

        拼接字段：题干 + 选项 + 知识点
        """
        parts: list[str] = [question.content or ""]

        if question.options:
            options_text = " ".join(
                f"{k}:{v}" for k, v in question.options.items()
            )
            parts.append(options_text)

        if question.knowledge_point_ids:
            kp_text = " ".join(str(kp) for kp in question.knowledge_point_ids)
            parts.append(f"知识点: {kp_text}")

        text = " | ".join(parts)
        return await self.embed_text(text)

    def _random_vector(self) -> list[float]:
        """生成归一化的随机测试向量."""
        vec = np.random.randn(self.dimension).astype(np.float32)
        vec /= np.linalg.norm(vec)
        return vec.tolist()

    async def close(self) -> None:
        """关闭 HTTP 客户端."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
