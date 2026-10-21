"""Opportunity areas (logic doc §8; v2 PLAN_V2 §4.1): candidates from the creator's own data
and the shared trend feed, merged, filtered and scored.

    Score = 10 × (0.35 F + 0.25 D + 0.25 T + 0.15 O)

The logic doc describes each part; the formulas below make those descriptions concrete
(DECISIONS D60). Every part is 0–1 and carries the facts it was computed from, which the
detail page is assembled from.

* F, creator fit: how close the topic is to the creator's sub-clusters, weighted by their
  views lift (lift 1.0 → half credit, 1.5+ → full), plus whether they've made the format.
* D, audience demand: the share of recent comments asking for it (5% → full), how the
  audience engaged with the nearest kind of reel, and whether places in comments match.
* T, timeliness: for dated events, closeness to the best window (7–14 days before, falling
  quickly after), plus posting momentum (2.25× week on week → full).
* O, openness: how crowded the topic is, from the trend feed (low 0.9, medium 0.6, high 0.3)
  or the reels posted on its hashtags in the last 7 days; 0.7 when nothing measures it.

v2 removed peer tracking: the "Competitor" source and the peer-evidence part are gone.
"""

from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass, field
from datetime import date

import numpy as np

from curo.services import topics

WEIGHTS = {"F": 0.35, "D": 0.25, "T": 0.25, "O": 0.15}
PART_NAMES = {
    "F": "Creator fit",
    "D": "Audience demand",
    "T": "Timeliness",
    "O": "Openness",
}
# Which source a merged topic is shown under ("where it was first found", logic doc §8):
# trends first, then the creator's own content, then audience requests.
TAG_ORDER = ("trend", "your_content", "audience")
SATURATION_OPENNESS = {"low": 0.9, "medium": 0.6, "high": 0.3}
TAG_LABELS = {
    "competitor": "Competitor",
    "trend": "Trend",
    "audience": "Audience",
    "your_content": "Your content",
}
TOP = 5
BRAND_UNSAFE = frozenset(
    [
        "alcohol",
        "beer",
        "whisky",
        "vodka",
        "gambling",
        "betting",
        "casino",
        "crypto",
        "bitcoin",
        "cigarette",
        "vape",
        "smoking",
        "politics",
        "election",
        "party-politics",
        "weapon",
        "gun",
    ]
)


@dataclass
class Candidate:
    key: str
    source: str
    keywords: set[str]  # words/tags that mark a reel or comment as on this topic
    anchors: set[str] = field(default_factory=set)  # the topic-defining ones, used to merge
    texts: list[str] = field(default_factory=list)
    sources: set[str] = field(default_factory=set)
    festival: dict | None = None
    hashtags: set[str] = field(default_factory=set)
    themes: list[dict] = field(default_factory=list)
    followup: dict | None = None
    subcluster: dict | None = None
    trend: dict | None = None  # the trend card it came from (key, name, saturation, momentum)

    def __post_init__(self) -> None:
        self.sources.add(self.source)

    @property
    def tag(self) -> str:
        return next(t for t in TAG_ORDER if t in self.sources)

    def absorb(self, other: Candidate) -> None:
        self.keywords |= other.keywords
        self.anchors |= other.anchors
        self.texts += other.texts
        self.sources |= other.sources
        self.festival = self.festival or other.festival
        self.hashtags |= other.hashtags
        self.themes += other.themes
        self.followup = self.followup or other.followup
        self.subcluster = self.subcluster or other.subcluster
        self.trend = self.trend or other.trend


KEY_PRIORITY = ("festival:", "trend:", "tag:", "theme:", "followup:", "subcluster:")


def _key_rank(key: str) -> int:
    return next((i for i, p in enumerate(KEY_PRIORITY) if key.startswith(p)), len(KEY_PRIORITY))


