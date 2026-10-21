"""Which simulation or draft a newly posted reel came from (logic doc §15 step 2: "CURO links
it to the project using its audio fingerprint, caption similarity and timing, and asks the
creator to confirm the match").

Public data gives no audio fingerprint, so the match rests on what it does give: how close
the reel's caption is to the draft's or simulation's caption, how close its length is to the
video that was simulated, and how soon after the simulation it was posted. A match is only
ever a suggestion; the creator confirms it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from curo.services.simulator import cosine

WEIGHTS = {"caption": 0.5, "length": 0.3, "timing": 0.2}
MATCH_MIN = 0.6
WINDOW_DAYS = 14
SOON_DAYS = 3


@dataclass
class Candidate:
    simulation_id: str | None
    project_id: str | None
    caption_vector: list[float] | None
    duration_s: float | None
    made_at: datetime  # when it was simulated (or the draft last changed)


@dataclass
class Match:
    candidate: Candidate
    score: float
    reasons: list[str]


def _length(reel_s: float | None, video_s: float | None) -> float:
    if reel_s is None or video_s is None:
        return 0.0
    gap = abs(reel_s - video_s)
    return 1.0 if gap <= 1.5 else 0.5 if gap <= 4 else 0.0


def _timing(posted_at: datetime, made_at: datetime) -> float:
    days = (posted_at - made_at).total_seconds() / 86400
    if days < 0 or days > WINDOW_DAYS:
        return 0.0  # posted before it was simulated, or long after
    return 1.0 if days <= SOON_DAYS else 1.0 - (days - SOON_DAYS) / (WINDOW_DAYS - SOON_DAYS)


def score(
    reel_vector: list[float] | None, reel_s: float | None, posted_at: datetime, c: Candidate
) -> Match:
    caption = (
        max(0.0, cosine(reel_vector, c.caption_vector)) if reel_vector and c.caption_vector else 0.0
    )
    length = _length(reel_s, c.duration_s)
    timing = _timing(posted_at, c.made_at)
    total = WEIGHTS["caption"] * caption + WEIGHTS["length"] * length + WEIGHTS["timing"] * timing
    reasons = []
    if caption >= 0.7:
        reasons.append("Its caption is close to your draft’s.")
    if length == 1.0:
        reasons.append("It’s the same length as the video you simulated.")
    if timing > 0:
        days = max(0, round((posted_at - c.made_at).total_seconds() / 86400))
        reasons.append(
            "You posted it the day you simulated it."
            if days == 0
            else f"You posted it {days} day{'s' if days != 1 else ''} after simulating it."
            if c.simulation_id
            else f"You posted it {days} day{'s' if days != 1 else ''} after working on the draft."
        )
    return Match(c, round(total, 3), reasons)


def best(
    reel_vector: list[float] | None,
    reel_s: float | None,
    posted_at: datetime,
    candidates: list[Candidate],
) -> Match | None:
    scored = [score(reel_vector, reel_s, posted_at, c) for c in candidates]
    scored = [m for m in scored if m.score >= MATCH_MIN]
    return max(scored, key=lambda m: (m.score, m.candidate.made_at)) if scored else None
