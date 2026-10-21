"""Contract tests' seam: a recorded vendor or model response, read by the real provider's own
parser into CURO's schema (MVP doc §4: "run contract tests on recorded responses every day,
so a change in the vendor's output is caught before it reaches creators").

A recording is one JSON file under ``api/tests/contracts/<kind>/`` written by
``tools/record_contracts.py``::

    {"kind": "llm/claude/T3", "recorded_at": "…", "source": {"model": "…"},
     "request": {…, no secrets}, "response": <the raw answer>}

``check(recording)`` parses it and applies the rules CURO relies on beyond the schema
(missing counts are None, vectors are 768 long and normalised…). It raises on any mismatch.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from curo.providers.public_data.base import CommentData, HashtagPageData, ProfileData, ReelData

PUBLIC_DATA_VENDORS = ("apify", "brightdata")
PUBLIC_DATA_METHODS = ("profile", "reels", "comments", "hashtag")


class ContractBroken(AssertionError):
    pass


def kinds() -> list[str]:
    """Every kind of recording CURO has a parser for."""
    from curo.schemas.tasks import TASKS

    out = [f"public_data/{v}/{m}" for v in PUBLIC_DATA_VENDORS for m in PUBLIC_DATA_METHODS]
    out += ["video/gemini", "embedding/gemini"]
    out += [f"llm/claude/{t}" for t in TASKS if t != "T1"]
    return out


def check(recording: dict[str, Any]) -> Any:
    kind = recording["kind"]
    parts = kind.split("/")
    response, request = recording["response"], recording.get("request") or {}
    if parts[0] == "public_data" and len(parts) == 3:
        return _public_data(parts[1], parts[2], response, request)
    if kind == "video/gemini":
        from curo.providers.video.gemini import parse_response

        return parse_response(response)
    if kind == "embedding/gemini":
        from curo.providers.embedding.gemini import parse_embeddings

        vectors = parse_embeddings(response)
        _require(vectors, "no vectors")
        for v in vectors:
            _require(abs(math.sqrt(sum(x * x for x in v)) - 1) < 1e-6, "a vector isn't normalised")
        texts = request.get("texts")
        _require(texts is None or len(texts) == len(vectors), "one vector per text")
        return vectors
    if parts[0] == "llm" and len(parts) == 3 and parts[1] == "claude":
        from curo.providers.llm import claude
        from curo.schemas.tasks import TASKS

        if parts[2] == "T14":
            return claude.parse_chat_message(response)
        return claude.parse_message(TASKS[parts[2]], response)
    raise ContractBroken(f"no parser for recordings of kind {kind!r}")


def _require(ok: bool, what: str) -> None:
    if not ok:
        raise ContractBroken(what)


def _public_data(vendor: str, method: str, response: Any, request: dict[str, Any]) -> Any:
    if vendor == "apify":
        from curo.providers.public_data import apify as module
    elif vendor == "brightdata":
        from curo.providers.public_data import brightdata as module
    else:
        raise ContractBroken(f"unknown public-data vendor {vendor!r}")
    parsers: dict[str, Callable[[], Any]] = {
        "profile": lambda: module.parse_profile(response),
        "reels": lambda: module.parse_reels(response),
        "comments": lambda: module.parse_comments(response),
        "hashtag": lambda: module.parse_hashtag_page(request.get("tag", ""), response),
    }
    if method not in parsers:
        raise ContractBroken(f"unknown public-data method {method!r}")
    out = parsers[method]()
    if isinstance(out, ProfileData):
        _counts(out.model_dump(), ("followers", "following", "posts"))
    elif isinstance(out, HashtagPageData):
        for reel in out.top + out.recent:
            _reel(reel)
    elif isinstance(out, list):
        _require(bool(out), f"{method}: nothing parsed from a non-empty recording")
        for item in out:
            if isinstance(item, ReelData):
                _reel(item)
            elif isinstance(item, CommentData):
                _require(bool(item.ig_comment_id) and item.text is not None, "comment id/text")
                _require(item.like_count >= 0 and item.reply_count >= 0, "negative comment count")
    return out


def _counts(values: dict[str, Any], names: tuple[str, ...]) -> None:
    for name in names:
        _require(values.get(name) is None or values[name] >= 0, f"{name} is negative")


def _reel(reel: ReelData) -> None:
    """Missing means unknown, never zero (MVP doc §4 data-quality rules)."""
    _counts(reel.model_dump(), ("views", "likes", "comments", "shares"))
    _require(not reel.likes_hidden or reel.likes is None, "hidden likes must be None, not a count")
    _require(
        not reel.comments_disabled or reel.comments is None,
        "comments turned off must be None, not a count",
    )
    _require(bool(reel.shortcode and reel.permalink), "a reel needs its shortcode and permalink")
