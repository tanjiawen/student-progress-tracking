"""
知识点管理 API 路由
核心功能：学科列表、知识点树、详情、路径、前置知识点
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_current_user
from app.core.exceptions import NotFoundException
from app.repositories.knowledge_point import KnowledgePointRepository
from app.repositories.knowledge_relation import KnowledgeRelationRepository
from app.repositories.subject import SubjectRepository
from app.schemas.common import BaseResponse
from app.schemas.knowledge import KnowledgePointPathItem, PrerequisiteItem, SubjectRead

router = APIRouter()


@router.get("/subjects", response_model=BaseResponse)
async def list_subjects(
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
) -> BaseResponse:
    """获取学科列表."""
    subjects = await SubjectRepository(session).get_all()
    return BaseResponse(
        data=[
            {
                "id": s.id,
                "name": s.name,
                "code": s.code,
                "description": s.description,
                "grade_levels": s.grade_levels,
                "sort_order": s.sort_order,
                "created_at": s.created_at,
            }
            for s in subjects
        ],
    )


@router.get("/subjects/{subject_id}/tree", response_model=BaseResponse)
async def get_knowledge_tree(
    subject_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
) -> BaseResponse:
    """获取学科知识点树."""
    kps = await KnowledgePointRepository(session).get_tree_by_subject(subject_id)

    id_to_node: dict[int, dict] = {}
    roots: list[dict] = []

    for kp in kps:
        node = {
            "id": kp.id,
            "subject_id": kp.subject_id,
            "parent_id": kp.parent_id,
            "code": kp.code,
            "name": kp.name,
            "description": kp.description,
            "level": kp.level,
            "sort_order": kp.sort_order,
            "is_leaf": kp.is_leaf,
            "children": [],
        }
        id_to_node[kp.id] = node

    for kp in kps:
        node = id_to_node[kp.id]
        if kp.parent_id and kp.parent_id in id_to_node:
            id_to_node[kp.parent_id]["children"].append(node)
        else:
            roots.append(node)

    return BaseResponse(data=roots)


@router.get("/points/{point_id}", response_model=BaseResponse)
async def get_knowledge_point(
    point_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
) -> BaseResponse:
    """获取知识点详情."""
    kp = await KnowledgePointRepository(session).get_by_id(point_id)
    if not kp:
        raise NotFoundException("知识点不存在")

    return BaseResponse(
        data={
            "id": kp.id,
            "subject_id": kp.subject_id,
            "parent_id": kp.parent_id,
            "code": kp.code,
            "name": kp.name,
            "description": kp.description,
            "level": kp.level,
            "sort_order": kp.sort_order,
            "is_leaf": kp.is_leaf,
            "created_at": kp.created_at,
            "updated_at": kp.updated_at,
        },
    )


@router.get("/points/{point_id}/path", response_model=BaseResponse)
async def get_knowledge_path(
    point_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
) -> BaseResponse:
    """获取知识点到根节点的完整路径."""
    path = await KnowledgePointRepository(session).get_path_to_root(point_id)
    if not path:
        raise NotFoundException("知识点不存在")

    items = [
        KnowledgePointPathItem(
            id=p.id,
            name=p.name,
            code=p.code,
            level=p.level,
        )
        for p in reversed(path)
    ]
    return BaseResponse(data=[item.model_dump() for item in items])


@router.get("/points/{point_id}/prerequisites", response_model=BaseResponse)
async def get_prerequisites(
    point_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
) -> BaseResponse:
    """获取知识点的所有前置知识点（递归）."""
    kp = await KnowledgePointRepository(session).get_by_id(point_id)
    if not kp:
        raise NotFoundException("知识点不存在")

    prereq_ids = await KnowledgeRelationRepository(session).get_prerequisites(point_id)
    items = []
    for pid in prereq_ids:
        p = await KnowledgePointRepository(session).get_by_id(pid)
        if p:
            items.append(
                PrerequisiteItem(
                    id=p.id,
                    name=p.name,
                    code=p.code,
                ).model_dump()
            )

    return BaseResponse(data=items)
