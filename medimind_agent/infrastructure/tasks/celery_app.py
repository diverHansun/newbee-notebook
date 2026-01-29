"""
Celery application for MediMind Agent.
"""

import os
from celery import Celery


broker_url = os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://redis:6379/0"))
backend_url = os.getenv("CELERY_RESULT_BACKEND", broker_url)

app = Celery(
    "medimind_agent",
    broker=broker_url,
    backend=backend_url,
    include=["medimind_agent.infrastructure.tasks.document_tasks"],
)

app.conf.task_default_queue = "default"
app.conf.result_expires = 3600
