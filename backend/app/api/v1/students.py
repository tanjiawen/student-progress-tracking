"""
学生学情 API 路由
核心功能：学生列表、知识状态查询、诊断报告、错题本、在线作答提交
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_current_user
from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.schemas.user import UserRead
from app.core.data_masking import DataMasker
from app.models.class_ import Class
from app.models.exam import Exam
from app.models.exam_question import ExamQuestion
from app.models.knowledge_point import KnowledgePoint
from app.models.student import Student
from app.models.student_knowledge_state import StudentKnowledgeState
from app.models.submission import GradingStatus, Submission
from app.models.subject import Subject
from app.models.user import User
from app.repositories.error_book_item import ErrorBookItemRepository
from app.repositories.exam import ExamRepository
from app.repositories.grading_result import GradingResultRepository
from app.repositories.knowledge_point import KnowledgePointRepository
from app.repositories.report import ReportRepository
from app.repositories.student import StudentRepository
from app.repositories.student_knowledge_state import StudentKnowledgeStateRepository
from app.repositories.subject import SubjectRepository
from app.repositories.submission import SubmissionRepository
from app.schemas.common import BaseResponse
from app.schemas.student import StudentDetail, StudentKnowledgeStateGrouped
from app.models.error_book_item import ErrorBookItem
from app.models.student_knowledge_state import StudentKnowledgeState, MasteryStatus
from app.models.knowledge_point import KnowledgePoint

router = APIRouter()


async def _check_student_access(
    student_id: int,
    current_user: dict,
    session: AsyncSession,
) -> Student:
    """Security fix V-012: resource-level authorization check.

    - admin: can access any student
    - teacher: can access students in classes they teach
    - student/parent: can only access their own student record
    """
    student = await StudentRepository(session).get_by_id(student_id)
    if not student:
        raise NotFoundException("学生不存在")

    role = current_user.role
    user_id = current_user.id

    if role == "admin":
        return student

    # For students: only allow access to their own record
    if role == "student":
        if student.user_id != user_id:
            raise ForbiddenException("无权访问其他学生的数据")
        return student

    # For teachers: check if student is in a class taught by this teacher
    if role == "teacher":
        # Query if this teacher teaches the class this student belongs to
        if student.class_id:
            class_obj = await session.get(Class, student.class_id)
            if class_obj and class_obj.teacher_id == user_id:
                return student
        # Also allow if the teacher is accessing their own profile (if they have one)
        if student.user_id == user_id:
            return student
        raise ForbiddenException("无权访问该学生数据")

    # For parents: only allow access to their own children
    if role == "parent":
        # TODO: implement parent-child relationship check
        if student.user_id != user_id:
            raise ForbiddenException("无权访问其他学生的数据")
        return student

    raise ForbiddenException("无权访问学生数据")


def _student_to_dict(student: Student, user: User | None = None, class_name: str | None = None) -> dict:
    return {
        "id": student.id,
        "user_id": student.user_id,
        "name": user.real_name if user else None,
        "student_no": student.student_number,
        "student_number": student.student_number,
        "class_id": student.class_id,
        "class_name": class_name,
        "enrollment_year": student.enrollment_year,
        "user_name": user.real_name if user else None,
        "created_at": student.created_at,
        "updated_at": student.updated_at,
    }


@router.get("", response_model=BaseResponse)
async def list_students(
    class_id: int | None = None,
    name: str | None = None,
    skip: int = 0,
    limit: int = 20,
    session: AsyncSession = Depends(get_session),
    current_user: UserRead = Depends(get_current_user),
) -> BaseResponse:
    """获取学生列表，支持按班级和姓名筛选（返回数据已脱敏）."""
    # Security fix V-019: filter by name in SQL before pagination
    from sqlalchemy import func

    stmt = (
        select(Student)
        .options(selectinload(Student.user), selectinload(Student.class_))
    )
    if class_id is not None:
        stmt = stmt.where(Student.class_id == class_id)
    # Fix V-019: use database-level case-insensitive name filtering
    if name:
        stmt = stmt.join(User, Student.user_id == User.id).where(
            func.lower(User.real_name).like(f"%{name.lower()}%")
        )
    stmt = stmt.offset(skip).limit(limit)
    result = await session.exec(stmt)
    students = list(result.all())

    items = [
        _student_to_dict(
            student,
            user=student.user,
            class_name=student.class_.name if student.class_ else None,
        )
        for student in students
    ]

    # 对学生姓名进行脱敏
    masked_items = DataMasker.mask_student_name_in_response(items)
    return BaseResponse(data=masked_items)


@router.get("/{student_id}", response_model=BaseResponse)
async def get_student(
    student_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserRead = Depends(get_current_user),
) -> BaseResponse:
    """获取学生详情（基本信息 + 班级 + 最近考试），姓名已脱敏."""
    student = await _check_student_access(student_id, current_user, session)

    user = await session.get(User, student.user_id)
    class_obj = await session.get(Class, student.class_id) if student.class_id else None

    # 最近考试：取最近 5 次提交关联的考试
    submissions = await SubmissionRepository(session).get_by_student(student_id)
    seen_exam_ids: set[int] = set()
    recent_exams: list[dict] = []
    for sub in sorted(submissions, key=lambda s: s.submitted_at or s.created_at, reverse=True):
        if sub.exam_id and sub.exam_id not in seen_exam_ids:
            seen_exam_ids.add(sub.exam_id)
            exam = await ExamRepository(session).get_by_id(sub.exam_id)
            if exam:
                recent_exams.append(
                    {
                        "exam_id": exam.id,
                        "title": exam.title,
                        "exam_date": exam.exam_date,
                        "status": exam.status.value if hasattr(exam.status, "value") else str(exam.status),
                    }
                )
            if len(recent_exams) >= 5:
                break

    detail = StudentDetail(
        **_student_to_dict(student, user=user, class_name=class_obj.name if class_obj else None),
        recent_exams=recent_exams,
    )
    return BaseResponse(data=DataMasker.mask_student_name_in_response(detail.model_dump()))


@router.get("/{student_id}/knowledge-state", response_model=BaseResponse)
async def get_knowledge_state(
    student_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserRead = Depends(get_current_user),
) -> BaseResponse:
    """获取学生知识状态，按学科分组返回掌握度列表."""
    student = await _check_student_access(student_id, current_user, session)

    states = await StudentKnowledgeStateRepository(session).get_by_student(student_id)

    # 按学科分组
    subject_groups: dict[int, dict] = {}
    for state in states:
        kp = await KnowledgePointRepository(session).get_by_id(state.knowledge_point_id)
        if not kp:
            continue
        subject = await SubjectRepository(session).get_by_id(kp.subject_id)
        subject_id = kp.subject_id
        subject_name = subject.name if subject else "未知学科"

        if subject_id not in subject_groups:
            subject_groups[subject_id] = {
                "subject_id": subject_id,
                "subject_name": subject_name,
                "items": [],
            }

        subject_groups[subject_id]["items"].append(
            {
                "knowledge_point_id": state.knowledge_point_id,
                "knowledge_point_name": kp.name,
                "mastery_probability": float(state.mastery_probability),
                "status": state.status.value if hasattr(state.status, "value") else str(state.status),
                "total_attempts": state.total_attempts,
                "correct_count": state.correct_count,
            }
        )

    return BaseResponse(data=list(subject_groups.values()))


@router.get("/{student_id}/reports", response_model=BaseResponse)
async def get_student_reports(
    student_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserRead = Depends(get_current_user),
) -> BaseResponse:
    """获取学生诊断报告列表."""
    student = await _check_student_access(student_id, current_user, session)

    reports = await ReportRepository(session).get_by_student(student_id)
    return BaseResponse(
        data=[
            {
                "id": r.id,
                "exam_id": r.exam_id,
                "report_type": r.report_type.value if hasattr(r.report_type, "value") else str(r.report_type),
                "title": r.title,
                "overall_comment": r.overall_comment,
                "total_score": float(r.total_score) if r.total_score is not None else None,
                "max_score": float(r.max_score) if r.max_score is not None else None,
                "rank": r.rank,
                "weak_points": r.weak_points,
                "recommendations": r.recommendations,
                "generated_by": r.generated_by.value if hasattr(r.generated_by, "value") else str(r.generated_by),
                "created_at": r.created_at,
            }
            for r in reports
        ],
    )


@router.get("/{student_id}/error-book", response_model=BaseResponse)
async def get_error_book(
    student_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserRead = Depends(get_current_user),
) -> BaseResponse:
    """获取学生错题本."""
    student = await _check_student_access(student_id, current_user, session)

    items = await ErrorBookItemRepository(session).get_by_student(student_id)
    return BaseResponse(
        data=[
            {
                "id": item.id,
                "exam_id": item.exam_id,
                "exam_question_id": item.exam_question_id,
                "question_template_id": item.question_template_id,
                "error_type": item.error_type,
                "error_count": item.error_count,
                "is_resolved": item.is_resolved,
                "last_error_at": item.last_error_at,
                "next_review_at": item.next_review_at,
                "notes": item.notes,
            }
            for item in items
        ],
    )


@router.post("/{student_id}/submit", response_model=BaseResponse, status_code=status.HTTP_201_CREATED)
async def submit_answer(
    student_id: int,
    exam_id: int,
    exam_question_id: int,
    answer_text: str = "",
    answer_image_urls: list[str] | None = None,
    session: AsyncSession = Depends(get_session),
    current_user: UserRead = Depends(get_current_user),
) -> BaseResponse:
    """提交作答（用于在线练习），创建 Submission 并触发判卷任务."""
    student = await _check_student_access(student_id, current_user, session)

    exam = await ExamRepository(session).get_by_id(exam_id)
    if not exam:
        raise NotFoundException("考试不存在")

    exam_question = await session.get(ExamQuestion, exam_question_id)
    if not exam_question:
        raise NotFoundException("题目不存在")

    submission = Submission(
        exam_id=exam_id,
        student_id=student_id,
        exam_question_id=exam_question_id,
        answer_text=answer_text,
        answer_image_urls=answer_image_urls or [],
        grading_status=GradingStatus.PENDING,
    )
    submission = await SubmissionRepository(session).create(submission)

    from app.tasks.grading import grade_submission

    task = grade_submission.delay(submission.id)
    return BaseResponse(
        data={"submission_id": submission.id, "task_id": task.id},
        message="提交成功，判卷任务已触发",
    )


@router.get("/{student_id}/error-book/export")
async def export_error_book_pdf(
    student_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserRead = Depends(get_current_user),
) -> Response:
    """导出错题本 PDF."""
    student = await _check_student_access(student_id, current_user, session)

    items = await ErrorBookItemRepository(session).get_by_student(student_id)
    pdf_bytes = await PDFExporter().export_error_book(student_id, items)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=error_book_{student_id}.pdf"
        },
    )


@router.get("/{student_id}/reports/export/{report_id}")
async def export_report_pdf(
    student_id: int,
    report_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserRead = Depends(get_current_user),
) -> Response:
    """导出诊断报告 PDF."""
    student = await _check_student_access(student_id, current_user, session)

    report = await ReportRepository(session).get_by_id(report_id)
    if not report or report.student_id != student_id:
        raise NotFoundException("报告不存在")

    pdf_bytes = await PDFExporter().export_report(report)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=report_{report_id}.pdf"
        },
    )


@router.get("/{student_id}/review-due", response_model=BaseResponse)
async def get_due_reviews(
    student_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserRead = Depends(get_current_user),
) -> BaseResponse:
    """获取今天需要复习的错题列表."""
    student = await _check_student_access(student_id, current_user, session)

    now = datetime.now(timezone.utc)
    stmt = (
        select(ErrorBookItem)
        .where(
            ErrorBookItem.student_id == student_id,
            ErrorBookItem.is_resolved.is_(False),
            ErrorBookItem.next_review_at.isnot(None),
            ErrorBookItem.next_review_at <= now,
        )
        .order_by(ErrorBookItem.next_review_at)
    )
    result = await session.exec(stmt)
    items = list(result.all())

    return BaseResponse(
        data=[
            {
                "id": item.id,
                "error_type": item.error_type,
                "error_count": item.error_count,
                "next_review_at": item.next_review_at.isoformat() if item.next_review_at else None,
                "review_count": item.review_count,
            }
            for item in items
        ],
    )


@router.post("/{student_id}/review/{error_book_item_id}")
async def submit_review(
    student_id: int,
    error_book_item_id: int,
    quality: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserRead = Depends(get_current_user),
) -> BaseResponse:
    """提交复习结果，更新 SM-2 参数，安排下次复习."""
    student = await _check_student_access(student_id, current_user, session)

    item = await ErrorBookItemRepository(session).get_by_id(error_book_item_id)
    if not item or item.student_id != student_id:
        raise NotFoundException("错题记录不存在")

    if quality < 0 or quality > 5:
        raise BadRequestException("答题质量 quality 必须在 0-5 之间")

    service = AdaptivePushService(session)
    next_review = await service.schedule_next_review(student_id, error_book_item_id, quality)

    return BaseResponse(
        data={
            "error_book_item_id": error_book_item_id,
            "quality": quality,
            "next_review_at": next_review,
            "is_resolved": item.is_resolved,
        }
    )


@router.get("/{student_id}/exams", response_model=BaseResponse)
async def get_student_exams(
    student_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserRead = Depends(get_current_user),
) -> BaseResponse:
    """获取学生的考试记录（基于 submissions + grading_results）."""
    from app.models.submission import Submission
    from app.models.exam import Exam
    from app.models.grading_result import GradingResult

    stmt = (
        select(Submission, Exam, GradingResult)
        .join(Exam, Submission.exam_id == Exam.id)
        .outerjoin(GradingResult, GradingResult.submission_id == Submission.id)
        .where(Submission.student_id == student_id)
        .order_by(Submission.created_at.desc())
    )
    result = await session.exec(stmt)
    rows = list(result.all())

    records = []
    for submission, exam, grading in rows:
        records.append({
            "id": submission.id,
            "exam_name": exam.title if exam else "未知考试",
            "score": float(grading.score) if grading else 0,
            "max_score": float(grading.max_score) if grading else 100,
            "date": submission.created_at.isoformat() if submission.created_at else None,
            "rank": None,
        })
    return BaseResponse(data=records)


@router.get("/{student_id}/weak-knowledges", response_model=BaseResponse)
async def get_weak_knowledges(
    student_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserRead = Depends(get_current_user),
) -> BaseResponse:
    """获取学生薄弱知识点 TOP 列表."""
    stmt = (
        select(StudentKnowledgeState, KnowledgePoint)
        .join(KnowledgePoint, StudentKnowledgeState.knowledge_point_id == KnowledgePoint.id)
        .where(
            StudentKnowledgeState.student_id == student_id,
            StudentKnowledgeState.status == MasteryStatus.weak,
        )
        .order_by(StudentKnowledgeState.mastery_probability.asc())
        .limit(20)
    )
    result = await session.exec(stmt)
    rows = list(result.all())

    items = []
    for ks, kp in rows:
        mastery = int(ks.mastery_probability * 100)
        level: str = "excellent" if mastery >= 85 else "good" if mastery >= 70 else "medium" if mastery >= 50 else "weak"
        items.append({
            "knowledge": kp.name,
            "mastery": mastery,
            "level": level,
            "error_count": ks.total_attempts - ks.correct_count,
        })
    return BaseResponse(data=items)


@router.patch("/{student_id}/error-book/{error_id}/mastered", response_model=BaseResponse)
async def mark_error_mastered(
    student_id: int,
    error_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserRead = Depends(get_current_user),
) -> BaseResponse:
    """标记错题已掌握."""
    item = await ErrorBookItemRepository(session).get_by_id(error_id)
    if not item or item.student_id != student_id:
        raise NotFoundException("错题记录不存在")

    item.is_resolved = True
    item.resolved_at = datetime.now(timezone.utc)
    session.add(item)
    await session.commit()
    await session.refresh(item)

    return BaseResponse(data={"id": item.id, "is_resolved": item.is_resolved})
