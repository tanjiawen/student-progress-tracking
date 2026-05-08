"""
考试/试卷 API 路由
核心功能：上传、OCR、题目解析、判卷、结果统计
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from sqlalchemy.orm import selectinload
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.dependencies import get_current_user
from app.core.exceptions import BadRequestException, NotFoundException
from app.core.rate_limiter import rate_limit_dependency
from app.models.exam import Exam, ExamStatus, ExamType
from app.models.exam_question import ExamQuestion
from app.models.grading_result import GradingResult
from app.models.student import Student
from app.models.submission import Submission
from app.models.subject import Subject
from app.models.user import User
from app.repositories.exam import ExamRepository
from app.repositories.exam_question import ExamQuestionRepository
from app.repositories.grading_result import GradingResultRepository
from app.repositories.student import StudentRepository
from app.repositories.submission import SubmissionRepository
from app.repositories.subject import SubjectRepository
from app.schemas.common import BaseResponse, PaginatedResponse
from app.schemas.exam import ExamRead
from app.services.pdf_exporter import PDFExporter
from app.services.pdf_service import pdf_service
from app.services.storage_service import storage_service
from app.services.watermark_service import watermark_service

router = APIRouter()


def _exam_to_dict(exam: Exam, subject_name: str | None = None) -> dict:
    """Convert Exam ORM object to a response dict compatible with ExamRead."""
    return {
        "id": exam.id,
        "title": exam.title,
        "description": None,
        "subject": subject_name or "",
        "grade_level": None,
        "total_score": float(exam.total_score) if exam.total_score is not None else 100.0,
        "duration_minutes": None,
        "exam_date": exam.exam_date,
        "status": exam.status.value if hasattr(exam.status, "value") else str(exam.status),
        "created_by": exam.created_by,
        "created_at": exam.created_at,
        "updated_at": exam.updated_at,
    }


@router.post("/upload", response_model=BaseResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(rate_limit_dependency)])
async def upload_exam(
    file: UploadFile = File(...),
    title: str = Form(""),
    subject: str = Form(""),
    class_id: int = Form(...),
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
) -> BaseResponse:
    """上传考试试卷（PDF 或图片）并创建考试记录.

    - file: PDF 或图片文件（最大 20MB，仅限 PDF/PNG/JPG）
    - title: 考试名称
    - subject: 学科名称
    - class_id: 班级 ID
    """
    if not file.filename:
        raise BadRequestException("未提供文件")

    contents = await file.read()
    if len(contents) == 0:
        raise BadRequestException("文件为空")

    # 文件大小限制（最大 20MB）
    max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(contents) > max_size:
        raise BadRequestException(f"文件大小超过限制（最大 {settings.MAX_UPLOAD_SIZE_MB}MB）")

    # 严格的文件类型检查：仅允许 PDF/PNG/JPG
    allowed_exts = {".pdf", ".png", ".jpg", ".jpeg"}
    ext = f".{file.filename.split('.')[-1].lower()}" if "." in file.filename else ""
    if ext not in allowed_exts:
        raise BadRequestException("仅支持 PDF、PNG、JPG 格式")

    content_type = file.content_type or ""
    allowed_content_types = {
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/jpg",
    }
    is_pdf = content_type == "application/pdf" or file.filename.lower().endswith(".pdf")
    is_image = content_type in {"image/png", "image/jpeg", "image/jpg"} or ext in {".png", ".jpg", ".jpeg"}

    # Reject known-bypass content types (e.g. image/svg+xml)
    if content_type and content_type not in allowed_content_types:
        raise BadRequestException("仅支持 PDF 或图片格式（jpg/png）")
    if not is_pdf and not is_image:
        raise BadRequestException("仅支持 PDF 或图片格式（jpg/png）")

    # 查找或确认学科
    subject_repo = SubjectRepository(session)
    stmt = select(Subject).where(Subject.name == subject)
    result = await session.exec(stmt)
    db_subject = result.first()
    if not db_subject:
        # 如果找不到，尝试用名称作为 code 查找
        db_subject = await subject_repo.get_by_code(subject)
    if not db_subject:
        raise BadRequestException(f"学科 '{subject}' 不存在，请先创建学科")

    # 创建考试记录
    exam = Exam(
        title=title or f"考试 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
        subject_id=db_subject.id,
        class_id=class_id,
        exam_type="quiz",
        total_score=100.0,
        status=ExamStatus.DRAFT,
        exam_date=datetime.now(timezone.utc),
        created_by=current_user.id,
    )
    exam = await ExamRepository(session).create(exam)

    # 上传文件到 MinIO
    if is_pdf:
        images = pdf_service.pdf_to_images(contents, dpi=300, enhance=True)
        for page_num, img_bytes, fmt in images:
            storage_service.upload_image(
                file_data=img_bytes,
                filename=f"page_{page_num}.{fmt}",
                exam_id=exam.id,
                page_number=page_num,
            )
    else:
        # 对直接上传的图片添加水印（PDF 转图在后续 OCR 流程中处理，暂不添加）
        watermarked = watermark_service.add_watermark(
            contents, f"Exam-{exam.id} User-{current_user.id}"
        )
        ext = file.filename.split(".")[-1].lower() if "." in file.filename else "jpg"
        storage_service.upload_image(
            file_data=watermarked,
            filename=file.filename,
            exam_id=exam.id,
            page_number=1,
        )

    return BaseResponse(
        data=_exam_to_dict(exam, subject_name=db_subject.name),
        message="上传成功，请调用 /exams/{exam_id}/start-ocr 进行识别",
    )


@router.post("", response_model=BaseResponse, status_code=status.HTTP_201_CREATED)
async def create_exam(
    title: str = Form(...),
    subject: str = Form(...),
    class_id: int = Form(...),
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
) -> BaseResponse:
    """创建考试记录（不上传文件，仅创建元数据）."""
    # 查找学科（先按 name，再按 code）
    stmt = select(Subject).where(Subject.name == subject)
    result = await session.exec(stmt)
    db_subject = result.first()
    if not db_subject:
        stmt = select(Subject).where(Subject.code == subject)
        result = await session.exec(stmt)
        db_subject = result.first()
    if not db_subject:
        raise BadRequestException(f"学科 '{subject}' 不存在")

    exam = Exam(
        title=title,
        subject_id=db_subject.id,
        class_id=class_id,
        exam_type=ExamType.QUIZ,
        total_score=100.0,
        status=ExamStatus.READY,
        created_by=getattr(current_user, "id", 1),
        exam_date=datetime.now(timezone.utc),
    )
    session.add(exam)
    await session.commit()
    await session.refresh(exam)

    return BaseResponse(
        data=_exam_to_dict(exam, subject_name=db_subject.name),
        message="考试创建成功",
    )


@router.get("", response_model=BaseResponse)
async def list_exams(
    class_id: int | None = None,
    subject_id: int | None = None,
    status: str | None = None,
    skip: int = 0,
    limit: int = 20,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
) -> BaseResponse:
    """获取考试列表，支持分页与筛选."""
    where_clauses = []
    if class_id is not None:
        where_clauses.append(Exam.class_id == class_id)
    if subject_id is not None:
        where_clauses.append(Exam.subject_id == subject_id)
    if status is not None:
        where_clauses.append(Exam.status == status)

    total_stmt = select(func.count(Exam.id))
    list_stmt = select(Exam).offset(skip).limit(limit).order_by(Exam.created_at.desc())
    if where_clauses:
        total_stmt = total_stmt.where(*where_clauses)
        list_stmt = list_stmt.where(*where_clauses)

    total_result = await session.exec(total_stmt)
    total = total_result.one()

    list_stmt = list_stmt.options(selectinload(Exam.questions), selectinload(Exam.submissions))
    list_result = await session.exec(list_stmt)
    exams = list(list_result.all())

    # Fetch subject names in batch to avoid N+1
    subject_ids = [e.subject_id for e in exams if e.subject_id]
    subject_map = {}
    if subject_ids:
        sub_stmt = select(Subject.id, Subject.name).where(Subject.id.in_(subject_ids))
        sub_result = await session.exec(sub_stmt)
        subject_map = {row[0]: row[1] for row in sub_result.all()}

    items = [
        _exam_to_dict(e, subject_name=subject_map.get(e.subject_id, ""))
        for e in exams
    ]
    total_pages = (total + limit - 1) // limit if limit > 0 else 0
    page = skip // limit + 1 if limit > 0 else 1

    return BaseResponse(
        data=PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=limit,
            total_pages=total_pages,
        ),
    )


@router.get("/{exam_id}", response_model=BaseResponse)
async def get_exam(
    exam_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
) -> BaseResponse:
    """获取考试详情（含题目列表）."""
    stmt = (
        select(Exam)
        .options(selectinload(Exam.questions), selectinload(Exam.submissions))
        .where(Exam.id == exam_id)
    )
    result = await session.exec(stmt)
    exam = result.first()
    if not exam:
        raise NotFoundException("考试不存在")

    questions = await ExamQuestionRepository(session).get_by_exam_ordered(exam_id)

    subject_result = await session.exec(select(Subject).where(Subject.id == exam.subject_id))
    subject = subject_result.first()

    return BaseResponse(
        data={
            "exam": _exam_to_dict(exam, subject_name=subject.name if subject else ""),
            "questions": [
                {
                    "id": q.id,
                    "sequence_number": q.sequence_number,
                    "question_type": q.question_type.value if hasattr(q.question_type, "value") else str(q.question_type),
                    "content": q.content,
                    "content_latex": q.content_latex,
                    "options": q.options,
                    "score": float(q.score) if q.score is not None else 0.0,
                    "ocr_confidence": q.ocr_confidence,
                    "status": q.status.value if hasattr(q.status, "value") else str(q.status),
                }
                for q in questions
            ],
        },
    )


@router.post("/{exam_id}/start-ocr", response_model=BaseResponse)
async def start_exam_ocr(
    exam_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
) -> BaseResponse:
    """启动考试 OCR 识别任务.

    要求考试状态为 draft。
    """
    exam = await ExamRepository(session).get_by_id(exam_id)
    if not exam:
        raise NotFoundException("考试不存在")
    if exam.status != ExamStatus.DRAFT:
        raise BadRequestException(
            f"当前状态 {exam.status.value if hasattr(exam.status, 'value') else exam.status} 不支持 OCR"
        )

    await ExamRepository(session).update_status(exam_id, ExamStatus.PROCESSING)

    from app.tasks.ocr import process_exam_ocr

    task = process_exam_ocr.delay(exam_id)
    return BaseResponse(data={"task_id": task.id})


@router.post("/{exam_id}/start-grading", response_model=BaseResponse)
async def start_exam_grading(
    exam_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
) -> BaseResponse:
    """启动考试批量判卷任务.

    要求考试状态为 ready。
    """
    exam = await ExamRepository(session).get_by_id(exam_id)
    if not exam:
        raise NotFoundException("考试不存在")
    if exam.status != ExamStatus.READY:
        raise BadRequestException(
            f"当前状态 {exam.status.value if hasattr(exam.status, 'value') else exam.status} 不支持判卷"
        )

    await ExamRepository(session).update_status(exam_id, ExamStatus.GRADING)

    from app.tasks.grading import batch_grade_exam

    task = batch_grade_exam.delay(exam_id)
    return BaseResponse(data={"task_id": task.id})


@router.get("/{exam_id}/questions", response_model=BaseResponse)
async def get_exam_questions(
    exam_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
) -> BaseResponse:
    """获取考试题目列表及 OCR 结果."""
    exam = await ExamRepository(session).get_by_id(exam_id)
    if not exam:
        raise NotFoundException("考试不存在")

    questions = await ExamQuestionRepository(session).get_by_exam_ordered(exam_id)
    return BaseResponse(
        data={
            "exam_id": exam_id,
            "questions": [
                {
                    "id": q.id,
                    "sequence_number": q.sequence_number,
                    "question_type": q.question_type.value if hasattr(q.question_type, "value") else str(q.question_type),
                    "content": q.content,
                    "content_latex": q.content_latex,
                    "options": q.options,
                    "score": float(q.score) if q.score is not None else 0.0,
                    "answer_area": q.answer_area,
                    "ocr_confidence": q.ocr_confidence,
                    "status": q.status.value if hasattr(q.status, "value") else str(q.status),
                }
                for q in questions
            ],
        },
    )


@router.get("/{exam_id}/submissions", response_model=BaseResponse)
async def get_exam_submissions(
    exam_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
) -> BaseResponse:
    """获取所有学生作答，按学生分组."""
    exam = await ExamRepository(session).get_by_id(exam_id)
    if not exam:
        raise NotFoundException("考试不存在")

    stmt = select(Submission).where(Submission.exam_id == exam_id)
    result = await session.exec(stmt)
    submissions = list(result.all())

    grouped: dict[int, list[dict]] = defaultdict(list)
    for sub in submissions:
        grouped[sub.student_id].append(
            {
                "id": sub.id,
                "exam_question_id": sub.exam_question_id,
                "answer_text": sub.answer_text,
                "answer_latex": sub.answer_latex,
                "answer_image_urls": sub.answer_image_urls,
                "submitted_at": sub.submitted_at,
                "grading_status": sub.grading_status.value if hasattr(sub.grading_status, "value") else str(sub.grading_status),
            }
        )

    return BaseResponse(
        data={
            "exam_id": exam_id,
            "groups": [
                {"student_id": sid, "submissions": items}
                for sid, items in grouped.items()
            ],
        },
    )


@router.get("/{exam_id}/results", response_model=BaseResponse)
async def get_exam_results(
    exam_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
) -> BaseResponse:
    """获取判卷结果及分数分布统计."""
    exam = await ExamRepository(session).get_by_id(exam_id)
    if not exam:
        raise NotFoundException("考试不存在")

    grading_results = await GradingResultRepository(session).get_by_exam(exam_id)
    scores = [float(gr.score) for gr in grading_results]
    max_scores = [float(gr.max_score) for gr in grading_results]

    total_score = sum(scores)
    total_max = sum(max_scores)

    # 按分数段统计（以百分比计）
    percentages = [s / m * 100 if m > 0 else 0 for s, m in zip(scores, max_scores)]
    distribution = {
        "0-59": len([p for p in percentages if p < 60]),
        "60-69": len([p for p in percentages if 60 <= p < 70]),
        "70-79": len([p for p in percentages if 70 <= p < 80]),
        "80-89": len([p for p in percentages if 80 <= p < 90]),
        "90-100": len([p for p in percentages if p >= 90]),
    }

    error_stats = await GradingResultRepository(session).get_error_stats(exam_id)
    error_types: dict[str, int] = defaultdict(int)
    for gr in error_stats:
        et = gr.error_type.value if hasattr(gr.error_type, "value") else str(gr.error_type)
        error_types[et] += 1

    return BaseResponse(
        data={
            "exam_id": exam_id,
            "total_score": round(total_score, 2),
            "max_score": round(total_max, 2),
            "score_rate": round(total_score / total_max, 4) if total_max > 0 else 0,
            "question_count": len(grading_results),
            "distribution": distribution,
            "error_types": dict(error_types),
            "results": [
                {
                    "submission_id": gr.submission_id,
                    "score": float(gr.score),
                    "max_score": float(gr.max_score),
                    "is_correct": gr.is_correct,
                    "error_type": gr.error_type.value if hasattr(gr.error_type, "value") else str(gr.error_type),
                    "confidence": float(gr.confidence) if gr.confidence is not None else None,
                }
                for gr in grading_results
            ],
        },
    )


@router.get("/{exam_id}/results/export")
async def export_exam_results_pdf(
    exam_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
) -> Response:
    """导出考试成绩单 PDF（教师用）."""
    exam = await ExamRepository(session).get_by_id(exam_id)
    if not exam:
        raise NotFoundException("考试不存在")

    # 使用显式 JOIN 单查询避免 N+1
    stmt = (
        select(
            Student.id.label("student_id"),
            Student.student_number,
            User.real_name,
            ExamQuestion.question_type,
            GradingResult.score,
        )
        .join(Submission, GradingResult.submission_id == Submission.id)
        .join(Student, Submission.student_id == Student.id)
        .join(User, Student.user_id == User.id)
        .join(ExamQuestion, Submission.exam_question_id == ExamQuestion.id)
        .where(Submission.exam_id == exam_id)
    )
    result = await session.exec(stmt)
    rows = list(result.all())

    student_scores: dict[int, dict] = {}
    for row in rows:
        sid = row.student_id
        if sid not in student_scores:
            student_scores[sid] = {
                "student_id": sid,
                "student_number": row.student_number or "",
                "student_name": row.real_name or "",
                "objective_score": 0.0,
                "subjective_score": 0.0,
                "total_score": 0.0,
            }
        score = float(row.score) if row.score is not None else 0.0
        qtype = str(row.question_type) if row.question_type else ""
        if qtype == "choice":
            student_scores[sid]["objective_score"] += score
        else:
            student_scores[sid]["subjective_score"] += score
        student_scores[sid]["total_score"] += score

    results = list(student_scores.values())
    pdf_bytes = await PDFExporter().export_exam_results(exam_id, results)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=exam_results_{exam_id}.pdf"
        },
    )
