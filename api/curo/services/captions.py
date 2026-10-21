"""Studio step 4: captions and hashtags (logic doc §12).

Captions: three that each do a different job (comments, likes, shares). The first line
restates the hook; one or two phrases people actually search are worked in; the call to
action matches the script's and isn't repeated; length, emoji and language follow the
creator's own captions. T12 writes them; the no-new-numbers check reads them.

Hashtags: candidates from the creator's past tags (with their results), tags on peer reels
on this topic, CURO's hashtag pages and tags T12 suggests. Each is scored

    0.5 × relevance + 0.3 × past results + 0.2 × specificity

and five are suggested as a mix: one broad topic tag, two niche, one community or region tag
and one series or signature tag if the creator has one. Never more than five — in the app, the
API and the database.
"""

from __future__ import annotations

import math
import re
import statistics
from collections.abc import Iterable
from dataclasses import dataclass, field

from curo.schemas.tasks import CaptionStyle
from curo.services.comments import language_of
from curo.services.text import hashtags_in
from curo.services.topics import PLACES

MAX_HASHTAGS = 5
WEIGHTS = {"relevance": 0.5, "results": 0.3, "specificity": 0.2}
MIX = ("broad", "niche", "niche", "local", "series")
GENERIC_TAGS = frozenset(
    [
        "reels",
        "reel",
        "reelsinstagram",
        "instagram",
        "instagood",
        "explore",
        "explorepage",
        "viral",
        "trending",
        "fyp",
        "foryou",
        "fashion",
        "style",
        "ootd",
        "love",
        "photography",
        "video",
        "instadaily",
    ]
)
JOB_WHY = {
    "comments": "Ends on a question → comments",
    "likes": "A quick summary people come back to → likes",
    "shares": "Relatable, easy to send → shares",
}
_EMOJI = re.compile(
    "[" + chr(0x2600) + "-" + chr(0x27BF) + chr(0x1F300) + "-" + chr(0x1FAFF) + "]"
)  # fmt: skip
_TAG_SPLIT = re.compile(r"#\w+")


class HashtagLimit(ValueError):
    """More than five hashtags: Instagram's own limit."""


def normalise_tags(tags: Iterable[str]) -> list[str]:
    """'#GanpatiOutfit ' → 'ganpatioutfit'; duplicates dropped; at most five or an error."""
    out: list[str] = []
    for t in tags:
        tag = t.strip().lstrip("#").lower()
        if tag and tag not in out:
            out.append(tag)
    if len(out) > MAX_HASHTAGS:
        raise HashtagLimit("You can pick up to 5 hashtags.")
    return out


# ------------------------------------------------------------------ the creator's caption style


def caption_style(captions: list[str]) -> CaptionStyle:
    words, emoji, langs = [], [], []
    for c in captions:
        body = _TAG_SPLIT.sub("", c)
        words.append(len(re.findall(r"[\w'’₹]+", body)))
        emoji.append(len(_EMOJI.findall(body)))
        if lang := language_of(body):
            langs.append(lang)
    if not words:
        return CaptionStyle()
    top = max(set(langs), key=langs.count) if langs else "en"
    language = top if langs and langs.count(top) / len(langs) >= 0.7 else "mixed"
    return CaptionStyle(
        words=round(statistics.median(words)),
        emoji=round(statistics.median(emoji)),
        language=language,  # type: ignore[arg-type]
    )


def search_phrases(topic: str | None, keywords: list[str], festival: str | None) -> list[str]:
    """Phrases people search, from the topic and its keywords ("Ganpati outfit ideas")."""
    out: list[str] = []
    if topic:
        out.append(topic)
    for k in keywords:
        phrase = k.strip()
        if phrase and len(phrase.split()) >= 2 and phrase.lower() not in (o.lower() for o in out):
            out.append(phrase[0].upper() + phrase[1:])
    if festival and festival.lower() not in (o.lower() for o in out):
        out.append(festival)
    return out[:3]


# ------------------------------------------------------------------ hashtags


@dataclass
class TagEvidence:
    tag: str
    creator_lifts: list[float] = field(default_factory=list)  # views lift of reels using it
    in_trend_feed: bool = False  # on a trend card in the creator's niche
    trend_momentum: float | None = None  # that card's posting growth (None: unknown)
    doc_share: float = 0.0  # share of the reels CURO has seen that use it
    page_posts: int | None = None
    suggested: bool = False  # suggested by T12


