"""Service layer unit tests."""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.exam import Exam, ExamStatus, ExamType
from app.models.user import User, UserRole
from app.repositories.exam import ExamRepository
from app.repositories.user import UserRepository
from app.services.answer_card_analyzer import AnswerCardAnalyzer
from app.services.grading_engine import GradingResult, grading_engine
from app.services.knowledge_tracker import knowledge_tracker


@pytest.mark.asyncio
async def test_exam_service_create_exam(db_session: AsyncSession) -> None:
    """ExamRepository create with a test session."""
    repo = ExamRepository(db_session)
    exam = Exam(
        title="单元测试考试",
        subject_id=1,
        class_id=1,
        exam_type=ExamType.QUIZ,
        total_score=100.0,
        status=ExamStatus.DRAFT,
        exam_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
        created_by=1,
    )
    created = await repo.create(exam)
    assert created.id is not None
    assert created.title == "单元测试考试"


@pytest.mark.asyncio
async def test_grading_engine_grade_choice() -> None:
    """Objective choice question grading."""
    result = grading_engine._grade_objective(
        question_type="choice",
        standard_answer="A",
        student_answer="A",
        max_score=5.0,
    )
    assert isinstance(result, GradingResult)
    assert result.is_correct is True
    assert result.score == 5.0
    assert result.error_type == "correct"

    result_wrong = grading_engine._grade_objective(
        question_type="choice",
        standard_answer="A",
        student_answer="B",
        max_score=5.0,
    )
    assert result_wrong.is_correct is False
    assert result_wrong.score == 0.0


@pytest.mark.asyncio
async def test_grading_engine_grade_subjective() -> None:
    """Subjective question grading with mocked LLM."""
    mock_response = (
        '{"is_correct": true, "score": 8, "error_type": "correct", '
        '"error_detail": "基本正确", "knowledge_points": [1], '
        '"suggestion": "注意格式", "confidence": 0.9}'
    )

    with patch.object(
        grading_engine,
        "_call_llm",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        result = await grading_engine.grade(
            question_type="calculation",
            question_content="求 y = x^2 的导数",
            standard_answer="2x",
            student_answer="2x",
            max_score=10.0,
        )

    assert isinstance(result, GradingResult)
    assert result.score == 8.0
    assert result.error_type == "correct"
    assert result.confidence == 0.9


@pytest.mark.asyncio
async def test_knowledge_tracker_update() -> None:
    """BKT update formula validation."""
    student_id = 42
    kp_id = 1

    # Initial state
    state = knowledge_tracker.get_state(student_id, kp_id)
    assert state.mastery_probability == 0.5

    # After correct answer
    state = knowledge_tracker.update_from_grading(
        student_id=student_id,
        knowledge_point_id=kp_id,
        is_correct=True,
        question_difficulty=3.0,
    )
    assert state.mastery_probability > 0.5
    assert state.total_attempts == 1
    assert state.correct_count == 1

    # After incorrect answer
    state_wrong = knowledge_tracker.update_from_grading(
        student_id=student_id,
        knowledge_point_id=kp_id,
        is_correct=False,
        error_type="calculation_error",
        question_difficulty=3.0,
    )
    assert state_wrong.total_attempts == 2


@pytest.mark.asyncio
async def test_answer_card_analyzer() -> None:
    """Answer card analysis with mocked DeepSeek API."""
    mock_llm_response = MagicMock()
    mock_llm_response.content = (
        '{"overall_evaluation": "表现良好", "mastered_knowledge": ["函数"], '
        '"weak_knowledge": ["几何"], "error_patterns": [], '
        '"short_term_suggestions": ["多练习"], "mid_term_suggestions": [], '
        '"long_term_suggestions": [], "next_exam_target": 85}'
    )
    mock_llm_response.model = "deepseek-chat"
    mock_llm_response.usage = {"prompt_tokens": 100, "completion_tokens": 50}

    analyzer = AnswerCardAnalyzer()

    with patch.object(
        analyzer.gateway,
        "chat",
        new_callable=AsyncMock,
        return_value=mock_llm_response,
    ):
        ocr_data: dict[str, Any] = {
            "student_info": {"name": "测试学生", "class": "初三(1)班"},
            "exam_info": {
                "title": "期中考试",
                "subject": "数学",
                "total_score": 85,
                "max_score": 100,
                "objective_score": 40,
                "subjective_score": 45,
            },
            "sections": [
                {
                    "questions": [
                        {
                            "number": 1,
                            "score": 5,
                            "max_score": 5,
                            "student_answer": "A",
                        },
                    ],
                },
            ],
        }

        report = await analyzer.analyze_learning_status(ocr_data)

    assert report.overall_evaluation == "表现良好"
    assert "函数" in report.mastered_knowledge
    assert "几何" in report.weak_knowledge
    assert report.next_exam_target == 85
