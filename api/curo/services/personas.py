"""Follower Personas (v2.2 §1–§3): every number about a persona, computed here.

A persona is a summary of a cluster of public comments, never one commenter. This module is
pure (no database, no models), so it is unit-tested directly:

* ``cluster``: exactly 4 groups by k-means (k = 4, several seeds; the result that agrees most
  with the others is kept), on each comment's embedding plus behaviour features; every group
  ends with at least 8% of the (90-day-weighted) comments.
* ``profile``: a group's facts — share, intents, themes, language mix, sentiment, the topics
  and formats it over-indexes on, the lift of the reels it comments on, turn-offs, places
  mentioned, favourite reels, confidence and mood — each with the sentence a creator reads.
* ``starter``: four "early guess" personas from niche templates when data is thin.
* ``match``: last build's personas against the new groups by centroid cosine (≥ 0.8 keeps the
  persona's id, name, colour and seed).
* ``code_fit`` and ``blend``: a persona's score for an idea or draft, and A in the idea score
  (Σ share × persona score / Σ share).

Likes are aggregate: public data says how many liked a reel, not who. So a group's "like"
behaviour is the like rate of the reels it comments on, and copy says "reels they comment on
also get…", never "they liked".
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import numpy as np

from curo.services.topics import PLACES

K = 4
MIN_SHARE = 0.08
SEEDS, FAST_SEEDS = 8, 3
FAST_MAX_COMMENTS = 600
RECENT_DAYS, OLD_WEIGHT = 90, 0.35
STARTER_MIN_COMMENTS, STARTER_MIN_REELS = 40, 5
HIGH_CONFIDENCE = 150
PERSONA_LOW_N = 15  # a persona with fewer comments of its own drops one confidence step
MATCH_COSINE = 0.8
SHIFT_POINTS = 0.05  # a share change that earns the recap's followers_shift slide
LOVE_INDEX, OFF_INDEX = 1.15, 0.75
MIN_ITEM_N = 5  # comments behind an over- or under-index
COLORS = ("blue", "lavender", "pink", "ink")
LABEL = "Built from your public comments. Personas are summaries, not real people."
EARLY_GUESS = "Early guess: gets sharper as people comment"

INTENTS = (
    "question",
    "request",
    "thats_me",
    "tags_friend",
    "plans_to_save",
    "disagreement",
    "praise",
    "other",
)
INTENT_WORDS = {
    "question": "ask questions",
    "request": "ask for more",
    "thats_me": "say “that’s me”",
    "tags_friend": "tag friends",
    "plans_to_save": "save ideas for later",
    "disagreement": "push back",
    "praise": "cheer you on",
    "other": "react",
}
LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "hinglish": "Hinglish",
    "mr": "Marathi",
    "ta": "Tamil",
    "te": "Telugu",
    "bn": "Bengali",
    "gu": "Gujarati",
}
FORMAT_LABELS = {
    "talking_head": "talking-head",
    "voiceover_broll": "voiceover",
    "grwm": "get-ready-with-me",
    "tutorial": "tutorial",
    "listicle": "list-style",
    "lookbook": "lookbook",
    "multi_look": "multi-look",
    "haul": "haul",
    "transition": "transition",
    "before_after": "before-and-after",
    "vlog": "vlog",
    "skit": "skit",
}
MOOD_WORDS = {1: "Not feeling it", 2: "Lukewarm", 3: "Interested", 4: "Fan", 5: "Big fan"}
MOOD_OF_METER = {1: "skip", 2: "unsure", 3: "neutral", 4: "like", 5: "love"}

# Studio: a persona's score → its reaction (v2.2 §6.3), and the reaction's badge.
REACTIONS = ((75, "watch_all"), (55, "watch"), (35, "scroll_past"), (0, "skip"))
REACTION_WORDS = {
    "watch_all": "Would watch it all",
    "watch": "Would watch",
    "scroll_past": "Might scroll past",
    "skip": "Would skip",
}
REACTION_MOOD = {"watch_all": "love", "watch": "like", "scroll_past": "unsure", "skip": "skip"}
BADGE = {"love": "Love", "like": "Like", "unsure": "Unsure", "skip": "Skip"}


# ------------------------------------------------------------------ inputs


@dataclass
class PComment:
    id: str
    reel_id: str
    text: str
    intent: str | None = None
    sentiment: str | None = None
    language: str | None = None
    theme: str | None = None  # the comment theme's label
    tags_friend: bool = False
    posted: datetime | None = None
    vector: list[float] | None = None


@dataclass
class PReel:
    id: str
    title: str
    posted: datetime
    format: str | None = None
    context: str | None = None
    group: str | None = None  # the sub-cluster label
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None

    def rate(self, metric: str) -> float | None:
        v = getattr(self, metric)
        if v is None or not self.views:
            return None
        return v / self.views


# ------------------------------------------------------------------ numbers


def pct(x: float) -> int:
    return round(100 * x)


def fx(x: float) -> str:
    """1.7×"""
    return f"{x:.1f}×"


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def cosine(a, b) -> float:
    va, vb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    d = float(np.linalg.norm(va) * np.linalg.norm(vb))
    return float(va @ vb / d) if d else 0.0


def largest_remainder(shares: list[float]) -> list[int]:
    """Whole percents that add up to 100."""
    total = sum(shares) or 1.0
    raw = [100 * s / total for s in shares]
    out = [math.floor(r) for r in raw]
    for i in sorted(range(len(raw)), key=lambda i: (-(raw[i] - math.floor(raw[i])), i)):
        if sum(out) >= 100:
            break
        out[i] += 1
    return out


# ------------------------------------------------------------------ weights and features


def weights(comments: list[PComment], reels: dict[str, PReel], today: datetime) -> np.ndarray:
    """Weighted towards the last 90 days: 1.0 inside, 0.35 older."""
    cutoff = today - timedelta(days=RECENT_DAYS)
    out = []
    for c in comments:
        when = c.posted or (reels[c.reel_id].posted if c.reel_id in reels else None)
        out.append(1.0 if when is None or when >= cutoff else OLD_WEIGHT)
    return np.asarray(out, dtype=float)


def _onehot(values: list[str | None], scale: float) -> np.ndarray:
    keys = sorted({v for v in values if v})
    if not keys:
        return np.zeros((len(values), 0))
    idx = {k: i for i, k in enumerate(keys)}
    m = np.zeros((len(values), len(keys)))
    for r, v in enumerate(values):
        if v:
            m[r, idx[v]] = 1.0
    return m * scale


def features(comments: list[PComment], reels: dict[str, PReel]) -> np.ndarray:
    """[embedding (unit) ⊕ intent ⊕ language ⊕ the reel's sub-cluster ⊕ its format ⊕ tags a
    friend]. Behaviour blocks are scaled so meaning and behaviour both count."""
    emb = np.asarray([c.vector for c in comments], dtype=float)
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    emb = emb / np.where(norms == 0, 1.0, norms)
    blocks = [
        emb,
        _onehot([c.intent for c in comments], 0.55),
        _onehot([c.language for c in comments], 0.3),
        _onehot([reels[c.reel_id].group if c.reel_id in reels else None for c in comments], 0.3),
        _onehot([reels[c.reel_id].format if c.reel_id in reels else None for c in comments], 0.3),
        np.asarray([[0.4 if c.tags_friend else 0.0] for c in comments]),
    ]
    return np.hstack(blocks)


# ------------------------------------------------------------------ clustering


@dataclass
class Clustering:
    labels: np.ndarray  # group 0–3 per comment, ordered by share (0 = largest)
    shares: list[float]
    stability: float  # mean adjusted Rand index of the kept run against the others


def _kmeans(x: np.ndarray, w: np.ndarray, k: int, seed: int) -> tuple[np.ndarray, float]:
    from sklearn.cluster import KMeans

    km = KMeans(n_clusters=k, n_init=1, random_state=seed, max_iter=200)
    labels = km.fit_predict(x, sample_weight=w)
    return labels, float(km.inertia_)


WARM_MARGIN = 1.05  # last month's grouping is kept unless a fresh one fits 5% better


def cluster(
    x: np.ndarray, w: np.ndarray, seeds: int = SEEDS, warm: np.ndarray | None = None
) -> Clustering:
    """Exactly 4 groups, the most stable of several k-means runs, each ≥ 8% of the weight.

    ``warm``: last build's grouping (a label per comment, from its centroids). k-means then
    also starts from it, and that result is kept unless the fresh one fits clearly better —
    so personas stay the same people month to month and only a real change moves them."""
    from sklearn.metrics import adjusted_rand_score

    if len(x) < K:
        raise ValueError("clustering needs at least 4 comments")
    runs = [_kmeans(x, w, K, s) for s in range(seeds)]
    agree = []
    for i, (li, _) in enumerate(runs):
        others = [adjusted_rand_score(li, lj) for j, (lj, _) in enumerate(runs) if j != i]
        agree.append(float(np.mean(others)) if others else 1.0)
    best = max(range(len(runs)), key=lambda i: (round(agree[i], 6), -runs[i][1], -i))
    labels = enforce_min_share(x, w, runs[best][0].copy())
    if warm is not None and len(set(warm.tolist())) == K:
        from sklearn.cluster import KMeans

        init = np.vstack([np.average(x[warm == g], axis=0, weights=w[warm == g]) for g in range(K)])
        km = KMeans(n_clusters=K, init=init, n_init=1, max_iter=200)
        kept = enforce_min_share(x, w, km.fit_predict(x, sample_weight=w))
        if inertia(x, w, kept) <= WARM_MARGIN * inertia(x, w, labels):
            labels = kept
    return Clustering(*_ordered(labels, w), stability=round(agree[best], 4))


def inertia(x: np.ndarray, w: np.ndarray, labels: np.ndarray) -> float:
    """Weighted sum of squared distances to each group's centre."""
    centres = _centres(x, w, labels)
    return float(sum(w[i] * np.sum((x[i] - centres[labels[i]]) ** 2) for i in range(len(x))))


