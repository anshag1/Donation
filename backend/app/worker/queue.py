"""Task dispatch, chosen once from config — same adapter pattern already
used for storage (storage_service.py) and email (email_service.py). Default
is FastAPI's in-process `BackgroundTasks` (fine at v1 scale — see
app/worker/tasks.py's own docstring for why). Setting REDIS_URL switches to
a durable RQ queue instead, without any call site needing to change: a
redeploy or crash mid-request no longer silently drops a receipt-generation
job, since it's now durably queued in Redis rather than living only in the
worker process's memory between "response sent" and "task runs."
"""

import uuid

from fastapi import BackgroundTasks

from app.config import Settings
from app.worker.tasks import generate_receipt_and_email


def enqueue_receipt_generation(
    background_tasks: BackgroundTasks, settings: Settings, donation_id: uuid.UUID
) -> None:
    if settings.durable_queue_configured:
        from app.worker.rq_queue import get_queue

        get_queue(settings).enqueue(generate_receipt_and_email, donation_id)
    else:
        background_tasks.add_task(generate_receipt_and_email, donation_id)
