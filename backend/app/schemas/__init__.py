from __future__ import annotations

from app.schemas.class_ import ClassCreate, ClassDetail, ClassRead
from app.schemas.common import BaseResponse, ErrorResponse, PaginatedResponse
from app.schemas.exam import ExamCreate, ExamList, ExamRead, ExamUpdate
from app.schemas.knowledge import (
    KnowledgePointPathItem,
    KnowledgePointRead,
    KnowledgePointTreeNode,
    PrerequisiteItem,
    SubjectRead,
)
from app.schemas.question import QuestionCreate, QuestionRead, QuestionUpdate
from app.schemas.report import ReportCreate, ReportRead
from app.schemas.student import (
    KnowledgeStateItem,
    StudentCreate,
    StudentDetail,
    StudentKnowledgeStateGrouped,
    StudentRead,
)
from app.schemas.submission import GradingResultRead, SubmissionCreate, SubmissionRead
from app.schemas.user import Token, TokenPayload, UserCreate, UserRead, UserUpdate

__all__ = [
    # common
    "BaseResponse",
    "PaginatedResponse",
    "ErrorResponse",
    # user
    "UserCreate",
    "UserRead",
    "UserUpdate",
    "Token",
    "TokenPayload",
    # exam
    "ExamCreate",
    "ExamRead",
    "ExamUpdate",
    "ExamList",
    # question
    "QuestionCreate",
    "QuestionRead",
    "QuestionUpdate",
    # submission
    "SubmissionCreate",
    "SubmissionRead",
    "GradingResultRead",
    # report
    "ReportCreate",
    "ReportRead",
    # student
    "StudentCreate",
    "StudentRead",
    "StudentDetail",
    "KnowledgeStateItem",
    "StudentKnowledgeStateGrouped",
    # class
    "ClassCreate",
    "ClassRead",
    "ClassDetail",
    # knowledge
    "SubjectRead",
    "KnowledgePointRead",
    "KnowledgePointTreeNode",
    "KnowledgePointPathItem",
    "PrerequisiteItem",
]