def warm_labels(vectors: np.ndarray, previous: list[list[float]]) -> np.ndarray:
    """Each comment's nearest previous persona centroid (embedding space)."""
    prev = np.asarray(previous, dtype=float)
    prev = prev / np.where(
        np.linalg.norm(prev, axis=1, keepdims=True) == 0,
        1,
        np.linalg.norm(prev, axis=1, keepdims=True),
    )
    v = vectors / np.where(
        np.linalg.norm(vectors, axis=1, keepdims=True) == 0,
        1,
        np.linalg.norm(vectors, axis=1, keepdims=True),
    )
    return np.argmax(v @ prev.T, axis=1)


def _centres(x: np.ndarray, w: np.ndarray, labels: np.ndarray) -> dict[int, np.ndarray]:
    out = {}
    for g in sorted(set(labels.tolist())):
        m = labels == g
        out[g] = np.average(x[m], axis=0, weights=w[m])
    return out


def _share(w: np.ndarray, labels: np.ndarray) -> dict[int, float]:
    total = float(w.sum()) or 1.0
    return {g: float(w[labels == g].sum()) / total for g in sorted(set(labels.tolist()))}


def enforce_min_share(x: np.ndarray, w: np.ndarray, labels: np.ndarray) -> np.ndarray:
    """A group under 8% merges into its nearest group and the largest splits in two, until all
    four pass; if splitting can't get there, the small group takes the nearest comments of the
    groups that can spare them."""
    for _ in range(8):
        shares = _share(w, labels)
        small = [g for g, s in shares.items() if s < MIN_SHARE]
        if len(shares) == K and not small:
            return labels
        if len(shares) == K:
            g = min(small, key=lambda g: (shares[g], g))
            centres = _centres(x, w, labels)
            near = min(
                (h for h in centres if h != g),
                key=lambda h: (float(np.linalg.norm(centres[g] - centres[h])), h),
            )
            labels[labels == g] = near
        # Split the largest group back into two.
        shares = _share(w, labels)
        big = max(shares, key=lambda g: (shares[g], -g))
        m = labels == big
        if m.sum() < 2:
            break
        sub, _ = _kmeans(x[m], w[m], 2, 0)
        new = max(set(labels.tolist())) + 1
        idx = np.where(m)[0]
        labels[idx[sub == 1]] = new
        labels = _relabel(labels)
    return _top_up(x, w, labels)


