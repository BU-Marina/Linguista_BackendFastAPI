"""Celery app config."""

from celery import Celery
from config.settings import settings

# settings = Settings()

celery_app = Celery(
    "core",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=3600,
    task_time_limit=30 * 60,
    timezone="UTC",
    include=[
        "tasks.email",
    ],
)
