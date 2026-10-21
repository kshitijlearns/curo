"""The accuracy record (logic doc §13 "Staying honest"; MVP doc accuracy_report).

Every simulation's estimate is kept. Once the creator confirms which posted reel it became,
and that reel is seven days old, its public counts at day 7 are compared with the estimated
ranges. "Curo's range contained the result for 8 of your last 10 reels" counts a reel as in
range when every count CURO could see at day 7 fell inside its range.

"If accuracy drops, the ranges are widened automatically": with at least five reels on record
and fewer than 70% in range, new estimates' ranges are made 25% wider (in log terms).
"""

from __future__ import annotations

from typing import Any

COUNTS = ("views", "likes", "comments", "shares")
SEVEN_DAYS_H = 168.0
RECORD = 10
MIN_RECORD = 5
GOOD_ENOUGH = 0.7
WIDEN = 1.25


def check(
    predicted: dict[str, dict[str, float]], actual: dict[str, float | None]
) -> tuple[bool | None, dict[str, Any]]:
    """(in range, per-count detail). None when no count could be compared."""
    detail: dict[str, Any] = {}
    for m in COUNTS:
        p, a = predicted.get(m), actual.get(m)
        if not p or a is None:
            continue  # a hidden count is unknown, not a miss
        detail[m] = {
            "actual": round(a),
            "low": p["low"],
            "high": p["high"],
            "in_range": p["low"] <= a <= p["high"],
        }
    if not detail:
        return None, detail
    return all(d["in_range"] for d in detail.values()), detail


def record(latest_first: list[bool]) -> dict[str, Any]:
    """The running record over the last ten checked reels, and how much to widen ranges."""
    recent = latest_first[:RECORD]
    hits, total = sum(recent), len(recent)
    widen = WIDEN if total >= MIN_RECORD and hits / total < GOOD_ENOUGH else 1.0
    return {"hits": hits, "total": total, "widen": widen}
