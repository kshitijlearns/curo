"""The Simulator's estimate without a trained model (MVP doc §10, T9; logic doc §13).

1. Neighbours: the 15 reels most like the upload by embedding (the same format ranks a little
   higher); v2 reads the creator's own reels only.
2. Their lifts: each neighbour's views and rate lifts against its own account's usual.
3. Estimate: the weighted (geometric) average of the neighbours' lifts, adjusted by the
   pattern-card effects of production features where the upload differs from most
   neighbours, capped at ±30%.
4. Range: the weighted 10th–90th percentile of the neighbours' lifts, widened when fewer
   than 8 neighbours are the creator's own.
5. Score: the weighted mix of predicted lifts (the audience toggle's weights) ranked against
   the creator's last 50 reels — 72 means "likely to do better than 72% of your recent reels".
6. Reasons: pattern effects the upload has (working) and doesn't (holding back).
7. Edits: proposed changes (T15) are re-scored with steps 3–5; the best three by gain for
   their effort are shown.

Everything here is computed from CURO's own records; every sentence carries the numbers it
was computed from and no others.
"""

from __future__ import annotations

import math
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np

from curo.schemas.taxonomy import UNKNOWN, label_for

METRICS = ("views", "like_rate", "comment_rate", "share_rate")
METRIC_WORDS = {
    "views": "views",
    "like_rate": "likes per view",
    "comment_rate": "comments per view",
    "share_rate": "shares per view",
}
METRIC_SHORT = {
    "views": "views",
    "like_rate": "likes",
    "comment_rate": "comments",
    "share_rate": "shares",
}
# Logic doc §13: the mix follows the audience toggle (views lift stands in for watch time).
AUDIENCE_WEIGHTS = {
    "followers": {"views": 0.15, "share_rate": 0.20, "like_rate": 0.40, "comment_rate": 0.25},
    "new": {"views": 0.45, "share_rate": 0.35, "like_rate": 0.10, "comment_rate": 0.10},
    "both": {"views": 0.30, "share_rate": 0.25, "like_rate": 0.25, "comment_rate": 0.20},
}
AUDIENCES = tuple(AUDIENCE_WEIGHTS)
K_NEIGHBOURS = 15
OWN_WEIGHT = 2.0
SAME_FORMAT_RANK = 1.15
ADJUST_CAP = 0.30
MIN_OWN = 8
HISTORY = 50
# Production choices a recording makes (logic doc §13: the features the estimate adjusts for).
ADJUSTABLE = (
    "hook_type",
    "opening_style",
    "narrative",
    "ending",
    "cta_type",
    "camera",
    "audio",
    "visual_style",
    "setting",
    "payoff_band",
    "duration_band",
    "pace",
    "onscreen_text",
)
EFFORT_COST = {"edit_only": 1.0, "reshoot": 2.0}


# ------------------------------------------------------------------ inputs


@dataclass
class Past:
    """A reel of the creator's that CURO knows."""

    reel_id: str
    own: bool
    vector: list[float]
    lifts: dict[str, float]
    features: dict[str, str]
    title: str
    username: str
    posted_at: datetime | None = None
    payoff_s: float | None = None

    @property
    def format(self) -> str | None:
        return self.features.get("format")


@dataclass
class Card:
    id: str
    feature: str
    value: str
    metric: str
    effect: float
    n: int
    scope: str


@dataclass
class Neighbour:
    past: Past
    similarity: float
    weight: float


@dataclass
class Range:
    low: float
    mid: float
    high: float


@dataclass
class Estimate:
    lifts: dict[str, Range]  # metric → predicted lift range
    adjustments: dict[str, float]  # metric → the pattern adjustment applied (capped)
    neighbours: list[Neighbour]
    own_n: int


# ------------------------------------------------------------------ helpers


def cosine(a: list[float], b: list[float]) -> float:
    va, vb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    d = float(np.linalg.norm(va) * np.linalg.norm(vb))
    return float(va @ vb / d) if d else 0.0


def weighted_quantile(values: list[float], weights: list[float], q: float) -> float:
    pairs = sorted(zip(values, weights, strict=True))
    total = sum(w for _, w in pairs)
    if not pairs or total <= 0:
        return float("nan")
    cut, acc = q * total, 0.0
    for v, w in pairs:
        acc += w
        if acc >= cut:
            return v
    return pairs[-1][0]


