"""Phase of reel (logic doc §7, DECISIONS D11).

Velocity is the views gained per hour between two snapshots, compared with the highest
velocity the reel has reached so far.

| Phase     | Rule                                                                    |
| Testing   | under 24 hours old and views still below the follower count             |
| Long tail | velocity below 10% of its highest for 48 hours (still trickling in)     |
| Slowing   | velocity below 50% of its highest                                       |
| Growing   | velocity rose in the last two snapshots                                 |
| Peak      | velocity within 80% of its highest and no longer rising; 50–80% that    |
|           | isn't rising also counts as Peak (not yet slowed below half, D11)       |

Rules are checked in that order (D11's precedence). How long each phase usually lasts is the
middle half (25th–75th percentile) of the creator's own reels. A reel first seen late in its
life never showed CURO its peak, so its phase is estimated from its age and the creator's
typical timeline, and says so.
"""

from __future__ import annotations

import itertools
import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass

from curo.services.metrics import Snap

PHASES = ("testing", "growing", "peak", "slowing", "longtail")
LABELS = {
    "testing": "Testing",
    "growing": "Growing",
    "peak": "Peak",
    "slowing": "Slowing",
    "longtail": "Long tail",
}
TEXT = {
    "testing": "Mostly being shown to your followers so far.",
    "growing": "Views are picking up speed.",
    "peak": "Views are climbing fast.",
    "slowing": "Views are slowing down.",
    "longtail": "New views have slowed to a trickle.",
}
TESTING_H = 24.0
LONG_TAIL_SHARE, LONG_TAIL_H = 0.10, 48.0
SLOWING_SHARE, PEAK_SHARE = 0.50, 0.80
RISING = 1.05  # a rise smaller than 5% is noise, not growth
BEYOND_FOLLOWERS = 2.0  # views ÷ followers from which the reel is clearly reaching non-followers
SEEN_LATE_H = 48.0
# Used only when the creator has no tracked history yet (hours since posting).
DEFAULT_STARTS = {"testing": 0.0, "growing": 24.0, "peak": 48.0, "slowing": 96.0, "longtail": 240.0}


@dataclass(frozen=True)
class Velocity:
    start_h: float
    end_h: float
    per_hour: float


def velocities(snaps: Sequence[Snap], from_posting: bool) -> list[Velocity]:
    """Views per hour between consecutive snapshots. A reel seen from its first hours also
    gets the interval from posting (0 views at age 0) to its first snapshot."""
    pts = sorted((s.age_h, s.views) for s in snaps if s.views is not None)
    if from_posting and pts and pts[0][0] > 0:
        pts.insert(0, (0.0, 0))
    out = []
    for (a1, v1), (a2, v2) in itertools.pairwise(pts):
        if a2 > a1:
            out.append(Velocity(a1, a2, max(0.0, (v2 - v1) / (a2 - a1))))
    return out


def phase_now(
    vels: Sequence[Velocity], age_h: float, views: float | None, followers: int | None
) -> str | None:
    """The phase at ``age_h`` given the velocities measured up to then."""
    if age_h < TESTING_H and views is not None and (followers is None or views < followers):
        return "testing"
    if not vels:
        return "testing" if age_h < TESTING_H else None
    peak = max(v.per_hour for v in vels)
    current = vels[-1].per_hour
    if peak <= 0:
        return "longtail"
    last_high = max((v.end_h for v in vels if v.per_hour >= LONG_TAIL_SHARE * peak), default=0.0)
    if current < LONG_TAIL_SHARE * peak and age_h - last_high >= LONG_TAIL_H:
        return "longtail"
    if current < SLOWING_SHARE * peak:
        return "slowing"
    if len(vels) >= 2 and current > RISING * vels[-2].per_hour:
        return "growing"
    return "peak"


