"""The collection schedule (PLAN_V2 §4.3): the creator's own reels only, with cost controls.
Pure functions.

- Snapshots at fixed ages: every 6 h for the first 48 h, daily to day 7, weekly to day 30,
  then stop — 0, 6 … 48 h, 3–7 days, 14, 21, 28 and 30 days (18 per reel). Fixed ages keep the
  baselines' age buckets (6 h, 1 d, 3 d, 7 d, 30 d) measured, not stretched over a week.
- New-reel discovery: every 12 h, the profile and the latest 3 reels.
- Comments: read once when a reel is first collected (onboarding, or discovery), then only
  comments newer than the newest stored, at about 24 h and 7 days after posting.
- A creator who hasn't opened the app in 14 days is paused (``is_paused``).

Snapshots are batched: one run per account covers all of its reels that are due, plus the
follower count.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

DISCOVERY_EVERY_H = 12.0
DISCOVERY_LIMIT = 3
STOP_AFTER_H = 30 * 24
COMMENT_READS_AT_H = (24.0, 7 * 24.0)  # the follow-up comment reads after the first

# Small slack so a job that ran a few minutes early still counts as "on time".
_SLACK_H = 0.25


def interval_h(age_h: float) -> float | None:
    """Hours between snapshots for a reel of this age, or None when tracking stops."""
    if age_h < 48:
        return 6.0
    if age_h < 7 * 24:
        return 24.0
    if age_h < STOP_AFTER_H:
        return 168.0
    return None


def planned_snapshots() -> list[float]:
    """The reel ages (hours) the schedule takes snapshots at, from a first one at posting."""
    out, t = [0.0], 0.0
    while True:
        every = interval_h(t)
        if every is None:
            return out
        t += every
        if t >= STOP_AFTER_H:
            return [*out, float(STOP_AFTER_H)]  # the last one at day 30: the settled count
        out.append(t)


PLANNED = planned_snapshots()
LATE_GRACE_H = 24.0  # a reel whose day-30 snapshot was missed still gets it within a day


def is_due(posted_at: datetime, last_taken_at: datetime | None, now: datetime) -> bool:
    """Due when the reel has reached a planned age it hasn't been snapshotted at yet."""
    age_h = (now - posted_at).total_seconds() / 3600
    if age_h > STOP_AFTER_H + LATE_GRACE_H:
        return False
    if last_taken_at is None:
        return True
    last_age = (last_taken_at - posted_at).total_seconds() / 3600
    target = next((a for a in PLANNED if a > last_age + _SLACK_H), None)
    return target is not None and age_h + _SLACK_H >= target


def discovery_due(last_discovered_at: datetime | None, now: datetime) -> bool:
    if last_discovered_at is None:
        return True
    since_h = (now - last_discovered_at).total_seconds() / 3600
    return since_h + _SLACK_H >= DISCOVERY_EVERY_H


def comment_read_due(posted_at: datetime, reads_done: int, now: datetime) -> bool:
    """The follow-up comment reads: one after 24 h, one after 7 days (``reads_done`` counts the
    reads after the first). Never more than those two."""
    if reads_done >= len(COMMENT_READS_AT_H):
        return False
    age_h = (now - posted_at).total_seconds() / 3600
    return age_h >= COMMENT_READS_AT_H[reads_done]


def is_paused(last_seen_at: datetime | None, now: datetime, pause_days: int) -> bool:
    """A creator who hasn't opened the app for ``pause_days`` days. Never seen counts as seen at
    sign-up, so a brand-new creator isn't paused."""
    return last_seen_at is not None and now - last_seen_at >= timedelta(days=pause_days)


@dataclass(frozen=True)
class ReelState:
    shortcode: str
    posted_at: datetime
    last_taken_at: datetime | None


def due_shortcodes(reels: list[ReelState], now: datetime) -> list[str]:
    return [r.shortcode for r in reels if is_due(r.posted_at, r.last_taken_at, now)]
