from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_current_user
from app.core.exceptions import BadRequestException, NotFoundException
from app.models.exercise import Exercise, ExerciseStatus
from app.repositories.exercise import ExerciseRepository
from app.repositories.exercise_question import ExerciseQuestionRepository
from app.schemas.common import BaseResponse, PaginatedResponse
from app.schemas.exercise import (
    DailyPlanRead,
    ExerciseCreate,
    ExerciseQuestionSubmit,
    ExerciseRead,
    ExerciseResultRead,
)
from app.services.adaptive_push import AdaptivePushService
from app.services.exercise_service import ExerciseService

router = APIRouter(prefix="/exercises", tags=["Exercises"])


def _exercise_to_dict(exercise: Exercise) -> dict[str, Any]:
    """Convert Exercise ORM object to a response dict."""
    return {
        "id": exercise.id,
        "student_id": exercise.student_id,
        "title": exercise.title,
        "target_knowledge_point_ids": exercise.target_knowledge_point_ids or [],
        "target_error_types": exercise.target_error_types or [],
        "difficulty_range": exercise.difficulty_range or {},
        "status": exercise.status.value if hasattr(exercise.status, "value") else str(exercise.status),
        "assigned_at": exercise.assigned_at,
        "due_at": exercise.due_at,
        "completed_at": exercise.completed_at,
        "created_at": exercise.created_at,
        "updated_at": exercise.updated_at,
    }


@router.post("", response_model=BaseResponse, status_code=status.HTTP_201_CREATED)
async def create_exercise(
    data: ExerciseCreate,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
) -> BaseResponse:
    """创建练习卷."""
    service = ExerciseService(session)
    exercise = await service.create_exercise(data)
    return BaseResponse(data=exercise.model_dump())


@router.get("", response_model=BaseResponse)
async def list_exercises(
    student_id: int | None = Query(None),
    status: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
) -> BaseResponse:
    """练习列表."""
    where_clauses = []
    if student_id is not None:
        where_clauses.append(Exercise.student_id == student_id)
    if status is not None:
        where_clauses.append(Exercise.status == status)

    total_stmt = select(func.count(Exercise.id))
    list_stmt = (
        select(Exercise)
        .offset(skip)
        .limit(limit)
        .order_by(Exercise.created_at.desc())
    )
    if where_clauses:
        total_stmt = total_stmt.where(*where_clauses)
        list_stmt = list_stmt.where(*where_clauses)

    total_result = await session.exec(total_stmt)
    total = total_result.one()

    list_result = await session.exec(list_stmt)
    exercises = list(list_result.all())

    total_pages = (total + limit - 1) // limit if limit > 0 else 0
    page = skip // limit + 1 if limit > 0 else 1

    return BaseResponse(
        data=PaginatedResponse(
            items=[_exercise_to_dict(e) for e in exercises],
            total=total,
            page=page,
            page_size=limit,
            total_pages=total_pages,
        ),
    )


@router.get("/{id}", response_model=BaseResponse)
async def get_exercise(
    id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
) -> BaseResponse:
    """练习详情（含题目列表）."""
    exercise = await ExerciseRepository(session).get_by_id(id)
    if not exercise:
        raise NotFoundException("练习卷不存在")

    questions = await ExerciseQuestionRepository(session).get_by_exercise(id)

    return BaseResponse(
        data={
            "exercise": _exercise_to_dict(exercise),
            "questions": [
                {
                    "id": q.id,
                    "sequence_number": q.sequence_number,
                    "content": q.content,
                    "content_latex": q.content_latex,
                    "options": q.options,
                    "max_score": q.max_score,
                    "ai_explanation": q.ai_explanation,
                }
                for q in questions
            ],
        },
    )


@router.post("/{id}/assign", response_model=BaseResponse)
async def assign_exercise(
    id: int,
    student_ids: list[int],
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
) -> BaseResponse:
    """分配练习给学生."""
    service = ExerciseService(session)
    result = await service.assign_exercise(id, student_ids)
    return BaseResponse(data=result)


@router.post("/{id}/submit", response_model=BaseResponse)
async def submit_answer(
    id: int,
    data: ExerciseQuestionSubmit,
    exercise_question_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
) -> BaseResponse:
    """提交作答.

    - exercise_question_id: 练习题目 ID
    - answer: 学生作答内容
    """
    # 验证题目属于该练习
    eq = await ExerciseQuestionRepository(session).get_by_id(exercise_question_id)
    if not eq or eq.exercise_id != id:
        raise BadRequestException("题目不属于该练习卷")

    service = ExerciseService(session)
    result = await service.submit_answer(exercise_question_id, data.answer)
    return BaseResponse(data=result)


@router.get("/{id}/result", response_model=BaseResponse)
async def get_exercise_result(
    id: int,
    student_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
) -> BaseResponse:
    """查看练习结果."""
    service = ExerciseService(session)
    result = await service.get_exercise_result(id, student_id)
    return BaseResponse(data=result)


@router.get("/student/{student_id}/due", response_model=BaseResponse)
async def get_due_exercises(
    student_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
) -> BaseResponse:
    """获取学生到期的练习."""
    exercises = await ExerciseRepository(session).get_due_exercises(student_id)
    return BaseResponse(
        data=[_exercise_to_dict(e) for e in exercises],
    )


@router.post("/student/{student_id}/daily-plan", response_model=BaseResponse)
async def generate_daily_plan(
    student_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
) -> BaseResponse:
    """为学生生成今日练习计划."""
    service = AdaptivePushService(session)
    plan = await service.generate_daily_plan(student_id)
    return BaseResponse(data=plan)
