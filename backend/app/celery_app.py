import os
from celery import Celery

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "docstribe",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "app.tasks.coordinator",
        "app.tasks.lab",
        "app.tasks.radiology",
        "app.tasks.followup",
        "app.tasks.completion",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)
