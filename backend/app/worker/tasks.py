from __future__ import annotations

from datetime import datetime

from app.worker.celery_app import celery_app


@celery_app.task(name="app.worker.tasks.ping")
def ping() -> dict[str, str]:
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
