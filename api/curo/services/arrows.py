"""Home's arrows (logic doc §6): is this reel doing better or worse than expected at this age?

Expected value, in this order:
1. The reel was simulated: the simulation's 7-day prediction × g(t), the share of its 7-day
   views this creator's reels usually reach by age t (the creator's growth curve).
2. Otherwise: the creator's usual, the median of their last 20 reels at the same age.

    change = (actual − expected) / expected

Changes between −5% and +5% show as a flat dash. Too little history (fewer than 3 reels at
that age) means no arrow rather than a guess.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from curo.services.metrics import AGE_BUCKETS, COUNTS, Baseline, baseline_at

FLAT_BAND = 0.05
MIN_BASELINE_N = 3
SEVEN_DAYS_H = AGE_BUCKETS["7d"]

Comparison = Literal["simulation", "usual"]


@dataclass(frozen=True)
class Arrow:
    metric: str
    actual: float
    expected: float
    change: float  # fraction: 0.32 = +32%
    compared_with: Comparison

    @property
    def percent(self) -> int:
        return round(self.change * 100)

    @property
    def direction(self) -> Literal["up", "down", "flat"]:
        if abs(self.change) <= FLAT_BAND:
            return "flat"
        return "up" if self.change > 0 else "down"


def change(actual: float, expected: float) -> float:
    return (actual - expected) / expected


def growth_share(baselines: Mapping[tuple[str, str], Baseline], age_h: float) -> float | None:
    """g(t): the share of 7-day views usually reached by age t (1.0 at 7 days; beyond 7 days
    the 30-day share if known, else 1.0 — the prediction is a 7-day figure)."""
    if age_h >= SEVEN_DAYS_H:
        return baseline_at(baselines, "views_share_7d", age_h) or 1.0
    return baseline_at(baselines, "views_share_7d", age_h)


def baseline_n(baselines: Mapping[tuple[str, str], Baseline], metric: str, age_h: float) -> int:
    """How many reels the usual at this age rests on (the fewer of the two buckets around it)."""
    ages = sorted(AGE_BUCKETS.items(), key=lambda kv: kv[1])
    below = [b for b, a in ages if a <= age_h]
    above = [b for b, a in ages if a >= age_h]
    keys = {below[-1] if below else ages[0][0], above[0] if above else ages[-1][0]}
    return min(baselines.get((metric, k), Baseline(None, None, None, 0)).n for k in keys)


def arrows_for(
    actual: Mapping[str, float | None],
    age_h: float,
    baselines: Mapping[tuple[str, str], Baseline],
    prediction_7d: Mapping[str, float | None] | None = None,
) -> dict[str, Arrow]:
    """An arrow per count that can be compared. Unknown counts (hidden likes…) get none."""
    out: dict[str, Arrow] = {}
    g = growth_share(baselines, age_h) if prediction_7d else None
    for metric in COUNTS:
        value = actual.get(metric)
        if value is None:
            continue
        predicted = (prediction_7d or {}).get(metric)
        if predicted and g:
            expected, compared = predicted * g, "simulation"
        else:
            if baseline_n(baselines, metric, age_h) < MIN_BASELINE_N:
                continue
            expected, compared = baseline_at(baselines, metric, age_h), "usual"
        if expected:
            out[metric] = Arrow(metric, float(value), expected, change(value, expected), compared)
    return out
