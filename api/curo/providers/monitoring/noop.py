"""Development monitoring: errors go to the log; events stay in public.events only."""

from __future__ import annotations

import logging
from typing import Any

from .base import Monitoring

log = logging.getLogger("curo.monitoring")
KEEP_EVENTS = 500  # the API runs for days in development: keep only the latest


class NoopMonitoring(Monitoring):
    name = "noop"

    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any], str | None]] = []  # kept for tests

    def capture_exception(self, exc: BaseException, context: dict[str, Any] | None = None) -> None:
        log.error("captured %s: %s %s", type(exc).__name__, exc, context or {})

    def capture_event(self, name: str, props: dict[str, Any], creator_id: str | None) -> None:
        self.events.append((name, props, creator_id))
        if len(self.events) > KEEP_EVENTS:
            del self.events[: len(self.events) - KEEP_EVENTS]
