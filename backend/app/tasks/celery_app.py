from __future__ import annotations

import asyncio
from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "agentica",
    broker=settings.celery_broker,
    backend=settings.celery_backend,
    include=["app.tasks.agent_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.tasks.agent_tasks.build_agent":  {"queue": "builds"},
        "app.tasks.agent_tasks.eval_agent":   {"queue": "evals"},
        "app.tasks.agent_tasks.deploy_agent": {"queue": "deploys"},
    },
)
