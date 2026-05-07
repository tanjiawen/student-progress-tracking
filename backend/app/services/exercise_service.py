from __future__ import annotations

import logging
from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.exercise import Exercise, ExerciseStatus
from app.models.exercise_question import ExerciseQuestion
from app.repositories.exercise import ExerciseRepository
from app.repositories.exercise_question import ExerciseQuestionRepository
from app.repositories.student import StudentRepository
from app.schemas.exercise import ExerciseCreate, ExerciseRead
from app.services.exercise_generator import ExerciseGenerator
from app.services.grading_engine import grading_engine

logger = logging.getLogger(__name__)


class ExerciseService:
    """练习服务."""

    def __init__(self, session: AsyncSession):
        self.exercise_repo = ExerciseRepository(session)
        self.exercise_question_repo = ExerciseQuestionRepository(session)
        self.student_repo = StudentRepository(session)
        self.generator = ExerciseGenerator(session)
        self.grading_engine = grading_engine
        self.session = session

    async def create_exercise(self, data: ExerciseCreate) -> ExerciseRead:
        """创建练习卷记录并触发异步生成任务."""
        # 验证学生存在
        student = await self.student_repo.get_by_id(data.student_id)
        if not student:
            raise BadRequestException(f"学生 {data.student_id} 不存在")

        exercise = Exercise(
            student_id=data.student_id,
            title=data.title,
            target_knowledge_point_ids=data.target_knowledge_point_ids,
            target_error_types=data.target_error_types,
            difficulty_range={"min": data.difficulty_range[0], "max": data.difficulty_range[1]},
            status=ExerciseStatus.draft,
            due_at=data.due_at,
        )

        exercise = await self.exercise_repo.create(exercise)

        # 触发异步生成任务
        from app.tasks.exercise import generate_exercise_task

        generate_exercise_task.delay(exercise.id)

        return ExerciseRead.model_validate(exercise)

    async def assign_exercise(self, exercise_id: int, student_ids: list[int]) -> dict[str, Any]:
        """分配练习给学生.

        为每个学生复制一份练习卷记录并触发生成。
        """
        original = await self.exercise_repo.get_by_id(exercise_id)
        if not original:
            raise NotFoundException("练习卷不存在")

        assigned_count = 0
        new_exercise_ids: list[int] = []

        for student_id in student_ids:
            student = await self.student_repo.get_by_id(student_id)
            if not student:
                logger.warning("学生 %s 不存在，跳过", student_id)
                continue

            # 为每个学生创建独立的练习卷
            exercise = Exercise(
                student_id=student_id,
                title=original.title,
                target_knowledge_point_ids=original.target_knowledge_point_ids,
                target_error_types=original.target_error_types,
                difficulty_range=original.difficulty_range,
                status=ExerciseStatus.draft,
                due_at=original.due_at,
            )
            exercise = await self.exercise_repo.create(exercise)

            from app.tasks.exercise import generate_exercise_task

            generate_exercise_task.delay(exercise.id)

            assigned_count += 1
            new_exercise_ids.append(exercise.id)

        return {
            "assigned_count": assigned_count,
            "exercise_ids": new_exercise_ids,
        }

    async def submit_answer(self, exercise_question_id: int, answer: str) -> dict[str, Any]:
        """学生提交作答.

        - 客观题即时判分
        - 主观题触发异步判卷
        """
        eq = await self.exercise_question_repo.get_by_id(exercise_question_id)
        if not eq:
            raise NotFoundException("题目不存在")

        # 保存作答
        eq = await self.exercise_question_repo.submit_answer(exercise_question_id, answer)
        if not eq:
            raise BadRequestException("提交失败")

        # 判断题型
        question_type = "short_answer"  # 默认主观题
        # 尝试从关联的模板获取题型
        if eq.question_template_id:
            from app.repositories.question_template import QuestionTemplateRepository

            qt_repo = QuestionTemplateRepository(self.session)
            qt = await qt_repo.get_by_id(eq.question_template_id)
            if qt:
                question_type = qt.question_type.value if hasattr(qt.question_type, "value") else str(qt.question_type)

        # 客观题即时判分
        if question_type in {"choice", "fill_blank"}:
            result = self.grading_engine._grade_objective(
                question_type=question_type,
                standard_answer=eq.standard_answer or "",
                student_answer=answer,
                max_score=eq.max_score,
            )
            await self.exercise_question_repo.update_grading_result(
                exercise_question_id=exercise_question_id,
                is_correct=result.is_correct,
                score=result.score,
                ai_explanation=result.suggestion or result.error_type_detail,
            )
            return {
                "exercise_question_id": exercise_question_id,
                "is_correct": result.is_correct,
                "score": result.score,
                "max_score": result.max_score,
                "error_type": result.error_type,
                "graded": True,
            }

        # 主观题触发异步判卷
        from app.tasks.exercise import grade_exercise_question_task

        grade_exercise_question_task.delay(exercise_question_id)

        return {
            "exercise_question_id": exercise_question_id,
            "graded": False,
            "message": "主观题已提交，正在异步判卷",
        }

    async def get_exercise_result(self, exercise_id: int, student_id: int) -> dict[str, Any]:
        """获取练习结果 + AI 解析."""
        exercise = await self.exercise_repo.get_by_id(exercise_id)
        if not exercise:
            raise NotFoundException("练习卷不存在")
        if exercise.student_id != student_id:
            raise BadRequestException("无权查看该练习结果")

        questions = await self.exercise_question_repo.get_by_exercise(exercise_id)

        total_score = 0.0
        max_score = 0.0
        correct_count = 0
        question_results: list[dict[str, Any]] = []

        for q in questions:
            total_score += q.score or 0.0
            max_score += q.max_score
            if q.is_correct:
                correct_count += 1

            question_results.append({
                "id": q.id,
                "sequence_number": q.sequence_number,
                "content": q.content,
                "student_answer": q.student_answer,
                "standard_answer": q.standard_answer,
                "is_correct": q.is_correct,
                "score": q.score,
                "max_score": q.max_score,
                "ai_explanation": q.ai_explanation,
            })

        # 生成 AI 总结
        ai_summary = None
        if exercise.status == ExerciseStatus.completed:
            weak_points = [
                q["sequence_number"]
                for q in question_results
                if not q["is_correct"]
            ]
            ai_summary = f"本次练习共 {len(questions)} 题，答对 {correct_count} 题，得分 {total_score:.1f}/{max_score:.1f}。"
            if weak_points:
                ai_summary += f" 第 {', '.join(str(i) for i in weak_points)} 题需要加强。"
            else:
                ai_summary += " 全部正确，继续保持！"

        return {
            "exercise_id": exercise_id,
            "student_id": student_id,
            "total_score": round(total_score, 2),
            "max_score": round(max_score, 2),
            "correct_count": correct_count,
            "question_count": len(questions),
            "questions": question_results,
            "ai_summary": ai_summary,
        }

    async def complete_exercise(self, exercise_id: int) -> Exercise | None:
        """标记练习为已完成."""
        exercise = await self.exercise_repo.get_by_id(exercise_id)
        if not exercise:
            return None

        exercise.status = ExerciseStatus.completed
        from datetime import datetime

        exercise.completed_at = datetime.utcnow()
        exercise.updated_at = datetime.utcnow()
        self.session.add(exercise)
        await self.session.commit()
        await self.session.refresh(exercise)
        return exercise