def _credit(lift: float) -> float:
    return max(0.0, min(1.0, 0.5 + (lift - 1.0)))


def relevance(tag: str, vocabulary: set[str]) -> float:
    """The share of the tag's letters covered by words of this draft (topic, script, idea)."""
    if not tag:
        return 0.0
    covered = [False] * len(tag)
    for w in sorted((w for w in vocabulary if len(w) >= 3), key=len, reverse=True):
        start = tag.find(w)
        while start != -1:
            for i in range(start, start + len(w)):
                covered[i] = True
            start = tag.find(w, start + 1)
    return sum(covered) / len(tag)


def results(e: TagEvidence) -> float:
    parts = []
    if e.creator_lifts:
        parts.append(_credit(statistics.median(e.creator_lifts)))
    if e.trend_momentum is not None:
        parts.append(_credit(e.trend_momentum))
    return sum(parts) / len(parts) if parts else 0.5  # unknown: neither good nor bad


def specificity(e: TagEvidence) -> float:
    if e.tag in GENERIC_TAGS:
        return 0.0
    by_share = 1.0 - min(1.0, max(0.0, (e.doc_share - 0.02) / 0.18))  # 2% → 1, 20% → 0
    if e.page_posts:
        by_posts = 1.0 - min(1.0, max(0.0, (math.log10(e.page_posts) - 4) / 3))  # 10K → 1, 10M → 0
        return round((by_share + by_posts) / 2, 3)
    return round(by_share, 3)


def kind(e: TagEvidence, festival_tags: set[str], series: set[str]) -> str:
    if e.tag in series:
        return "series"
    if any(place in e.tag for place in PLACES):
        return "local"
    if e.tag in GENERIC_TAGS or e.tag in festival_tags or e.doc_share > 0.10:
        return "broad"
    if e.page_posts and e.page_posts > 1_000_000:
        return "broad"
    return "niche"


@dataclass
class ScoredTag:
    tag: str
    kind: str
    score: float
    relevance: float
    results: float
    specificity: float


def score_tags(
    evidence: list[TagEvidence],
    vocabulary: set[str],
    festival_tags: set[str],
    series: set[str],
    region_words: set[str],
) -> list[ScoredTag]:
    out = []
    for e in evidence:
        k = kind(e, festival_tags, series)
        rel = relevance(e.tag, vocabulary)
        if k == "local" and any(r in e.tag for r in region_words):
            rel = max(rel, 0.6)  # the creator's audience is there, even if the script isn't
        if k == "series":
            rel = max(rel, 0.5)
        res, spec = results(e), specificity(e)
        total = (
            WEIGHTS["relevance"] * rel + WEIGHTS["results"] * res + WEIGHTS["specificity"] * spec
        )
        out.append(ScoredTag(e.tag, k, round(total, 3), round(rel, 3), round(res, 3), spec))
    return sorted(out, key=lambda s: (-s.score, s.tag))


def suggest(scored: list[ScoredTag]) -> list[str]:
    """Five tags as a mix — broad, niche, niche, local, series — the best of each kind; a kind
    with no candidate is filled by the next best niche tag, then any."""
    chosen: list[str] = []
    for want in MIX:
        pick = next((s for s in scored if s.kind == want and s.tag not in chosen), None)
        pick = pick or next((s for s in scored if s.kind == "niche" and s.tag not in chosen), None)
        pick = pick or next((s for s in scored if s.tag not in chosen), None)
        if pick:
            chosen.append(pick.tag)
    return chosen[:MAX_HASHTAGS]


def series_tags(
    creator_captions: list[tuple[str, list[str]]], shared_tags: dict[str, int]
) -> set[str]:
    """Tags the creator uses on three or more reels that the niche's trend feed doesn't share:
    their series or signature."""
    counts: dict[str, int] = {}
    for _caption, tags in creator_captions:
        for t in {t.lower() for t in tags}:
            counts[t] = counts.get(t, 0) + 1
    return {
        t
        for t, n in counts.items()
        if n >= 3 and shared_tags.get(t, 0) <= 1 and t not in GENERIC_TAGS
    }


def tags_in_caption(caption: str) -> list[str]:
    return [t.lower() for t in hashtags_in(caption)]
