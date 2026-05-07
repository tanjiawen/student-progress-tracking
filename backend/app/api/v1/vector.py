"""向量检索 API 路由."""

from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.dependencies import get_session
from app.core.exceptions import BadRequestException, NotFoundException
from app.repositories.question_template import QuestionTemplateRepository
from app.services.question_vector_service import QuestionVectorService

router = APIRouter(prefix="/vector", tags=["Vector Search"])


@router.post("/search")
async def vector_search(query: str, limit: int = 5) -> Any:
    """文本 → Embedding → Qdrant 搜索."""
    try:
        service = QuestionVectorService()
        results = await service.find_similar_by_text(text=query, limit=limit)
        return {"query": query, "results": results}
    except Exception as e:
        raise BadRequestException(f"向量搜索失败: {str(e)}") from e


@router.get("/questions/{question_id}/similar")
async def get_similar_questions(question_id: int, limit: int = 5) -> Any:
    """找相似题."""
    try:
        service = QuestionVectorService()
        results = await service.find_similar_questions(
            question_id=question_id,
            limit=limit,
        )
        return {"question_id": question_id, "results": results}
    except Exception as e:
        raise BadRequestException(f"相似题搜索失败: {str(e)}") from e


@router.post("/questions/{question_id}/index")
async def index_question(
    question_id: int,
    session: AsyncSession = Depends(get_session),
) -> Any:
    """手动触发单题入库."""
    repo = QuestionTemplateRepository(session)
    question = await repo.get_by_id(question_id)
    if not question:
        raise NotFoundException(f"题目 {question_id} 不存在")

    try:
        service = QuestionVectorService()
        vector_id = await service.index_question(question, repository=repo)
        return {
            "question_id": question_id,
            "vector_id": vector_id,
            "message": "索引成功",
        }
    except Exception as e:
        raise BadRequestException(f"题目索引失败: {str(e)}") from e


@router.post("/reindex-all")
async def reindex_all_questions(
    session: AsyncSession = Depends(get_session),
) -> Any:
    """全量重建索引."""
    repo = QuestionTemplateRepository(session)
    service = QuestionVectorService()

    try:
        # 获取所有题目（分批处理避免内存爆炸）
        batch_size = 100
        total_indexed = 0
        skip = 0

        while True:
            questions = await repo.get_all(skip=skip, limit=batch_size)
            if not questions:
                break

            await service.index_batch(questions, repository=repo)
            total_indexed += len(questions)
            skip += batch_size

        return {
            "total_indexed": total_indexed,
            "message": "全量重建索引完成",
        }
    except Exception as e:
        raise BadRequestException(f"全量重建索引失败: {str(e)}") from e
