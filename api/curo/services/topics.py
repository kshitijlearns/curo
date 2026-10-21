"""Topics: what a reel, comment or hashtag is about, and how fast it's moving.

Shared by the hashtag collection and opportunity building. A topic is matched by keywords
(words and hashtags) so the evidence stays explainable: "6 creators you track posted about
Ganpati" means six of them used those words or tags.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import date, datetime, timedelta

_WORD = re.compile(r"[a-z0-9₹']+")
GENERIC = frozenset(
    [
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "of",
        "to",
        "in",
        "on",
        "at",
        "for",
        "with",
        "from",
        "by",
        "is",
        "are",
        "was",
        "it",
        "this",
        "that",
        "my",
        "your",
        "our",
        "you",
        "i",
        "me",
        "we",
        "they",
        "look",
        "looks",
        "outfit",
        "outfits",
        "idea",
        "ideas",
        "reel",
        "reels",
        "video",
        "new",
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "way",
        "ways",
        "style",
        "styling",
        "how",
        "what",
        "why",
        "when",
        "where",
        "which",
        "who",
        "week",
        "day",
        "days",
        "best",
        "under",
        "part",
        "get",
        "ready",
        "festive",
        "edition",
        "first",
        "last",
        "next",
    ]
)
# Niche of a creator (from their DNA's broad cluster) → festival-calendar niche.
NICHE_OF_CLUSTER = {
    "fashion_styling": "fashion",
    "beauty": "beauty",
    "food": "food",
    "fitness": "fitness",
    "travel": "travel",
    "creator_tips": "creator_tips",
    "comedy": "comedy",
    "education": "education",
    "lifestyle": "lifestyle",
    "other": "lifestyle",
}
# Places that pin comments to a region (a group-level hint only, logic doc §3).
PLACES = {
    "mumbai": "IN-MH", "pune": "IN-MH", "lalbaug": "IN-MH", "thane": "IN-MH", "nagpur": "IN-MH",
    "bandra": "IN-MH", "dadar": "IN-MH", "delhi": "IN-DL", "noida": "IN-UP", "lucknow": "IN-UP",
    "bengaluru": "IN-KA", "bangalore": "IN-KA", "chennai": "IN-TN", "hyderabad": "IN-TG",
    "kolkata": "IN-WB", "ahmedabad": "IN-GJ", "surat": "IN-GJ", "jaipur": "IN-RJ",
}  # fmt: skip


def words(text: str) -> list[str]:
    return _WORD.findall((text or "").lower())


def keyword_tags(keywords: Iterable[str]) -> set[str]:
    """Calendar keywords as hashtags: "ganpati outfit" → "ganpatioutfit"."""
    return {re.sub(r"[^a-z0-9]", "", k.lower()) for k in keywords if k.strip()}


def mentions(text: str, hashtags: Iterable[str], keywords: Iterable[str]) -> bool:
    """Does a caption (or comment) with these hashtags talk about the topic?"""
    found = set(words(text))
    tags = [t.lower() for t in hashtags]
    for k in keywords:
        k = k.lower()
        if " " in k:
            if k in (text or "").lower() or k.replace(" ", "") in tags:
                return True
        elif k in found or any(k == t or (len(k) >= 5 and k in t) for t in tags):
            return True
    return False


def distinctive(texts: Iterable[str], min_count: int = 2) -> set[str]:
    """Words and tags shared by at least ``min_count`` of the texts, minus generic ones."""
    counts: Counter[str] = Counter()
    for t in texts:
        counts.update(
            set(w for w in words(t) if w not in GENERIC and len(w) > 2 and not w.isdigit())
        )
    return {w for w, n in counts.items() if n >= min_count}


MIN_COVERAGE = 0.25  # a partly covered day counts once at least a quarter of it is seen


def daily_counts(
    posted: Iterable[datetime], fetched_at: datetime, oldest: datetime | None
) -> dict[str, list[float]]:
    """Reels per calendar day as {day: [count, coverage]} for the days before today. A page
    lists only its most recent reels, so when it was cut off (``oldest`` given) the oldest
    day is only partly seen: its count is scaled up by the share of the day covered. Days
    inside the covered span with no reels count as 0."""
    posted = list(posted)
    if not posted:
        return {}
    counts: Counter[date] = Counter(p.date() for p in posted)
    start = oldest.date() if oldest else min(counts)
    out: dict[str, list[float]] = {}
    d = start
    while d < fetched_at.date():
        n = counts.get(d, 0)
        coverage = 1.0
        if oldest and d == oldest.date():
            day_start = datetime.combine(d, datetime.min.time(), tzinfo=oldest.tzinfo)
            coverage = 1.0 - (oldest - day_start).total_seconds() / 86400
        if coverage >= MIN_COVERAGE:
            out[d.isoformat()] = [round(n / coverage, 1), round(coverage, 2)]
        d += timedelta(days=1)
    return out


def merge_counts(
    old: Mapping[str, list[float]], new: Mapping[str, list[float]]
) -> dict[str, list[float]]:
    """Keep, for each day, the count seen with the most coverage."""
    out = dict(old)
    for day, value in new.items():
        if day not in out or value[1] >= out[day][1]:
            out[day] = value
    return out


def growth(counts: Mapping[str, list[float]], today: date, min_days: int = 5) -> float | None:
    """Posting momentum: the daily rate over the last 7 days ÷ the daily rate over the 28
    days before (as many of them as are known, at least ``min_days`` on each side)."""
    recent = [counts[d][0] for d in _days(today, 1, 7) if d in counts]
    before = [counts[d][0] for d in _days(today, 8, 35) if d in counts]
    if len(recent) < min_days or len(before) < min_days:
        return None
    rate_before = sum(before) / len(before)
    if rate_before <= 0:
        return None
    return round((sum(recent) / len(recent)) / rate_before, 2)


def _days(today: date, start: int, end: int) -> list[str]:
    return [(today - timedelta(days=k)).isoformat() for k in range(start, end + 1)]


def regions_in(texts: Iterable[str]) -> Counter[str]:
    """How often comments mention places in each region."""
    out: Counter[str] = Counter()
    for t in texts:
        for w in set(words(t)):
            if w in PLACES:
                out[PLACES[w]] += 1
    return out
