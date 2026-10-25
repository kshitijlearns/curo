"""Studio step 1: the three ideas (logic doc §9).

An AI model writes about 15 candidates from a fixed evidence pack (T6); candidates citing no
evidence are dropped; this module scores the rest and picks three that do different jobs.

    Idea score = 0.40 H + 0.30 A + 0.20 T + 0.10 N      (v2: no peers, PLAN_V2 §4.1)

The logic doc names the parts; the formulas below make them concrete (DECISIONS D69). Each
part is 0–1 and carries the facts it came from, which become the idea's "why" line and the
"Why this idea" panel.

* H, your history: the lift CURO expects for this creator from the idea's topic (the nearest
  sub-cluster, weighted by how near it is), format (the creator's reels in that format) and
  hook type (its pattern card), mixed across metrics with the Simulator's "both audiences"
  weights (views 30%, shares 25%, likes 25%, comments 20%). Usual = half credit, 1.5× = full.
* A, audience (v2.2): the share-weighted score of the creator's 4 Follower Personas,
  A = Σ share_i × persona_score_i / Σ share_i. While 15 candidates are ranked, each persona
  score is the code fit (services/personas.code_fit); for the ideas shown it is the blend of
  T27's score and the code fit, so the verdict and the persona avatars agree. Without
  personas yet: 0.6 × how much of the audience asks for it (a matching request or question
  theme; 5% of comments = full) + 0.4 × the expected lift on the behaviour it aims for.
* T, trend: for a dated event, 0.6 × the timing window (if the idea is about it) + 0.4 ×
  momentum of a rising tag it rides or a trend card it adapts; otherwise that momentum alone
  (unknown = 0.3).
* N, novelty: 1 − its highest similarity to the creator's last 10 reels.

Picking three: the best proven idea, then repeatedly the idea with the highest
0.7 × score − 0.3 × similarity to those already chosen, filling the slots Proven (a format that
already works for the creator), Adapted (a trending angle from the shared trend feed, made the
creator's own) and Explore (what the audience asks for, or a fresh angle).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

import numpy as np

from curo.services import personas as P

WEIGHTS = {"H": 0.40, "A": 0.30, "T": 0.20, "N": 0.10}
PART_NAMES = {"H": "Your history", "A": "Audience", "T": "Trend", "N": "Novelty"}
SLOTS = ("proven", "adapted", "explore")
# The Simulator's "both audiences" mix (logic doc §13), so H speaks the Simulator's language.
METRIC_MIX = {"views": 0.30, "share_rate": 0.25, "like_rate": 0.25, "comment_rate": 0.20}
TARGET_METRIC = {
    "views": "views",
    "likes": "like_rate",
    "comments": "comment_rate",
    "shares": "share_rate",
}
METRIC_WORDS = {
    "views": "views",
    "like_rate": "likes per view",
    "comment_rate": "comments per view",
    "share_rate": "shares per view",
}
K_FORMAT = 10  # a format's lift counts n / (n + 10), like a pattern card's
# How a format reads in "your … reels" / "a … reel".
FORMAT_NAMES = {
    "talking_head": "talking-head",
    "voiceover_broll": "voiceover",
    "grwm": "get-ready-with-me",
    "tutorial": "tutorial",
    "listicle": "list",
    "lookbook": "lookbook",
    "multi_look": "multi-look",
    "haul": "haul",
    "transition": "transition",
    "before_after": "before-and-after",
    "vlog": "vlog",
    "skit": "skit",
}
DIVERSITY = (0.7, 0.3)
THEME_MATCH = 0.6  # similarity at which an idea answers a comment theme it doesn't name
TREND_MATCH = 0.5  # similarity at which an idea adapts a trend card's angle
FULL_ASK_SHARE = 0.05
VERDICTS = ((0.75, "Strong"), (0.55, "Worth trying"), (0.0, "Risky"))


# ------------------------------------------------------------------ inputs


@dataclass
class Group:
    """A creator sub-cluster, described at caption level (topics are compared on captions)."""

    id: str
    label: str
    vector: list[float]
    typical_sim: float
    lifts: dict[str, float]  # metric → median lift
    n: int
    format: str | None = None


@dataclass
class FormatStat:
    format: str
    n: int
    lifts: dict[str, float]  # metric → median lift of the creator's reels in this format


@dataclass
class CardFact:
    id: str
    feature: str
    value: str
    metric: str
    effect: float
    n: int
    scope: str  # "yours" | "similar_creators"


@dataclass
class ThemeFact:
    key: str
    label: str
    share: float
    n: int
    vector: list[float]
    words: set[str] = field(default_factory=set)


@dataclass
class TrendAngle:
    """A trend card from the creator's niche feed, with one of its example angles."""

    key: str
    name: str
    angle: str
    momentum: float | None
    vector: list[float]


