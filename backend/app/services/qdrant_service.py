"""Qdrant 向量库操作封装."""

import asyncio
import warnings

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    PointIdsList,
    PointStruct,
    VectorParams,
)

from app.core.config import settings


class QdrantService:
    """Qdrant 向量库操作封装."""

    def __init__(self) -> None:
        self.client = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
        )
        self.collection_name = "questions"
        self.vector_size = settings.EMBEDDING_DIMENSION

    async def ensure_collection(self) -> None:
        """创建 collection（如果不存在）."""
        try:
            collections = await asyncio.to_thread(
                self.client.get_collections,
            )
            existing = {c.name for c in collections.collections}

            if self.collection_name in existing:
                # 校验 vector_size 是否一致
                info = await asyncio.to_thread(
                    self.client.get_collection,
                    collection_name=self.collection_name,
                )
                config = info.config.params.vectors
                if hasattr(config, "size") and config.size != self.vector_size:
                    warnings.warn(
                        f"Collection '{self.collection_name}' 存在但 vector_size "
                        f"({config.size}) 与当前配置 ({self.vector_size}) 不一致",
                        stacklevel=2,
                    )
                return

            await asyncio.to_thread(
                self.client.create_collection,
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE,
                ),
            )
        except Exception as e:
            raise ConnectionError(
                f"Qdrant 连接或创建 collection 失败: {e}\n"
                f"请检查 QDRANT_URL ({settings.QDRANT_URL}) 是否正确，"
                f"以及 Qdrant 服务是否已启动。"
            ) from e

    async def upsert_question(
        self,
        question_id: int,
        vector: list[float],
        payload: dict,
    ) -> None:
        """插入/更新向量.

        Args:
            question_id: 题目 ID，同时作为 point id
            vector: 嵌入向量
            payload: 附加元数据
        """
        point = PointStruct(
            id=question_id,
            vector=vector,
            payload=payload,
        )
        await asyncio.to_thread(
            self.client.upsert,
            collection_name=self.collection_name,
            points=[point],
            wait=True,
        )

    async def upsert_batch(
        self,
        points: list[tuple[int, list[float], dict]],
    ) -> None:
        """批量插入/更新向量.

        Args:
            points: [(question_id, vector, payload), ...]
        """
        if not points:
            return

        batch = [
            PointStruct(id=qid, vector=vec, payload=pld)
            for qid, vec, pld in points
        ]
        await asyncio.to_thread(
            self.client.upsert,
            collection_name=self.collection_name,
            points=batch,
            wait=True,
        )

    async def search_similar(
        self,
        vector: list[float],
        limit: int = 5,
        filters: dict | None = None,
        exclude_id: int | None = None,
    ) -> list[dict]:
        """相似度搜索.

        Args:
            vector: 查询向量
            limit: 返回数量上限
            filters: 额外过滤条件（如 knowledge_point_ids）
            exclude_id: 排除指定 question_id

        Returns:
            [{question_id, score, payload}, ...]
        """
        qdrant_filter = self._build_filter(filters, exclude_id)

        results = await asyncio.to_thread(
            self.client.search,
            collection_name=self.collection_name,
            query_vector=vector,
            limit=limit,
            query_filter=qdrant_filter,
            with_payload=True,
        )

        return [
            {
                "question_id": res.id,
                "score": res.score,
                "payload": res.payload,
            }
            for res in results
        ]

    async def delete_question(self, question_id: int) -> None:
        """删除向量."""
        await asyncio.to_thread(
            self.client.delete,
            collection_name=self.collection_name,
            points_selector=PointIdsList(points=[question_id]),
            wait=True,
        )

    async def get_by_id(self, question_id: int) -> dict | None:
        """获取向量及 payload.

        Returns:
            {"question_id": ..., "vector": ..., "payload": ...} 或 None
        """
        try:
            results = await asyncio.to_thread(
                self.client.retrieve,
                collection_name=self.collection_name,
                ids=[question_id],
                with_vectors=True,
                with_payload=True,
            )
        except UnexpectedResponse as e:
            if e.status_code == 404:
                return None
            raise

        if not results:
            return None

        point = results[0]
        return {
            "question_id": point.id,
            "vector": point.vector,
            "payload": point.payload,
        }

    async def count(self) -> int:
        """获取 collection 中向量总数."""
        result = await asyncio.to_thread(
            self.client.count,
            collection_name=self.collection_name,
        )
        return result.count

    async def scroll(
        self,
        filters: dict | None = None,
        limit: int = 10,
        offset: int | str | None = None,
    ) -> tuple[list[dict], int | str | None]:
        """纯过滤检索（无需向量）.

        Args:
            filters: 过滤条件
            limit: 返回数量上限
            offset: 分页偏移

        Returns:
            (结果列表, 下一页 offset)
        """
        qdrant_filter = self._build_filter(filters, exclude_id=None)

        results, next_offset = await asyncio.to_thread(
            self.client.scroll,
            collection_name=self.collection_name,
            scroll_filter=qdrant_filter,
            limit=limit,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        return (
            [
                {
                    "question_id": res.id,
                    "payload": res.payload,
                }
                for res in results
            ],
            next_offset,
        )

    def _build_filter(
        self,
        filters: dict | None,
        exclude_id: int | None,
    ) -> Filter | None:
        """构建 Qdrant Filter."""
        must_conditions = []

        if exclude_id is not None:
            must_conditions.append(
                FieldCondition(
                    key="id",
                    match=MatchAny(except_=[exclude_id]),
                )
            )

        if not filters:
            return Filter(must=must_conditions) if must_conditions else None

        if "knowledge_point_ids" in filters:
            kp_ids = filters["knowledge_point_ids"]
            if isinstance(kp_ids, int):
                kp_ids = [kp_ids]
            must_conditions.append(
                FieldCondition(
                    key="knowledge_point_ids",
                    match=MatchAny(any=kp_ids),
                )
            )

        if "subject_id" in filters:
            must_conditions.append(
                FieldCondition(
                    key="subject_id",
                    match=MatchAny(any=[filters["subject_id"]]),
                )
            )

        if "difficulty" in filters:
            must_conditions.append(
                FieldCondition(
                    key="difficulty",
                    match=MatchAny(any=[filters["difficulty"]]),
                )
            )

        if "question_type" in filters:
            must_conditions.append(
                FieldCondition(
                    key="question_type",
                    match=MatchAny(any=[filters["question_type"]]),
                )
            )

        return Filter(must=must_conditions) if must_conditions else None