def phrase(feature: str, value: str) -> str:
    """How a DNA value reads in a sentence ("a send-to-a-friend prompt")."""
    special = {
        ("payoff_band", "under_2s"): "the payoff in the first 2 seconds",
        ("payoff_band", "2_to_4s"): "the payoff at 2–4 seconds",
        ("payoff_band", "over_4s"): "the payoff after 4 seconds",
        ("ending", "choice_question"): "a choice-question ending",
        ("ending", "final_look"): "an ending on the final look",
        ("ending", "open_question"): "an open-question ending",
        ("ending", "recap"): "a recap ending",
        ("cta_type", "comment_prompt"): "a comment prompt",
        ("cta_type", "share_prompt"): "a send-to-a-friend prompt",
        ("cta_type", "save_prompt"): "a save prompt",
        ("cta_type", "follow_prompt"): "a follow prompt",
        ("cta_type", "none"): "no call to action",
        ("opening_style", "final_look_first"): "an opening on the final look",
        ("opening_style", "product_closeup"): "a close-up opening",
        ("opening_style", "face_to_camera"): "a face-to-camera opening",
        ("duration_band", "under_20s"): "a length under 20 seconds",
        ("duration_band", "20_to_40s"): "a length of 20–40 seconds",
        ("duration_band", "over_40s"): "a length over 40 seconds",
        ("onscreen_text", "yes"): "text on screen",
        ("onscreen_text", "no"): "no text on screen",
        ("pace", "fast"): "fast cutting",
        ("pace", "slow"): "slow cutting",
        ("pace", "medium"): "medium-paced cutting",
        ("core_tension", "choice_dilemma"): "a choice at its heart",
        ("core_tension", "relatable_struggle"): "a relatable struggle",
        ("core_tension", "insider_tip"): "an insider tip",
        ("core_tension", "doing_it_wrong"): "a “you’re doing it wrong” angle",
        ("core_tension", "budget_limit"): "a budget limit",
        ("core_tension", "transformation"): "a transformation",
        ("core_tension", "comparison"): "a comparison",
        ("core_tension", "celebration"): "a celebration",
    }
    if (feature, value) in special:
        return special[(feature, value)]
    words = value.replace("_", " ")
    noun = FEATURE_NOUNS.get(feature)
    if noun is None:  # format, core tension: their plain names read on their own
        label = label_for(value)
        return label[0].lower() + label[1:]
    text = f"{words} {noun}" if noun else words
    return f"{'an' if text[0] in 'aeiou' else 'a'} {text}"


# How each feature's values read as a noun phrase ("a mistake hook", "a tripod camera").
FEATURE_NOUNS = {
    "hook_type": "hook",
    "opening_style": "opening",
    "narrative": "structure",
    "ending": "ending",
    "cta_type": "",
    "camera": "camera setup",
    "audio": "audio track",
    "visual_style": "look",
    "setting": "setting",
}


# ------------------------------------------------------------------ 1–4. the estimate


def neighbours(
    vector: list[float], fmt: str | None, pool: list[Past], k: int = K_NEIGHBOURS
) -> list[Neighbour]:
    ranked = []
    for p in pool:
        sim = cosine(vector, p.vector)
        if sim <= 0:
            continue
        rank = sim * (SAME_FORMAT_RANK if fmt and fmt != "unknown" and p.format == fmt else 1.0)
        ranked.append((rank, sim, p))
    ranked.sort(key=lambda x: (-x[0], x[2].reel_id))
    return [Neighbour(p, sim, sim * (OWN_WEIGHT if p.own else 1.0)) for _, sim, p in ranked[:k]]


def majority(near: list[Neighbour], feature: str) -> str | None:
    votes: Counter[str] = Counter()
    for n in near:
        v = n.past.features.get(feature)
        if v and v != "unknown":
            votes[v] += n.weight
    return votes.most_common(1)[0][0] if votes else None


def effect(cards: list[Card], feature: str, value: str | None, metric: str) -> float | None:
    if not value:
        return None
    return next(
        (
            c.effect
            for c in cards
            if c.feature == feature and c.value == value and c.metric == metric
        ),
        None,
    )


def adjustment(
    features: dict[str, str], near: list[Neighbour], cards: list[Card], metric: str
) -> float:
    """Where the upload differs from most neighbours, the ratio of the two values' pattern
    effects (the upload's value ÷ the neighbours' usual value), multiplied, capped at ±30%."""
    factor = 1.0
    for feature in ADJUSTABLE:
        mine = features.get(feature)
        theirs = majority(near, feature)
        if not mine or mine == "unknown" or mine == theirs:
            continue
        e_mine = effect(cards, feature, mine, metric) or 1.0
        e_theirs = effect(cards, feature, theirs, metric) or 1.0
        factor *= e_mine / e_theirs
    return min(1 + ADJUST_CAP, max(1 - ADJUST_CAP, factor))