@dataclass
class Festival:
    name: str
    starts_on: date
    ends_on: date
    keywords: set[str] = field(default_factory=set)


@dataclass
class TrendFact:
    festival: str | None = None
    starts_on: date | None = None
    ends_on: date | None = None
    keywords: set[str] = field(default_factory=set)
    rising: dict[str, float] = field(default_factory=dict)  # tag → growth (last 7 d ÷ 28 before)
    others: list[Festival] = field(default_factory=list)  # other festivals in the next months


@dataclass
class Context:
    today: date
    groups: list[Group]
    formats: dict[str, FormatStat]
    cards: list[CardFact]
    themes: list[ThemeFact]
    trend: TrendFact
    recent: list[list[float]]  # the creator's last 10 reels (caption vectors)
    trend_angles: list[TrendAngle] = field(default_factory=list)
    personas: list[P.PersonaFit] = field(default_factory=list)  # v2.2: A's inputs


@dataclass
class Candidate:
    text: str
    format: str
    hook_type: str
    target: str  # views | likes | comments | shares
    vector: list[float]
    description: str = ""
    angle: str = ""
    evidence_ids: list[str] = field(default_factory=list)
    source: str = "generated"


@dataclass
class Part:
    value: float
    facts: list[str]


@dataclass
class Scored:
    candidate: Candidate
    parts: dict[str, Part]
    score: float
    slot: str | None = None

    @property
    def values(self) -> dict[str, float]:
        return {k: p.value for k, p in self.parts.items()}


# ------------------------------------------------------------------ helpers


def clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def cosine(a: list[float], b: list[float]) -> float:
    va, vb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    d = float(np.linalg.norm(va) * np.linalg.norm(vb))
    return float(va @ vb / d) if d else 0.0


def lift_credit(lift: float | None) -> float:
    """Usual (1.0) = half credit, 1.5× or more = full, half the usual or less = none."""
    return 0.5 if lift is None else clamp(0.5 + (lift - 1.0))


def idea_score(values: dict[str, float]) -> float:
    return sum(WEIGHTS[k] * values[k] for k in WEIGHTS)


def shares(values: dict[str, float]) -> dict[str, int]:
    """Each part's share of the score, w·s / Σ w·s, as whole percents adding up to 100."""
    total = idea_score(values)
    raw = {k: (100 * WEIGHTS[k] * values[k] / total if total else 0.0) for k in WEIGHTS}
    out = {k: math.floor(v) for k, v in raw.items()}
    left = 100 - sum(out.values()) if total else 0
    for k in sorted(raw, key=lambda k: -(raw[k] - math.floor(raw[k]))):
        if left <= 0:
            break
        out[k] += 1
        left -= 1
    return out


def format_name(fmt: str) -> str:
    return FORMAT_NAMES.get(fmt, fmt.replace("_", " "))


def verdict(score: float) -> str:
    return next(name for floor, name in VERDICTS if score >= floor)


def _words(text: str) -> set[str]:
    return {w.strip(".,!?:;'’\"“”()").lower() for w in text.split() if len(w) > 2}


