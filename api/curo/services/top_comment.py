"""Top comment (logic doc §7): ranked by its own likes, then replies. The creator's own
comments, likely bots and emoji-only comments are skipped. A negative top comment is still
shown, with a label: hiding criticism would make the insight less honest. No commenter handle
is ever shown (DECISIONS D13)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from curo.services.text import is_emoji_only


@dataclass(frozen=True)
class TopComment:
    text: str
    likes: int
    replies: int
    negative: bool


def top_comment(comments: Iterable[Mapping[str, Any]]) -> TopComment | None:
    eligible = [
        c
        for c in comments
        if not c.get("is_creator")
        and not c.get("is_bot")
        and not is_emoji_only(c.get("text") or "")
    ]
    if not eligible:
        return None
    best = max(eligible, key=lambda c: (c.get("like_count") or 0, c.get("reply_count") or 0))
    negative = best.get("sentiment") == "negative" or best.get("intent") == "disagreement"
    return TopComment(
        best["text"], best.get("like_count") or 0, best.get("reply_count") or 0, negative
    )
