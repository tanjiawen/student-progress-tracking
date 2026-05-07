from __future__ import annotations

"""自适应练习推送服务."""

import logging
import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.error_book_item import ErrorBookItem
from app.models.exercise import Exercise, ExerciseStatus
from app.models.knowledge_point import KnowledgePoint
from app.models.question_template import QuestionTemplate
from app.models.student_knowledge_state import MasteryStatus, StudentKnowledgeState
from app.repositories.error_book_item import ErrorBookItemRepository
from app.repositories.exercise import ExerciseRepository
from app.repositories.student_knowledge_state import StudentKnowledgeStateRepository
from app.services.spaced_repetition import SpacedRepetition

logger = logging.getLogger(__name__)


class AdaptivePushService:
    """自适应练习推送服务."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.error_book_repo = ErrorBookItemRepository(session)
        self.knowledge_state_repo = StudentKnowledgeStateRepository(session)
        self.exercise_repo = ExerciseRepository(session)
        self.spaced = SpacedRepetition()

    # ------------------------------------------------------------------
    # 每日计划
    # ------------------------------------------------------------------

    async def generate_daily_plan(self, student_id: int) -> dict:
        """生成今日练习计划.

        计划构成：
        - 错题复习 30%（已掌握度低的错题）
        - 薄弱强化 40%（薄弱知识点的变式题）
        - 新知预习 30%（下一个知识点的入门题）
        """
        # 1. 获取错题本中到期的错题
        due_errors = await self._get_due_errors(student_id)
        due_errors.sort(key=lambda e: self.calculate_review_priority(e), reverse=True)

        # 2. 获取薄弱知识点（掌握度 < 0.6）
        weak_states = await self.knowledge_state_repo.get_weak_points(student_id, threshold=0.6)
        weak_kp_ids = [s.knowledge_point_id for s in weak_states]

        # 3. 获取最近未练习的知识点（避免重复）
        recent_kp_ids = await self._get_recent_exercise_knowledge_points(student_id)
        new_kp_candidates = await self._get_new_knowledge_candidates(
            student_id, weak_kp_ids, recent_kp_ids
        )

        # 4. 组装题目（目标 5-10 题）
        target_total = 8
        error_count = max(1, int(target_total * 0.3))
        weak_count = max(1, int(target_total * 0.4))
        new_count = max(1, target_total - error_count - weak_count)

        selected_errors = due_errors[:error_count]
        selected_weak_kps = weak_kp_ids[:weak_count]
        selected_new_kps = new_kp_candidates[:new_count]

        questions: list[dict] = []
        for idx, err in enumerate(selected_errors, 1):
            questions.append({
                "sequence": idx,
                "type": "error_review",
                "error_book_item_id": err.id,
                "knowledge_point_ids": [err.question_template_id] if err.question_template_id else [],
                "source": "error_book",
            })

        for idx, kp_id in enumerate(selected_weak_kps, len(questions) + 1):
            questions.append({
                "sequence": idx,
                "type": "weak_reinforce",
                "knowledge_point_id": kp_id,
                "source": "weak_point",
            })

        for idx, kp_id in enumerate(selected_new_kps, len(questions) + 1):
            questions.append({
                "sequence": idx,
                "type": "new_preview",
                "knowledge_point_id": kp_id,
                "source": "new_knowledge",
            })

        # 5. 保存为 Exercise 记录
        exercise = Exercise(
            student_id=student_id,
            title=f"每日练习 {datetime.now(UTC).strftime('%Y-%m-%d')}",
            target_knowledge_point_ids=list(
                set(
                    [q.get("knowledge_point_id") for q in questions if q.get("knowledge_point_id")]
                    + [
                        kp_id
                        for q in questions
                        for kp_id in (q.get("knowledge_point_ids") or [])
                    ]
                )
            ),
            target_error_types=list({e.error_type for e in selected_errors}),
            difficulty_range={"min": 1, "max": 3},
            status=ExerciseStatus.assigned,
            assigned_at=datetime.now(UTC),
            due_at=datetime.now(UTC) + timedelta(days=1),
        )
        exercise = await self.exercise_repo.create(exercise)

        plan = {
            "exercise_id": exercise.id,
            "student_id": student_id,
            "date": datetime.now(UTC).strftime("%Y-%m-%d"),
            "question_count": len(questions),
            "questions": questions,
            "error_review_count": len(selected_errors),
            "weak_reinforce_count": len(selected_weak_kps),
            "new_preview_count": len(selected_new_kps),
        }

        # 6. 推送通知（日志记录，实际可接入 WebSocket/推送服务）
        logger.info("Daily plan generated for student_id=%s: %s", student_id, plan)
        return plan

    # ------------------------------------------------------------------
    # 复习优先级
    # ------------------------------------------------------------------

    async def calculate_review_priority(
        self,
        error_item: ErrorBookItem,
    ) -> float:
        """计算错题复习优先级得分.

        因素：
        - 错误次数（越多越优先）
        - 距离上次复习时间（越久越优先）
        - 知识点重要性（越重要越优先）—— 此处用 level 代理
        - 掌握度（越低越优先）
        """
        # 错误次数权重
        error_score = min(error_item.error_count * 10, 50)

        # 距离上次复习时间权重
        days_since_review = 0
        if error_item.next_review_at:
            days_since_review = (datetime.now(UTC) - error_item.next_review_at).days
        review_score = max(days_since_review * 2, 0)

        # 知识点重要性（用 question_template 的 difficulty 或 knowledge_point level 代理）
        importance_score = 10
        if error_item.question_template:
            importance_score = error_item.question_template.difficulty * 5

        # 掌握度权重（越低越优先，需要从知识状态表查）
        mastery_score = 25  # 默认中等
        # 异步调用移到外部；此处简化为基于 error_count 和 review_count 估算
        if error_item.review_count > 0:
            mastery_score = max(5, 25 - error_item.review_count * 3)

        return error_score + review_score + importance_score + mastery_score

    # ------------------------------------------------------------------
    # SM-2 调度
    # ------------------------------------------------------------------

    async def schedule_next_review(
        self,
        student_id: int,
        error_item_id: int,
        quality: int,
    ) -> datetime:
        """基于 SM-2 算法安排下次复习时间."""
        item = await self.error_book_repo.get_by_id(error_item_id)
        if not item:
            raise ValueError(f"ErrorBookItem {error_item_id} not found")

        interval, new_ef, repetition = self.spaced.calculate_next_review(
            quality=quality,
            repetition_count=item.sm2_repetition_count,
            easiness_factor=float(item.sm2_easiness_factor),
            interval_days=item.sm2_interval_days,
        )

        next_review = datetime.now(UTC) + timedelta(days=interval)

        item.sm2_interval_days = interval
        item.sm2_easiness_factor = new_ef
        item.sm2_repetition_count = repetition
        item.next_review_at = next_review
        item.review_count += 1
        item.updated_at = datetime.now(UTC)

        # 如果 quality >= 4 且重复次数 >= 3，视为已掌握
        if quality >= 4 and repetition >= 3:
            item.is_resolved = True
            item.resolved_at = datetime.now(UTC)

        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)

        return next_review

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    async def _get_due_errors(self, student_id: int) -> list[ErrorBookItem]:
        """获取该学生已到期的错题."""
        now = datetime.now(UTC)
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
        result = await self.session.exec(stmt)
        return list(result.all())

    async def _get_recent_exercise_knowledge_points(self, student_id: int) -> list[int]:
        """获取最近 7 天已练习的知识点 ID（去重）."""
        since = datetime.now(UTC) - timedelta(days=7)
        stmt = (
            select(Exercise.target_knowledge_point_ids)
            .where(
                Exercise.student_id == student_id,
                Exercise.assigned_at >= since,
            )
        )
        result = await self.session.exec(stmt)
        kp_ids: set[int] = set()
        for row in result.all():
            ids = row or []
            kp_ids.update(ids)
        return list(kp_ids)

    async def _get_new_knowledge_candidates(
        self,
        student_id: int,
        weak_kp_ids: list[int],
        recent_kp_ids: list[int],
    ) -> list[int]:
        """获取新知预习候选知识点（已掌握但近期未练的相邻知识点）."""
        # 查询已掌握的知识点
        mastered_stmt = (
            select(StudentKnowledgeState.knowledge_point_id)
            .where(
                StudentKnowledgeState.student_id == student_id,
                StudentKnowledgeState.status == MasteryStatus.mastered,
            )
        )
        result = await self.session.exec(mastered_stmt)
        mastered_ids = [r.knowledge_point_id for r in result.all()]

        # 排除薄弱和最近已练的
        exclude = set(weak_kp_ids + recent_kp_ids)
        candidates = [kp_id for kp_id in mastered_ids if kp_id not in exclude]

        if not candidates:
            # 如果没有已掌握且未练的，随机选一些未接触的知识点
            all_kp_stmt = select(KnowledgePoint.id).where(KnowledgePoint.is_deleted.is_(False))
            all_result = await self.session.exec(all_kp_stmt)
            all_ids = [r.id for r in all_result.all()]
            candidates = [kp_id for kp_id in all_ids if kp_id not in exclude]

        random.shuffle(candidates)
        return candidates
