"""RQ worker process for the durable task queue — only meaningful once
REDIS_URL is configured (see app/worker/queue.py / app/worker/rq_queue.py).
Run with: `python -m scripts.worker` (same venv as the API process).

In local-first mode (no REDIS_URL), receipt generation runs in-process via
FastAPI BackgroundTasks instead, and this script has nothing to do.
"""

from redis import Redis
from rq import Queue, Worker

from app.config import get_settings
from app.worker.rq_queue import QUEUE_NAME


def main() -> None:
    settings = get_settings()
    if not settings.durable_queue_configured:
        raise SystemExit(
            "REDIS_URL is not set - there is no durable queue to work off. "
            "This process is only needed once REDIS_URL is configured; "
            "until then, receipt generation runs in-process instead."
        )

    connection = Redis.from_url(settings.redis_url)
    worker = Worker([Queue(QUEUE_NAME, connection=connection)], connection=connection)
    worker.work()


if __name__ == "__main__":
    main()