def estimate(
    features: dict[str, str], near: list[Neighbour], cards: list[Card], accuracy_widen: float = 1.0
) -> Estimate:
    """``accuracy_widen`` > 1 when the creator's recent estimates missed too often (logic doc
    §13: "If accuracy drops, the ranges are widened automatically")."""
    own_n = sum(1 for n in near if n.past.own)
    widen = 1 + 0.5 * (MIN_OWN - own_n) / MIN_OWN if own_n < MIN_OWN else 1.0
    widen *= accuracy_widen
    lifts: dict[str, Range] = {}
    adjustments: dict[str, float] = {}
    for metric in METRICS:
        pairs = [(n.past.lifts[metric], n.weight) for n in near if n.past.lifts.get(metric, 0) > 0]
        if not pairs:
            continue  # unknown, never zero (no neighbour shows this count)
        values, weights = [v for v, _ in pairs], [w for _, w in pairs]
        mid = math.exp(sum(w * math.log(v) for v, w in pairs) / sum(weights))
        low = weighted_quantile(values, weights, 0.10)
        high = weighted_quantile(values, weights, 0.90)
        factor = adjustment(features, near, cards, metric)
        mid, low, high = mid * factor, low * factor, high * factor
        low = min(low, mid)
        high = max(high, mid)
        if widen > 1:  # fewer than 8 of the creator's own reels to go on: a wider range
            low = mid * (low / mid) ** widen
            high = mid * (high / mid) ** widen
        lifts[metric] = Range(round(low, 3), round(mid, 3), round(high, 3))
        adjustments[metric] = round(factor, 3)
    return Estimate(lifts, adjustments, near, own_n)


# ------------------------------------------------------------------ 5. the score


def mixed(lifts: dict[str, float], audience: str) -> float | None:
    """The weighted geometric mix of lifts; a metric that isn't known is left out and the
    others' weights are rescaled."""
    w = AUDIENCE_WEIGHTS[audience]
    known = {m: v for m, v in lifts.items() if m in w and v and v > 0}
    total = sum(w[m] for m in known)
    if not total:
        return None
    return math.exp(sum(w[m] * math.log(v) for m, v in known.items()) / total)


def score(predicted: dict[str, float], history: list[dict[str, float]], audience: str) -> int:
    """The share of the creator's last 50 reels this would beat on the audience's mix."""
    mine = mixed(predicted, audience)
    past = [x for h in history[:HISTORY] if (x := mixed(h, audience)) is not None]
    if mine is None or not past:
        return 50
    below = sum(1 for x in past if x < mine)
    same = sum(1 for x in past if x == mine)
    return round(100 * (below + 0.5 * same) / len(past))


def scores(est: Estimate, history: list[dict[str, float]]) -> dict[str, int]:
    mids = {m: r.mid for m, r in est.lifts.items()}
    return {a: score(mids, history, a) for a in AUDIENCES}


def score_label(value: int) -> str:
    """The line under the score. The score is a percentile of the creator's recent reels, so
    50 is their middle reel (DECISIONS D84)."""
    if value >= 80:
        return "Strong — likely above most of your recent reels"
    if value >= 60:
        return "Likely above your baseline"
    if value >= 40:
        return "Around your baseline"
    return "Likely below your baseline"


def summary(rows: list[dict], holding: list[Reason]) -> str:
    """The sentence under the score: the counts estimated furthest above the creator's usual,
    and the strongest thing holding the recording back."""
    up = sorted(
        (r for r in rows if r.get("known") and r["change_pct"] > 0), key=lambda r: -r["change_pct"]
    )
    names = [r["label"] for r in up[:2]]
    if names:
        first = f"Strongest on {' and '.join(names)}."
    else:
        first = "Estimated below your usual on every public count."
    if holding:
        short = holding[0].short
        return f"{first} {short[0].upper()}{short[1:]} is the main thing holding it back."
    return f"{first} Nothing in it is linked with less in your patterns."


# ------------------------------------------------------------------ 6. reasons


