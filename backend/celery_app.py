import os
from pathlib import Path

from celery import Celery
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(ENV_PATH)

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "amqp://complaint:complaint@127.0.0.1:5672//")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "rpc://")

celery_app = Celery(
    "complaint_backend",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["tasks.complaint_tasks", "tasks.maintenance_tasks"],
)

celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Seoul",
    enable_utc=True,
    beat_schedule={
        "cleanup-expired-complaint-data-hourly": {
            "task": "maintenance.cleanup_expired",
            "schedule": 3600.0,
        },
    },
)