def same_topic(a: Candidate, b: Candidate, comments_by_theme: dict[str, list[dict]]) -> bool:
    """Candidates that mean the same thing (logic doc §8 step 2): they share a defining word
    or tag, most of one's evidence names the other, or an audience theme is mostly about it."""
    for x, y in ((a, b), (b, a)):
        if x.anchors & (y.anchors | y.hashtags):
            return True
        if x.anchors and y.texts:
            naming = sum(1 for t in y.texts if topics.mentions(t, [], x.anchors))
            if naming / len(y.texts) >= 0.5:
                return True
    for x, y in ((a, b), (b, a)):
        for theme in x.themes:
            if x.source != "audience":
                continue
            comments = comments_by_theme.get(theme["key"], [])
            if not comments:
                continue
            if y.anchors:  # most of the theme's comments name the other topic
                hits = sum(1 for c in comments if topics.mentions(c["text"], [], y.anchors))
                if hits / len(comments) >= 0.3:
                    return True
            if y.followup:  # that reel draws more of the theme's comments than any other
                per_reel = Counter(c["reel_id"] for c in comments)
                top_reel, top_n = per_reel.most_common(1)[0]
                if top_reel == y.followup["reel_id"] and top_n / len(comments) >= 0.2:
                    return True
    return False


def merge(cands: list[Candidate], comments_by_theme: dict[str, list[dict]]) -> list[Candidate]:
    """Greedy merge in key priority order; the merged topic keeps the most stable key."""
    pool = sorted(cands, key=lambda c: (_key_rank(c.key), c.key))
    out: list[Candidate] = []
    for c in pool:
        target = next((o for o in out if same_topic(o, c, comments_by_theme)), None)
        if target is None:
            out.append(c)
        else:
            target.absorb(c)
    return out


# ------------------------------------------------------------------ scoring


@dataclass
class Part:
    value: float
    facts: list[str]


@dataclass
class Context:
    today: date
    subclusters: list[dict]  # label, centroid, lifts {metric: {lift, n}}, typical_sim, reel_ids
    creator_formats: dict[str, int]
    comments: list[
        dict
    ]  # labelled non-bot comments on the last 30 reels: text, intent, theme_key, reel_id
    comment_regions: dict[str, int]
    hashtag_growth: dict[str, float]
    hashtag_reels_7d: dict[str, int] = field(default_factory=dict)  # tag → reels in 7 days


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _cos(a: list[float], b: list[float]) -> float:
    va, vb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    d = float(np.linalg.norm(va) * np.linalg.norm(vb))
    return float(va @ vb / d) if d else 0.0


def best_subcluster(vector: list[float] | None, ctx: Context) -> tuple[dict | None, float]:
    """The sub-cluster the topic sits closest to, and how close (1 = as close as its own reels).
    Topics are described by captions and comments, so they're compared with each sub-cluster's
    captions (not with its video descriptions)."""
    best, best_match = None, 0.0
    if vector is None:
        return None, 0.0
    for g in ctx.subclusters:
        rel = min(1.0, max(0.0, _cos(vector, g["caption_vector"])) / max(g["typical_sim"], 1e-6))
        if rel > best_match:
            best, best_match = g, rel
    return best, best_match


def lift_credit(lift: float | None) -> float:
    return 0.5 if lift is None else _clamp(0.5 + (lift - 1.0))


def part_f(c: Candidate, vector: list[float] | None, ctx: Context) -> Part:
    group, rel = best_subcluster(vector, ctx)
    facts: list[str] = []
    if group is None:
        match = 0.0
    else:
        views = (group["lifts"].get("views") or {}).get("lift")
        match = rel * lift_credit(views)
        if views:
            facts.append(f"Your “{group['label']}” reels get {views:.1f}× your usual views.")
    # Format: the creator's own topics are in formats they've made; others are open.
    fmt = 1.0 if (c.followup or c.subcluster) else 0.5
    return Part(round(0.7 * match + 0.3 * fmt, 3), facts)