def nearest_group(vector: list[float], ctx: Context) -> tuple[Group | None, float]:
    """The sub-cluster the idea sits closest to, and how close (1 = as close as its own reels)."""
    best, best_rel = None, 0.0
    for g in ctx.groups:
        rel = min(1.0, max(0.0, cosine(vector, g.vector)) / max(g.typical_sim, 1e-6))
        if rel > best_rel:
            best, best_rel = g, rel
    return best, best_rel


def hook_card(ctx: Context, hook_type: str, metric: str) -> CardFact | None:
    return next(
        (
            c
            for c in ctx.cards
            if c.feature == "hook_type" and c.value == hook_type and c.metric == metric
        ),
        None,
    )


def expected_lifts(c: Candidate, ctx: Context) -> dict[str, float]:
    """Per metric: topic lift (nearest sub-cluster, shrunk by distance), format lift (shrunk by
    count) — their geometric mean, so a sub-cluster that *is* the format isn't counted twice —
    times the hook type's pattern-card effect. Capped to 0.3–3×."""
    group, rel = nearest_group(c.vector, ctx)
    fmt = ctx.formats.get(c.format)
    out = {}
    for metric in METRIC_MIX:
        topic = 1.0 + rel * ((group.lifts.get(metric) or 1.0) - 1.0) if group else 1.0
        if fmt and fmt.n:
            w = fmt.n / (fmt.n + K_FORMAT)
            form = 1.0 + w * ((fmt.lifts.get(metric) or 1.0) - 1.0)
        else:
            form = 1.0
        card = hook_card(ctx, c.hook_type, metric)
        hook = card.effect if card else 1.0
        out[metric] = min(3.0, max(0.3, math.sqrt(max(topic, 1e-6) * max(form, 1e-6)) * hook))
    return out


def mixed_lift(lifts: dict[str, float]) -> float:
    return math.exp(sum(w * math.log(lifts[m]) for m, w in METRIC_MIX.items()))


def format_works(ctx: Context, fmt: str) -> bool:
    stat = ctx.formats.get(fmt)
    return bool(stat and stat.n >= 3 and (stat.lifts.get("views") or 0) >= 1.0)


def mentions_any(text: str, keywords: set[str]) -> bool:
    low = text.lower()
    return any(k and k.lower() in low for k in keywords)


# ------------------------------------------------------------------ the five parts


def part_h(c: Candidate, ctx: Context) -> Part:
    lift = mixed_lift(expected_lifts(c, ctx))
    group, rel = nearest_group(c.vector, ctx)
    facts = []
    if group and rel >= 0.5 and group.lifts.get("views"):
        facts.append(
            f"Your “{group.label}” reels get {group.lifts['views']:.2f}× your usual views."
        )
    fmt = ctx.formats.get(c.format)
    if fmt and fmt.n >= 3 and fmt.lifts.get("views"):
        facts.append(
            f"Your {format_name(c.format)} reels get {fmt.lifts['views']:.2f}× your usual "
            f"views ({fmt.n} reels)."
        )
    elif c.format and c.format != "unknown" and not fmt:
        facts.append(f"You haven’t made a {format_name(c.format)} reel yet.")
    return Part(round(lift_credit(lift), 3), facts)


def matched_themes(c: Candidate, ctx: Context) -> list[ThemeFact]:
    """Themes the idea answers: those it cites as evidence, those whose key word it uses
    ("where", "price", "budget"…), or one it is very close to."""
    words = _words(f"{c.text} {c.angle}")
    cited = {e.removeprefix("theme:") for e in c.evidence_ids if e.startswith("theme:")}
    out = [
        t
        for t in ctx.themes
        if t.key in cited or t.words & words or cosine(c.vector, t.vector) >= THEME_MATCH
    ]
    return sorted(out, key=lambda t: -t.share)


