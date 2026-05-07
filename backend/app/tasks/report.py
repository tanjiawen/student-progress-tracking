import asyncio
import json
import logging
from typing import Any

from celery_worker import celery_app

from app.ai.gateway import LLMGateway, LLMMessage, LLMRequest
from app.db import SessionLocal
from app.models.exam import Exam
from app.models.grading_result import GradingResult
from app.models.report import GeneratedBy, Report, ReportType
from app.models.submission import GradingStatus, Submission
from app.services.answer_card_analyzer import AnswerCardAnalyzer

logger = logging.getLogger(__name__)


def _run_async(coro):
    return asyncio.run(coro)


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
)
def generate_report(self, report_id: int) -> dict[str, Any]:
    """生成诊断报告任务."""
    logger.info("Start generating report_id=%s", report_id)
    db = SessionLocal()
    analyzer = AnswerCardAnalyzer()
    try:
        report = db.get(Report, report_id)
        if not report:
            raise ValueError(f"Report {report_id} not found")

        # 聚合学生判卷结果
        submissions = (
            db.query(Submission)
            .filter(
                Submission.student_id == report.student_id,
                Submission.grading_status == GradingStatus.GRADED,
            )
            .all()
        )

        grading_results: list[GradingResult] = []
        if submissions:
            submission_ids = [s.id for s in submissions]
            grading_results = (
                db.query(GradingResult)
                .filter(GradingResult.submission_id.in_(submission_ids))
                .all()
            )

        # 构建错题数据
        wrong_questions = []
        submission_map = {s.id: s for s in submissions}
        for gr in grading_results:
            if not gr.is_correct:
                sub = submission_map.get(gr.submission_id)
                wrong_questions.append(
                    {
                        "question_id": sub.exam_question_id if sub else None,
                        "score": gr.score,
                        "max_score": gr.max_score,
                        "error_type": gr.error_type.value if gr.error_type else "",
                        "knowledge_points": gr.knowledge_point_ids,
                    }
                )

        self.update_state(
            state="PROGRESS",
            meta={"current": 1, "total": 3, "stage": "analyzing"},
        )

        exam = db.get(Exam, report.exam_id) if report.exam_id else None

        if wrong_questions:
            ocr_data = {
                "student_info": {"student_id": report.student_id},
                "exam_info": {
                    "exam_id": report.exam_id,
                    "title": exam.title if exam else report.title,
                },
                "sections": [
                    {
                        "questions": [
                            {
                                "number": i + 1,
                                "score": wq["score"],
                                "max_score": wq["max_score"],
                                "sub_questions": [
                                    {
                                        "sub_number": "",
                                        "score": wq["score"],
                                        "max_score": wq["max_score"],
                                        "issues": [wq["error_type"] or "未知错误"],
                                        "knowledge_points": wq["knowledge_points"]
                                        or [],
                                    }
                                ],
                            }
                            for i, wq in enumerate(wrong_questions)
                        ]
                    }
                ],
            }

            full_report = _run_async(analyzer.generate_full_report(ocr_data))

            report.weak_points = [
                {
                    "knowledge_point": k.knowledge_point,
                    "mastery_level": k.mastery_level,
                    "priority_review": k.priority_review,
                }
                for k in full_report.knowledge_mastery
            ]
            report.error_distribution = {
                "overall_evaluation": (
                    full_report.learning_analysis.overall_evaluation
                    if full_report.learning_analysis
                    else ""
                ),
                "mastered_knowledge": (
                    full_report.learning_analysis.mastered_knowledge
                    if full_report.learning_analysis
                    else []
                ),
                "weak_knowledge": (
                    full_report.learning_analysis.weak_knowledge
                    if full_report.learning_analysis
                    else []
                ),
            }
            report.recommendations = [
                {
                    "type": "short_term",
                    "content": s,
                }
                for s in (
                    full_report.learning_analysis.short_term_suggestions
                    if full_report.learning_analysis
                    else []
                )
            ] + [
                {
                    "type": "mid_term",
                    "content": s,
                }
                for s in (
                    full_report.learning_analysis.mid_term_suggestions
                    if full_report.learning_analysis
                    else []
                )
            ]
            report.radar_data = {
                "knowledge_mastery": [
                    k.to_dict() for k in full_report.knowledge_mastery
                ]
            }
            report.overall_comment = (
                full_report.learning_analysis.overall_evaluation
                if full_report.learning_analysis
                else ""
            )
        else:
            prompt = f"""请为学生 {report.student_id} 生成一份学情诊断报告。
考试: {report.exam_id}
报告类型: {report.report_type.value if isinstance(report.report_type, ReportType) else report.report_type}

请输出 JSON 格式：
{{
  "overall_evaluation": "总体评价",
  "mastered_knowledge": [],
  "weak_knowledge": [],
  "suggestions": []
}}"""

            request = LLMRequest(
                messages=[
                    LLMMessage(
                        role="system", content="你是一位教育分析师。"
                    ),
                    LLMMessage(role="user", content=prompt),
                ],
                model="deepseek-chat",
                max_tokens=2048,
                temperature=0.3,
            )
            response = _run_async(
                analyzer.gateway.chat(request, preferred_provider="deepseek")
            )
            try:
                parsed = json.loads(response.content)
            except json.JSONDecodeError:
                parsed = {}

            report.overall_comment = parsed.get("overall_evaluation", "")
            report.weak_points = [
                {"knowledge_point": kp, "mastery_level": 0.0}
                for kp in parsed.get("weak_knowledge", [])
            ]
            report.recommendations = [
                {"type": "general", "content": s}
                for s in parsed.get("suggestions", [])
            ]

        report.generated_by = GeneratedBy.ai
        db.add(report)
        db.commit()

        logger.info("Report generated: id=%s", report_id)
        return {
            "success": True,
            "report_id": report_id,
        }

    except Exception as exc:
        logger.exception("Report generation failed for id=%s", report_id)
        raise self.retry(exc=exc)

    finally:
        db.close()
        _run_async(analyzer.close())