def topic_comments(c: Candidate, ctx: Context) -> list[dict]:
    """Requests and questions about the topic: in its theme, or naming its defining words."""
    theme_keys = {t["key"] for t in c.themes}
    asks = [x for x in ctx.comments if x["intent"] in ("request", "question")]
    return [
        x
        for x in asks
        if x["theme_key"] in theme_keys or (c.anchors and topics.mentions(x["text"], [], c.anchors))
    ]


def part_d(c: Candidate, vector: list[float] | None, ctx: Context) -> Part:
    total = len(ctx.comments)
    asked = topic_comments(c, ctx)
    share = len(asked) / total if total else 0.0
    ask = _clamp(share / 0.05)
    group, _ = best_subcluster(vector, ctx)
    eng = 0.5
    if group:
        rates = [
            (group["lifts"].get(m) or {}).get("lift")
            for m in ("comment_rate", "like_rate")
            if (group["lifts"].get(m) or {}).get("lift")
        ]
        if rates:
            eng = lift_credit(statistics.fmean(rates))
    facts = []
    if share:
        facts.append(f"{round(share * 100, 1)}% of your recent comments ask about it.")
    loc = 0.7  # nothing place-specific about the topic
    if c.festival:
        regional = [r for r in c.festival.get("regions", []) if r != "IN"]
        if regional:
            hits = {r: n for r, n in ctx.comment_regions.items() if r in regional}
            loc = 1.0 if hits else 0.3
            if hits:
                facts.append("Your comments often mention places where it’s celebrated.")
    return Part(round(0.5 * ask + 0.3 * eng + 0.2 * loc, 3), facts)


def window_credit(days_until: int, during: bool) -> float:
    """Best 7–14 days before a dated event, falling quickly after it starts."""
    if during:
        return 0.5
    if days_until < 0:
        return 0.0
    if days_until < 7:
        return 0.6 + 0.4 * days_until / 7
    if days_until <= 14:
        return 1.0
    if days_until <= 30:
        return 1.0 - 0.6 * (days_until - 14) / 16
    return 0.2


def momentum(c: Candidate, ctx: Context) -> tuple[float | None, str | None]:
    """Momentum: the topic's hashtags in CURO's index (last 7 days vs the 28 before), the trend
    card it came from, or a reel to follow up that is picking up again."""
    known = sorted(ctx.hashtag_growth[t] for t in c.hashtags if t in ctx.hashtag_growth)
    if known:
        g = statistics.median(known)
        lead = max((t for t in c.hashtags if t in ctx.hashtag_growth), key=ctx.hashtag_growth.get)
        return g, (
            f"Daily posts on #{lead} are {ctx.hashtag_growth[lead]:.1f}× what they were over the "
            "4 weeks before."
        )
    if c.followup and c.followup.get("velocity_growth"):
        g = c.followup["velocity_growth"]
        return (
            g,
            f"“{c.followup['title']}” is gaining views {g:.1f}× faster than at its last snapshot.",
        )
    if c.trend and c.trend.get("momentum"):
        return float(c.trend["momentum"]), c.trend.get("why_rising")
    return None, None


def part_t(c: Candidate, ctx: Context) -> Part:
    g, fact = momentum(c, ctx)
    m = 0.3 if g is None else _clamp((g - 1.0) / 1.25)
    facts = [fact] if fact else []
    if c.festival:
        start, end = c.festival["starts_on"], c.festival["ends_on"]
        days = (start - ctx.today).days
        during = start <= ctx.today <= end
        w = window_credit(days, during)
        facts.insert(
            0,
            f"{c.festival['name']} starts in {days} days."
            if days > 0
            else f"{c.festival['name']} is on now.",
        )
        return Part(round(0.6 * w + 0.4 * m, 3), facts)
    return Part(round(m, 3), facts)