@dataclass
class Reason:
    key: str
    kind: str  # "working" | "holding"
    feature: str
    value: str  # the upload's value
    better: str | None  # for holding: the value associated with more
    card: Card
    strength: float
    text: str = ""
    short: str = ""
    evidence: list[dict] = field(default_factory=list)
    moment: str | None = None  # "hook" | "ending": where in the video (a storyboard frame)


def all_reasons(
    features: dict[str, str], cards: list[Card], audience: str
) -> tuple[list[Reason], list[Reason]]:
    """Every reason, strongest first: what's working (the upload has a value the creator's
    patterns link with more) and what's holding it back (a value linked with less, or a better
    value it doesn't have). Strength is the effect size weighted by how much the audience's mix
    counts that metric. A value appears once, on whichever side it is stronger."""
    w = AUDIENCE_WEIGHTS[audience]
    working: dict[str, Reason] = {}
    holding: dict[str, Reason] = {}

    def keep(side: dict[str, Reason], r: Reason) -> None:
        if r.strength > 0 and (r.key not in side or r.strength > side[r.key].strength):
            side[r.key] = r

    for c in cards:
        if c.feature not in ADJUSTABLE and c.feature != "core_tension":
            continue
        mine = features.get(c.feature)
        if not mine or mine == "unknown":
            continue
        strength = abs(math.log(c.effect)) * w.get(c.metric, 0.0)
        key = f"{c.feature}:{mine}"
        if mine == c.value and c.effect > 1:
            keep(working, Reason(key, "working", c.feature, mine, None, c, strength))
        elif mine == c.value and c.effect < 1:
            better = _best_alternative(cards, c, mine)
            keep(holding, Reason(key, "holding", c.feature, mine, better, c, strength))
        elif mine != c.value and c.effect > 1 and c.feature in ADJUSTABLE:
            # A value the creator's patterns link with more, which this recording doesn't have
            # (and its own value isn't linked with as much on that metric).
            own = effect(cards, c.feature, mine, c.metric)
            if own is not None and own >= c.effect:
                continue
            keep(holding, Reason(key, "holding", c.feature, mine, c.value, c, strength))
    for key in set(working) & set(holding):
        if working[key].strength >= holding[key].strength:
            del holding[key]
        else:
            del working[key]

    def order(rs) -> list[Reason]:
        return sorted(rs, key=lambda r: (-r.strength, r.key))

    return order(working.values()), order(holding.values())


def reasons(
    features: dict[str, str],
    cards: list[Card],
    audience: str,
    payoff_s: float | None,
    limit: int = 3,
) -> tuple[list[Reason], list[Reason]]:
    """The top three of each side, written out (MVP doc T9 step 6)."""
    working, holding = all_reasons(features, cards, audience)
    out_w, out_h = working[:limit], holding[:limit]
    for r in out_w + out_h:
        r.text, r.short = _sentence(r, payoff_s)
        r.moment = edit_moment({r.feature: r.value})
    return out_w, out_h


def _best_alternative(cards: list[Card], c: Card, mine: str) -> str | None:
    alts = [
        x
        for x in cards
        if x.feature == c.feature and x.metric == c.metric and x.value != mine and x.effect > 1
    ]
    return max(alts, key=lambda x: (x.effect, x.value)).value if alts else None


PAYOFF_ORDER = ("under_2s", "2_to_4s", "over_4s")


def _whose(card: Card) -> tuple[str, str, str]:
    """(whose reels, whose usual, how many) for a card's sentence."""
    if card.scope == "yours":
        return "your reels", "your usual", f" ({card.n} reels)"
    return "reels by creators like you", "their usual", ""


def _sentence(r: Reason, payoff_s: float | None) -> tuple[str, str]:
    """The item's sentence and a short name for it (for the line under the score)."""
    c = r.card
    metric = METRIC_WORDS[c.metric]
    reels, usual, n = _whose(c)
    mine = phrase(r.feature, r.value)
    if r.kind == "working":
        return f"It has {mine} — {reels} with it got {c.effect:.2f}× {usual} {metric}{n}.", mine
    if r.better and c.value == r.better:  # missing a value linked with more
        better = phrase(r.feature, r.better)
        slower = (
            r.feature == "payoff_band"
            and r.value in PAYOFF_ORDER
            and r.better in PAYOFF_ORDER
            and PAYOFF_ORDER.index(r.value) > PAYOFF_ORDER.index(r.better)
        )
        if slower and payoff_s is not None:
            return (
                f"The payoff lands at {payoff_s:.1f} seconds. {reels.capitalize()} with {better} "
                f"got {c.effect:.2f}× {usual} {metric}{n}.",
                "the slow payoff",
            )
        return (
            f"It has {mine}. {reels.capitalize()} with {better} got {c.effect:.2f}× {usual} "
            f"{metric}{n}.",
            mine,
        )
    return f"It has {mine} — {reels} with it got {c.effect:.2f}× {usual} {metric}{n}.", mine


