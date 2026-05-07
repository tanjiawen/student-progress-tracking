from app.repositories.base import BaseRepository
from app.repositories.class_ import ClassRepository
from app.repositories.error_book_item import ErrorBookItemRepository
from app.repositories.exam import ExamRepository
from app.repositories.exam_question import ExamQuestionRepository
from app.repositories.exercise import ExerciseRepository
from app.repositories.exercise_question import ExerciseQuestionRepository
from app.repositories.grading_result import GradingResultRepository
from app.repositories.knowledge_point import KnowledgePointRepository
from app.repositories.knowledge_relation import KnowledgeRelationRepository
from app.repositories.question_template import QuestionTemplateRepository
from app.repositories.report import ReportRepository
from app.repositories.student import StudentRepository
from app.repositories.student_knowledge_state import StudentKnowledgeStateRepository
from app.repositories.subject import SubjectRepository
from app.repositories.submission import SubmissionRepository
from app.repositories.user import UserRepository

__all__ = [
    "BaseRepository",
    "ClassRepository",
    "ErrorBookItemRepository",
    "ExamRepository",
    "ExamQuestionRepository",
    "ExerciseRepository",
    "ExerciseQuestionRepository",
    "GradingResultRepository",
    "KnowledgePointRepository",
    "KnowledgeRelationRepository",
    "QuestionTemplateRepository",
    "ReportRepository",
    "StudentRepository",
    "StudentKnowledgeStateRepository",
    "SubjectRepository",
    "SubmissionRepository",
    "UserRepository",
]
