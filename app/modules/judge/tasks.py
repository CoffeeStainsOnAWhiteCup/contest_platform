import logging
import uuid
from celery import Task

from app.core.celery_app import celery
from app.core.config import settings
from app.modules.judge.sandbox.runner import SandboxUnavailable
from app.modules.judge.service import (
    JudgeBusy,
    judge_submission_sync,
    mark_stale_submission_system_error,
    mark_submission_system_error,
)

logger = logging.getLogger(__name__)


@celery.task(bind=True, name="judge.judge_submission", max_retries=settings.JUDGE_MAX_ATTEMPTS)  # type: ignore[untyped-decorator]
def judge_submission(self: Task, submission_id: str) -> None:
    submission_uuid = uuid.UUID(submission_id)
    try:
        judge_submission_sync(submission_uuid)
    except JudgeBusy as exc:
        if self.request.retries >= self.max_retries:
            logger.warning("Submission %s remained running after retries: %s", submission_uuid, exc)
            mark_stale_submission_system_error(
                submission_uuid,
                f"Submission remained running: {exc}",
            )
            return
        raise self.retry(exc=exc, countdown=settings.JUDGE_STALE_TIMEOUT_S)
    except SandboxUnavailable as exc:
        if self.request.retries >= self.max_retries:
            attempt = getattr(exc, "attempt", None)
            if attempt is None:
                logger.warning(
                    "Sandbox unavailable after retries for submission %s without an attempt token: %s",
                    submission_uuid,
                    exc,
                )
            else:
                mark_submission_system_error(
                    submission_uuid,
                    f"Sandbox unavailable after retries: {exc}",
                    expected_attempt=attempt,
                )
            return
        raise self.retry(exc=exc, countdown=min(60, 2 ** (self.request.retries + 1)))
    except Exception:
        logger.exception("Judge task failed for submission %s", submission_id)
