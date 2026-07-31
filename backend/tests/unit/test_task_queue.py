"""app/worker/queue.py's dispatch decision: BackgroundTasks by default,
RQ+Redis once REDIS_URL is configured — without a real Redis connection in
either branch of this test (the RQ path is verified via monkeypatching
get_queue(), not a live queue)."""

import uuid
from unittest.mock import MagicMock

from fastapi import BackgroundTasks

from app.config import Settings
from app.worker.queue import enqueue_receipt_generation
from app.worker.tasks import generate_receipt_and_email


def _settings(**overrides) -> Settings:
    base = Settings(database_url="postgresql://x", jwt_secret="x")
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def test_uses_background_tasks_when_redis_not_configured(monkeypatch):
    settings = _settings(redis_url="")
    background_tasks = BackgroundTasks()
    donation_id = uuid.uuid4()

    enqueue_receipt_generation(background_tasks, settings, donation_id)

    assert len(background_tasks.tasks) == 1
    task = background_tasks.tasks[0]
    assert task.func is generate_receipt_and_email
    assert task.args == (donation_id,)


def test_enqueues_on_rq_when_redis_configured(monkeypatch):
    settings = _settings(redis_url="redis://localhost:6380/0")
    fake_queue = MagicMock()
    monkeypatch.setattr("app.worker.rq_queue.get_queue", lambda s: fake_queue)

    background_tasks = BackgroundTasks()
    donation_id = uuid.uuid4()

    enqueue_receipt_generation(background_tasks, settings, donation_id)

    fake_queue.enqueue.assert_called_once_with(generate_receipt_and_email, donation_id)
    assert len(background_tasks.tasks) == 0
