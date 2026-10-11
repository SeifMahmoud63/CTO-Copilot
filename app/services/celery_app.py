"""Celery app: Redis broker, Africa/Cairo beat schedule for the daily CTO report."""
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery = Celery(
    "cto_copilot",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery.conf.update(
    timezone=settings.report_timezone,
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
celery.conf.beat_schedule = {
    "daily-cto-report": {
        "task": "reports.generate_daily",
        "schedule": crontab(hour=settings.report_hour, minute=settings.report_minute),
    },
}


@celery.task(name="reports.generate_daily", bind=True, max_retries=2, default_retry_delay=300)
def generate_daily_task(self, report_date: str | None = None):
    """Beat entrypoint: run the full hybrid pipeline (metrics -> AI -> PDF -> DB)."""
    import asyncio

    from app.services.report_service import generate_daily_report

    try:
        return asyncio.run(generate_daily_report(report_date))
    except Exception as exc:
        raise self.retry(exc=exc)
