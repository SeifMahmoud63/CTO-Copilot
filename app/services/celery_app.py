"""Celery app: Redis broker, Africa/Cairo beat schedules (daily report + inbox poll)."""
from datetime import timedelta

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

# Same interpreter-shutdown DB noise filter as the API process (see main.py).
from app.db.session import install_loop_noise_filter as _install_noise_filter
_install_noise_filter()

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
    "email-inbox-poll": {
        "task": "emails.poll_inbox",
        "schedule": timedelta(minutes=max(1, settings.email_poll_interval_minutes)),
    },
    "slack-sla-monitor": {
        "task": "slack.check_sla_breaches",
        "schedule": timedelta(minutes=30),
    },
}


from celery.signals import worker_process_init


@worker_process_init.connect
def on_worker_init(**kwargs):
    """Dispose any inherited pool from parent process on fork."""
    try:
        from app.db.session import engine
        engine.sync_engine.dispose()
    except Exception:
        pass


def _run_async(coro_fn, *args, **kwargs):
    """Run an async entrypoint with engine disposal inside the SAME event loop.

    The worker is prefork while every task runs its own asyncio loop. Pooled
    aiomysql connections must be cleanly awaited and disposed BEFORE the
    task's event loop closes; disposing in a separate subsequent loop crashes with
    'Event loop is closed' because the connection's original loop is dead.
    """
    import asyncio

    from app.db.session import dispose_engine

    async def _runner():
        try:
            return await coro_fn(*args, **kwargs)
        finally:
            await dispose_engine()

    return asyncio.run(_runner())


@celery.task(name="reports.generate_daily", bind=True, max_retries=2, default_retry_delay=300)
def generate_daily_task(self, report_date: str | None = None):
    """Beat entrypoint: run the full hybrid pipeline (metrics -> AI -> PDF -> DB)."""
    from app.services.report_service import generate_daily_report

    try:
        return _run_async(generate_daily_report, report_date)
    except Exception as exc:
        raise self.retry(exc=exc)


@celery.task(name="emails.poll_inbox", bind=True, max_retries=2, default_retry_delay=300)
def poll_inbox_task(self, limit: int = 25):
    """Beat entrypoint: one inbox polling round (fetch -> summarize -> score -> DB)."""
    from app.services.email_service import poll_inbox

    try:
        return _run_async(poll_inbox, limit=limit)
    except Exception as exc:
        raise self.retry(exc=exc)


@celery.task(name="evals.run_full", bind=True, max_retries=0)
def run_eval_task(self, use_judge: bool = True, max_questions: int | None = None,
                  sse_enabled: bool | None = None):
    """Manual entrypoint (Eval Lab UI): full torture run, results to MLflow.

    No retries by design: a failed eval run must be inspected, not blindly
    repeated at 2x LLM cost. Per-question errors become ERROR verdicts instead.
    """
    from app.services.eval_service import run_eval

    return _run_async(run_eval, use_judge=use_judge, max_questions=max_questions,
                      sse_enabled=sse_enabled, task_id=self.request.id)


@celery.task(name="slack.check_sla_breaches", bind=True, max_retries=2, default_retry_delay=300)
def check_sla_breaches_task(self):
    """Beat entrypoint: scan open PRs and dispatch Slack alerts for overdue SLA breaches."""
    from app.services.slack_service import slack_service

    try:
        return _run_async(slack_service.check_and_notify_overdue_prs)
    except Exception as exc:
        raise self.retry(exc=exc)
