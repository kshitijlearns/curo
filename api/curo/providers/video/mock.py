"""Mock video understanding.

It reads the stored file like the real provider does. Files downloaded by the mock public-data
provider are small placeholders that name their fixture reel; for those it returns that reel's
fixture T1 output (``fixtures/data/t1``), written from the reel's DNA by the generator; the
demo's sample recordings (``fixtures/data/samples.json``) carry the same marker in their MP4
headers. Any other file — a video a creator records — gets a deliberately thin description,
so DNA extraction marks most fields unknown rather than inventing them.
"""

from __future__ import annotations

import json
from functools import cached_property
from pathlib import Path

from curo.providers.public_data.mock import DEFAULT_DATA_DIR, MOCK_VIDEO_MAGIC
from curo.providers.storage.base import StorageProvider
from curo.schemas.tasks import SecondDescription, Shot, T1Input, T1Output
from curo.services import mp4

from .base import Sample, VideoUnderstandingError, VideoUnderstandingProvider


class MockVideoProvider(VideoUnderstandingProvider):
    name = "mock"
    model = "mock-video-v1"

    def __init__(self, storage: StorageProvider, data_dir: Path | str | None = None):
        self.storage = storage
        self._dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR

    @cached_property
    def _fixture_t1(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for p in sorted((self._dir / "t1").glob("*.json")):
            out.update(json.loads(p.read_text(encoding="utf-8")))
        return out

    @cached_property
    def _samples(self) -> list[dict]:
        path = self._dir / "samples.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []

    def samples(self) -> list[Sample]:
        return [
            Sample(
                s["name"],
                s["title"],
                s["description"],
                s["caption"],
                float(s["duration_s"]),
                s["width"],
                s["height"],
            )
            for s in self._samples
        ]

    def sample_file(self, name: str) -> bytes | None:
        """A real MP4 container (length and size in its headers, no picture) carrying the
        marker that names the sample's fixture understanding."""
        s = next((s for s in self._samples if s["name"] == name), None)
        if s is None:
            return None
        marker = MOCK_VIDEO_MAGIC + json.dumps({"shortcode": s["shortcode"]}).encode() + b"\n"
        return mp4.build(float(s["duration_s"]), s["width"], s["height"], marker)

    def understand(self, video: T1Input) -> T1Output:
        data = self.storage.get(video.bucket, video.path)
        # The marker opens a placeholder file, or sits in a sample recording's MP4 headers.
        at = data.find(MOCK_VIDEO_MAGIC, 0, 4096)
        if at >= 0:
            start = at + len(MOCK_VIDEO_MAGIC)
            end = data.find(b"\n", start)
            ref = json.loads(data[start : end if end >= 0 else None].decode("utf-8"))
            found = self._fixture_t1.get(ref["shortcode"])
            if found is None:
                raise VideoUnderstandingError(f"no fixture understanding for {ref['shortcode']}")
            return T1Output.model_validate(found)
        return self._thin(video)

    @staticmethod
    def _thin(video: T1Input) -> T1Output:
        duration = video.duration_s or 15.0
        return T1Output(
            duration_s=duration,
            shots=[Shot(start=0.0, end=duration)],
            seconds=[
                SecondDescription(t=float(s), description="A person on screen")
                for s in range(int(duration))
            ],
        )
