from celery import Celery

from app.core.config import settings

celery = Celery(
    "contest_platform",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.modules.judge.tasks"],
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_default_queue="judge",
    task_routes={"judge.judge_submission": {"queue": "judge"}},
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    task_ignore_result=True,
    broker_connection_retry_on_startup=True,
    task_soft_time_limit=180,
    task_time_limit=240,
)