def _relabel(labels: np.ndarray) -> np.ndarray:
    keys = sorted(set(labels.tolist()))
    return np.asarray([keys.index(v) for v in labels.tolist()])


def _top_up(x: np.ndarray, w: np.ndarray, labels: np.ndarray) -> np.ndarray:
    total = float(w.sum()) or 1.0
    for _ in range(K):
        shares = _share(w, labels)
        small = [g for g, s in shares.items() if s < MIN_SHARE]
        if not small:
            break
        g = small[0]
        centre = _centres(x, w, labels)[g]
        need = MIN_SHARE * total - float(w[labels == g].sum())
        donors = {h for h, s in shares.items() if h != g and s > MIN_SHARE}
        order = sorted(
            (i for i in range(len(labels)) if labels[i] in donors),
            key=lambda i: (float(np.linalg.norm(x[i] - centre)), i),
        )
        for i in order:
            if need <= 1e-9:
                break
            h = labels[i]
            if float(w[labels == h].sum()) - w[i] < MIN_SHARE * total:
                continue
            labels[i] = g
            need -= w[i]
    return labels


def _ordered(labels: np.ndarray, w: np.ndarray) -> tuple[np.ndarray, list[float]]:
    """Groups renumbered by share, largest first (ties by first appearance)."""
    shares = _share(w, labels)
    first = {g: int(np.where(labels == g)[0][0]) for g in shares}
    order = sorted(shares, key=lambda g: (-round(shares[g], 9), first[g]))
    remap = {g: i for i, g in enumerate(order)}
    return np.asarray([remap[v] for v in labels.tolist()]), [shares[g] for g in order]


def centroid(vectors: list[list[float]], w: np.ndarray | None = None) -> list[float]:
    m = np.asarray(vectors, dtype=float)
    c = np.average(m, axis=0, weights=w) if w is not None else m.mean(axis=0)
    n = float(np.linalg.norm(c))
    return (c / n if n else c).round(6).tolist()


# ------------------------------------------------------------------ profiles


