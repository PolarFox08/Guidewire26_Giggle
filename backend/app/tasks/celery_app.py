"""Celery application configuration and beat schedule."""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "giggle",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.trigger_polling",
        "app.tasks.weekly_renewal",
        "app.tasks.cascade_recovery",
        "app.tasks.aqi_polling",
    ],
)

celery_app.conf.update(
    timezone="Asia/Kolkata",
    enable_utc=False,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "trigger-polling-30m": {
            "task": "app.tasks.trigger_polling.poll_all_zones",
            "schedule": 1800.0,
        },
        "weekly-renewal-sunday-midnight": {
            "task": "app.tasks.weekly_renewal.renew_all_policies",
            "schedule": crontab(hour="0", minute="0", day_of_week="sunday"),
        },
        "cascade-recovery-12h": {
            "task": "app.tasks.cascade_recovery.check_recovering_zones",
            "schedule": 43200.0,
        },
        "aqi-polling-hourly": {
            "task": "app.tasks.aqi_polling.poll_aqi_zones",
            "schedule": 3600.0,
        },
    },
)

# Use explicit imports so all task modules are loaded in worker/beat startup.
celery_app.autodiscover_tasks(packages=["app.tasks"], force=True)
