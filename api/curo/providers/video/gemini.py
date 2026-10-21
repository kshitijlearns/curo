"""Gemini video understanding (T1) — NOT IMPLEMENTED YET (needs GEMINI_API_KEY).

TODO when the key arrives (see docs/INTEGRATION.md):
1. Read the video bytes from storage (video.bucket / video.path).
2. Upload through the Gemini File API; wait until the file is ACTIVE.
3. generateContent with model GEMINI_VIDEO_MODEL, the prompt api/prompts/T1_watch_video.v1.md
   (curo.prompts.load(T1)), and responseSchema = T1Output's JSON schema
   (responseMimeType application/json). Default media resolution: ~300 tokens per second.
4. Validate the JSON with T1Output.model_validate; raise VideoUnderstandingError on failure.
5. Delete the uploaded file from the File API afterwards.
6. Read the answer with ``parse_response`` (below, already real): tools/record_contracts.py
   records responses the same way and tests/test_contracts.py replays them through it.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from curo.schemas.tasks import T1Input, T1Output

from .base import VideoUnderstandingError, VideoUnderstandingProvider

_TODO = "Gemini video provider not implemented yet: set VIDEO_PROVIDER=mock (see INTEGRATION.md)"


class GeminiVideoProvider(VideoUnderstandingProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str, storage):
        self.api_key = api_key
        self.model = model
        self.storage = storage

    def understand(self, video: T1Input) -> T1Output:
        raise NotImplementedError(_TODO)


def parse_response(raw: dict[str, Any]) -> T1Output:
    """A generateContent answer with a JSON response schema: the first candidate's text is
    the T1 output. A blocked prompt or an unfinished answer is an error, never a guess."""
    if (raw.get("promptFeedback") or {}).get("blockReason"):
        raise VideoUnderstandingError(f"Gemini blocked the video: {raw['promptFeedback']}")
    candidates = raw.get("candidates") or []
    if not candidates:
        raise VideoUnderstandingError("Gemini returned no answer")
    first = candidates[0]
    if first.get("finishReason") not in (None, "STOP"):
        raise VideoUnderstandingError(f"Gemini stopped early: {first.get('finishReason')}")
    text = "".join(p.get("text", "") for p in (first.get("content") or {}).get("parts", []))
    try:
        return T1Output.model_validate(json.loads(text))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise VideoUnderstandingError(f"Gemini's answer doesn't match T1: {exc}") from exc
