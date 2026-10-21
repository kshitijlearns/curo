"""Numbers CURO derives from the Reel Record (logic doc §4): values at an age, rates, lifts.

Rules enforced here:
* Missing means unknown. A hidden count is None, never 0; a rate with an unknown part is
  None; None values are left out of every median.
* Every comparison is at the same age. A reel's value at age t is read from its snapshots
  (straight-line between the two around t); it is never extrapolated before its first
  snapshot. The one approximation: reels change little after 30 days, so for the 30-day
  bucket a reel first seen later than that counts with its first snapshot (DECISIONS D41).
* Lift = the reel's value ÷ the creator's median at the same age.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from itertools import pairwise

AGE_BUCKETS: dict[str, float] = {"6h": 6.0, "1d": 24.0, "3d": 72.0, "7d": 168.0, "30d": 720.0}
SETTLED_H = 720.0
COUNTS = ("views", "likes", "comments", "shares")
RATES = {"like_rate": "likes", "comment_rate": "comments", "share_rate": "shares"}
METRICS = COUNTS + tuple(RATES)
# What the learning steps compare reels on: the Outlier Index (views) and the three rates.
LIFT_METRICS = ("views", "like_rate", "comment_rate", "share_rate")


@dataclass(frozen=True)
class Snap:
    age_h: float
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None


@dataclass
class ReelSeries:
    reel_id: str
    posted_at: datetime
    age_now_h: float
    snaps: list[Snap] = field(default_factory=list)
    paid: bool = False
    deleted: bool = False

    @property
    def latest_age(self) -> float | None:
        return max((s.age_h for s in self.snaps), default=None)


def count_at(snaps: list[Snap], metric: str, age_h: float) -> float | None:
    """A count at an age, read from snapshots (None when it can't be known)."""
    pts = sorted((s.age_h, getattr(s, metric)) for s in snaps if getattr(s, metric) is not None)
    if not pts:
        return None
    first_age, first_value = pts[0]
    if age_h < first_age:
        # Settled: a reel first seen after 30 days counts with its first snapshot.
        return float(first_value) if age_h >= SETTLED_H else None
    for (a1, v1), (a2, v2) in pairwise(pts):
        if a1 <= age_h <= a2:
            if a2 == a1:
                return float(v2)
            return v1 + (v2 - v1) * (age_h - a1) / (a2 - a1)
    last_age, last_value = pts[-1]
    return float(last_value) if age_h == last_age else None


def metric_at(series: ReelSeries, metric: str, age_h: float) -> float | None:
    """A count, or a rate per view, at an age."""
    if metric in RATES:
        part = count_at(series.snaps, RATES[metric], age_h)
        views = count_at(series.snaps, "views", age_h)
        if part is None or not views:
            return None
        return part / views
    return count_at(series.snaps, metric, age_h)


@dataclass(frozen=True)
class Baseline:
    median: float | None
    p25: float | None
    p75: float | None
    n: int


def _quantiles(values: list[float]) -> Baseline:
    if not values:
        return Baseline(None, None, None, 0)
    v = sorted(values)

    def q(p: float) -> float:  # linear interpolation, as numpy's default
        k = (len(v) - 1) * p
        lo, hi = math.floor(k), math.ceil(k)
        return v[lo] + (v[hi] - v[lo]) * (k - lo)

    return Baseline(q(0.5), q(0.25), q(0.75), len(v))


def compute_baselines(reels: list[ReelSeries], window: int = 20) -> dict[tuple[str, str], Baseline]:
    """Median, p25 and p75 of each metric at each age, over the last ``window`` reels that have
    reached that age with a known value. Paid partnerships are left out (they may have been
    boosted); deleted reels stay in. Also the growth curve g(t): the share of its 7-day views a
    reel has by age t (``views_share_7d``)."""
    eligible = sorted((r for r in reels if not r.paid), key=lambda r: r.posted_at, reverse=True)
    out: dict[tuple[str, str], Baseline] = {}
    for bucket, age in AGE_BUCKETS.items():
        for metric in METRICS:
            values: list[float] = []
            for r in eligible:
                if r.age_now_h < age:
                    continue
                v = metric_at(r, metric, age)
                if v is not None:
                    values.append(v)
                    if len(values) == window:
                        break
            out[(metric, bucket)] = _quantiles(values)
        shares: list[float] = []
        for r in eligible:
            if r.age_now_h < max(age, AGE_BUCKETS["7d"]):
                continue
            v, v7 = count_at(r.snaps, "views", age), count_at(r.snaps, "views", AGE_BUCKETS["7d"])
            if v is not None and v7:
                shares.append(v / v7)
                if len(shares) == window:
                    break
        out[("views_share_7d", bucket)] = _quantiles(shares)
    return out


def baseline_at(
    baselines: Mapping[tuple[str, str], Baseline], metric: str, age_h: float
) -> float | None:
    """The creator's median for ``metric`` at any age, between the fixed buckets: straight
    lines in log-age (and log-value for counts). Counts aren't estimated before 6 hours;
    rates use the 6-hour median there. Beyond 30 days the 30-day median holds."""
    pts = [
        (AGE_BUCKETS[b], baselines[(metric, b)].median)
        for b in AGE_BUCKETS
        if (metric, b) in baselines and baselines[(metric, b)].median is not None
    ]
    if not pts:
        return None
    for a, v in pts:
        if age_h == a:
            return v
    is_count = metric in COUNTS
    if age_h <= pts[0][0]:
        if age_h < pts[0][0] and is_count:
            return None
        return pts[0][1]
    if age_h >= pts[-1][0]:
        return pts[-1][1] if pts[-1][0] >= SETTLED_H or age_h == pts[-1][0] else None
    for (a1, v1), (a2, v2) in pairwise(pts):
        if a1 <= age_h <= a2:
            x = (math.log(age_h) - math.log(a1)) / (math.log(a2) - math.log(a1))
            if is_count and v1 > 0 and v2 > 0:
                return math.exp(math.log(v1) + (math.log(v2) - math.log(v1)) * x)
            return v1 + (v2 - v1) * x
    return None


@dataclass(frozen=True)
class Lift:
    age_h: float
    value: float
    expected: float
    lift: float


def reel_lifts(
    series: ReelSeries, baselines: Mapping[tuple[str, str], Baseline]
) -> dict[str, Lift]:
    """Each lift metric at the reel's reference age: its latest snapshot, capped at 30 days
    (the settled value for older reels). Metrics that can't be known are left out."""
    latest = series.latest_age
    if latest is None:
        return {}
    age = min(latest, SETTLED_H)
    out: dict[str, Lift] = {}
    for metric in LIFT_METRICS:
        value = metric_at(series, metric, age)
        expected = baseline_at(baselines, metric, age)
        if value is None or not expected:
            continue
        out[metric] = Lift(age, value, expected, value / expected)
    return out
