from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from celery_worker import celery_app

from app.ai.gateway import LLMGateway
from app.core.database import async_session
from app.models.exercise import Exercise, ExerciseStatus
from app.models.exercise_question import ExerciseQuestion
from app.repositories.exercise import ExerciseRepository
from app.repositories.exercise_question import ExerciseQuestionRepository
from app.repositories.student_knowledge_state import StudentKnowledgeStateRepository
from app.services.exercise_generator import ExerciseGenerator
from app.services.grading_engine import GradingEngine
from app.services.spaced_repetition import SpacedRepetition

logger = logging.getLogger(__name__)


def _run_async(coro):
    return asyncio.run(coro)


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
)
def generate_exercise_task(self, exercise_id: int) -> dict[str, Any]:
    """生成练习卷任务."""
    logger.info("Start generating exercise_id=%s", exercise_id)

    async def _do_generate() -> dict[str, Any]:
        async with async_session() as session:
            exercise_repo = ExerciseRepository(session)
            exercise = await exercise_repo.get_by_id(exercise_id)
            if not exercise:
                raise ValueError(f"Exercise {exercise_id} not found")

            generator = ExerciseGenerator(session)

            target_kps = exercise.target_knowledge_point_ids or []
            target_errors = exercise.target_error_types or []
            diff_range = exercise.difficulty_range or {"min": 1, "max": 5}
            difficulty_range = (diff_range.get("min", 1), diff_range.get("max", 5))

            self.update_state(
                state="PROGRESS",
                meta={"current": 0, "total": 100, "stage": "retrieving"},
            )

            result = await generator.generate_exercise(
                student_id=exercise.student_id,
                target_knowledge_point_ids=target_kps,
                target_error_types=target_errors,
                difficulty_range=difficulty_range,
                question_count=10,
            )

            self.update_state(
                state="PROGRESS",
                meta={"current": 50, "total": 100, "stage": "saving"},
            )

            # 保存题目到数据库
            eq_repo = ExerciseQuestionRepository(session)
            questions = result.get("questions", [])
            for q in questions:
                eq = ExerciseQuestion(
                    exercise_id=exercise_id,
                    sequence_number=q.get("sequence_number", 1),
                    content=q.get("content", ""),
                    content_latex=q.get("content_latex"),
                    options=q.get("options"),
                    standard_answer=q.get("standard_answer", ""),
                    max_score=q.get("max_score", 5.0),
                    ai_explanation=q.get("explanation") or q.get("ai_explanation"),
                )
                session.add(eq)

            await session.commit()

            # 更新练习状态为 assigned
            await exercise_repo.update_status(exercise_id, ExerciseStatus.assigned)

            logger.info(
                "Exercise generated: id=%s, questions=%s",
                exercise_id,
                len(questions),
            )
            return {
                "success": True,
                "exercise_id": exercise_id,
                "question_count": len(questions),
            }

    return _run_async(_do_generate())


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 30},
)
def grade_exercise_question_task(self, exercise_question_id: int) -> dict[str, Any]:
    """异步判卷任务."""
    logger.info("Start grading exercise_question_id=%s", exercise_question_id)

    async def _do_grade() -> dict[str, Any]:
        async with async_session() as session:
            eq_repo = ExerciseQuestionRepository(session)
            eq = await eq_repo.get_by_id(exercise_question_id)
            if not eq:
                raise ValueError(f"ExerciseQuestion {exercise_question_id} not found")

            if not eq.student_answer:
                return {
                    "success": False,
                    "exercise_question_id": exercise_question_id,
                    "reason": "No student answer",
                }

            # 尝试获取题型
            question_type = "short_answer"
            if eq.question_template_id:
                from app.repositories.question_template import QuestionTemplateRepository

                qt_repo = QuestionTemplateRepository(session)
                qt = await qt_repo.get_by_id(eq.question_template_id)
                if qt:
                    question_type = (
                        qt.question_type.value
                        if hasattr(qt.question_type, "value")
                        else str(qt.question_type)
                    )

            grading_engine = GradingEngine()
            result = await grading_engine.grade(
                question_type=question_type,
                question_content=eq.content,
                standard_answer=eq.standard_answer or "",
                student_answer=eq.student_answer,
                max_score=eq.max_score,
            )

            await eq_repo.update_grading_result(
                exercise_question_id=exercise_question_id,
                is_correct=result.is_correct,
                score=result.score,
                ai_explanation=result.suggestion or result.error_type_detail,
            )

            # 更新学生知识状态
            if eq.question_template_id:
                from app.repositories.exercise import ExerciseRepository
                from app.repositories.question_template import QuestionTemplateRepository

                exercise_repo = ExerciseRepository(session)
                exercise = await exercise_repo.get_by_id(eq.exercise_id)
                student_id = exercise.student_id if exercise else None

                qt_repo = QuestionTemplateRepository(session)
                qt = await qt_repo.get_by_id(eq.question_template_id)
                if qt and qt.knowledge_point_ids and student_id:
                    kp_repo = StudentKnowledgeStateRepository(session)
                    for kp_id in qt.knowledge_point_ids:
                        state = await kp_repo.get_by_student_and_kp(
                            student_id, kp_id
                        )
                        # 这里简化处理：实际应调用 knowledge_tracker 更新
                        if state:
                            state.total_attempts += 1
                            if result.is_correct:
                                state.correct_count += 1
                            session.add(state)
                    await session.commit()

            logger.info(
                "Graded exercise_question_id=%s, is_correct=%s, score=%s",
                exercise_question_id,
                result.is_correct,
                result.score,
            )
            return {
                "success": True,
                "exercise_question_id": exercise_question_id,
                "is_correct": result.is_correct,
                "score": result.score,
                "max_score": result.max_score,
            }

    return _run_async(_do_grade())


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
)
def auto_assign_review_task(self, student_id: int) -> dict[str, Any]:
    """间隔重复推送任务.

    根据错题本和薄弱知识点，自动为学生生成复习练习。
    """
    logger.info("Auto assign review for student_id=%s", student_id)

    async def _do_assign() -> dict[str, Any]:
        async with async_session() as session:
            from app.services.adaptive_push import AdaptivePushService

            service = AdaptivePushService(session)
            plan = await service.generate_daily_plan(student_id)
            return {
                "success": True,
                "student_id": student_id,
                "exercise_id": plan.get("exercise_id"),
                "question_count": plan.get("question_count"),
                "reason": plan.get("reason"),
            }

    return _run_async(_do_assign())