@dataclass
class Item:
    """Something a group over- or under-indexes on: a format or a sub-cluster."""

    kind: str  # "format" | "topic"
    value: str
    label: str
    index: float  # share of the group's comments on these reels ÷ share of all comments
    n: int  # the group's comments on these reels
    all_share: float  # share of all comments that sit on these reels
    group_share: float
    lift: float | None = None  # these reels' best rate against the creator's median
    metric: str | None = None


@dataclass
class Profile:
    slot: int
    share: float
    share_pct: int
    n_comments: int
    n_reels: int
    intents: list[tuple[str, float]]
    themes: list[tuple[str, float]]
    languages: list[tuple[str, float]]
    positive: float | None
    negative: float | None
    sentiment: float | None
    lifts: dict[str, float]  # likes / shares / comments: the reels they comment on vs usual
    loves: list[Item]
    turn_offs: list[Item]
    places: list[str]
    tags_friend: float
    favourite_reels: list[dict]
    meter: int
    mood: str
    confidence: str
    samples: list[str] = field(default_factory=list)  # T25's paraphrase material (never stored)
    facts: list[str] = field(default_factory=list)
    comes_for_hint: list[str] = field(default_factory=list)

    @property
    def top_intent(self) -> str:
        return self.intents[0][0] if self.intents else "other"

    def evidence(self) -> dict[str, Any]:
        """What is stored in the persona's profile (no comment text)."""
        return {
            "share": round(self.share, 4),
            "share_pct": self.share_pct,
            "n_comments": self.n_comments,
            "n_reels": self.n_reels,
            "intents": [{"intent": i, "share": round(s, 3)} for i, s in self.intents],
            "themes": [{"label": t, "share": round(s, 3)} for t, s in self.themes],
            "languages": [
                {"language": lang, "name": language_name(lang), "share": round(s, 3)}
                for lang, s in self.languages
            ],
            "positive": _r(self.positive),
            "negative": _r(self.negative),
            "sentiment": _r(self.sentiment),
            "lifts": {k: round(v, 2) for k, v in self.lifts.items()},
            "loves": [_item(i) for i in self.loves],
            "turn_offs": [_item(i) for i in self.turn_offs],
            "places": self.places,
            "tags_friend": round(self.tags_friend, 3),
            "favourite_reels": self.favourite_reels,
            "meter": self.meter,
            "meter_word": MOOD_WORDS[self.meter],
            "mood": self.mood,
            "facts": self.facts,
        }


def _r(x: float | None) -> float | None:
    return None if x is None else round(x, 3)


def _item(i: Item) -> dict:
    return {
        "kind": i.kind,
        "value": i.value,
        "label": i.label,
        "index": round(i.index, 2),
        "n": i.n,
        "lift": None if i.lift is None else round(i.lift, 2),
        "metric": i.metric,
        "evidence": item_evidence(i),
    }


def language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code, code)


def format_label(fmt: str) -> str:
    return FORMAT_LABELS.get(fmt, fmt.replace("_", " "))


METRIC_WORDS = {"likes": "likes", "shares": "shares", "comments": "comments"}


def item_evidence(i: Item) -> str:
    """The sentence behind a love or a turn-off (every number in it is a fact)."""
    what = f"{i.label} reels" if i.kind == "format" else f"your “{i.label}” reels"
    if i.index >= 1:
        line = f"This group comments on {what} {fx(i.index)} as often as everyone else"
        if i.lift and i.metric and i.lift > 1:
            line += f", and they get {fx(i.lift)} your usual {METRIC_WORDS[i.metric]}"
        return line + "."
    return (
        f"Only {pct(i.group_share)}% of this group’s comments are on {what}, against "
        f"{pct(i.all_share)}% of all your comments."
    )


def medians(reels: list[PReel]) -> dict[str, float]:
    out = {}
    for m in ("likes", "shares", "comments"):
        vals = sorted(r.rate(m) for r in reels if r.rate(m) is not None)
        if vals:
            mid = len(vals) // 2
            out[m] = vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2
    return out


def _lifts(counts: Counter, reels: dict[str, PReel], usual: dict[str, float]) -> dict[str, float]:
    """The comment-weighted mean of (reel rate ÷ the creator's median) over the reels a group
    comments on; a metric no reel has stays out (unknown, never zero)."""
    out = {}
    for m, med in usual.items():
        if not med:
            continue
        num = den = 0.0
        for rid, n in counts.items():
            r = reels.get(rid)
            rate = r.rate(m) if r else None
            if rate is None:
                continue
            num += n * rate / med
            den += n
        if den:
            out[m] = num / den
    return out


