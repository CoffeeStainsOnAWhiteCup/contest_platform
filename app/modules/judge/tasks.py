import logging
import uuid

from app.core.celery_app import celery
from app.core.config import settings
from app.modules.judge.sandbox.runner import SandboxUnavailable
from app.modules.judge.service import judge_submission_sync, mark_submission_system_error

logger = logging.getLogger(__name__)


@celery.task(bind=True, name="judge.judge_submission", max_retries=settings.JUDGE_MAX_ATTEMPTS)
def judge_submission(self, submission_id: str) -> None:
    submission_uuid = uuid.UUID(submission_id)
    try:
        judge_submission_sync(submission_uuid)
    except SandboxUnavailable as exc:
        if self.request.retries >= self.max_retries:
            mark_submission_system_error(submission_uuid, f"Sandbox unavailable after retries: {exc}")
            return
        raise self.retry(exc=exc, countdown=min(60, 2 ** (self.request.retries + 1)))
    except Exception as exc:
        logger.exception("Judge task failed for submission %s", submission_id)
        mark_submission_system_error(submission_uuid, f"Judge task failed: {exc}")