def persona_scores(c: Candidate, ctx: Context) -> dict[str, float]:
    """Each persona's code fit for the candidate (0–1)."""
    text = f"{c.text} {c.angle} {c.description}"
    return {p.id: P.code_fit(c.vector, text, c.format, p)[0] for p in ctx.personas}


def part_a(c: Candidate, ctx: Context, scores: dict[str, float] | None = None) -> Part:
    if ctx.personas:
        return persona_part(ctx, scores or persona_scores(c, ctx))
    themes = matched_themes(c, ctx)
    asks = max((min(1.0, t.share / FULL_ASK_SHARE) for t in themes), default=0.0)
    metric = TARGET_METRIC[c.target]
    lift = expected_lifts(c, ctx)[metric]
    facts = []
    if themes:
        t = themes[0]
        facts.append(f"{round(t.share * 100, 1)}% of your recent comments {_phrase(t.label)}.")
    group, rel = nearest_group(c.vector, ctx)
    if group and rel >= 0.5 and group.lifts.get(metric) and metric != "views":
        facts.append(
            f"Your “{group.label}” reels get {group.lifts[metric]:.2f}× your usual "
            f"{METRIC_WORDS[metric]}."
        )
    return Part(round(0.6 * asks + 0.4 * lift_credit(lift), 3), facts)


def persona_part(ctx: Context, scores: dict[str, float]) -> Part:
    """A from the persona scores, with the "3 of 4 follower groups are in" line as its fact."""
    value = P.audience_part(scores, ctx.personas)
    rows = [
        (p.name, P.reaction_for(100 * scores[p.id]), p.share)
        for p in sorted(ctx.personas, key=lambda p: -p.share)
        if p.id in scores
    ]
    return Part(round(value, 3), [P.summary(rows)] if rows else [])


def _phrase(label: str) -> str:
    verb, _, rest = label.partition(" ")
    return ({"asks": "ask", "wants": "want"}.get(verb.lower(), verb.lower()) + f" {rest}").strip()


def adapted_from(c: Candidate, ctx: Context) -> TrendAngle | None:
    """The trend card the idea adapts: one it cites, else the angle it sits closest to."""
    cited = {e.removeprefix("trend:card:") for e in c.evidence_ids if e.startswith("trend:card:")}
    for t in ctx.trend_angles:
        if t.key in cited:
            return t
    near = [(t, cosine(c.vector, t.vector)) for t in ctx.trend_angles]
    near = [(t, sim) for t, sim in near if sim >= TREND_MATCH]
    return max(near, key=lambda x: (x[1], x[0].key))[0] if near else None


def trend_credit(m: float | None) -> float:
    """A trend card's momentum → 0–1 (unknown counts a little: it is in the feed)."""
    return 0.5 if m is None else clamp((m - 1.0) / 1.25)


def window_credit(days_until: int, during: bool) -> float:
    """Best 7–14 days before a dated event, falling quickly after it starts (as opportunities)."""
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


def part_t(c: Candidate, ctx: Context) -> Part:
    tr = ctx.trend
    words = c.text.lower()
    riding = {t: g for t, g in tr.rising.items() if t.lower() in words.replace(" ", "")}
    facts = []
    adapted = adapted_from(c, ctx)
    if riding:
        tag, g = max(riding.items(), key=lambda kv: kv[1])
        momentum = clamp((g - 1.0) / 1.25)
        facts.append(f"Daily posts on #{tag} are {g:.1f}× the 4 weeks before.")
    elif adapted is not None:
        momentum = trend_credit(adapted.momentum)
        facts.append(f"It adapts a trend picking up in your niche: {adapted.name}.")
    else:
        momentum = 0.3
    fest = festival_of(c, ctx)
    if fest is not None:
        days = (fest.starts_on - ctx.today).days
        during = fest.starts_on <= ctx.today <= fest.ends_on
        facts.insert(
            0, f"{fest.name} starts in {days} days." if days > 0 else f"{fest.name} is on now."
        )
        return Part(round(0.6 * window_credit(days, during) + 0.4 * momentum, 3), facts)
    if tr.festival:  # a dated event is coming, and this idea isn't about it
        return Part(round(0.6 * 0.2 + 0.4 * momentum, 3), facts)
    return Part(round(momentum, 3), facts)