def _items(
    kind: str,
    key_of,
    label_of,
    mine: list[PComment],
    everyone: list[PComment],
    reels: dict[str, PReel],
    usual: dict[str, float],
) -> list[Item]:
    mine_n = Counter(key_of(reels.get(c.reel_id)) for c in mine)
    all_n = Counter(key_of(reels.get(c.reel_id)) for c in everyone)
    total_mine, total_all = len(mine) or 1, len(everyone) or 1
    out = []
    for value, n_all in all_n.items():
        if not value or value == "unknown":
            continue
        g_share = mine_n.get(value, 0) / total_mine
        a_share = n_all / total_all
        if not a_share:
            continue
        ids = Counter(c.reel_id for c in mine if key_of(reels.get(c.reel_id)) == value)
        lifts = _lifts(ids, reels, usual) if ids else {}
        best = max(lifts, key=lambda m: (lifts[m], m)) if lifts else None
        out.append(
            Item(
                kind=kind,
                value=value,
                label=label_of(value),
                index=g_share / a_share,
                n=mine_n.get(value, 0),
                all_share=a_share,
                group_share=g_share,
                lift=lifts.get(best) if best else None,
                metric=best,
            )
        )
    return out


def meter(sentiment: float | None, lifts: dict[str, float]) -> int:
    """A 1–5 mood from sentiment (positive − negative share) and the reels' engagement lift."""
    s = 0.5 if sentiment is None else (sentiment + 1) / 2
    known = [v for v in lifts.values() if v is not None]
    lift = sum(known) / len(known) if known else 1.0
    v = 0.65 * s + 0.35 * clamp((lift - 0.6) / 0.9)
    return 1 + sum(v >= b for b in (0.3, 0.45, 0.6, 0.72))


def confidence_for(usable: int, own: int, starter: bool) -> str:
    if starter or usable < STARTER_MIN_COMMENTS:
        return "low"
    level = "high" if usable > HIGH_CONFIDENCE else "medium"
    if own < PERSONA_LOW_N:
        level = {"high": "medium", "medium": "low"}[level]
    return level


_HANDLE = re.compile(r"@[\w.…]+")


def clean_sample(text: str) -> str:
    """Comment text for T25 to paraphrase: handles removed, trimmed (never stored)."""
    return re.sub(r"\s+", " ", _HANDLE.sub("", text or "")).strip()[:160]


def profile(
    slot: int,
    mine: list[PComment],
    everyone: list[PComment],
    share: float,
    share_pct: int,
    reels: dict[str, PReel],
    usable: int,
    today: datetime,
    vectors: np.ndarray | None = None,
) -> Profile:
    usual = medians(list(reels.values()))
    n = len(mine)
    intents = Counter(c.intent for c in mine if c.intent)
    labelled = sum(intents.values()) or 1
    themes = Counter(c.theme for c in mine if c.theme)
    langs = Counter(c.language for c in mine if c.language)
    lang_total = sum(langs.values()) or 1
    recent = [c for c in mine if c.posted is None or c.posted >= today - timedelta(days=90)] or mine
    sent = Counter(c.sentiment for c in recent if c.sentiment)
    s_total = sum(sent.values())
    positive = sent["positive"] / s_total if s_total else None
    negative = sent["negative"] / s_total if s_total else None
    sentiment = positive - negative if s_total else None  # type: ignore[operator]
    on_reel = Counter(c.reel_id for c in mine)
    lifts = _lifts(on_reel, reels, usual)
    items = _items(
        "format", lambda r: r.format if r else None, format_label, mine, everyone, reels, usual
    ) + _items("topic", lambda r: r.group if r else None, lambda v: v, mine, everyone, reels, usual)
    loves = sorted(
        (i for i in items if i.index >= LOVE_INDEX and i.n >= MIN_ITEM_N),
        key=lambda i: (-i.index, -i.n, i.value),
    )[:4]
    offs = sorted(
        (i for i in items if i.index <= OFF_INDEX and i.all_share >= 0.1),
        key=lambda i: (i.index, -i.all_share, i.value),
    )[:3]
    places = Counter()
    for c in mine:
        for w in set(re.findall(r"[a-z]+", c.text.lower())):
            if w in PLACES:
                places[w.title()] += 1
    favourite = sorted(on_reel.items(), key=lambda kv: (-kv[1], kv[0]))[:4]
    m = meter(sentiment, lifts)
    p = Profile(
        slot=slot,
        share=share,
        share_pct=share_pct,
        n_comments=n,
        n_reels=len(on_reel),
        intents=[(i, c / labelled) for i, c in intents.most_common(4)],
        # Themes big enough to describe the group: at least 3 comments and 5% of its comments.
        themes=[
            (t, c / (n or 1))
            for t, c in sorted(themes.items(), key=lambda kv: (-kv[1], kv[0]))
            if c >= 3 and c / (n or 1) >= 0.05
        ][:4],
        languages=[
            (lang, c / lang_total)
            for lang, c in sorted(langs.items(), key=lambda kv: (-kv[1], kv[0]))
        ][:3],
        positive=positive,
        negative=negative,
        sentiment=sentiment,
        lifts=lifts,
        loves=loves,
        turn_offs=offs,
        places=[p for p, c in places.most_common(3) if c >= 3],
        tags_friend=sum(c.tags_friend or c.intent == "tags_friend" for c in mine) / (n or 1),
        favourite_reels=[
            {"id": rid, "title": reels[rid].title if rid in reels else "A reel", "comments": k}
            for rid, k in favourite
        ],
        meter=m,
        mood=MOOD_OF_METER[m],
        confidence=confidence_for(usable, n, False),
    )
    p.samples = _samples(mine, vectors)
    # What they come for: the topics (the creator's own sub-clusters) they over-index on;
    # their requests are "wants more", not "comes for".
    p.comes_for_hint = [i.label for i in loves if i.kind == "topic"][:2]
    p.facts = facts(p)
    return p


