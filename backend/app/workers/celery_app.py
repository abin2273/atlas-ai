from app.core.config import settings
from celery import Celery

celery_app = Celery(
    "atlas_ai",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.features.documents.tasks"],
)
celery_app.conf.update(
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    broker_transport_options={"visibility_timeout": 3600},
    result_expires=3600,
)