def part_o(c: Candidate, ctx: Context) -> Part:
    """Openness: how crowded the topic is. The trend card's saturation when it came from the
    trend feed, else the reels posted on its hashtags in the last 7 days."""
    if c.trend and c.trend.get("saturation") in SATURATION_OPENNESS:
        sat = c.trend["saturation"]
        return Part(SATURATION_OPENNESS[sat], [f"How crowded it is in your niche: {sat}."])
    counts = {t: ctx.hashtag_reels_7d[t] for t in c.hashtags if t in ctx.hashtag_reels_7d}
    if not counts:
        return Part(0.7, [])  # nothing measures how crowded it is: neither open nor crowded
    tag, n = max(counts.items(), key=lambda kv: (kv[1], kv[0]))
    sat = "low" if n < 50 else "medium" if n < 200 else "high"
    return Part(SATURATION_OPENNESS[sat], [f"#{tag} had {n} new reels in the last 7 days ({sat})."])


@dataclass
class Scored:
    candidate: Candidate
    parts: dict[str, Part]
    score: float  # 0–10

    @property
    def contributions(self) -> dict[str, float]:
        return {k: WEIGHTS[k] * p.value for k, p in self.parts.items()}


def score(c: Candidate, vector: list[float] | None, ctx: Context) -> Scored:
    parts = {
        "F": part_f(c, vector, ctx),
        "D": part_d(c, vector, ctx),
        "T": part_t(c, ctx),
        "O": part_o(c, ctx),
    }
    total = 10 * sum(WEIGHTS[k] * parts[k].value for k in WEIGHTS)
    return Scored(c, parts, round(total, 2))


# ------------------------------------------------------------------ filters and texts


def posted_recently(c: Candidate, creator_recent: list[dict]) -> bool:
    """The creator posted on this topic in the last 14 days (a follow-up is exempt)."""
    if c.followup or not c.anchors:
        return False
    return any(topics.mentions(r["caption"], r["hashtags"], c.anchors) for r in creator_recent)


def unsafe(c: Candidate, blocked: set[str]) -> bool:
    words = c.keywords | c.anchors | c.hashtags
    return bool(words & BRAND_UNSAFE) or any(b in w for b in blocked for w in words)


def signals(s: Scored) -> list[str]:
    out = []
    if s.parts["F"].value >= 0.6:
        out.append("Your niche")
    if "trend" in s.candidate.sources or s.parts["T"].value >= 0.6:
        out.append("Trend")
    if "audience" in s.candidate.sources or s.parts["D"].value >= 0.6:
        out.append("Audience")
    if "your_content" in s.candidate.sources:
        out.append("Your content")
    return out[:4]


def top_parts(s: Scored, n: int = 2) -> list[str]:
    return [k for k, _ in sorted(s.contributions.items(), key=lambda kv: -kv[1])[:n]]


def card_text(s: Scored, name: str) -> str:
    """The one line on Home, assembled from where the topic was found."""
    c = s.candidate
    if c.tag == "trend":
        facts = s.parts["T"].facts
        return " ".join(facts[:2]) if facts else f"{name} is picking up right now."
    if c.followup:
        if c.followup.get("growing"):
            return f"“{c.followup['title']}” is picking up again — a follow-up could ride its momentum."
        return f"People are asking for more of “{c.followup['title']}” — a follow-up answers them."
    if c.tag == "audience" and c.themes:
        share = round(sum(t["share"] for t in c.themes) * 100, 1)
        return (
            f"{share}% of your recent comments {c.themes[0]['phrase']} — a reel that answers it meets a "
            "demand your audience has already voiced."
        )
    if c.subcluster:
        return (
            f"Your “{c.subcluster['label']}” reels do well and you haven’t posted one in a month."
        )
    return name


def fit_rows(s: Scored, why_it_fits: str) -> list[dict]:
    """ "Why it fits you": the creator-fit sentence, then the strongest other facts."""
    rows = [{"k": "Your content", "t": why_it_fits}] if why_it_fits else []
    for key in top_parts(s, n=5):
        if key == "F":
            continue
        label = {"D": "Audience", "T": "Timing", "O": "Room left"}[key]
        for fact in s.parts[key].facts[:1]:
            rows.append({"k": label, "t": fact})
    return rows[:4]
