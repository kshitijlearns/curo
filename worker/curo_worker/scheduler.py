"""The scheduler: one loop that decides what is due at ``clock.now()`` and enqueues it.

It reads CURO's clock, so time travel (FAKE_NOW, tools/timetravel.py) moves the
schedule too. The logic lives in ``curo.jobs.scheduler`` so tests and the seed replay
run exactly the same code.
"""

from __future__ import annotations

import logging
import time

from curo import clock, heartbeat
from curo.jobs.scheduler import tick

log = logging.getLogger("curo.scheduler")
TICK_SECONDS = 15


PAUSE_KEY = "curo:scheduler:paused"  # set by `python -m curo.seed demo` while it replays


def run_scheduler() -> None:
    from curo.redis_client import get_redis

    log.info("scheduler started; clock: %s", clock.describe())
    while True:
        try:
            heartbeat.beat("scheduler")
            if get_redis().get(PAUSE_KEY):
                time.sleep(TICK_SECONDS)
                continue
            enqueued = tick()
            if enqueued:
                log.info("enqueued %s at %s", enqueued, clock.now().isoformat())
        except Exception as exc:  # never let one bad tick stop the schedule
            log.exception("scheduler tick failed: %s", exc)
        time.sleep(TICK_SECONDS)
