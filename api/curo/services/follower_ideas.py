"""What your followers will love (v2.1 §5.4): ideas from the creator's own audience and best work.

Candidates:
1. **Audience requests and questions**: comment themes ("part 2", "where is it from", "budget
   version", "tutorial please"), with their share of comments and an example.
2. **Proven formats**: the creator's sub-clusters and pattern cards that lift likes, comments or
   shares — "more of what worked".
3. **Persona interests**: the Simulator's audience segments, when they exist.

    score = 0.45 × audience demand + 0.35 × proven performance + 0.20 × novelty

Demand: a theme's share of comments (15% = full), a segment's share of the audience (30% =
full). Proven: lift above usual (2× = full); an ask with no performance history is neutral
(0.5). Novelty: 1 − the closest similarity to the creator's last 10 reels. Top 5 shown.
"""

from __future__ import annotations

from dataclasses import dataclass, field

WEIGHTS = {"demand": 0.45, "proven": 0.35, "novelty": 0.20}
SHOWN = 5
DUPLICATE = 0.85  # embedding similarity at which two ideas are the same idea

# A theme's words → the audience segment it's for (when no Simulator segments exist yet).
SEGMENT_HINTS = [
    (("price", "budget", "cost", "link", "buy", "where", "shop"), "Budget shoppers"),
    (("festive", "festival", "ganpati", "diwali", "wedding", "occasion"), "Festive planners"),
    (("how", "tutorial", "steps", "tips", "learn"), "Idea savers"),
    (("camera", "edit", "light", "filming", "phone"), "Fellow creators"),
    (("part", "more", "next"), "Loyal fans"),
]


@dataclass
class Candidate:
    key: str
    kind: str  # request | proven | segment
    topic: str
    segment: str
    facts: list[str]
    examples: list[str] = field(default_factory=list)
    demand: float = 0.0
    proven: float = 0.5
    novelty: float = 0.5
    vector: list[float] | None = None

    @property
    def score(self) -> float:
        return round(
            WEIGHTS["demand"] * self.demand
            + WEIGHTS["proven"] * self.proven
            + WEIGHTS["novelty"] * self.novelty,
            3,
        )

    @property
    def parts(self) -> dict[str, float]:
        return {
            "demand": round(self.demand, 3),
            "proven": round(self.proven, 3),
            "novelty": round(self.novelty, 3),
        }


def clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def segment_for(text: str, segments: list[dict] | None = None) -> str:
    words = text.lower()
    if segments:
        best = max(
            segments,
            key=lambda s: (
                sum(1 for i in s.get("interests", []) if i.lower() in words),
                s["share"],
            ),
        )
        return best["label"]
    for cues, label in SEGMENT_HINTS:
        if any(c in words for c in cues):
            return label
    return "Loyal fans"


def from_themes(themes: list[dict], segments: list[dict] | None) -> list[Candidate]:
    out = []
    for t in themes:
        pct = round(t["share"] * 100, 1)
        facts = [
            f"{t['n']} comments asked about this: {t['label']}.",
            f"That's {pct}% of your recent comments.",
        ]
        out.append(
            Candidate(
                key=f"theme:{t['label'].lower()}",
                kind="request",
                topic=t["label"],
                segment=segment_for(t["label"], segments),
                facts=facts,
                examples=[e for e in t.get("samples", [])][:2],
                demand=clamp(t["share"] / 0.15),
                proven=0.5,
            )
        )
    return out


def from_groups(groups: list[dict], segments: list[dict] | None) -> list[Candidate]:
    out = []
    for g in groups:
        lift = g.get("lift")
        if lift is None or lift <= 1 or g["n"] < 3:
            continue
        out.append(
            Candidate(
                key=f"group:{g['label'].lower()}",
                kind="proven",
                topic=g["label"],
                segment=segment_for(g["label"], segments),
                facts=[
                    f"Your “{g['label']}” reels get {lift:.1f}× your usual views ({g['n']} reels)."
                ],
                demand=0.3,
                proven=clamp(lift - 1.0),
            )
        )
    return out


METRIC_WORDS = {"like_rate": "likes", "comment_rate": "comments", "share_rate": "shares"}


def from_cards(cards: list[dict], label_for) -> list[Candidate]:
    out = []
    for c in cards:
        if c["metric"] not in METRIC_WORDS or c["effect"] <= 1 or c["n"] < 5:
            continue
        what = label_for(c["value"])
        words = METRIC_WORDS[c["metric"]]
        out.append(
            Candidate(
                key=f"card:{c['feature']}:{c['value']}:{c['metric']}",
                kind="proven",
                topic=what,
                segment="Loyal fans",
                facts=[
                    f"Reels with {what.lower()} get {c['effect']:.1f}× your usual {words} ({c['n']} reels)."
                ],
                demand=0.35 if c["metric"] in ("comment_rate", "share_rate") else 0.25,
                proven=clamp(c["effect"] - 1.0),
            )
        )
    return out  # fmt: skip


def from_segments(segments: list[dict]) -> list[Candidate]:
    out = []
    for s in segments:
        out.append(
            Candidate(
                key=f"segment:{s['key']}",
                kind="segment",
                topic=s["description"],
                segment=s["label"],
                facts=[
                    f"{round(s['share'] * 100)}% of your AI audience are {s['label'].lower()}s: {s['description']}"
                ],
                demand=clamp(s["share"] / 0.3),
                proven=0.3,
            )
        )
    return out  # fmt: skip


def cosine(a: list[float], b: list[float]) -> float:
    num = sum(x * y for x, y in zip(a, b, strict=False))
    da = sum(x * x for x in a) ** 0.5
    db = sum(y * y for y in b) ** 0.5
    return num / (da * db) if da and db else 0.0


def rank(
    candidates: list[Candidate],
    recent: list[list[float]],
    opportunities: list[tuple[list[float], float]],
) -> list[Candidate]:
    """Novelty, dedupe against opportunity areas (the higher section keeps an idea) and each
    other (the higher score wins), then the top 5 by score."""
    for c in candidates:
        if c.vector and recent:
            c.novelty = clamp(1 - max(cosine(c.vector, r) for r in recent))
    kept: list[Candidate] = []
    for c in sorted(candidates, key=lambda c: (-c.score, c.key)):
        if c.vector and any(
            cosine(c.vector, v) >= DUPLICATE and score >= c.score for v, score in opportunities
        ):
            continue  # Opportunity areas already shows it, with a higher score
        if c.vector and any(k.vector and cosine(c.vector, k.vector) >= DUPLICATE for k in kept):
            continue
        kept.append(c)
    return kept[:SHOWN]


def template(kind: str, topic: str, segment: str | None, facts: list[str]) -> tuple[str, str]:
    """A plain title and why from the evidence (T24's fallback and its mock)."""
    topic = topic.strip().rstrip(".")
    low = topic.lower()
    if kind == "request":
        if "part 2" in low or "part two" in low:
            title = "The part 2 they keep asking for"
        elif "where" in low or "link" in low or "from" in low:
            title = "Where every piece is from"
        elif "price" in low or "budget" in low or "cost" in low:
            title = "The budget version they asked for"
        elif "how" in low or "tutorial" in low or "camera" in low or "edit" in low:
            title = "Show them how you make it"
        else:
            title = f"Answer this: {topic}"
        why = f"Your followers asked for it. {facts[0]}"
    elif kind == "proven":
        title = f"More {low}"
        why = f"More of what already works for you. {facts[0]}"
    else:
        who = segment or "your audience"
        title = f"Made for {who.lower()}"
        why = f"A reel for the people who watch you most. {facts[0]}"
    return title[:60], why[:160]
