import asyncio
import logging
from typing import Any

from celery_worker import celery_app

from app.core.websocket_manager import manager
from app.db import SessionLocal
from app.models.exam import Exam, ExamStatus
from app.models.exam_question import ExamQuestion
from app.models.grading_result import ErrorType, GradingResult
from app.models.question_template import QuestionTemplate
from app.models.student import Student
from app.models.submission import GradingStatus, Submission
from app.services.grading_engine import grading_engine

logger = logging.getLogger(__name__)


def _run_async(coro):
    return asyncio.run(coro)


_ERROR_TYPE_MAP = {
    "correct": ErrorType.CORRECT,
    "concept_error": ErrorType.CONCEPT_ERROR,
    "calculation_error": ErrorType.CALCULATION_ERROR,
    "misreading": ErrorType.MISREADING,
    "missing_step": ErrorType.MISSING_STEP,
    "logic_break": ErrorType.LOGIC_BREAK,
    "formula_error": ErrorType.FORMULA_ERROR,
    "notation_error": ErrorType.NOTATION_ERROR,
    "incomplete": ErrorType.INCOMPLETE,
    "unclear": ErrorType.UNCLEAR,
    "unknown": ErrorType.UNKNOWN,
}


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
)
def grade_submission(self, submission_id: int) -> dict[str, Any]:
    """单题判卷任务."""
    logger.info("Start grading submission_id=%s", submission_id)
    db = SessionLocal()
    submission: Submission | None = None
    try:
        submission = db.get(Submission, submission_id)
        if not submission:
            raise ValueError(f"Submission {submission_id} not found")

        submission.grading_status = GradingStatus.GRADING
        db.add(submission)
        db.commit()

        # 获取关联的 exam_question 和 question_template
        exam_question = db.get(ExamQuestion, submission.exam_question_id)
        if not exam_question:
            raise ValueError(
                f"ExamQuestion {submission.exam_question_id} not found"
            )

        question_template = None
        if exam_question.question_template_id:
            question_template = db.get(
                QuestionTemplate, exam_question.question_template_id
            )

        std_ans = question_template.standard_answer if question_template else ""
        max_score = exam_question.score

        grading_result = _run_async(
            grading_engine.grade(
                question_type=exam_question.question_type.value,
                question_content=exam_question.content,
                standard_answer=std_ans,
                student_answer=submission.answer_text or "",
                max_score=max_score,
                knowledge_point_hints=(
                    question_template.knowledge_point_ids
                    if question_template
                    else None
                ),
            )
        )

        gr = GradingResult(
            submission_id=submission_id,
            is_correct=grading_result.is_correct,
            score=grading_result.score,
            max_score=grading_result.max_score,
            error_type=_ERROR_TYPE_MAP.get(
                grading_result.error_type or "unknown", ErrorType.UNKNOWN
            ),
            error_type_detail=grading_result.error_type_detail or "",
            knowledge_point_ids=grading_result.knowledge_point_ids,
            suggestion=grading_result.suggestion or "",
            confidence=grading_result.confidence,
            ai_model=grading_result.ai_model or "",
            raw_response=grading_result.raw_response,
        )
        db.add(gr)

        submission.grading_status = GradingStatus.GRADED
        db.add(submission)
        db.commit()

        # 推送 WebSocket 通知给学生
        student = db.get(Student, submission.student_id)
        if student and student.user_id:
            asyncio.run(
                manager.send_to_user(
                    str(student.user_id),
                    manager.build_message(
                        "exam.graded",
                        {
                            "submission_id": submission_id,
                            "exam_id": submission.exam_id,
                            "score": grading_result.score,
                            "max_score": max_score,
                            "is_correct": grading_result.is_correct,
                        },
                    ),
                )
            )

        logger.info(
            "Grading completed for submission_id=%s, score=%s/%s",
            submission_id,
            grading_result.score,
            max_score,
        )
        return {
            "success": True,
            "submission_id": submission_id,
            "score": grading_result.score,
            "max_score": max_score,
            "is_correct": grading_result.is_correct,
        }

    except Exception as exc:
        logger.exception("Grading failed for submission_id=%s", submission_id)
        if submission:
            submission.grading_status = GradingStatus.MANUAL_REVIEW
            db.add(submission)
            db.commit()
        raise self.retry(exc=exc)

    finally:
        db.close()


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
)
def batch_grade_exam(self, exam_id: int) -> dict[str, Any]:
    """批量判卷任务."""
    logger.info("Start batch grading for exam_id=%s", exam_id)
    db = SessionLocal()
    exam: Exam | None = None
    try:
        exam = db.get(Exam, exam_id)
        if not exam:
            raise ValueError(f"Exam {exam_id} not found")

        pending_submissions = (
            db.query(Submission)
            .filter(
                Submission.exam_id == exam_id,
                Submission.grading_status.in_(
                    [GradingStatus.PENDING, GradingStatus.MANUAL_REVIEW]
                ),
            )
            .all()
        )

        total = len(pending_submissions)
        teacher_id = exam.created_by

        for i, sub in enumerate(pending_submissions):
            self.update_state(
                state="PROGRESS",
                meta={
                    "current": i + 1,
                    "total": total,
                    "stage": "dispatching",
                    "submission_id": sub.id,
                },
            )
            asyncio.run(
                manager.send_to_user(
                    str(teacher_id),
                    manager.build_message(
                        "grading_progress",
                        {
                            "exam_id": exam_id,
                            "progress": round((i + 1) / total * 100, 2),
                            "stage": "dispatching",
                            "current": i + 1,
                            "total": total,
                        },
                    ),
                )
            )
            grade_submission.delay(sub.id)

        exam.status = ExamStatus.GRADED
        db.add(exam)
        db.commit()

        asyncio.run(
            manager.send_to_user(
                str(teacher_id),
                manager.build_message(
                    "grading_progress",
                    {
                        "exam_id": exam_id,
                        "progress": 100.0,
                        "stage": "completed",
                        "dispatched_count": total,
                        "status": "graded",
                    },
                ),
            )
        )

        logger.info(
            "Batch grading dispatched for exam_id=%s, submissions=%s",
            exam_id,
            total,
        )
        return {
            "success": True,
            "exam_id": exam_id,
            "dispatched_count": total,
            "status": "graded",
        }

    except Exception as exc:
        logger.exception("Batch grading failed for exam_id=%s", exam_id)
        raise self.retry(exc=exc)

    finally:
        db.close()
