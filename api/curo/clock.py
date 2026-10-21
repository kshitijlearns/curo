"""The one source of "now" for CURO.

Everything (API, worker, scheduler, providers) calls ``clock.now()``; nothing calls
``datetime.now()`` directly. In development ``FAKE_NOW`` sets a time-travel anchor, so
snapshots, phases and the scheduler can be demonstrated, e.g. 12 days before
Ganesh Chaturthi.

Fake time runs forward at real speed from its anchor, or stays frozen. The anchor is
shared through Redis so the API, worker and scheduler agree, and
``tools/timetravel.py`` moves it for every process at once. Without Redis, each
process keeps its own anchor (fine for tests and scripts).
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from curo.config import get_settings

REDIS_KEY = "curo:clock"
_CACHE_SECONDS = 2.0
_REDIS_RETRY_SECONDS = 10.0


@dataclass(frozen=True)
class ClockState:
    fake_anchor: datetime  # the fake time at real_anchor
    real_anchor: datetime  # the real time when fake_anchor was set
    frozen: bool = False
    env: str = ""  # the FAKE_NOW value in force when this state was created
    manual: bool = False  # True when set by time travel rather than by FAKE_NOW

    def now(self) -> datetime:
        if self.frozen:
            return self.fake_anchor
        return self.fake_anchor + (datetime.now(UTC) - self.real_anchor)

    def to_json(self) -> str:
        return json.dumps(
            {
                "fake_anchor": self.fake_anchor.isoformat(),
                "real_anchor": self.real_anchor.isoformat(),
                "frozen": self.frozen,
                "env": self.env,
                "manual": self.manual,
            }
        )

    @staticmethod
    def from_json(raw: str | bytes) -> ClockState:
        d = json.loads(raw)
        return ClockState(
            fake_anchor=datetime.fromisoformat(d["fake_anchor"]),
            real_anchor=datetime.fromisoformat(d["real_anchor"]),
            frozen=bool(d.get("frozen", False)),
            env=d.get("env", ""),
            manual=bool(d.get("manual", False)),
        )


_lock = threading.Lock()
_override: datetime | None = None  # set by tests via frozen_at()
_cache: tuple[float, ClockState | None] = (0.0, None)
_local_state: ClockState | None = None  # used when Redis is unavailable
_redis_down_until = 0.0


def now() -> datetime:
    """Current time (UTC, timezone-aware), honouring FAKE_NOW / time travel."""
    if _override is not None:
        return _override
    state = _current_state()
    return state.now() if state else datetime.now(UTC)


def today_local(tz: str | None = None) -> datetime:
    """``now()`` in the creator's timezone (defaults to DEFAULT_TIMEZONE)."""
    return now().astimezone(ZoneInfo(tz or get_settings().default_timezone))


def to_utc(dt: datetime) -> datetime:
    """Make a datetime timezone-aware UTC; naive values are read in DEFAULT_TIMEZONE."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(get_settings().default_timezone))
    return dt.astimezone(UTC)


@contextmanager
def frozen_at(dt: datetime) -> Iterator[None]:
    """Test helper: freeze ``now()`` at ``dt`` inside the block."""
    global _override
    previous = _override
    _override = to_utc(dt)
    try:
        yield
    finally:
        _override = previous


# --- Time travel (used by tools/timetravel.py and the seed replay) ---------------


def set_time(dt: datetime, frozen: bool = False) -> ClockState:
    state = ClockState(to_utc(dt), datetime.now(UTC), frozen, env=_env_value(), manual=True)
    _store(state)
    return state


def advance(delta: timedelta) -> ClockState:
    current = now()
    state = _current_state()
    return set_time(current + delta, frozen=bool(state and state.frozen))


def reset() -> None:
    """Forget any manual time travel; fall back to FAKE_NOW (or real time)."""
    global _local_state, _cache, _redis_down_until
    with _lock:
        _local_state = None
        _cache = (0.0, None)
        _redis_down_until = 0.0
    client = _redis()
    if client is not None:
        client.delete(REDIS_KEY)


def describe() -> dict:
    state = _current_state()
    return {
        "now": now().isoformat(),
        "fake": state is not None,
        "frozen": bool(state and state.frozen),
        "source": "real" if state is None else ("time travel" if state.manual else "FAKE_NOW"),
    }


# --- internals --------------------------------------------------------------------


def _env_value() -> str:
    fake = get_settings().fake_now
    return to_utc(fake).isoformat() if fake else ""


def _from_env() -> ClockState | None:
    env = _env_value()
    if not env:
        return None
    return ClockState(datetime.fromisoformat(env), datetime.now(UTC), env=env)


def _current_state() -> ClockState | None:
    global _cache, _local_state
    with _lock:
        expires, cached = _cache
        if time.monotonic() < expires:
            return cached

    env = _env_value()
    client = _redis()
    state: ClockState | None
    if client is None:
        with _lock:
            if _local_state is None or _local_state.env != env:
                _local_state = _from_env()
            state = _local_state
    else:
        raw = client.get(REDIS_KEY)
        state = ClockState.from_json(raw) if raw else None
        # A changed FAKE_NOW in .env replaces whatever was stored before,
        # including earlier time travel.
        stale = state is not None and state.env != env
        if state is None or stale:
            state = _from_env()
            if state is not None:
                client.set(REDIS_KEY, state.to_json())
            elif stale:
                client.delete(REDIS_KEY)

    with _lock:
        _cache = (time.monotonic() + _CACHE_SECONDS, state)
    return state


def _store(state: ClockState) -> None:
    global _local_state, _cache
    client = _redis()
    if client is not None:
        client.set(REDIS_KEY, state.to_json())
    with _lock:
        _local_state = state
        _cache = (time.monotonic() + _CACHE_SECONDS, state)


def _redis():
    """A Redis client, or None when Redis can't be reached (checked at most every 10 s)."""
    global _redis_down_until
    if time.monotonic() < _redis_down_until:
        return None
    from curo.redis_client import get_redis  # local import: avoid a cycle at import time

    client = get_redis()
    try:
        client.ping()
        return client
    except Exception:
        _redis_down_until = time.monotonic() + _REDIS_RETRY_SECONDS
        return None
