"""VideoUnderstandingProvider (T1): watch a stored video and describe it (MVP doc §5).

The input names a file in storage; the provider reads it from there (Gemini uploads it
through its File API). The output is ``T1Output``.

A provider may also offer sample recordings it can understand, for trying the Simulator
without filming anything. Real providers offer none; the mock offers the demo's takes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from curo.schemas.tasks import T1Input, T1Output


class VideoUnderstandingError(Exception):
    pass


@dataclass(frozen=True)
class Sample:
    name: str
    title: str
    description: str
    caption: str
    duration_s: float
    width: int
    height: int


class VideoUnderstandingProvider(ABC):
    name: str = "abstract"
    model: str = "abstract"

    @abstractmethod
    def understand(self, video: T1Input) -> T1Output: ...

    def samples(self) -> list[Sample]:
        """Sample recordings this provider understands (none, for a real provider)."""
        return []

    def sample_file(self, name: str) -> bytes | None:
        """The bytes of a sample recording, as an MP4 file."""
        return None
