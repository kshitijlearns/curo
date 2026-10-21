"""Monitoring (MVP doc §6: Sentry for errors, PostHog for product analytics).

``capture_exception`` reports an unexpected error with what was going on (the route or job,
never a creator's content). ``capture_event`` sends a product event, the same ones CURO keeps
in ``public.events``, with the creator's id only (no names, captions or comments).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Monitoring(ABC):
    name: str = "abstract"

    @abstractmethod
    def capture_exception(
        self, exc: BaseException, context: dict[str, Any] | None = None
    ) -> None: ...

    @abstractmethod
    def capture_event(self, name: str, props: dict[str, Any], creator_id: str | None) -> None: ...
