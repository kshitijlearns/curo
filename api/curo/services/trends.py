"""Trending for you (PLAN_V2 §4.4): a shared trend feed per niche, personalised per creator.

The feed is built once per niche from public hashtag pages (posting momentum and how crowded
each tag is) and the festival calendar. T16 writes the cards' words from those facts only.
"Trending for you" then ranks the niche's cards by how close they sit to the creator's own
content, so nothing is fetched per creator.
"""

from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np

from curo.services import topics

MIN_GROWTH = 1.2  # a tag counts as rising from 1.2× week on week
CO_TAG_MIN = 3  # a tag seen with the niche's tags on 3+ recent reels is a format/angle trend
MAX_CARDS = 6
FESTIVAL_LEAD_DAYS = 30
SHOWN = 4


@dataclass
class Page:
    tag: str
    growth: float | None
    reels_7d: int | None
    post_count: int | None
    captions: list[str] = field(default_factory=list)
    co_tags: Counter = field(default_factory=Counter)


@dataclass
class Candidate:
    key: str
    kind: str  # "festival" | "hashtag" | "format"
    label: str
    hashtags: list[str]
    momentum: float | None
    saturation: str
    window_start: date | None
    window_end: date | None
    facts: list[str]
    captions: list[str] = field(default_factory=list)


def saturation_of(reels_7d: int | None) -> str:
    """How crowded: reels posted on the tag in the last 7 days (from the page CURO read)."""
    if reels_7d is None:
        return "unknown"
    return "low" if reels_7d < 50 else "medium" if reels_7d < 200 else "high"


def _momentum_fact(tag: str, g: float | None) -> str | None:
    if g is None:
        return None
    return f"Daily posts on #{tag} are {g:.1f}× what they were over the 4 weeks before."


def candidates(pages: list[Page], festivals: list[dict], today: date) -> list[Candidate]:
    """Festivals coming up, rising hashtags, and tags that keep turning up alongside the
    niche's (a format or angle catching on). Strongest momentum first; at most six."""
    by_tag = {p.tag: p for p in pages}
    out: list[Candidate] = []
    used: set[str] = set()
    for f in festivals:
        days = (f["starts_on"] - today).days
        if days > FESTIVAL_LEAD_DAYS or f["ends_on"] < today:
            continue
        tags = sorted(t for t in topics.keyword_tags(f["keywords"]) if t in by_tag)
        growths = [by_tag[t].growth for t in tags if by_tag[t].growth is not None]
        g = round(statistics.median(growths), 2) if growths else None
        reels = [by_tag[t].reels_7d for t in tags if by_tag[t].reels_7d is not None]
        facts = [
            f"{f['name']} starts in {days} days." if days > 0 else f"{f['name']} is on now.",
        ]
        if tags and g is not None:
            lead = max(tags, key=lambda t: by_tag[t].growth or 0)
            facts.append(_momentum_fact(lead, by_tag[lead].growth) or "")
        out.append(
            Candidate(
                key=f"festival:{f['id']}",
                kind="festival",
                label=f["name"],
                hashtags=tags,
                momentum=g,
                saturation=saturation_of(max(reels) if reels else None),
                window_start=f["starts_on"] - timedelta(days=14),
                window_end=f["ends_on"],
                facts=[x for x in facts if x],
                captions=[c for t in tags for c in by_tag[t].captions[:3]],
            )
        )
        used |= set(tags)
    for p in sorted(pages, key=lambda p: -(p.growth or 0)):
        if p.tag in used or p.growth is None or p.growth < MIN_GROWTH:
            continue
        out.append(
            Candidate(
                key=f"tag:{p.tag}",
                kind="hashtag",
                label=f"#{p.tag}",
                hashtags=[p.tag],
                momentum=p.growth,
                saturation=saturation_of(p.reels_7d),
                window_start=today,
                window_end=today + timedelta(days=14),
                facts=[_momentum_fact(p.tag, p.growth) or ""],
                captions=p.captions[:5],
            )
        )
        used.add(p.tag)
    co: Counter = Counter()
    for p in pages:
        co.update(p.co_tags)
    for tag, n in co.most_common():
        if tag in used or tag in by_tag or n < CO_TAG_MIN:
            continue
        out.append(
            Candidate(
                key=f"format:{tag}",
                kind="format",
                label=f"#{tag}",
                hashtags=[tag],
                momentum=None,
                saturation="unknown",
                window_start=today,
                window_end=today + timedelta(days=21),
                facts=[f"#{tag} turned up on {n} recent reels in this niche’s hashtag pages."],
            )
        )
        used.add(tag)
        if len(out) >= MAX_CARDS + 2:
            break
    ranked = sorted(out, key=lambda c: (c.kind != "festival", -(c.momentum or 0), c.key))
    return ranked[:MAX_CARDS]


# ------------------------------------------------------------------ personalising


def _cos(a: list[float], b: list[float]) -> float:
    va, vb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    d = float(np.linalg.norm(va) * np.linalg.norm(vb))
    return float(va @ vb / d) if d else 0.0


def momentum_credit(m: float | None) -> float:
    """Posting growth → 0–1: flat (1.0×) is 0.2, 2.25× or more is 1."""
    if m is None:
        return 0.4
    return max(0.0, min(1.0, 0.2 + 0.8 * (float(m) - 1.0) / 1.25))


@dataclass
class Ranked:
    card: dict
    fit: float
    score: float
    why: str


def rank_for_creator(
    cards: list[dict], vectors: list[list[float]], subclusters: list[dict], shown: int = SHOWN
) -> list[Ranked]:
    """Score = 0.6 × fit with the creator's own content + 0.4 × momentum. Fit is how close the
    card sits to the creator's nearest sub-cluster, relative to how close that sub-cluster's
    own reels sit (1 = as close as their own reels)."""
    out = []
    for card, v in zip(cards, vectors, strict=True):
        best, rel = None, 0.0
        for g in subclusters:
            r = min(1.0, max(0.0, _cos(v, g["caption_vector"])) / max(g["typical_sim"], 1e-6))
            if r > rel:
                best, rel = g, r
        fit = round(rel, 3)
        score = round(0.6 * fit + 0.4 * momentum_credit(card.get("momentum")), 3)
        if best is not None and rel >= 0.4:
            lift = (best["lifts"].get("views") or {}).get("lift")
            why = (
                f"Close to your “{best['label']}” reels, which get {lift:.1f}× your usual views."
                if lift
                else f"Close to your “{best['label']}” reels."
            )
        else:
            why = "Popular in your niche; a step away from what you usually post."
        out.append(Ranked(card, fit, score, why))
    out.sort(key=lambda r: (-r.score, r.card["name"]))
    return out[:shown]
