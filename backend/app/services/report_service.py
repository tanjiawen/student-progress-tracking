"""报告服务 — 负责诊断报告的生成、趋势分析等."""

from __future__ import annotations

import datetime
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.exam import Exam
from app.models.grading_result import ErrorType, GradingResult
from app.models.report import GeneratedBy, Report, ReportType
from app.models.submission import Submission
from app.repositories.exam import ExamRepository
from app.repositories.grading_result import GradingResultRepository
from app.repositories.report import ReportRepository
from app.repositories.student import StudentRepository
from app.repositories.student_knowledge_state import (
    StudentKnowledgeStateRepository,
)
from app.services.answer_card_analyzer import AnswerCardAnalyzer


class ReportService:
    """诊断报告业务服务，聚合判卷结果与知识状态生成结构化报告."""

    def __init__(self, session: AsyncSession) -> None:
        self.report_repo = ReportRepository(session)
        self.grading_result_repo = GradingResultRepository(session)
        self.knowledge_state_repo = StudentKnowledgeStateRepository(session)
        self.student_repo = StudentRepository(session)
        self.exam_repo = ExamRepository(session)
        self.session = session

    async def generate_single_exam_report(
        self, student_id: int, exam_id: int
    ) -> dict:
        """聚合数据 → 调用 AnswerCardAnalyzer → 保存 Report.

        Args:
            student_id: 学生 ID
            exam_id: 考试 ID

        Returns:
            dict: 生成后的报告摘要
        """
        student = await self.student_repo.get_by_id(student_id)
        if not student:
            raise NotFoundException(f"学生 {student_id} 不存在")

        exam = await self.exam_repo.get_by_id(exam_id)
        if not exam:
            raise NotFoundException(f"考试 {exam_id} 不存在")

        # 聚合该学生在该考试下的所有 submission + grading_result
        statement = (
            select(Submission, GradingResult)
            .outerjoin(
                GradingResult,
                Submission.id == GradingResult.submission_id,
            )
            .where(
                Submission.exam_id == exam_id,
                Submission.student_id == student_id,
            )
        )
        result = await self.session.exec(statement)
        rows = result.all()

        if not rows:
            raise BadRequestException(
                f"学生 {student_id} 在考试 {exam_id} 下无作答记录"
            )

        # 构造 AnswerCardAnalyzer 所需的结构化数据
        sections: list[dict[str, Any]] = []
        questions: list[dict[str, Any]] = []
        total_score = 0.0
        max_total = 0.0

        for submission, grading in rows:
            q_score = float(grading.score) if grading else 0.0
            q_max = float(grading.max_score) if grading else float(submission.exam_question.score) if submission.exam_question else 0.0
            total_score += q_score
            max_total += q_max

            issues = []
            if grading and grading.error_type != ErrorType.CORRECT:
                issues.append(grading.error_type.value)

            questions.append({
                "number": submission.exam_question.sequence_number if submission.exam_question else 0,
                "score": q_score,
                "max_score": q_max,
                "issues": issues,
                "knowledge_points": grading.knowledge_point_ids if grading else [],
                "student_answer": submission.answer_text or "",
            })

        sections.append({"questions": questions})

        ocr_data = {
            "student_info": {
                "name": student.student_number,
                "class": str(student.class_id) if student.class_id else "",
            },
            "exam_info": {
                "title": exam.title,
                "subject": str(exam.subject_id),
                "total_score": total_score,
                "max_score": max_total,
            },
            "sections": sections,
        }

        analyzer = AnswerCardAnalyzer()
        try:
            card_report = await analyzer.generate_full_report(ocr_data)
        finally:
            await analyzer.close()

        learning = card_report.learning_analysis
        weak_points = (
            [{"name": w, "type": "weak"} for w in learning.weak_knowledge]
            if learning
            else []
        )

        error_distribution: dict[str, int] = {}
        for _, grading in rows:
            if grading:
                key = grading.error_type.value
                error_distribution[key] = error_distribution.get(key, 0) + 1

        report = Report(
            student_id=student_id,
            exam_id=exam_id,
            report_type=ReportType.single_exam,
            title=f"{exam.title} 诊断报告",
            overall_comment=learning.overall_evaluation if learning else "",
            total_score=total_score,
            max_score=max_total,
            weak_points=weak_points,
            error_distribution=error_distribution,
            trend_data={},
            radar_data={
                "dimensions": [
                    {
                        "name": k.knowledge_point,
                        "mastery": k.mastery_level,
                    }
                    for k in card_report.knowledge_mastery
                ]
            }
            if card_report.knowledge_mastery
            else {},
            recommendations=[
                {"term": "short", "content": s}
                for s in (learning.short_term_suggestions if learning else [])
            ]
            + [
                {"term": "mid", "content": s}
                for s in (learning.mid_term_suggestions if learning else [])
            ]
            + [
                {"term": "long", "content": s}
                for s in (learning.long_term_suggestions if learning else [])
            ],
            generated_by=GeneratedBy.ai,
            ai_model=learning.model if learning else "",
            usage=learning.usage if learning else {},
        )

        saved = await self.report_repo.create(report)

        return {
            "report_id": saved.id,
            "student_id": student_id,
            "exam_id": exam_id,
            "title": saved.title,
            "total_score": float(saved.total_score) if saved.total_score else None,
            "max_score": float(saved.max_score) if saved.max_score else None,
            "created_at": saved.created_at,
        }

    async def get_student_trend(self, student_id: int, months: int = 3) -> dict:
        """获取最近 N 个月的考试成绩趋势.

        Args:
            student_id: 学生 ID
            months: 回溯月数，默认 3 个月

        Returns:
            dict: 趋势数据
        """
        student = await self.student_repo.get_by_id(student_id)
        if not student:
            raise NotFoundException(f"学生 {student_id} 不存在")

        since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            days=months * 30
        )

        statement = (
            select(Exam, Submission, GradingResult)
            .join(Submission, Exam.id == Submission.exam_id)
            .outerjoin(
                GradingResult,
                Submission.id == GradingResult.submission_id,
            )
            .where(
                Submission.student_id == student_id,
                Exam.exam_date >= since,
            )
            .order_by(Exam.exam_date)
        )
        result = await self.session.exec(statement)
        rows = result.all()

        trend_items: list[dict[str, Any]] = []
        for exam, submission, grading in rows:
            trend_items.append(
                {
                    "exam_id": exam.id,
                    "exam_title": exam.title,
                    "exam_date": exam.exam_date.isoformat()
                    if exam.exam_date
                    else None,
                    "score": float(grading.score) if grading else None,
                    "max_score": float(grading.max_score)
                    if grading
                    else None,
                    "error_type": grading.error_type.value if grading else None,
                }
            )

        # 按考试汇总总分
        exam_scores: dict[int, dict[str, Any]] = {}
        for item in trend_items:
            eid = item["exam_id"]
            if eid not in exam_scores:
                exam_scores[eid] = {
                    "exam_id": eid,
                    "exam_title": item["exam_title"],
                    "exam_date": item["exam_date"],
                    "total_score": 0.0,
                    "max_score": 0.0,
                }
            if item["score"] is not None:
                exam_scores[eid]["total_score"] += item["score"]
            if item["max_score"] is not None:
                exam_scores[eid]["max_score"] += item["max_score"]

        summaries = sorted(
            exam_scores.values(),
            key=lambda x: x["exam_date"] or "",
        )

        return {
            "student_id": student_id,
            "months": months,
            "exam_count": len(summaries),
            "trend": [
                {
                    "exam_id": s["exam_id"],
                    "exam_title": s["exam_title"],
                    "exam_date": s["exam_date"],
                    "total_score": round(s["total_score"], 2),
                    "max_score": round(s["max_score"], 2),
                    "score_rate": (
                        round(s["total_score"] / s["max_score"], 4)
                        if s["max_score"] > 0
                        else 0
                    ),
                }
                for s in summaries
            ],
        }