def _samples(mine: list[PComment], vectors: np.ndarray | None) -> list[str]:
    """Up to 5 comments near the group's middle, for T25 to paraphrase (never stored)."""
    if not mine:
        return []
    order = list(range(len(mine)))
    if vectors is not None and len(vectors) == len(mine):
        c = vectors.mean(axis=0)
        order.sort(key=lambda i: (float(np.linalg.norm(vectors[i] - c)), mine[i].text))
    else:
        order.sort(key=lambda i: mine[i].text)
    out: list[str] = []
    for i in order:
        s = clean_sample(mine[i].text)
        if len(s) >= 8 and s not in out:
            out.append(s)
        if len(out) == 5:
            break
    return out


def facts(p: Profile) -> list[str]:
    """The sentences (and the only numbers) T25, T26 and T27 may use about this group."""
    out = [f"{p.share_pct}% of your comments come from this group."]
    out.append(f"{p.n_comments} comments across {p.n_reels} reels.")
    clear = [(i, s) for i, s in p.intents if i != "other" and s >= 0.15]
    if clear:  # "other" (no clear intent) says nothing about them
        i, s = clear[0]
        out.append(f"{pct(s)}% of their comments {INTENT_WORDS[i]}.")
    for t, s in p.themes[:2]:
        out.append(f"{pct(s)}% of their comments: {t}.")
    if p.languages:
        out.append(
            "Their comments are in "
            + ", ".join(f"{language_name(lang)} ({pct(s)}%)" for lang, s in p.languages)
            + "."
        )
    if p.positive is not None and p.positive >= 0.1:  # questions and requests read neutral
        out.append(f"{pct(p.positive)}% of their recent comments are positive.")
    for m in ("shares", "likes", "comments"):
        if m in p.lifts:
            out.append(
                f"Reels they comment on also get {fx(p.lifts[m])} your usual {METRIC_WORDS[m]}."
            )
    for i in p.loves[:2] + p.turn_offs[:2]:
        out.append(item_evidence(i))
    if p.places:
        places = p.places
        said = places[0] if len(places) == 1 else f"{', '.join(places[:-1])} and {places[-1]}"
        out.append(f"They mention {said}.")
    if p.tags_friend >= 0.1:
        out.append(f"{pct(p.tags_friend)}% of their comments tag a friend.")
    return out[:14]


# ------------------------------------------------------------------ the whole build (pure)


@dataclass
class Built:
    profiles: list[Profile]  # by slot
    centroids: list[list[float]]
    labels: list[int]
    stability: float


def build(
    comments: list[PComment],
    reels: dict[str, PReel],
    today: datetime,
    seeds: int = SEEDS,
    previous: list[list[float]] | None = None,
) -> Built:
    """Cluster usable comments (each with a vector) into 4 personas' facts. ``previous``: last
    build's 4 persona centroids, to start from (identity across months)."""
    x = features(comments, reels)
    w = weights(comments, reels, today)
    emb = np.asarray([c.vector for c in comments], dtype=float)
    warm = warm_labels(emb, previous) if previous and len(previous) == K else None
    cl = cluster(x, w, seeds=seeds, warm=warm)
    shares_pct = largest_remainder(cl.shares)
    profiles, centroids = [], []
    for g in range(K):
        m = cl.labels == g
        mine = [c for c, keep in zip(comments, m, strict=True) if keep]
        profiles.append(
            profile(
                g + 1,
                mine,
                comments,
                cl.shares[g],
                shares_pct[g],
                reels,
                len(comments),
                today,
                emb[m],
            )
        )
        centroids.append(centroid(emb[m].tolist(), w[m]))
    return Built(profiles, centroids, cl.labels.tolist(), cl.stability)


def is_thin(usable: int, reels_with_comments: int) -> bool:
    return usable < STARTER_MIN_COMMENTS or reels_with_comments < STARTER_MIN_REELS


# ------------------------------------------------------------------ starter personas (thin data)

