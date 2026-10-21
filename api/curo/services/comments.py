"""Comment reading (logic doc §5 step 4): language, and grouping requests and questions into
themes such as "wants budget versions". Labels themselves come from T3."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from curo.services.text import is_emoji_only

_DEVANAGARI = re.compile(f"[{chr(0x0900)}-{chr(0x097F)}]")
_LATIN = re.compile(r"[A-Za-z]")
# Common Hindi words written in Latin letters (Hinglish markers).
_HINGLISH = re.compile(
    r"\b(?:yaar|kya|hai|hain|kahan|kaha|kitne|kitna|mera|meri|bhi|banao|dikhao|liya|pehnu|liye"
    r"|wala|wali|sasta|bahut|sundar|baat|haal|laga|sirf|karti|karta|hoon|dusra|kab|aayega|mein"
    r"|milega|ye|yeh|bilkul|mujhe|accha|acha|bohot|kaise|kiya)\b",
    re.IGNORECASE,
)

THEME_KINDS = ("request", "question")
MIN_THEME_N = 2
# Theme phrases this close (cosine) are the same theme said differently.
MERGE_SIMILARITY = 0.9


def language_of(text: str) -> str | None:
    """'hi' (Devanagari), 'hinglish' (Hindi in Latin letters), 'en', or None (emoji only)."""
    if not text or is_emoji_only(text):
        return None
    if _DEVANAGARI.search(text):
        return "hi"
    if not _LATIN.search(text):
        return None
    return "hinglish" if _HINGLISH.search(text) else "en"


def theme_key(theme: str | None) -> str | None:
    if not theme:
        return None
    key = re.sub(r"[^\w\s']", " ", theme.lower())
    key = re.sub(r"\s+", " ", key).strip()
    if not key or key in ("other question", "other request"):
        return None
    return key


@dataclass
class ThemeGroup:
    key: str
    kind: str
    comment_ids: list[str] = field(default_factory=list)


def group_themes(
    items: list[tuple[str, str, str]], embed: Callable[[list[str]], list[list[float]]]
) -> list[ThemeGroup]:
    """Group (comment_id, intent, theme_key) by theme, merging keys whose phrases mean the
    same (embedding cosine ≥ 0.9; a real model words the same theme slightly differently).
    The group's key is its most common phrase; its kind is its most common intent."""
    by_key: dict[str, list[tuple[str, str]]] = {}
    for cid, intent, key in items:
        if intent in THEME_KINDS and key:
            by_key.setdefault(key, []).append((cid, intent))
    keys = sorted(by_key, key=lambda k: (-len(by_key[k]), k))
    if not keys:
        return []
    vectors = np.asarray(embed(keys), dtype=float)
    parent = list(range(len(keys)))
    for i in range(len(keys)):
        for j in range(i):
            if float(vectors[i] @ vectors[j]) >= MERGE_SIMILARITY:
                parent[i] = parent[j]
                break
    merged: dict[int, list[str]] = {}
    for i, root in enumerate(parent):
        while parent[root] != root:
            root = parent[root]
        merged.setdefault(root, []).append(keys[i])
    groups = []
    for root, members in merged.items():
        rows = [row for k in members for row in by_key[k]]
        kind = Counter(intent for _cid, intent in rows).most_common(1)[0][0]
        groups.append(ThemeGroup(keys[root], kind, [cid for cid, _ in rows]))
    return sorted(groups, key=lambda g: (-len(g.comment_ids), g.key))
