import asyncio
import logging
from typing import Any

from celery_worker import celery_app

from app.ai.ocr_engine import ocr_engine
from app.core.websocket_manager import manager
from app.db import SessionLocal
from app.models.exam import Exam, ExamStatus
from app.models.exam_question import ExamQuestion, ExamQuestionStatus, QuestionType
from app.models.student import Student
from app.models.submission import GradingStatus, Submission
from app.models.subject import Subject
from app.services.layout_parser import layout_parser
from app.services.storage_service import storage_service

logger = logging.getLogger(__name__)


def _run_async(coro):
    return asyncio.run(coro)


_QUESTION_TYPE_MAP = {
    "choice": QuestionType.CHOICE,
    "fill_blank": QuestionType.FILL_BLANK,
    "short_answer": QuestionType.SHORT_ANSWER,
    "calculation": QuestionType.CALCULATION,
    "proof": QuestionType.PROOF,
}


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
)
def process_exam_ocr(self, exam_id: int) -> dict[str, Any]:
    """考试 OCR 处理任务."""
    logger.info("Start OCR for exam_id=%s", exam_id)
    db = SessionLocal()
    exam: Exam | None = None
    try:
        exam = db.get(Exam, exam_id)
        if not exam:
            raise ValueError(f"Exam {exam_id} not found")

        exam.status = ExamStatus.PROCESSING
        db.add(exam)
        db.commit()

        # 从 MinIO 列出试卷图片
        prefix = f"exams/{exam_id}/images/"
        objects = list(
            storage_service.client.list_objects(
                storage_service.bucket_name,
                prefix=prefix,
                recursive=True,
            )
        )
        total = len(objects)
        all_questions: list[ExamQuestion] = []

        # 获取学科提示
        subject = db.get(Subject, exam.subject_id)
        subject_hint = subject.name if subject else "数学"

        teacher_id = exam.created_by

        for i, obj in enumerate(objects):
            object_name = obj.object_name
            if not object_name:
                continue

            self.update_state(
                state="PROGRESS",
                meta={"current": i + 1, "total": total, "stage": "downloading"},
            )

            asyncio.run(
                manager.send_to_user(
                    str(teacher_id),
                    manager.build_message(
                        "ocr_progress",
                        {
                            "exam_id": exam_id,
                            "progress": round((i + 1) / total * 100, 2),
                            "stage": "downloading",
                            "current": i + 1,
                            "total": total,
                        },
                    ),
                )
            )

            img_bytes = storage_service.get_file_bytes(object_name)

            self.update_state(
                state="PROGRESS",
                meta={"current": i + 1, "total": total, "stage": "ocr"},
            )

            asyncio.run(
                manager.send_to_user(
                    str(teacher_id),
                    manager.build_message(
                        "ocr_progress",
                        {
                            "exam_id": exam_id,
                            "progress": round((i + 1) / total * 100, 2),
                            "stage": "ocr",
                            "current": i + 1,
                            "total": total,
                        },
                    ),
                )
            )

            ocr_result = _run_async(
                ocr_engine.analyze_exam_page(
                    image_bytes=img_bytes,
                    subject_hint=subject_hint,
                )
            )

            if not ocr_result.get("success"):
                logger.warning("OCR failed for %s of exam %s", object_name, exam_id)
                continue

            parsed = layout_parser.parse_ocr_result(
                ocr_data=ocr_result["data"],
                page_number=i + 1,
            )

            for q in parsed:
                eq = ExamQuestion(
                    exam_id=exam_id,
                    sequence_number=q.sequence,
                    question_type=_QUESTION_TYPE_MAP.get(
                        q.question_type, QuestionType.SHORT_ANSWER
                    ),
                    content=q.content,
                    content_latex=getattr(q, "content_latex", None),
                    options=getattr(q, "options", None),
                    score=q.score,
                    answer_area=getattr(q, "answer_area", None),
                    ocr_confidence=getattr(q, "ocr_confidence", None),
                    status=ExamQuestionStatus.PENDING,
                )
                db.add(eq)
                all_questions.append(eq)

            db.commit()

        exam.status = ExamStatus.READY
        db.add(exam)
        db.commit()

        asyncio.run(
            manager.send_to_user(
                str(teacher_id),
                manager.build_message(
                    "ocr_progress",
                    {
                        "exam_id": exam_id,
                        "progress": 100.0,
                        "stage": "completed",
                        "question_count": len(all_questions),
                        "status": "ready",
                    },
                ),
            )
        )

        logger.info(
            "OCR completed for exam_id=%s, questions=%s",
            exam_id,
            len(all_questions),
        )
        return {
            "success": True,
            "exam_id": exam_id,
            "question_count": len(all_questions),
            "status": "ready",
        }

    except Exception as exc:
        logger.exception("OCR failed for exam_id=%s", exam_id)
        if exam:
            exam.status = ExamStatus.DRAFT
            db.add(exam)
            db.commit()
        raise self.retry(exc=exc)

    finally:
        db.close()


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
)
def process_answer_sheet_ocr(self, submission_id: int) -> dict[str, Any]:
    """答题卡 OCR 任务."""
    logger.info("Start answer sheet OCR for submission_id=%s", submission_id)
    db = SessionLocal()
    submission: Submission | None = None
    try:
        submission = db.get(Submission, submission_id)
        if not submission:
            raise ValueError(f"Submission {submission_id} not found")

        image_urls = submission.answer_image_urls or []
        if not image_urls:
            raise ValueError(
                f"Submission {submission_id} has no answer_image_urls"
            )

        student = db.get(Student, submission.student_id)
        student_user_id = student.user_id if student else None

        self.update_state(
            state="PROGRESS",
            meta={"current": 1, "total": 3, "stage": "downloading"},
        )

        if student_user_id:
            asyncio.run(
                manager.send_to_user(
                    str(student_user_id),
                    manager.build_message(
                        "answer_ocr_progress",
                        {
                            "submission_id": submission_id,
                            "progress": 33.0,
                            "stage": "downloading",
                        },
                    ),
                )
            )

        # 取第一张图片进行识别
        object_name = image_urls[0]
        img_bytes = storage_service.get_file_bytes(object_name)

        self.update_state(
            state="PROGRESS",
            meta={"current": 2, "total": 3, "stage": "ocr"},
        )

        if student_user_id:
            asyncio.run(
                manager.send_to_user(
                    str(student_user_id),
                    manager.build_message(
                        "answer_ocr_progress",
                        {
                            "submission_id": submission_id,
                            "progress": 66.0,
                            "stage": "ocr",
                        },
                    ),
                )
            )

        # 获取题目内容作为上下文
        exam_question = db.get(ExamQuestion, submission.exam_question_id)
        question_content = exam_question.content if exam_question else ""

        ocr_result = _run_async(
            ocr_engine.recognize_student_answer(
                image_bytes=img_bytes,
                question_content=question_content,
            )
        )

        self.update_state(
            state="PROGRESS",
            meta={"current": 3, "total": 3, "stage": "parsing"},
        )

        submission.answer_text = ocr_result.get("text", "")
        submission.grading_status = GradingStatus.PENDING
        db.add(submission)
        db.commit()

        if student_user_id:
            asyncio.run(
                manager.send_to_user(
                    str(student_user_id),
                    manager.build_message(
                        "answer_ocr_progress",
                        {
                            "submission_id": submission_id,
                            "progress": 100.0,
                            "stage": "completed",
                        },
                    ),
                )
            )

        logger.info(
            "Answer sheet OCR completed for submission_id=%s",
            submission_id,
        )
        return {
            "success": True,
            "submission_id": submission_id,
            "text": submission.answer_text,
        }

    except Exception as exc:
        logger.exception(
            "Answer sheet OCR failed for submission_id=%s", submission_id
        )
        raise self.retry(exc=exc)

    finally:
        db.close()