NICHE_NOUNS = {
    "fashion": ("looks", "outfit ideas", "styling tips"),
    "beauty": ("looks", "routines", "product picks"),
    "food": ("recipes", "dishes", "kitchen tips"),
    "fitness": ("workouts", "routines", "form tips"),
    "travel": ("trips", "places to go", "travel tips"),
    "comedy": ("sketches", "jokes", "relatable bits"),
    "education": ("lessons", "explainers", "study tips"),
    "creator_tips": ("reel tips", "edits", "growth tips"),
    "lifestyle": ("days", "ideas", "everyday tips"),
}
# (intent, name, short, tagline, comes_for, loves, wants_more, turn_offs, engagement, voice,
#  typical comment, base share). {a} {b} {c} are the niche's nouns.
STARTERS = [
    (
        "praise",
        "The Loyal Fan",
        "Loyal Fan",
        "Shows up for every post and cheers you on.",
        ["your {a}", "your personality"],
        ["your signature style", "behind-the-scenes moments"],
        ["more of your everyday {a}"],
        ["long gaps between posts"],
        "Mostly warm comments and emojis; rarely asks questions.",
        "warm, upbeat, short",
        "Obsessed with this, you never miss!",
        0.34,
    ),
    (
        "plans_to_save",
        "The Idea Saver",
        "Idea Saver",
        "Saves {b} to try later.",
        ["{b} to try", "{c}"],
        ["clear step-by-step reels", "round-ups worth saving"],
        ["save-worthy round-ups"],
        ["reels that rush the details"],
        "Saves and says they'll try it; asks for the steps.",
        "practical, appreciative",
        "Saving this to try next week!",
        0.24,
    ),
    (
        "question",
        "The Curious Asker",
        "Curious Asker",
        "Wants the details behind every reel.",
        ["the details behind your {a}", "{c}"],
        ["reels that answer “how” and “where”", "details in the caption"],
        ["details and links in the caption"],
        ["no details on where things are from"],
        "Asks questions in the comments and waits for your reply.",
        "curious, friendly, direct",
        "Where is this from? Need the details!",
        0.24,
    ),
    (
        "tags_friend",
        "The Friend Tagger",
        "Friend Tagger",
        "Sends your reels to the group chat.",
        ["something to send to friends", "relatable {a}"],
        ["relatable moments", "reels made to share"],
        ["more reels made for sharing"],
        ["reels with nothing to react to"],
        "Tags friends and shares reels more than they comment.",
        "playful, chatty",
        "This is so us, we have to try it!",
        0.18,
    ),
]