def festival_of(c: Candidate, ctx: Context) -> Festival | None:
    """The festival the idea is about: the project's own, else any other one it names."""
    tr = ctx.trend
    if tr.festival and tr.starts_on and mentions_any(c.text, tr.keywords | {tr.festival}):
        return Festival(tr.festival, tr.starts_on, tr.ends_on or tr.starts_on, tr.keywords)
    return next((f for f in tr.others if mentions_any(c.text, f.keywords | {f.name})), None)


def part_n(c: Candidate, ctx: Context) -> Part:
    if not ctx.recent:
        return Part(1.0, [])
    top = max(cosine(c.vector, v) for v in ctx.recent)
    value = clamp(1.0 - top)
    fact = (
        "Different from your last 10 reels."
        if value >= 0.6
        else "Close to a reel you posted recently."
        if value < 0.3
        else ""
    )
    return Part(round(value, 3), [fact] if fact else [])


def score(c: Candidate, ctx: Context, persona: dict[str, float] | None = None) -> Scored:
    """``persona``: blended persona scores (0–1), once T27 has run for this idea."""
    parts = {
        "H": part_h(c, ctx),
        "A": part_a(c, ctx, persona),
        "T": part_t(c, ctx),
        "N": part_n(c, ctx),
    }
    return Scored(c, parts, round(idea_score({k: p.value for k, p in parts.items()}), 4))


# ------------------------------------------------------------------ slots and the diversity rule


def qualifies(s: Scored, slot: str, ctx: Context) -> bool:
    v = s.values
    if slot == "proven":
        return format_works(ctx, s.candidate.format)
    if slot == "adapted":
        return adapted_from(s.candidate, ctx) is not None or v["T"] >= 0.6
    asks = bool(matched_themes(s.candidate, ctx))
    return asks or v["N"] >= 0.6 or s.candidate.format not in ctx.formats


def diversity_value(s: Scored, chosen: list[Scored]) -> float:
    a, b = DIVERSITY
    sim = max((cosine(s.candidate.vector, o.candidate.vector) for o in chosen), default=0.0)
    return a * s.score - b * sim


def pick_three(scored: list[Scored], ctx: Context) -> list[Scored]:
    """Fill Proven, Adapted, Explore in turn: the qualifying idea with the highest
    0.7 × score − 0.3 × similarity to those already chosen (the first pick is simply the best
    proven idea). A slot nothing qualifies for takes the best remaining idea by the same rule."""
    pool = list(scored)
    chosen: list[Scored] = []
    for slot in SLOTS:
        if not pool:
            break
        fits = [s for s in pool if qualifies(s, slot, ctx)] or pool
        best = max(fits, key=lambda s: (diversity_value(s, chosen), s.score))
        best.slot = slot
        chosen.append(best)
        pool.remove(best)
    return chosen


# The parts that earn an idea its slot, so each of the three says what it brings.
SLOT_PARTS = {"proven": ("H",), "adapted": ("T",), "explore": ("A", "N")}


def why_line(s: Scored) -> str:
    """The idea's one-line reason: a fact from the part that earned its slot (the stronger of
    them), else from the strongest part."""

    def by_weight(keys) -> list[str]:
        return sorted(keys, key=lambda k: -WEIGHTS[k] * s.parts[k].value)

    first = by_weight(SLOT_PARTS.get(s.slot or "", ()))
    for k in first + [k for k in by_weight(s.parts) if k not in first]:
        if s.parts[k].facts:
            return s.parts[k].facts[0]
    return "Built from your data."


# ------------------------------------------------------------------ the validate chat


