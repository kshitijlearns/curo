"""Liveness heartbeats for background processes, kept in Redis.

The worker and scheduler call ``beat()`` every few seconds; ``/health`` reads
``last_beat()`` to report whether they are running.
"""

from __future__ import annotations

import time

from curo.redis_client import get_redis

_KEY = "curo:heartbeat:{}"
TTL_SECONDS = 60


def beat(process: str) -> None:
    get_redis().set(_KEY.format(process), str(time.time()), ex=TTL_SECONDS)


def seconds_since_beat(process: str) -> float | None:
    """Seconds since the process last beat, or None if it hasn't in the last minute."""
    raw = get_redis().get(_KEY.format(process))
    return None if raw is None else max(0.0, time.time() - float(raw))
