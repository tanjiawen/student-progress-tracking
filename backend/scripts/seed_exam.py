#!/usr/bin/env python3
"""测试考试数据注入脚本.

基于 test/answer_card_ocr_result.json 创建考试、题目、作答、判卷、
知识点状态、错题本及诊断报告.

用法:
    cd backend && .venv/bin/python scripts/seed_exam.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
BACKEND_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import async_session
from app.models import (
    Class,
    ErrorBookItem,
    ErrorType,
    Exam,
    ExamQuestion,
    ExamQuestionStatus,
    ExamStatus,
    ExamType,
    GeneratedBy,
    GradingResult,
    GradingStatus,
    KnowledgePoint,
    QuestionType,
    Report,
    ReportType,
    Student,
    StudentKnowledgeState,
    Subject,
    Submission,
    User,
)
from app.models.student_knowledge_state import MasteryStatus

OCR_JSON_PATH = PROJECT_ROOT / "test" / "answer_card_ocr_result.json"

# 简化的知识点映射（题目 -> 知识点编码列表）
# 仅用于演示，实际应由 AI 判卷时动态提取
QUESTION_KP_MAP: dict[int, list[str]] = {
    19: ["POL-8B-1-2-1", "POL-8B-1-1-1", "POL-8B-3-2-1"],
    20: ["POL-8B-2-1-1", "POL-8B-2-1-2"],
    21: ["POL-8B-1-1-1", "POL-8B-1-1-2", "POL-8B-3-1-2"],
    22: ["POL-8B-3-2-1", "POL-8B-3-2-2"],
}


def load_ocr_data() -> dict:
    if not OCR_JSON_PATH.exists():
        raise FileNotFoundError(f"OCR 数据文件不存在: {OCR_JSON_PATH}")
    with open(OCR_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


async def get_pol_subject_id(session: AsyncSession) -> int:
    stmt = select(Subject).where(Subject.code == "POL")
    result = await session.exec(stmt)
    subj = result.first()
    if not subj:
        raise ValueError("学科 'POL' 不存在，请先运行 seed_data.py")
    return subj.id


async def get_target_class_id(session: AsyncSession) -> int:
    stmt = select(Class).where(Class.name == "八(28)班")
    result = await session.exec(stmt)
    cls = result.first()
    if not cls:
        raise ValueError("班级 '八(28)班' 不存在，请先运行 seed_data.py")
    return cls.id


async def get_target_student_id(session: AsyncSession) -> int:
    stmt = select(Student).where(Student.student_number == "24022845")
    result = await session.exec(stmt)
    student = result.first()
    if not student:
        raise ValueError("学生 '24022845' 不存在，请先运行 seed_data.py")
    return student.id


async def get_teacher_id(session: AsyncSession) -> int:
    stmt = select(User).where(User.username == "teacher1")
    result = await session.exec(stmt)
    user = result.first()
    if not user:
        raise ValueError("用户 'teacher1' 不存在，请先运行 seed_data.py")
    return user.id


async def get_kp_id_map(session: AsyncSession) -> dict[str, int]:
    stmt = select(KnowledgePoint)
    result = await session.exec(stmt)
    return {kp.code: kp.id for kp in result.all()}


async def seed_exam_record(
    session: AsyncSession,
    ocr_data: dict,
    subject_id: int,
    class_id: int,
    teacher_id: int,
) -> int:
    print("📝 注入考试记录...")
    exam_info = ocr_data["exam_info"]
    stmt = select(Exam).where(Exam.title == exam_info["title"])
    result = await session.exec(stmt)
    existing = result.first()
    if existing:
        print(f"   ⚠️ 考试已存在: {existing.title} (id={existing.id})")
        return existing.id

    exam = Exam(
        title=exam_info["title"],
        subject_id=subject_id,
        class_id=class_id,
        exam_type=ExamType.MIDTERM,
        total_score=exam_info["max_score"],
        status=ExamStatus.GRADED,
        exam_date=datetime(2026, 4, 15, 9, 0, 0, tzinfo=timezone.utc),
        created_by=teacher_id,
    )
    session.add(exam)
    await session.commit()
    await session.refresh(exam)
    print(f"   ✅ 创建考试: {exam.title} (id={exam.id})")
    return exam.id


async def seed_exam_questions(
    session: AsyncSession, exam_id: int, ocr_data: dict
) -> list[ExamQuestion]:
    print("📝 注入试卷题目...")
    questions: list[ExamQuestion] = []

    for section in ocr_data["sections"]:
        for q in section["questions"]:
            stmt = select(ExamQuestion).where(
                ExamQuestion.exam_id == exam_id,
                ExamQuestion.sequence_number == q["number"],
            )
            result = await session.exec(stmt)
            existing = result.first()
            if existing:
                print(
                    f"   ⚠️ 题目已存在: 第{existing.sequence_number}题 (id={existing.id})"
                )
                questions.append(existing)
                continue

            qtype = (
                QuestionType.CHOICE
                if q.get("type") == "choice"
                else QuestionType.SHORT_ANSWER
            )
            content = q.get("title", f"{section['section_title']}第{q['number']}题")

            eq = ExamQuestion(
                exam_id=exam_id,
                sequence_number=q["number"],
                question_type=qtype,
                content=content,
                score=q.get("max_score", 0),
                status=ExamQuestionStatus.CORRECTED,
            )
            session.add(eq)
            await session.commit()
            await session.refresh(eq)
            print(f"   ✅ 创建题目: 第{eq.sequence_number}题 (id={eq.id})")
            questions.append(eq)

    return questions


def _determine_error_type(
    question_num: int, score: float, max_score: float, sections: list
) -> ErrorType:
    if score >= max_score:
        return ErrorType.CORRECT

    # 选择题错误
    if question_num <= 18:
        return ErrorType.CONCEPT_ERROR

    # 根据 OCR 中的 feedback/issues 判断
    for section in sections:
        for q in section.get("questions", []):
            if q["number"] != question_num:
                continue
            feedback = ""
            issues: list[str] = []
            for sq in q.get("sub_questions", []):
                feedback += sq.get("feedback", "")
                issues.extend(sq.get("issues", []))
            full_text = feedback + " " + " ".join(issues)
            if "概念混淆" in full_text or "混淆" in full_text:
                return ErrorType.CONCEPT_ERROR
            if "逻辑" in full_text or "混乱" in full_text:
                return ErrorType.LOGIC_BREAK
            if "不完整" in full_text or "缺少" in full_text:
                return ErrorType.INCOMPLETE
            if "字迹不清" in full_text or "无法辨认" in full_text:
                return ErrorType.UNCLEAR

    return ErrorType.UNKNOWN


async def seed_submissions_and_grading(
    session: AsyncSession,
    exam_id: int,
    student_id: int,
    questions: list[ExamQuestion],
    ocr_data: dict,
    kp_id_map: dict[str, int],
) -> list[GradingResult]:
    print("✍️  注入作答与判卷结果...")

    # 构建题目得分映射
    score_map: dict[int, dict] = {}
    for section in ocr_data["sections"]:
        for q in section.get("questions", []):
            score_map[q["number"]] = q

    grading_results: list[GradingResult] = []

    for eq in questions:
        qdata = score_map.get(eq.sequence_number, {})
        student_score = qdata.get("score", 0)
        max_score = qdata.get("max_score", eq.score)
        answer_text = str(qdata.get("student_answer", ""))

        # 主观题无 student_answer 字段，用空字符串
        if eq.question_type == QuestionType.SHORT_ANSWER:
            answer_text = ""

        stmt = select(Submission).where(
            Submission.exam_id == exam_id,
            Submission.student_id == student_id,
            Submission.exam_question_id == eq.id,
        )
        result = await session.exec(stmt)
        sub = result.first()
        if sub:
            print(
                f"   ⚠️ 作答已存在: 第{eq.sequence_number}题 (submission_id={sub.id})"
            )
        else:
            sub = Submission(
                exam_id=exam_id,
                student_id=student_id,
                exam_question_id=eq.id,
                answer_text=answer_text,
                grading_status=GradingStatus.GRADED,
            )
            session.add(sub)
            await session.commit()
            await session.refresh(sub)
            print(
                f"   ✅ 创建作答: 第{eq.sequence_number}题 (submission_id={sub.id})"
            )

        # 检查是否已有判卷结果
        stmt_gr = select(GradingResult).where(
            GradingResult.submission_id == sub.id
        )
        result_gr = await session.exec(stmt_gr)
        if result_gr.first():
            print(f"   ⚠️ 判卷结果已存在: submission_id={sub.id}")
            continue

        error_type = _determine_error_type(
            eq.sequence_number, student_score, max_score, ocr_data["sections"]
        )
        is_correct = student_score >= max_score

        # 知识点映射
        kp_codes = QUESTION_KP_MAP.get(eq.sequence_number, [])
        kp_ids = [kp_id_map[c] for c in kp_codes if c in kp_id_map]

        gr = GradingResult(
            submission_id=sub.id,
            is_correct=is_correct,
            score=student_score,
            max_score=max_score,
            error_type=error_type,
            knowledge_point_ids=kp_ids or None,
            confidence=0.95,
            ai_model="deepseek-chat",
        )
        session.add(gr)
        await session.commit()
        await session.refresh(gr)
        print(
            f"   ✅ 创建判卷: 第{eq.sequence_number}题 "
            f"得分{student_score}/{max_score} [{error_type.value}]"
        )
        grading_results.append(gr)

    return grading_results


async def seed_student_knowledge_states(
    session: AsyncSession,
    student_id: int,
    kp_id_map: dict[str, int],
) -> None:
    print("🧠 注入知识点掌握状态...")

    # 基于判卷结果模拟的掌握度（简化映射）
    kp_performance: list[tuple[str, float, int, int, str | None]] = [
        ("POL-8B-1-1-1", 0.70, 2, 1, None),
        ("POL-8B-1-1-2", 0.70, 2, 1, None),
        ("POL-8B-1-2-1", 0.60, 2, 1, "incomplete"),
        ("POL-8B-1-2-2", 0.50, 1, 0, "concept_error"),
        ("POL-8B-2-1-1", 0.90, 2, 2, None),
        ("POL-8B-2-1-2", 0.85, 2, 2, None),
        ("POL-8B-2-2-1", 0.75, 2, 1, None),
        ("POL-8B-3-1-1", 0.60, 2, 1, "incomplete"),
        ("POL-8B-3-1-2", 0.50, 2, 1, "logic_break"),
        ("POL-8B-3-2-1", 0.50, 2, 1, "concept_error"),
        ("POL-8B-3-2-2", 0.60, 2, 1, None),
        ("POL-8B-4-1", 0.70, 1, 1, None),
        ("POL-8B-4-2", 0.70, 1, 1, None),
    ]

    for code, prob, attempts, correct, last_err in kp_performance:
        kp_id = kp_id_map.get(code)
        if not kp_id:
            continue

        stmt = select(StudentKnowledgeState).where(
            StudentKnowledgeState.student_id == student_id,
            StudentKnowledgeState.knowledge_point_id == kp_id,
        )
        result = await session.exec(stmt)
        existing = result.first()
        if existing:
            print(f"   ⚠️ 知识点状态已存在: {code}")
            continue

        status = (
            MasteryStatus.mastered
            if prob >= 0.8
            else MasteryStatus.weak
            if prob < 0.6
            else MasteryStatus.normal
        )

        sks = StudentKnowledgeState(
            student_id=student_id,
            knowledge_point_id=kp_id,
            mastery_probability=prob,
            total_attempts=attempts,
            correct_count=correct,
            consecutive_correct=correct,
            last_error_type=last_err,
            status=status,
        )
        session.add(sks)
        await session.commit()
        print(
            f"   ✅ 创建知识点状态: {code} 掌握度={prob:.0%} [{status.value}]"
        )


async def seed_error_book_items(
    session: AsyncSession,
    exam_id: int,
    student_id: int,
    questions: list[ExamQuestion],
    grading_results: list[GradingResult],
) -> None:
    print("📕 注入错题本...")
    for eq, gr in zip(questions, grading_results):
        if gr.error_type == ErrorType.CORRECT:
            continue

        stmt = select(ErrorBookItem).where(
            ErrorBookItem.student_id == student_id,
            ErrorBookItem.exam_id == exam_id,
            ErrorBookItem.exam_question_id == eq.id,
        )
        result = await session.exec(stmt)
        if result.first():
            print(f"   ⚠️ 错题已存在: 第{eq.sequence_number}题")
            continue

        item = ErrorBookItem(
            student_id=student_id,
            exam_id=exam_id,
            exam_question_id=eq.id,
            error_type=gr.error_type.value,
        )
        session.add(item)
        await session.commit()
        print(f"   ✅ 创建错题: 第{eq.sequence_number}题 [{gr.error_type.value}]")


async def seed_report(
    session: AsyncSession,
    exam_id: int,
    student_id: int,
    ocr_data: dict,
) -> None:
    print("📊 注入诊断报告...")
    stmt = select(Report).where(
        Report.student_id == student_id,
        Report.exam_id == exam_id,
        Report.report_type == ReportType.single_exam,
    )
    result = await session.exec(stmt)
    if result.first():
        print("   ⚠️ 诊断报告已存在")
        return

    exam_info = ocr_data["exam_info"]
    report = Report(
        student_id=student_id,
        exam_id=exam_id,
        report_type=ReportType.single_exam,
        title=f"{exam_info['title']}诊断报告",
        overall_comment="本次考试总体表现中等，选择题后半部分失分较多，主观题存在概念混淆和表述不完整的问题。",
        total_score=exam_info["total_score"],
        max_score=exam_info["max_score"],
        weak_points=[
            {"name": "宪法是根本法", "severity": "medium"},
            {"name": "全国人大的立法权", "severity": "high"},
            {"name": "民族区域自治制度", "severity": "high"},
            {"name": "基层群众自治制度", "severity": "medium"},
        ],
        error_distribution={
            "concept_error": 5,
            "incomplete": 3,
            "logic_break": 2,
            "unclear": 2,
        },
        trend_data={},
        radar_data={
            "labels": [
                "宪法知识",
                "权利义务",
                "政治制度",
                "法治精神",
                "选择题",
            ],
            "values": [55, 85, 50, 70, 78],
        },
        recommendations=[
            {"type": "review", "content": "重点复习第一单元宪法相关知识，区分宪法与其他法律的地位关系。"},
            {"type": "practice", "content": "加强第三单元政治制度部分的辨析练习，避免概念混淆。"},
            {"type": "habit", "content": "答题时注意表述完整性，分点作答，引用法律依据。"},
        ],
        generated_by=GeneratedBy.ai,
        ai_model="deepseek-chat",
    )
    session.add(report)
    await session.commit()
    print("   ✅ 创建诊断报告")


async def main() -> None:
    print("=" * 50)
    print("📝 开始注入测试考试数据")
    print("=" * 50)

    ocr_data = load_ocr_data()
    exam_info = ocr_data["exam_info"]
    student_info = ocr_data["student_info"]
    print(f"📄 OCR 数据源: {OCR_JSON_PATH.name}")
    print(f"   考试: {exam_info['title']}")
    print(f"   学生: {student_info['name']} ({student_info['class']})")
    print(f"   得分: {exam_info['total_score']} / {exam_info['max_score']}")

    try:
        async with async_session() as session:
            subject_id = await get_pol_subject_id(session)
            class_id = await get_target_class_id(session)
            student_id = await get_target_student_id(session)
            teacher_id = await get_teacher_id(session)
            kp_id_map = await get_kp_id_map(session)

            print()
            exam_id = await seed_exam_record(
                session, ocr_data, subject_id, class_id, teacher_id
            )

            print()
            questions = await seed_exam_questions(session, exam_id, ocr_data)

            print()
            grading_results = await seed_submissions_and_grading(
                session, exam_id, student_id, questions, ocr_data, kp_id_map
            )

            print()
            await seed_student_knowledge_states(session, student_id, kp_id_map)

            print()
            await seed_error_book_items(
                session, exam_id, student_id, questions, grading_results
            )

            print()
            await seed_report(session, exam_id, student_id, ocr_data)

        print("\n" + "=" * 50)
        print("🎉 测试考试数据注入完成!")
        print("=" * 50)
    except Exception as e:
        print(f"\n❌ 考试数据注入失败: {type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
