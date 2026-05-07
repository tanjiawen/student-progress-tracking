from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "student_progress",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.ocr", "app.tasks.grading", "app.tasks.exercise", "app.tasks.report", "app.tasks.scheduler"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,
    worker_prefetch_multiplier=1,
)

if __name__ == "__main__":
    celery_app.start()
