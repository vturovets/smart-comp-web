from __future__ import annotations

from celery import Celery

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


@celery_app.on_after_configure.connect
def announce_startup(sender: Celery, **_: object) -> None:
    sender.log.info("Celery worker bootstrapped for %s", settings.environment)
