"""Data-quality rules for public snapshots (MVP doc §4). Pure functions.

| Situation                          | Rule                                                        |
| Likes hidden                       | store NULL; left out of rates and baselines                 |
| Share count not shown              | store NULL; reel left out of share baselines                |
| Comments turned off                | store NULL; no comment-based audience cards                 |
| A snapshot lower than the previous | keep the previous value; flag the snapshot                  |
| Reel deleted                       | mark deleted; keep its past snapshots (collection.py)       |
| Account private or deleted         | stop collecting; hide from peers; keep aggregates (jobs)    |
| Scrape fails                       | retry once, backup vendor, then mark missed (failover.py)   |
"""

from __future__ import annotations

from dataclasses import dataclass

METRICS = ("views", "likes", "comments", "shares")


@dataclass(frozen=True)
class Counts:
    views: int | None
    likes: int | None
    comments: int | None
    shares: int | None

    def get(self, metric: str) -> int | None:
        return getattr(self, metric)


@dataclass(frozen=True)
class CleanSnapshot:
    counts: Counts
    flagged: bool
    flag_reason: str | None


def clean_snapshot(new: Counts, previous: Counts | None) -> CleanSnapshot:
    """Apply the rules to a fresh snapshot, given the reel's previous one.

    Public counts only ever grow. If one comes back lower than before (a vendor glitch,
    a removed spam comment), keep the previous value and flag the snapshot. A count that
    was public and is now missing stays NULL (unknown), never 0.
    """
    values = {}
    reasons = []
    for metric in METRICS:
        value = new.get(metric)
        prev = previous.get(metric) if previous else None
        if value is not None and value < 0:
            value = None
            reasons.append(f"{metric}_negative")
        if value is not None and prev is not None and value < prev:
            reasons.append(f"{metric}_decreased")
            value = prev
        values[metric] = value
    return CleanSnapshot(Counts(**values), bool(reasons), ",".join(reasons) or None)
