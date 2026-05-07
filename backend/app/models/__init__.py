"""SQLModel models for student progress tracking."""

from __future__ import annotations

from app.models.ai_call_log import AICallLog, AICallStatus, AITaskType
from app.models.audit_log import AuditLog
from app.models.class_ import Class
from app.models.class_student import ClassStudent
from app.models.error_book_item import ErrorBookItem
from app.models.exam import Exam, ExamStatus, ExamType
from app.models.exam_question import ExamQuestion, ExamQuestionStatus
from app.models.exercise import Exercise, ExerciseStatus
from app.models.exercise_question import ExerciseQuestion
from app.models.grading_result import ErrorType, GradingResult
from app.models.knowledge_point import KnowledgePoint
from app.models.knowledge_relation import KnowledgeRelation, RelationType
from app.models.notification import Notification, NotificationType
from app.models.notification_setting import NotificationSetting
from app.models.question_template import QuestionTemplate, QuestionType
from app.models.report import GeneratedBy, Report, ReportType
from app.models.student import Student
from app.models.student_knowledge_state import StudentKnowledgeState
from app.models.submission import GradingStatus, Submission
from app.models.subject import Subject
from app.models.user import User, UserRole

__all__ = [
    "AICallLog",
    "AICallStatus",
    "AITaskType",
    "AuditLog",
    "Class",
    "ClassStudent",
    "ErrorBookItem",
    "ErrorType",
    "Exam",
    "ExamQuestion",
    "ExamQuestionStatus",
    "ExamStatus",
    "ExamType",
    "Exercise",
    "ExerciseQuestion",
    "ExerciseStatus",
    "GeneratedBy",
    "GradingResult",
    "GradingStatus",
    "KnowledgePoint",
    "KnowledgeRelation",
    "Notification",
    "NotificationSetting",
    "NotificationType",
    "QuestionTemplate",
    "QuestionType",
    "RelationType",
    "Report",
    "ReportType",
    "Student",
    "StudentKnowledgeState",
    "Subject",
    "Submission",
    "User",
    "UserRole",
]
