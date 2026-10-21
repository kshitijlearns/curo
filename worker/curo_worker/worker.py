"""The job worker: an RQ worker on the ``studio`` and ``curo`` queues, plus a heartbeat.

Studio steps (a creator is waiting) are served before background work.

RQ forks a work horse per job, which needs Linux/macOS; the worker runs in Docker.
Tests don't need it: jobs are plain functions and run inline.
"""

from __future__ import annotations

import logging
import threading
import time

from curo import heartbeat
from curo.redis_client import get_redis

log = logging.getLogger("curo.worker")
QUEUE_NAMES = ("studio", "curo")  # in priority order
HEARTBEAT_SECONDS = 10


def _heartbeat_loop(stop: threading.Event) -> None:
    while not stop.is_set():
        try:
            heartbeat.beat("worker")
        except Exception as exc:  # Redis hiccup: keep going, the next beat retries
            log.warning("heartbeat failed: %s", exc)
        stop.wait(HEARTBEAT_SECONDS)


def run_worker() -> None:
    from rq import Queue, Worker

    redis = get_redis()
    while True:  # wait for Redis on startup instead of crashing the container
        try:
            redis.ping()
            break
        except Exception as exc:
            log.info("waiting for Redis: %s", exc)
            time.sleep(2)

    stop = threading.Event()
    threading.Thread(target=_heartbeat_loop, args=(stop,), daemon=True).start()
    log.info("worker ready on queues %s", ", ".join(QUEUE_NAMES))
    queues = [Queue(name, connection=redis) for name in QUEUE_NAMES]
    try:
        Worker(queues, connection=redis).work(with_scheduler=False)
    finally:
        stop.set()