EVIDENCE_POOL = 5


def evidence(r: Reason, upload_vector: list[float], pool: list[Past], k: int = 2) -> list[dict]:
    """Reels behind an item (logic doc §13): of the five reels most like this upload that show
    the value in question (for a better value it lacks, that value), the two that show the
    pattern most clearly, with their result on the card's metric. A card from the creator's
    own reels is shown with their reels; a similar-creators card with tracked creators' reels."""
    want = r.better if r.kind == "holding" and r.better and r.card.value == r.better else r.value
    metric = r.card.metric
    own = r.card.scope == "yours"
    found = [
        p
        for p in pool
        if p.own == own and p.features.get(r.feature) == want and p.lifts.get(metric)
    ]
    found.sort(key=lambda p: (-cosine(upload_vector, p.vector), p.reel_id))
    strongest_first = r.card.effect > 1  # a value linked with less: its weakest results
    closest = sorted(
        found[:EVIDENCE_POOL],
        key=lambda p: (-p.lifts[metric] if strongest_first else p.lifts[metric], p.reel_id),
    )
    return [
        {
            "who": "Your reel" if p.own else f"@{p.username}",
            "title": p.title,
            "stat": f"{p.lifts[metric]:.1f}× {'your' if p.own else 'their'} usual "
            f"{METRIC_WORDS[metric]}",
            "tone": int(p.reel_id.replace("-", "")[:4], 16) % 4 if p.reel_id else 0,
        }
        for p in closest[:k]
    ]


# ------------------------------------------------------------------ 7. edits


def rescore_edit(
    features: dict[str, str],
    change: dict[str, str],
    near: list[Neighbour],
    cards: list[Card],
    history: list[dict[str, float]],
    before: dict[str, int],
) -> dict[str, int]:
    """The score change for each audience if the recording had the edit's feature values:
    steps 3–5 again on the same neighbours (MVP doc T9 step 7)."""
    after = scores(estimate({**features, **change}, near, cards), history)
    return {a: after[a] - before[a] for a in AUDIENCES}


def best_edits(
    gains: list[tuple[str, dict[str, int], str]], audience: str, k: int = 3
) -> list[str]:
    """The ids of the edits that help this audience most for their effort: (id, gains, effort)."""
    helping = [(i, g[audience], e) for i, g, e in gains if g[audience] > 0]
    helping.sort(key=lambda x: (-x[1] / EFFORT_COST.get(x[2], 1.0), -x[1], x[0]))
    return [i for i, _, _ in helping[:k]]


def factors(features: dict[str, str], cards: list[Card]) -> list[Reason]:
    """What T15 proposes edits for: every holding-back item, for any audience, that names a
    better value to move to."""
    seen: dict[tuple[str, str], Reason] = {}
    for audience in AUDIENCES:
        for r in all_reasons(features, cards, audience)[1]:
            if r.better and r.feature in ADJUSTABLE:
                key = (r.feature, r.better)
                if key not in seen or r.card.effect > seen[key].card.effect:
                    seen[key] = r
    return sorted(seen.values(), key=lambda r: (-abs(math.log(r.card.effect)), r.key))


def fact(r: Reason) -> str:
    """The pattern behind a factor, as one sentence of numbers from the card."""
    reels, usual, n = _whose(r.card)
    return (
        f"{reels.capitalize()} with {phrase(r.feature, r.card.value)} got "
        f"{r.card.effect:.2f}× {usual} {METRIC_WORDS[r.card.metric]}{n}."
    )


# Which Studio change carries an edit back to the draft (logic doc §13: "Edit & re-run"
# writes accepted script and storyboard changes back to the project).
SCRIPT_HOOK = {"payoff_band", "opening_style", "hook_type"}
SCRIPT_ENDING = {"cta_type", "ending"}
BAND_SECONDS = {"under_20s": 18.0, "20_to_40s": 32.0, "over_40s": 45.0}


@dataclass
class StudioChange:
    step: str  # "script" | "storyboard"
    action: str  # a Studio revision action (services.revisions.ACTIONS)
    params: dict[str, str | float] = field(default_factory=dict)


