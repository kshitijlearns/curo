"""Shared Redis connection (queue, clock, worker heartbeats)."""

from __future__ import annotations

import threading

import redis

from curo.config import get_settings

_client: redis.Redis | None = None
_lock = threading.Lock()


def get_redis() -> redis.Redis:
    global _client
    with _lock:
        if _client is None:
            _client = redis.Redis.from_url(
                get_settings().redis_url, socket_connect_timeout=1.0, socket_timeout=3.0
            )
        return _client


def set_redis(client: redis.Redis | None) -> None:
    """Replace the shared client (tests pass a fakeredis instance; None resets)."""
    global _client
    with _lock:
        _client = client