def timeline(
    snaps: Sequence[Snap], followers: int | None, from_posting: bool
) -> list[tuple[float, float, str | None]]:
    """(age, velocity, phase) at each snapshot, using only what was known at that moment."""
    vels = velocities(snaps, from_posting)
    views_at = {s.age_h: s.views for s in snaps}
    return [
        (v.end_h, v.per_hour, phase_now(vels[: i + 1], v.end_h, views_at.get(v.end_h), followers))
        for i, v in enumerate(vels)
    ]


@dataclass(frozen=True)
class PhaseStats:
    """How a creator's tracked reels move through the phases."""

    durations: dict[str, list[float]]  # hours spent in a phase, per reel that moved on from it
    starts: dict[str, list[float]]  # age when each reel entered the phase

    def usual_start(self, phase: str) -> float:
        s = self.starts.get(phase)
        return statistics.median(s) if s else DEFAULT_STARTS[phase]


def phase_stats(timelines: Sequence[list[tuple[float, float, str | None]]]) -> PhaseStats:
    """A phase starts at the first snapshot that shows it and lasts until the first snapshot
    showing the next one. Only stretches the reel has moved on from count as durations."""
    durations: dict[str, list[float]] = {p: [] for p in PHASES}
    starts: dict[str, list[float]] = {p: [] for p in PHASES}
    for tl in timelines:
        runs: list[tuple[str, float]] = []  # (phase, age first seen)
        for age, _v, phase in tl:
            if phase is not None and (not runs or runs[-1][0] != phase):
                runs.append((phase, age))
        seen: set[str] = set()
        spent: dict[str, float] = {}
        for k, (phase, start) in enumerate(runs):
            if phase not in seen:
                starts[phase].append(start)
                seen.add(phase)
            if k < len(runs) - 1:
                spent[phase] = spent.get(phase, 0.0) + (runs[k + 1][1] - start)
        for phase, hours in spent.items():
            durations[phase].append(hours)
    return PhaseStats(durations, starts)


def _quartiles(values: list[float]) -> tuple[float, float]:
    v = sorted(values)
    if len(v) == 1:
        return v[0], v[0]
    q = statistics.quantiles(v, n=4, method="inclusive")
    return q[0], q[2]


def usual_range(stats: PhaseStats, phase: str) -> str | None:
    """How long this phase usually lasts for this creator, e.g. "1 – 3 days"."""
    if phase == "longtail":
        if not stats.starts["longtail"]:
            return None
        return f"Day {max(1, round(stats.usual_start('longtail') / 24))}+"
    values = stats.durations.get(phase) or []
    if len(values) < 2:
        return None
    lo, hi = _quartiles(values)
    if hi < 24:
        lo_h, hi_h = max(1, round(lo)), max(1, round(hi))
        return f"{lo_h} hours" if lo_h == hi_h else f"{lo_h} – {hi_h} hours"
    lo_d, hi_d = max(1, math.floor(lo / 24)), max(1, math.ceil(hi / 24))
    return f"{lo_d} days" if lo_d == hi_d else f"{lo_d} – {hi_d} days"


def estimate_by_age(stats: PhaseStats, age_h: float) -> str:
    """For a reel seen late: the phase the creator's reels have usually reached by this age
    (the one that usually starts latest without starting after it)."""
    if age_h < TESTING_H:
        return "testing"
    reached = [p for p in PHASES[1:] if stats.usual_start(p) <= age_h]
    if not reached:
        return "testing"
    return max(reached, key=lambda p: (stats.usual_start(p), PHASES.index(p)))


def description(phase: str, views: float | None, followers: int | None) -> str:
    """The logic doc's text, plus "beyond your followers" when views pass 2× followers
    (views ÷ followers is the only public signal; no exact share is ever claimed)."""
    text = TEXT[phase]
    if views and followers and phase in ("growing", "peak"):
        ratio = views / followers
        if ratio >= BEYOND_FOLLOWERS:
            text = (
                f"{text[:-1]} and are already {ratio:.0f}× your follower count, so it’s reaching "
                "people beyond your followers."
            )
    return text
