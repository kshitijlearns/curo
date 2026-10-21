"""Small text helpers for captions and comments."""

from __future__ import annotations

import re

# Character ranges built from code points so no invisible characters live in the source
# (the formatter rewrites "\u" escapes into literal characters): Devanagari, and the emoji /
# symbol blocks seen in captions and comments.
_DEVANAGARI = f"{chr(0x0900)}-{chr(0x097F)}"
_EMOJI = (
    f"{chr(0x2600)}-{chr(0x27BF)}{chr(0x1F000)}-{chr(0x1FAFF)}"
    f"{chr(0x2B50)}{chr(0x1F1E6)}-{chr(0x1F1FF)}"
)
_JOINERS = chr(0x200D) + chr(0xFE0F)  # zero-width joiner, emoji presentation selector

_HASHTAG = re.compile("#([\\w" + _DEVANAGARI + "]+)")
_MENTION = re.compile(r"@([A-Za-z0-9._]{1,30})")
_EMOJI_ONLY = re.compile("^[\\s" + _EMOJI + _JOINERS + "]+$")
_SENTENCE_END = re.compile("[.!?]\\s|\\s[" + _EMOJI + "]")
_TRAILING = re.compile("[\\s" + _EMOJI + _JOINERS + "]+$")


def hashtags_in(caption: str) -> list[str]:
    """Hashtags in order, lower-cased, without '#', de-duplicated."""
    seen: list[str] = []
    for tag in _HASHTAG.findall(caption or ""):
        t = tag.lower()
        if t not in seen:
            seen.append(t)
    return seen


def mentions_in(text: str) -> list[str]:
    return [m.lower().rstrip(".") for m in _MENTION.findall(text or "")]


def mask_mentions(text: str) -> str:
    """Replace @handles with '@…' so no third-party handle is stored (privacy rule)."""
    return _MENTION.sub("@…", text or "")


def is_emoji_only(text: str) -> bool:
    return bool(_EMOJI_ONLY.match(text or ""))


def reel_title(caption: str, max_len: int = 70) -> str:
    """A short display title: the caption's first sentence or line, without hashtags."""
    text = (caption or "").strip().split("\n", 1)[0]
    text = _HASHTAG.sub("", text)
    text = _MENTION.sub("", text)
    # Cut at the first sentence end, or at an emoji that follows a clause.
    m = _SENTENCE_END.search(text)
    if m and m.start() >= 8:
        text = text[: m.start() + 1]
    text = _TRAILING.sub("", text).strip()
    text = text.rstrip(" .,!—-:")
    if len(text) > max_len:
        text = text[: max_len - 1].rsplit(" ", 1)[0] + "…"
    return text or "Untitled reel"
