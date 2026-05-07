from __future__ import annotations

"""定时任务调度 —— Celery Beat."""

import asyncio
import logging
from datetime import UTC, datetime

from celery.schedules import crontab
from sqlalchemy import select

from celery_worker import celery_app
from app.db import SessionLocal
from app.models.error_book_item import ErrorBookItem
from app.models.exercise import Exercise
from app.models.report import Report, ReportType
from app.models.student import Student
from app.services.adaptive_push import AdaptivePushService
from app.services.report_service import ReportService

logger = logging.getLogger(__name__)


def _run_async(coro):
    return asyncio.run(coro)


# ------------------------------------------------------------------
# Celery Beat Schedule
# ------------------------------------------------------------------

celery_app.conf.beat_schedule = {
    "daily-exercise-plan": {
        "task": "app.tasks.scheduler.generate_daily_plans",
        "schedule": crontab(hour=8, minute=0),  # 每天早上 8 点
    },
    "review-reminder": {
        "task": "app.tasks.scheduler.send_review_reminders",
        "schedule": crontab(hour=19, minute=0),  # 每天晚上 7 点
    },
    "weekly-report": {
        "task": "app.tasks.scheduler.generate_weekly_reports",
        "schedule": crontab(day_of_week=0, hour=21, minute=0),  # 每周日晚上 9 点
    },
}


# ------------------------------------------------------------------
# 任务实现
# ------------------------------------------------------------------

@celery_app.task(bind=True)
def generate_daily_plans(self) -> dict:
    """每天早上 8 点为所有学生生成每日练习计划."""
    logger.info("[Scheduler] Start generating daily plans")
    db = SessionLocal()
    try:
        students = db.query(Student).all()
        success = 0
        failed = 0

        for student in students:
            try:
                # AdaptivePushService 需要 AsyncSession，这里用同步兼容方式
                # 实际项目中建议拆分为纯同步 repository 或单独 async worker
                # 这里简化为直接创建 Exercise 记录（跳过 LLM 生成）
                plan = _run_async(
                    _async_generate_daily_plan_for_student(student.id)
                )
                success += 1
                logger.debug("Daily plan generated for student_id=%s", student.id)
            except Exception as exc:
                failed += 1
                logger.warning("Daily plan failed for student_id=%s: %s", student.id, exc)

        logger.info("[Scheduler] Daily plans done: success=%s, failed=%s", success, failed)
        return {"success": success, "failed": failed}

    finally:
        db.close()


async def _async_generate_daily_plan_for_student(student_id: int) -> dict:
    """异步包装：生成单个学生的每日计划."""
    from app.core.database import async_engine
    from sqlmodel.ext.asyncio.session import AsyncSession

    async with AsyncSession(async_engine) as session:
        service = AdaptivePushService(session)
        return await service.generate_daily_plan(student_id)


@celery_app.task(bind=True)
def send_review_reminders(self) -> dict:
    """每天晚上 7 点发送错题复习提醒."""
    logger.info("[Scheduler] Start sending review reminders")
    db = SessionLocal()
    try:
        now = datetime.now(UTC)
        # 查询今天需要复习的错题
        due_items = (
            db.query(ErrorBookItem)
            .filter(
                ErrorBookItem.is_resolved.is_(False),
                ErrorBookItem.next_review_at.isnot(None),
                ErrorBookItem.next_review_at <= now,
            )
            .all()
        )

        # 按学生分组
        student_map: dict[int, int] = {}
        for item in due_items:
            student_map[item.student_id] = student_map.get(item.student_id, 0) + 1

        # 推送通知（日志模拟，实际可接入 WebSocket/APNs/FCM）
        for student_id, count in student_map.items():
            logger.info(
                "[Reminder] student_id=%s has %s due reviews today",
                student_id,
                count,
            )

        logger.info("[Scheduler] Review reminders sent to %s students", len(student_map))
        return {"student_count": len(student_map), "total_items": len(due_items)}

    finally:
        db.close()


@celery_app.task(bind=True)
def generate_weekly_reports(self) -> dict:
    """每周日晚上 9 点生成周报告."""
    logger.info("[Scheduler] Start generating weekly reports")
    db = SessionLocal()
    try:
        # 获取本周有作答的学生
        from datetime import timedelta
        since = datetime.now(UTC) - timedelta(days=7)

        from app.models.submission import Submission
        student_ids = (
            db.query(Submission.student_id)
            .filter(Submission.created_at >= since)
            .distinct()
            .all()
        )
        student_ids = [s[0] for s in student_ids]

        success = 0
        failed = 0
        for sid in student_ids:
            try:
                _run_async(_async_generate_weekly_report(sid))
                success += 1
            except Exception as exc:
                failed += 1
                logger.warning("Weekly report failed for student_id=%s: %s", sid, exc)

        logger.info("[Scheduler] Weekly reports done: success=%s, failed=%s", success, failed)
        return {"success": success, "failed": failed}

    finally:
        db.close()


async def _async_generate_weekly_report(student_id: int) -> dict:
    """异步包装：生成单个学生的周报告."""
    from app.core.database import async_engine
    from sqlmodel.ext.asyncio.session import AsyncSession

    async with AsyncSession(async_engine) as session:
        service = ReportService(session)
        # 取最近一场考试生成单次考试报告作为周报告示例
        from app.models.submission import Submission
        from sqlalchemy import desc
        stmt = (
            select(Submission.exam_id)
            .where(Submission.student_id == student_id)
            .order_by(desc(Submission.created_at))
            .limit(1)
        )
        result = await session.exec(stmt)
        row = result.first()
        if row and row.exam_id:
            summary = await service.generate_single_exam_report(student_id, row.exam_id)
            return summary
        return {"student_id": student_id, "message": "No recent exam found"}
