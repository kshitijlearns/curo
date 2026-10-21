"""Everything the Simulator's estimate (T9) reads, loaded once per run.

The creator's own reels (v2: no peers), each with its DNA features, embedding and lifts
against the account's usual; the creator's last 50 reels for the score; the
pattern cards; the 7-day usual for the report; posting times for the best slot. All of it is
what CURO has collected — missing counts stay missing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from curo import clock
from curo.services import dna as dna_svc
from curo.services.arrows import baseline_n
from curo.services.metrics import (
    AGE_BUCKETS,
    LIFT_METRICS,
    ReelSeries,
    baseline_at,
    compute_baselines,
    metric_at,
    reel_lifts,
)
from curo.services.records import load_dna, load_series
from curo.services.simulator import HISTORY, Card, Past
from curo.services.text import reel_title

SEVEN_DAYS_H = AGE_BUCKETS["7d"]
MIN_BASELINE_N = 3  # a usual resting on fewer reels isn't a usual yet (as Home's arrows)


@dataclass
class SimData:
    creator_id: UUID
    account_id: UUID
    username: str
    timezone: str
    now: datetime
    own: list[Past]
    history: list[dict[str, float]]  # the creator's last 50 reels' lifts, newest first
    cards: list[Card]
    baselines_7d: dict[str, float | None]
    posts: list[tuple[datetime, float]]  # (local posting time, views lift)
    widen: float = 1.0  # > 1 when recent estimates missed too often (services/accuracy.py)

    @property
    def pool(self) -> list[Past]:
        return self.own


def neighbour_lifts(s: ReelSeries, baselines: dict) -> dict[str, float]:
    """A reel's 7-day lift per metric (MVP doc T9 step 2). A reel CURO first saw after day 7
    has no 7-day value; it counts with its lift at its reference age instead, which is
    measured against the usual at that same age (DECISIONS D82)."""
    out: dict[str, float] = {}
    ref = reel_lifts(s, baselines)
    for metric in LIFT_METRICS:
        value = metric_at(s, metric, SEVEN_DAYS_H) if s.age_now_h >= SEVEN_DAYS_H else None
        usual = baseline_at(baselines, metric, SEVEN_DAYS_H)
        if (
            value is not None
            and usual
            and baseline_n(baselines, metric, SEVEN_DAYS_H) >= MIN_BASELINE_N
        ):
            out[metric] = value / usual
        elif metric in ref and baseline_n(baselines, metric, ref[metric].age_h) >= MIN_BASELINE_N:
            out[metric] = ref[metric].lift
    return {m: round(v, 4) for m, v in out.items() if v > 0}


def _vectors(conn, account_ids: list[UUID]) -> dict[str, list[float]]:
    rows = conn.execute(
        """
        select e.reel_id, e.embedding::text as v
          from public.reel_embeddings e join public.reels r on r.id = e.reel_id
         where r.account_id = any(%s) and not r.is_deleted
        """,
        (account_ids,),
    ).fetchall()
    return {str(r["reel_id"]): json.loads(r["v"]) for r in rows}


def _pasts(
    conn, account_ids: list[UUID], own: bool, names: dict[UUID, str]
) -> tuple[list[Past], dict[UUID, list[ReelSeries]], dict[str, dict[str, float]]]:
    series = load_series(conn, account_ids)
    dna = load_dna(conn, account_ids)
    vectors = _vectors(conn, account_ids)
    out: list[Past] = []
    all_lifts: dict[str, dict[str, float]] = {}
    for account_id, reels in series.items():
        baselines = compute_baselines(reels)
        for s in reels:
            lifts = neighbour_lifts(s, baselines)
            all_lifts[s.reel_id] = lifts
            d = dna.get(s.reel_id)
            if s.paid or s.deleted or d is None or s.reel_id not in vectors or not lifts:
                continue  # paid reels may have been boosted; deleted ones aren't shown
            transcript = d["transcript"] or {}
            out.append(
                Past(
                    reel_id=s.reel_id,
                    own=own,
                    vector=vectors[s.reel_id],
                    lifts=lifts,
                    features=dna_svc.features(
                        d["content"] or {}, d["production"] or {}, transcript, d["duration_s"]
                    ),
                    title=reel_title(d["caption"] or ""),
                    username=names[account_id],
                    posted_at=s.posted_at,
                    payoff_s=transcript.get("first_payoff_s"),
                )
            )
    out.sort(key=lambda p: p.reel_id)
    return out, series, all_lifts


def load(conn, creator_id: UUID) -> SimData:
    now = clock.now()
    creator = conn.execute(
        """
        select c.id, c.account_id, c.timezone, c.accuracy, a.username
          from public.creators c join public.accounts a on a.id = c.account_id where c.id = %s
        """,
        (creator_id,),
    ).fetchone()
    account_id = creator["account_id"]
    tz = ZoneInfo(creator["timezone"])
    own, own_series, own_lifts = _pasts(conn, [account_id], True, {account_id: creator["username"]})

    series = own_series[account_id]
    newest = sorted((s for s in series if not s.paid), key=lambda s: s.posted_at, reverse=True)
    history = [own_lifts[s.reel_id] for s in newest if own_lifts.get(s.reel_id)][:HISTORY]
    baselines = compute_baselines(series)
    baselines_7d = {
        m: (b.median if (b := baselines.get((m, "7d"))) and b.n >= MIN_BASELINE_N else None)
        for m in LIFT_METRICS
    }
    posts = [
        (s.posted_at.astimezone(tz), own_lifts[s.reel_id]["views"])
        for s in series
        if not s.paid and "views" in own_lifts.get(s.reel_id, {})
    ]
    cards = [
        Card(r["id"], r["feature"], r["value"], r["metric"], float(r["effect"]), r["n"], r["scope"])
        for r in conn.execute(
            """
            select id::text, feature, value, metric, effect, n, scope from public.pattern_cards
             where account_id = %s order by abs(ln(effect)) desc, feature, value, metric
            """,
            (account_id,),
        ).fetchall()
    ]
    return SimData(
        creator_id=creator_id,
        account_id=account_id,
        username=creator["username"],
        timezone=creator["timezone"],
        now=now,
        own=own,
        history=history,
        cards=cards,
        baselines_7d=baselines_7d,
        posts=posts,
        widen=float((creator["accuracy"] or {}).get("widen") or 1.0),
    )