def studio_changes(change: dict[str, str]) -> list[StudioChange]:
    keys = set(change)
    out: list[StudioChange] = []
    if keys & SCRIPT_HOOK:
        out.append(StudioChange("script", "rewrite_hook"))
    if keys & SCRIPT_ENDING:
        out.append(StudioChange("script", "change_ending"))
    if "duration_band" in keys and change["duration_band"] in BAND_SECONDS:
        seconds = BAND_SECONDS[change["duration_band"]]
        action = "expand" if change["duration_band"] == "over_40s" else "shorten"
        out.append(StudioChange("script", action, {"seconds": seconds}))
    if "pace" in keys:
        direction = "slower" if change["pace"] == "slow" else "faster"
        out.append(StudioChange("storyboard", "pacing", {"direction": direction}))
    if change.get("onscreen_text") == "yes":
        out.append(StudioChange("storyboard", "label_frames"))
    if keys & {"camera", "setting", "visual_style"}:
        out.append(StudioChange("storyboard", "change_shot"))
    return out


def edit_moment(change: dict[str, str]) -> str | None:
    """Where in the video an edit lands: "hook", "ending", or None for the whole video."""
    if set(change) & SCRIPT_HOOK:
        return "hook"
    if set(change) & SCRIPT_ENDING:
        return "ending"
    return None


# ------------------------------------------------------------------ the report, timing, accuracy


def report(est: Estimate, baselines: dict[str, float | None]) -> list[dict]:
    """Each metric as the creator's 7-day usual × the predicted lift: a range, and the change
    against that usual. A metric with no known usual is left as unknown."""
    rows = []
    for metric in METRICS:
        r = est.lifts.get(metric)
        base = baselines.get(metric)
        if r is None or not base:
            rows.append({"metric": metric, "label": METRIC_SHORT[metric], "known": False})
            continue
        rows.append(
            {
                "metric": metric,
                "label": METRIC_SHORT[metric],
                "known": True,
                "baseline": base,
                "low": base * r.low,
                "mid": base * r.mid,
                "high": base * r.high,
                "change_pct": round((r.mid - 1) * 100),
            }
        )
    return rows


def predicted_counts(
    est: Estimate, baselines: dict[str, float | None]
) -> dict[str, dict[str, float]]:
    """7-day counts (views, likes, comments, shares) for Home's arrows once the reel is posted
    (DECISIONS D50): views from the views lift, the others as views × each rate."""
    v = est.lifts.get("views")
    base_v = baselines.get("views")
    if v is None or not base_v:
        return {}
    out = {"views": {"low": base_v * v.low, "mid": base_v * v.mid, "high": base_v * v.high}}
    for metric, count in (
        ("like_rate", "likes"),
        ("comment_rate", "comments"),
        ("share_rate", "shares"),
    ):
        r, base = est.lifts.get(metric), baselines.get(metric)
        if r is None or not base:
            continue
        out[count] = {k: out["views"][k] * base * getattr(r, k) for k in ("low", "mid", "high")}
    return {m: {k: round(x) for k, x in v.items()} for m, v in out.items()}


WINDOWS = ((6, 9), (9, 12), (12, 15), (15, 18), (18, 21), (21, 24))
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
DAY_NAMES = ("Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays", "Sundays")


def _window(h: int) -> tuple[int, int] | None:
    return next((w for w in WINDOWS if w[0] <= h < w[1]), None)


def _hours(w: tuple[int, int]) -> str:
    def fmt(h: int) -> str:
        h12 = h % 12 or 12
        return f"{h12} {'AM' if h < 12 or h == 24 else 'PM'}"

    a, b = fmt(w[0]), fmt(w[1] % 24 if w[1] == 24 else w[1])
    if a.split()[1] == b.split()[1]:
        return f"{a.split()[0]}–{b}"
    return f"{a}–{b}"


