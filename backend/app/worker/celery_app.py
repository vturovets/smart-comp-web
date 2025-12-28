from __future__ import annotations

import logging

from celery import Celery
from celery.signals import setup_logging

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "smart_comp",
    broker=str(settings.redis_url),
    backend=str(settings.result_backend),
    include=["app.worker.tasks"],
)
celery_app.conf.task_default_queue = settings.task_queue
celery_app.conf.task_routes = {"app.worker.tasks.*": {"queue": settings.task_queue}}
celery_app.conf.task_always_eager = settings.environment == "test"
celery_app.conf.task_eager_propagates = True
celery_app.conf.task_time_limit = settings.job_timeout_seconds + 60


@celery_app.on_after_configure.connect
def announce_startup(sender: Celery, **_: object) -> None:
    log = getattr(sender, "log", None)
    if log and hasattr(log, "info"):
        log.info("Celery worker bootstrapped for %s", settings.environment)


@setup_logging.connect
def configure_celery_logging(**_: object) -> None:
    """Raise the celery.worker logger level to suppress periodic timer chatter."""

    # Celery reinitializes logging when the worker boots, so set the level via the
    # setup_logging signal to ensure it sticks.
    logging.getLogger("celery.worker").setLevel(logging.WARNING)
    logging.getLogger("celery.worker.strategy").setLevel(logging.WARNING)
