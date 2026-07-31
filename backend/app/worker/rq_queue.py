"""RQ (Redis Queue) connection — only ever imported when REDIS_URL is
configured (see `durable_queue_configured` in app/config.py and
get_task_queue() in app/worker/queue.py). Kept as its own module so the
`redis`/`rq` imports never load at all in local-first mode.
"""

from functools import lru_cache

import redis
from rq import Queue

from app.config import Settings

QUEUE_NAME = "donation-receipts"


@lru_cache
def _connection(redis_url: str) -> redis.Redis:
    return redis.Redis.from_url(redis_url)


def get_queue(settings: Settings) -> Queue:
    return Queue(QUEUE_NAME, connection=_connection(settings.redis_url))