def starter(
    niche: str | None,
    topics: list[str],
    language: list[tuple[str, float]],
    priors: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Four early-guess personas from niche templates. Shares come from the niche's intent mix
    across CURO creators (when known), else the templates' defaults."""
    a, b, c = NICHE_NOUNS.get(niche or "lifestyle", NICHE_NOUNS["lifestyle"])
    raw = []
    for t in STARTERS:
        prior = (priors or {}).get(t[0])
        if t[0] == "question" and priors:
            prior = (priors.get("question") or 0) + (priors.get("request") or 0)
        raw.append(0.5 * t[11] + 0.5 * prior if prior is not None else t[11])
    order = sorted(range(len(STARTERS)), key=lambda i: (-raw[i], i))
    shares = [raw[i] for i in order]
    total = sum(shares)
    shares = [s / total for s in shares]
    pcts = largest_remainder(shares)
    out = []
    for slot, (i, share, sp) in enumerate(zip(order, shares, pcts, strict=True), start=1):
        (intent, name, short, tag, comes, loves, wants, offs, eng, voice, typical, _s) = STARTERS[i]

        def f(s: str) -> str:
            return s.format(a=a, b=b, c=c)

        comes_for = [f(x) for x in comes]
        if topics and slot == 1:
            comes_for = [f"your {topics[0].lower()} reels", *comes_for][:3]
        out.append(
            {
                "slot": slot,
                "intent": intent,
                "name": name,
                "short_name": short,
                "tagline": f(tag),
                "share": share,
                "share_pct": sp,
                "comes_for": comes_for,
                "loves": [f(x) for x in loves],
                "wants_more": [f(x) for x in wants],
                "turn_offs": [f(x) for x in offs],
                "engagement_style": eng,
                "language": [{"language": lang, "share": round(s, 3)} for lang, s in language],
                "voice": voice,
                "typical_comment": typical,
                "meter": 3,
                "mood": "neutral",
            }
        )
    return out


# ------------------------------------------------------------------ identity across builds


def match(previous: list[list[float] | None], current: list[list[float]]) -> dict[int, int]:
    """Best one-to-one assignment of new groups (index) to previous personas (index) by
    centroid cosine; only pairs at ≥ 0.8 keep the persona."""
    if not previous or not current:
        return {}
    from scipy.optimize import linear_sum_assignment

    sim = np.zeros((len(current), len(previous)))
    for i, c in enumerate(current):
        for j, p in enumerate(previous):
            sim[i, j] = cosine(c, p) if p is not None else -1.0
    rows, cols = linear_sum_assignment(-sim)
    return {int(i): int(j) for i, j in zip(rows, cols, strict=True) if sim[i, j] >= MATCH_COSINE}


def colours(kept: dict[int, str]) -> list[str]:
    """Colours by slot: a kept persona keeps its colour; new ones take free colours in order."""
    free = [c for c in COLORS if c not in kept.values()]
    return [kept[s] if s in kept else free.pop(0) for s in range(K)]


# ------------------------------------------------------------------ Studio: a persona's score


@dataclass
class PersonaFit:
    """What the idea scorer needs about one persona (loaded once per Studio request)."""

    id: str
    name: str
    short_name: str
    share: float
    vector: list[float] | None  # the comment centroid
    topic_vector: list[float] | None  # its favourite reels and what it comes for
    ask_words: set[str] = field(default_factory=set)
    love_formats: set[str] = field(default_factory=set)
    off_formats: set[str] = field(default_factory=set)
    loves: list[str] = field(default_factory=list)
    wants_more: list[str] = field(default_factory=list)
    turn_offs: list[str] = field(default_factory=list)
    is_starter: bool = False


STOP = frozenset(
    [
        "the",
        "and",
        "for",
        "with",
        "your",
        "you",
        "this",
        "that",
        "more",
        "what",
        "from",
        "about",
        "into",
        "they",
        "them",
        "their",
        "have",
        "want",
        "wants",
        "asks",
        "ask",
        "need",
        "some",
        "like",
        "make",
        "made",
        "reel",
        "reels",
        "video",
        "videos",
        "content",
        "please",
        "can",
        "could",
        "would",
        "will",
        "just",
        "how",
        "where",
        "when",
        "which",
        "who",
        "why",
        "are",
        "was",
        "were",
        "been",
        "being",
        "one",
        "also",
        "any",
        "every",
        "than",
        "then",
        "there",
        "here",
    ]
)


def words_of(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", (text or "").lower()) if len(w) > 2 and w not in STOP}


def code_fit(
    vector: list[float] | None, text: str, fmt: str | None, p: PersonaFit
) -> tuple[float, dict[str, float]]:
    """0–1: how well an idea or draft fits a persona, from code alone (v2.2 §6.4):
    0.30 + 0.40 × topic + 0.20 × asks + 0.10 × a loved format − 0.25 × a turn-off format."""
    sims = [cosine(vector, v) for v in (p.topic_vector, p.vector) if v is not None and vector]
    topic = clamp((max(sims) - 0.1) / 0.4) if sims else 0.5
    asks = 1.0 if words_of(text) & p.ask_words else 0.0
    love = 1.0 if fmt and fmt in p.love_formats else 0.0
    off = 1.0 if fmt and fmt in p.off_formats else 0.0
    value = clamp(0.30 + 0.40 * topic + 0.20 * asks + 0.10 * love - 0.25 * off)
    return round(value, 4), {"topic": round(topic, 3), "asks": asks, "love": love, "off": off}


def blend(model: float | None, code: float, model_weight: float) -> float:
    """A persona's score (0–100): model × weight + code × (1 − weight); code alone without a
    model score."""
    if model is None:
        return round(code, 2)
    return round(model_weight * model + (1 - model_weight) * code, 2)


def reaction_for(score: float) -> str:
    return next(r for floor, r in REACTIONS if score >= floor)


def audience_part(scores: dict[str, float], fits: list[PersonaFit]) -> float:
    """A = Σ share_i × persona_score_i / Σ share_i, with persona scores on 0–1."""
    total = sum(p.share for p in fits if p.id in scores)
    if not total:
        return 0.0
    return sum(p.share * scores[p.id] for p in fits if p.id in scores) / total


def summary(reactions: list[tuple[str, str, float]]) -> str:
    """ "3 of 4 follower groups are in. The Budget Stylist isn't sure." — from (name, reaction,
    share), largest share first."""
    n = len(reactions)
    yes = [r for r in reactions if r[1] in ("watch_all", "watch")]
    no = [r for r in reactions if r[1] not in ("watch_all", "watch")]
    if not n:
        return ""
    if not no:
        return f"All {n} follower groups are in."
    lead = no[0]
    tail = f"{lead[0]} isn’t sure." if lead[1] == "scroll_past" else f"{lead[0]} would skip it."
    if not yes:
        return f"None of your {n} follower groups is in yet. {tail}"
    return f"{len(yes)} of {n} follower groups are in. {tail}"


def loving_summary(meters: list[int]) -> str:
    """Home's line: "3 of 4 of your follower groups are loving your recent reels." """
    n = len(meters)
    k = sum(1 for m in meters if m >= 4)
    if k == n and n:
        return f"All {n} of your follower groups are loving your recent reels."
    if k == 0:
        return f"None of your {n} follower groups is a big fan yet: see what would win them over."
    return f"{k} of {n} of your follower groups are loving your recent reels."
