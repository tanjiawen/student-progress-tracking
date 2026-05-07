"""
学生学情 API 路由
核心功能：知识状态查询、薄弱点分析、雷达图、趋势
"""

from typing import Any, Optional

from fastapi import APIRouter, Query

from app.core.exceptions import BadRequestException
from app.services.knowledge_tracker import knowledge_tracker

router = APIRouter()


@router.get("/{student_id}/knowledge-states")
async def get_knowledge_states(
    student_id: int,
    subject_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Any:
    """获取学生知识点掌握状态列表"""
    from app.services.knowledge_tracker import knowledge_tracker

    # 获取所有状态
    all_states = [
        state for key, state in knowledge_tracker._states.items()
        if key[0] == student_id
    ]

    # 过滤
    if status:
        all_states = [s for s in all_states if s.get_status() == status]

    # 排序（按掌握度从低到高）
    all_states.sort(key=lambda s: s.get_decayed_mastery())

    # 分页
    total = len(all_states)
    start = (page - 1) * page_size
    end = start + page_size
    page_states = all_states[start:end]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [s.to_dict() for s in page_states],
    }


@router.get("/{student_id}/weak-points")
async def get_weak_points(
    student_id: int,
    top_k: int = Query(5, ge=1, le=20),
) -> Any:
    """获取学生薄弱知识点 TOP K"""
    weak_points = knowledge_tracker.get_weak_points(
        student_id=student_id,
        top_k=top_k,
    )
    return {
        "student_id": student_id,
        "total": len(weak_points),
        "items": weak_points,
    }


@router.get("/{student_id}/knowledge-radar")
async def get_knowledge_radar(
    student_id: int,
) -> Any:
    """获取学生知识点雷达图数据"""
    # 示例维度（实际应从数据库加载）
    dimension_kps = {
        "函数与方程": [1, 2, 3, 4, 5],
        "几何": [6, 7, 8, 9, 10],
        "概率统计": [11, 12, 13],
        "数列": [14, 15, 16],
        "三角函数": [17, 18, 19],
    }

    radar_data = knowledge_tracker.get_radar_data(
        student_id=student_id,
        dimension_kps=dimension_kps,
    )

    return {
        "student_id": student_id,
        "dimensions": radar_data,
    }


@router.get("/{student_id}/mastery-trend")
async def get_mastery_trend(
    student_id: int,
    knowledge_point_id: int,
) -> Any:
    """获取某知识点的掌握度变化趋势"""
    # 示例历史数据（实际应从数据库加载）
    history = [
        {"date": "2026-03-01", "is_correct": False},
        {"date": "2026-03-15", "is_correct": True},
        {"date": "2026-04-01", "is_correct": False},
        {"date": "2026-04-15", "is_correct": True},
        {"date": "2026-05-01", "is_correct": True},
    ]

    trend = knowledge_tracker.get_mastery_trend(
        student_id=student_id,
        knowledge_point_id=knowledge_point_id,
        history=history,
    )

    return {
        "student_id": student_id,
        "knowledge_point_id": knowledge_point_id,
        "trend": trend,
    }
