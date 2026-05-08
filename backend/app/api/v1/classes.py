"""
班级管理 API 路由
核心功能：班级 CRUD、学生管理、考试列表、薄弱知识点热力图
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, status
from sqlalchemy.orm import selectinload
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_current_user
from app.core.exceptions import BadRequestException, NotFoundException
from app.models.class_ import Class
from app.models.class_student import ClassStudent
from app.models.knowledge_point import KnowledgePoint
from app.models.student import Student
from app.models.student_knowledge_state import StudentKnowledgeState
from app.models.user import User
from app.repositories.class_ import ClassRepository
from app.repositories.exam import ExamRepository
from app.repositories.knowledge_point import KnowledgePointRepository
from app.repositories.student import StudentRepository
from app.schemas.class_ import ClassCreate, ClassRead
from app.schemas.common import BaseResponse
from app.services.heatmap_service import HeatmapService

router = APIRouter()


def _class_to_dict(class_obj: Class) -> dict:
    return {
        "id": class_obj.id,
        "name": class_obj.name,
        "grade": class_obj.grade,
        "subject_id": class_obj.subject_id,
        "teacher_id": class_obj.teacher_id,
        "academic_year": class_obj.academic_year,
        "semester": class_obj.semester,
        "created_at": class_obj.created_at,
        "updated_at": class_obj.updated_at,
    }


@router.get("", response_model=BaseResponse)
async def list_classes(
    skip: int = 0,
    limit: int = 20,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
) -> BaseResponse:
    """获取班级列表."""
    classes = await ClassRepository(session).get_all(skip=skip, limit=limit)
    return BaseResponse(data=[_class_to_dict(c) for c in classes])


@router.post("", response_model=BaseResponse, status_code=status.HTTP_201_CREATED)
async def create_class(
    name: str = Form(...),
    grade: str = Form(...),
    academic_year: str = Form(...),
    semester: str = Form(...),
    subject_id: int | None = Form(None),
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
) -> BaseResponse:
    """创建班级."""
    class_obj = Class(
        name=name,
        grade=grade,
        academic_year=academic_year,
        semester=semester,
        subject_id=subject_id,
        teacher_id=current_user.id,
    )
    class_obj = await ClassRepository(session).create(class_obj)
    return BaseResponse(data=_class_to_dict(class_obj))


@router.get("/{class_id}", response_model=BaseResponse)
async def get_class(
    class_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
) -> BaseResponse:
    """获取班级详情（含学生列表）."""
    class_obj = await ClassRepository(session).get_by_id(class_id)
    if not class_obj:
        raise NotFoundException("班级不存在")

    stmt = (
        select(Student)
        .options(selectinload(Student.user))
        .where(Student.class_id == class_id)
    )
    result = await session.exec(stmt)
    students = list(result.all())
    student_items = [
        {
            "id": student.id,
            "user_id": student.user_id,
            "student_number": student.student_number,
            "user_name": student.user.real_name if student.user else None,
            "enrollment_year": student.enrollment_year,
        }
        for student in students
    ]

    # 组装符合前端 ClassDetail 的响应
    return BaseResponse(
        data={
            "id": class_obj.id,
            "name": class_obj.name,
            "student_count": len(student_items),
            "exam_count": 0,
            "students": student_items,
            "exams": [],
            "heatmap": [],
        },
    )


@router.post("/{class_id}/students", response_model=BaseResponse)
async def add_students_to_class(
    class_id: int,
    student_ids: list[int],
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
) -> BaseResponse:
    """批量添加学生到班级."""
    class_obj = await ClassRepository(session).get_by_id(class_id)
    if not class_obj:
        raise NotFoundException("班级不存在")

    added = 0
    for sid in student_ids:
        student = await StudentRepository(session).get_by_id(sid)
        if not student:
            continue
        # 更新学生当前班级
        student.class_id = class_id
        session.add(student)
        # 创建关联记录
        existing = await session.exec(
            select(ClassStudent).where(
                ClassStudent.class_id == class_id,
                ClassStudent.student_id == sid,
            )
        )
        if not existing.first():
            session.add(ClassStudent(class_id=class_id, student_id=sid))
        added += 1

    await session.commit()
    return BaseResponse(data={"added": added, "class_id": class_id})


@router.get("/{class_id}/exams", response_model=BaseResponse)
async def get_class_exams(
    class_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
) -> BaseResponse:
    """获取班级考试列表."""
    class_obj = await ClassRepository(session).get_by_id(class_id)
    if not class_obj:
        raise NotFoundException("班级不存在")

    exams = await ExamRepository(session).get_by_class(class_id)
    return BaseResponse(
        data=[
            {
                "id": e.id,
                "title": e.title,
                "subject_id": e.subject_id,
                "exam_type": e.exam_type.value if hasattr(e.exam_type, "value") else str(e.exam_type),
                "status": e.status.value if hasattr(e.status, "value") else str(e.status),
                "exam_date": e.exam_date,
                "created_at": e.created_at,
            }
            for e in exams
        ],
    )


@router.get("/{class_id}/heatmap", response_model=BaseResponse)
async def get_class_heatmap(
    class_id: int,
    subject_id: int | None = None,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
) -> BaseResponse:
    """获取班级薄弱知识点热力图数据（矩阵格式）."""
    class_obj = await ClassRepository(session).get_by_id(class_id)
    if not class_obj:
        raise NotFoundException("班级不存在")

    data = await HeatmapService(session).generate_class_heatmap(class_id, subject_id)
    return BaseResponse(data=data)


@router.get("/{class_id}/heatmap/trend", response_model=BaseResponse)
async def get_class_knowledge_trend(
    class_id: int,
    knowledge_point_id: int,
    months: int = 3,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
) -> BaseResponse:
    """获取单个知识点在班级中的掌握度趋势."""
    class_obj = await ClassRepository(session).get_by_id(class_id)
    if not class_obj:
        raise NotFoundException("班级不存在")

    data = await HeatmapService(session).generate_knowledge_trend(
        class_id, knowledge_point_id, months
    )
    return BaseResponse(data=data)