REASONS = {
    "H": (
        "It’s close to the kind of reel that does best for you.",
        "It’s far from the reels that usually work for you.",
    ),
    "A": (
        "Your audience is already asking for something like it.",
        "Your audience hasn’t asked for this yet.",
    ),
    "T": (
        "The timing lines up with what your niche is posting about.",
        "It isn’t tied to a trend right now.",
    ),
    "N": ("It’s different from your recent reels.", "It’s close to something you posted recently."),
}


def reasons(s: Scored) -> list[dict[str, str]]:
    """Two reasons with their evidence, matching the verdict: a Strong idea's two strongest
    parts, a Risky idea's two weakest, otherwise one of each. A part is only ever called a
    strength when it scores at least half."""
    contrib = {k: WEIGHTS[k] * s.parts[k].value for k in WEIGHTS}
    gap = {k: WEIGHTS[k] * (1 - s.parts[k].value) for k in WEIGHTS}
    strongest = sorted(WEIGHTS, key=lambda k: (-contrib[k], k))
    weakest = sorted(WEIGHTS, key=lambda k: (-gap[k], k))
    band = verdict(s.score)
    if band == "Strong":
        picks = strongest[:2]
    elif band == "Risky":
        picks = weakest[:2]
    else:
        picks = [strongest[0], next(k for k in weakest if k != strongest[0])]
    return [_reason(s, k) for k in picks]


def _reason(s: Scored, part: str) -> dict[str, str]:
    good = s.parts[part].value >= 0.5
    facts = s.parts[part].facts
    evidence = facts[0] if facts else ("From your data." if good else _absence(part))
    return {"text": REASONS[part][0 if good else 1], "evidence": evidence}


def _absence(part: str) -> str:
    return {
        "H": "None of your sub-clusters is close to it",
        "A": "No follower group is in yet",
        "T": "No dated event or rising tag in it",
        "N": "Similar to one of your last 10 reels",
    }[part]


@dataclass
class Tweak:
    text: str
    gain: float


def tweaks(s: Scored, ctx: Context, rescore) -> list[Tweak]:
    """Changes that would raise the score, each re-scored with the same formula
    (``rescore(candidate) -> Scored``). The best two that help are shown."""
    c = s.candidate
    out: list[Tweak] = []
    working = [f for f in ctx.formats if format_works(ctx, f) and f != c.format]
    if working:
        best_fmt = max(working, key=lambda f: ctx.formats[f].lifts.get("views") or 0)
        alt = rescore(_with(c, format=best_fmt))
        stat = ctx.formats[best_fmt]
        out.append(
            Tweak(
                f"Make it a {format_name(best_fmt)} reel — yours get "
                f"{stat.lifts['views']:.2f}× your usual views.",
                round(alt.score - s.score, 2),
            )
        )
    asked = {t.key for t in matched_themes(c, ctx)}
    open_themes = [t for t in ctx.themes if t.key not in asked]
    if open_themes:
        t = max(open_themes, key=lambda t: t.share)
        alt = rescore(_with(c, text=f"{c.text} {' '.join(sorted(t.words))}"))
        out.append(
            Tweak(
                f"Answer what your audience keeps asking: {round(t.share * 100, 1)}% of your "
                f"recent comments {_phrase(t.label)}.",
                round(alt.score - s.score, 2),
            )
        )
    tr = ctx.trend
    if tr.festival and festival_of(c, ctx) is None:
        alt = rescore(_with(c, text=f"{c.text} for {tr.festival}"))
        days = (tr.starts_on - ctx.today).days if tr.starts_on else None
        when = f" — it starts in {days} days" if days and days > 0 else ""
        out.append(Tweak(f"Tie it to {tr.festival}{when}.", round(alt.score - s.score, 2)))
    return sorted((t for t in out if t.gain >= 0.01), key=lambda t: -t.gain)[:2]


def _with(c: Candidate, **changes) -> Candidate:
    from dataclasses import replace

    return replace(c, **changes)
