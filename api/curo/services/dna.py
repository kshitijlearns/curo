"""DNA helpers (logic doc §4–5): the confidence rule, the text that gets embedded, and the
features pattern mining compares reels on."""

from __future__ import annotations

from typing import Any

from curo.schemas.tasks import T1Output, T2Output
from curo.schemas.taxonomy import ALL_FIELDS, CONTENT_FIELDS, MIN_CONFIDENCE, UNKNOWN

# Fields mined for pattern cards (closed lists only; hook text and entities are free text).
MINED_FIELDS = tuple(ALL_FIELDS)


def apply_confidence(out: T2Output) -> tuple[dict[str, Any], dict[str, Any], dict[str, float]]:
    """Content and production DNA with every field below 0.6 confidence stored as unknown
    (never guessed). Returns (content, production, confidence)."""
    conf = {k: round(float(v), 3) for k, v in out.confidence.items()}

    def keep(name: str) -> bool:
        return conf.get(name, 0.0) >= MIN_CONFIDENCE

    content = out.content.model_dump()
    production = out.production.model_dump()
    for part in (content, production):
        for name in list(part):
            if keep(name):
                continue
            if name in ALL_FIELDS:
                part[name] = UNKNOWN
            elif name == "hook_text":
                part[name] = ""
            elif name == "cuts_per_10s":
                part[name] = None
            elif name == "key_entities":
                part[name] = []
    for name in ALL_FIELDS:  # a field the model left out has no confidence: unknown
        target = content if name in CONTENT_FIELDS else production
        target.setdefault(name, UNKNOWN)
    return content, production, conf


def embedding_text(caption: str, t1: T1Output) -> str:
    """Transcript + caption + what's on screen and seen (MVP doc §5), each description once."""
    seen = list(dict.fromkeys(s.description for s in t1.seconds))
    parts = [
        caption,
        t1.transcript_text(),
        " ".join(o.text for o in t1.onscreen_text),
        ". ".join(seen),
    ]
    return "\n".join(p for p in parts if p)


def _band(
    value: float | None, edges: tuple[float, float], names: tuple[str, str, str]
) -> str | None:
    if value is None:
        return None
    if value < edges[0]:
        return names[0]
    return names[1] if value <= edges[1] else names[2]


def features(
    content: dict[str, Any],
    production: dict[str, Any],
    transcript: dict[str, Any] | None,
    duration_s: float | None,
) -> dict[str, str]:
    """The values a reel is compared on: every known closed field, plus code-derived bands
    (length, time to first payoff, cutting pace, on-screen text)."""
    out: dict[str, str] = {}
    for name in MINED_FIELDS:
        value = content.get(name) if name in CONTENT_FIELDS else production.get(name)
        if value and value != UNKNOWN and not (name == "core_tension" and value == "none"):
            out[name] = value  # "no core tension" is an absence, not a choice to compare
    duration = _band(
        float(duration_s) if duration_s is not None else None,
        (20, 40),
        ("under_20s", "20_to_40s", "over_40s"),
    )
    if duration:
        out["duration_band"] = duration
    t1 = transcript or {}
    payoff = _band(t1.get("first_payoff_s"), (2, 4), ("under_2s", "2_to_4s", "over_4s"))
    if payoff:
        out["payoff_band"] = payoff
    pace = _band(production.get("cuts_per_10s"), (2.5, 3.8), ("slow", "medium", "fast"))
    if pace:
        out["pace"] = pace
    if transcript is not None:
        out["onscreen_text"] = "yes" if t1.get("onscreen_text") else "no"
    return out