def best_time(posts: list[tuple[datetime, float]], now: datetime) -> dict | None:
    """The best slot in the next 48 hours (logic doc §13): the creator's views lift by posting
    day and 3-hour window (at least 2 reels), else by window alone (at least 3). Times are the
    creator's local time."""
    by_slot: dict[tuple[int, tuple[int, int]], list[float]] = defaultdict(list)
    by_window: dict[tuple[int, int], list[float]] = defaultdict(list)
    for at, lift in posts:
        w = _window(at.hour)
        if w and lift > 0:
            by_slot[(at.weekday(), w)].append(lift)
            by_window[w].append(lift)
    busy: set = set()
    best = None
    t = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    seen = set()
    while t < now + timedelta(hours=48):
        w = _window(t.hour)
        key = (t.weekday(), w)
        if w and key not in seen and w not in busy:
            seen.add(key)
            slot = by_slot.get(key, [])
            if len(slot) >= 2:
                value, basis = statistics.median(slot), ("day", len(slot))
            elif len(by_window.get(w, [])) >= 3:
                value, basis = statistics.median(by_window[w]), ("window", len(by_window[w]))
            else:
                value = None
            if value is not None and (best is None or value > best[0]):
                best = (value, t, w, basis)
        t += timedelta(hours=1)
    if best is None:
        return None
    value, t, w, (kind, n) = best
    when = f"{DAYS[t.weekday()]}, {_hours(w)}"
    if kind == "day":
        fact = f"Your reels posted on {DAY_NAMES[t.weekday()]} {_hours(w)} got {value:.1f}× your usual views ({n} reels)."
    else:
        fact = f"Your reels posted {_hours(w)} got {value:.1f}× your usual views ({n} reels)."
    if busy:
        fact += " It avoids the hours the creators you track post most."
    return {"label": when, "fact": fact, "at": t.isoformat()}


def accuracy_note(hits: int, total: int) -> str:
    if not total:
        return (
            "Curo checks every estimate against the real result once the reel is posted. None "
            "of your simulated reels has been posted yet, so there’s no record to show."
        )
    return f"Curo’s range contained the result for {hits} of your last {total} simulated reels."


# ------------------------------------------------------------------ comparing with the Studio draft


def _words(text: str) -> set[str]:
    return {w.strip(".,!?:;'’\"“”—–()").lower() for w in text.split() if len(w) > 2}


def compare(transcript: str, duration_s: float | None, beats: list[dict]) -> list[dict]:
    """Line the video's words up with the script, beat by beat (logic doc §13): skipped beats,
    a changed hook, a missing call to action, a length difference, dropped noted lines."""
    sentences = [s for s in _split(transcript)]
    said = [_words(s) for s in sentences]

    def match(text: str) -> float:
        want = _words(text)
        if not want or not said:
            return 0.0
        return max(len(want & got) / len(want) for got in said)

    out = []
    scores_ = {b["id"]: match(b["text"]) for b in beats}
    hook = next((b for b in beats if b["role"] == "hook"), None)
    end = next((b for b in reversed(beats) if b["role"] == "ending"), None)
    if hook and scores_[hook["id"]] < 0.5:
        out.append({"kind": "hook", "text": "Your opening line isn’t the script’s hook."})
    if end and scores_[end["id"]] < 0.4:
        out.append(
            {
                "kind": "cta",
                "text": "The script’s last line (its call to action) isn’t in the video.",
            }
        )
    skipped = [b for b in beats if b not in (hook, end) and scores_[b["id"]] < 0.4]
    if skipped:
        n = len(skipped)
        out.append(
            {
                "kind": "skipped",
                "text": f"{n} of the script’s lines {'isn’t' if n == 1 else 'aren’t'} in the video.",
            }
        )
    noted = [b for b in beats if b.get("note") and scores_[b["id"]] < 0.4]
    for b in noted:
        out.append(
            {
                "kind": "note",
                "text": f"A line Curo linked with {b['note']['type']} was dropped: “{b['text']}”",
            }
        )
    planned = beats[-1]["end_s"] if beats else None
    if duration_s and planned and abs(duration_s - planned) >= 5:
        out.append(
            {
                "kind": "length",
                "text": f"The video runs {round(duration_s)} seconds; the script planned {round(planned)}.",
            }
        )
    return out


def _split(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]


# ------------------------------------------------------------------ the DNA panels

