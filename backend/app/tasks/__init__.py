from app.tasks.exercise import (
    auto_assign_review_task,
    generate_exercise_task,
    grade_exercise_question_task,
)
from app.tasks.grading import batch_grade_exam, grade_submission
from app.tasks.ocr import process_answer_sheet_ocr, process_exam_ocr
from app.tasks.report import generate_report

__all__ = [
    "process_exam_ocr",
    "process_answer_sheet_ocr",
    "grade_submission",
    "batch_grade_exam",
    "generate_exercise_task",
    "grade_exercise_question_task",
    "auto_assign_review_task",
    "generate_report",
]
