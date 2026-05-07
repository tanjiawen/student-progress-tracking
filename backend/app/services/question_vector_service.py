"""题目向量入库、检索、同步."""

from app.models.question_template import QuestionTemplate
from app.repositories.question_template import QuestionTemplateRepository
from app.services.embedding_service import EmbeddingService
from app.services.qdrant_service import QdrantService


class QuestionVectorService:
    """题目向量管理：编排 EmbeddingService + QdrantService."""

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        qdrant_service: QdrantService | None = None,
    ) -> None:
        self.embedding = embedding_service or EmbeddingService()
        self.qdrant = qdrant_service or QdrantService()

    async def index_question(
        self,
        question: QuestionTemplate,
        repository: QuestionTemplateRepository | None = None,
    ) -> str:
        """单题入库.

        1. Embedding
        2. Upsert to Qdrant
        3. 更新 question_template.vector_id

        Args:
            question: 题目模板
            repository: 可选的仓库实例，用于更新 vector_id

        Returns:
            vector_id（即 str(question.id)）
        """
        if question.id is None:
            raise ValueError("Question must have an id to be indexed")

        vector = await self.embedding.embed_question(question)

        payload = {
            "question_id": question.id,
            "subject_id": question.subject_id,
            "knowledge_point_ids": question.knowledge_point_ids or [],
            "difficulty": question.difficulty,
            "question_type": question.question_type.value
            if hasattr(question.question_type, "value")
            else question.question_type,
        }

        await self.qdrant.upsert_question(
            question_id=question.id,
            vector=vector,
            payload=payload,
        )

        vector_id = str(question.id)
        question.vector_id = vector_id

        if repository is not None:
            await repository.update(question.id, {"vector_id": vector_id})

        return vector_id

    async def index_batch(
        self,
        questions: list[QuestionTemplate],
        repository: QuestionTemplateRepository | None = None,
    ) -> list[str]:
        """批量入库.

        Args:
            questions: 题目模板列表
            repository: 可选的仓库实例

        Returns:
            vector_id 列表
        """
        if not questions:
            return []

        vectors = await self.embedding.embed_batch(
            [await self._build_text(q) for q in questions]
        )

        points: list[tuple[int, list[float], dict]] = []
        vector_ids: list[str] = []

        for question, vector in zip(questions, vectors, strict=True):
            if question.id is None:
                raise ValueError("All questions must have an id to be indexed")

            payload = {
                "question_id": question.id,
                "subject_id": question.subject_id,
                "knowledge_point_ids": question.knowledge_point_ids or [],
                "difficulty": question.difficulty,
                "question_type": question.question_type.value
                if hasattr(question.question_type, "value")
                else question.question_type,
            }
            points.append((question.id, vector, payload))
            vector_ids.append(str(question.id))

        await self.qdrant.upsert_batch(points)

        if repository is not None:
            for question in questions:
                question.vector_id = str(question.id)
                await repository.update(question.id, {"vector_id": str(question.id)})

        return vector_ids

    async def find_similar_questions(
        self,
        question_id: int,
        limit: int = 5,
    ) -> list[dict]:
        """找相似题.

        1. 从 Qdrant 获取该题向量
        2. 搜索相似向量（排除自己）
        3. 返回 [{question_id, score, payload}, ...]
        """
        record = await self.qdrant.get_by_id(question_id)
        if record is None:
            return []

        vector = record["vector"]
        return await self.qdrant.search_similar(
            vector=vector,
            limit=limit,
            exclude_id=question_id,
        )

    async def find_similar_by_text(
        self,
        text: str,
        limit: int = 5,
        filters: dict | None = None,
    ) -> list[dict]:
        """文本搜索：先 Embedding，再向量检索.

        Args:
            text: 查询文本
            limit: 返回数量
            filters: 过滤条件

        Returns:
            相似题目列表
        """
        vector = await self.embedding.embed_text(text)
        return await self.qdrant.search_similar(
            vector=vector,
            limit=limit,
            filters=filters,
        )

    async def search_by_knowledge_point(
        self,
        kp_id: int,
        limit: int = 10,
    ) -> list[dict]:
        """按知识点过滤搜索.

        由于需要向量才能搜索，这里构造一个零向量并应用过滤条件，
        或者更合理的做法是利用 Qdrant 的 scroll API。
        这里使用 scroll 获取该知识点下的题目。
        """
        return await self.qdrant.search_similar(
            vector=[0.0] * self.qdrant.vector_size,
            limit=limit,
            filters={"knowledge_point_ids": [kp_id]},
        )

    async def _build_text(self, question: QuestionTemplate) -> str:
        """构建用于 Embedding 的文本（供 batch 使用）."""
        parts: list[str] = [question.content or ""]

        if question.options:
            options_text = " ".join(
                f"{k}:{v}" for k, v in question.options.items()
            )
            parts.append(options_text)

        if question.knowledge_point_ids:
            kp_text = " ".join(str(kp) for kp in question.knowledge_point_ids)
            parts.append(f"知识点: {kp_text}")

        return " | ".join(parts)

    async def delete_index(self, question_id: int) -> None:
        """删除题目的向量索引."""
        await self.qdrant.delete_question(question_id)