DISPLAY = {
    "fashion_styling": "Fashion and styling",
    "creator_tips": "Creator tips",
    "creator_solo": "You, solo",
    "creator_with_friend": "You and a friend",
    "no_person": "No one on screen",
    "choice_dilemma": "A choice",
    "relatable_struggle": "A relatable struggle",
    "insider_tip": "An insider tip",
    "doing_it_wrong": "“You’re doing it wrong”",
    "budget_limit": "A budget limit",
    "multi_look": "One item, many looks",
    "grwm": "Get ready with me",
    "voiceover_broll": "Voiceover over B-roll",
    "talking_head": "Talking to camera",
    "how_to": "How-to",
    "number_list": "Number list",
    "bold_claim": "Bold claim",
    "curiosity_gap": "Curiosity gap",
    "trend_audio": "Trending audio",
    "face_to_camera": "Face to camera",
    "final_look_first": "Final look first",
    "product_closeup": "Close-up on the product",
    "mirror_shot": "Mirror shot",
    "action_mid_shot": "Mid-shot, in action",
    "text_over_broll": "Text over B-roll",
    "step_by_step": "Step by step",
    "story_arc": "Story",
    "problem_solution": "Problem, then solution",
    "day_in_the_life": "Day in the life",
    "reveal_then_explain": "Reveal, then explain",
    "choice_question": "Choice question",
    "open_question": "Open question",
    "final_look": "On the final look",
    "comment_prompt": "Comment prompt",
    "save_prompt": "Save prompt",
    "share_prompt": "Send-to-a-friend prompt",
    "follow_prompt": "Follow prompt",
    "part_two_tease": "Part 2 tease",
    "first_person": "First person",
    "second_person": "Second person",
    "selfie_handheld": "Selfie, handheld",
    "mirror_selfie": "Mirror selfie",
    "original_speech": "Your own voice",
    "music_only": "Music only",
    "natural_light": "Natural light",
    "warm_light": "Warm light",
    "bright_even": "Bright, even light",
    "living_room": "Living room",
    "event_venue": "Event venue",
}


def display(value: str | None) -> str:
    if not value or value == UNKNOWN:
        return "Unknown"
    return DISPLAY.get(value, value.replace("_", " ").capitalize())


def _mmss(seconds: float) -> str:
    s = round(seconds)
    return f"{s // 60}:{s % 60:02d}"


def content_rows(content: dict, subcluster: str | None) -> list[list[str]]:
    return [
        ["Cluster", display(content.get("cluster"))],
        ["Sub-cluster", subcluster or "Unknown"],
        ["Context", display(content.get("context"))],
        ["Characters", display(content.get("characters"))],
        ["Core tension", display(content.get("core_tension"))],
    ]


def production_rows(
    production: dict, features: dict[str, str], duration_s: float | None, t1: dict
) -> list[list[str]]:
    hook = display(production.get("hook_type"))
    if production.get("hook_text"):
        hook = f"{hook} · “{production['hook_text']}”"
    cuts = production.get("cuts_per_10s")
    pace = display(features.get("pace"))
    if cuts is not None and pace != "Unknown":
        pace = f"{pace} · {cuts:.1f} cuts per 10 seconds"
    payoff = t1.get("first_payoff_s")
    camera = [display(production.get(k)) for k in ("pov", "camera")]
    setting = [display(production.get(k)) for k in ("setting", "visual_style")]
    return [
        ["Format", display(production.get("format"))],
        ["Hook", hook],
        ["Opening", display(production.get("opening_style"))],
        ["Narrative", display(production.get("narrative"))],
        ["Ending", display(production.get("ending"))],
        ["Call to action", display(production.get("cta_type"))],
        ["POV · camera", " · ".join(camera)],
        ["Audio", display(production.get("audio"))],
        ["Setting · light", " · ".join(setting)],
        ["Length", _mmss(duration_s) if duration_s else "Unknown"],
        ["First payoff", f"At {payoff:.1f} seconds" if payoff is not None else "Unknown"],
        ["Cutting", pace],
        [
            "On-screen text",
            {"yes": "Yes", "no": "No"}.get(features.get("onscreen_text", ""), "Unknown"),
        ],
    ]


NEAR_COPY = 0.9
CLOSE = 0.75


def originality(vector: list[float], recent: list[Past]) -> tuple[float, Past | None]:
    """1 − the highest similarity to any of the creator's recent reels (v2: their own, not
    peers'), and that reel."""
    best, top = None, 0.0
    for p in recent:
        sim = cosine(vector, p.vector)
        if sim > top:
            best, top = p, sim
    return round(1 - top, 2), best


def originality_text(value: float, closest: Past | None) -> str:
    similarity = 1 - value
    if closest is None:
        return "No recent reels of yours to compare with"
    where = f"your “{closest.title}”"
    if similarity >= NEAR_COPY:
        return f"Low · very close to {where}"
    if similarity >= CLOSE:
        return f"Medium · closest to {where}"
    return f"High · the closest is {where}"


def fit_band(value: float) -> str:
    return "High" if value >= 0.66 else "Medium" if value >= 0.33 else "Low"
