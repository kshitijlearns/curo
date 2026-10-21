"""Home's cards and the Insights screen, assembled from the Reel Record (logic doc §6–7).

Everything is read inside the creator's RLS session. Baselines are computed from the same
snapshots on each request (cheap, and always as current as the last snapshot); the stored
``baselines`` rows serve the background jobs.
"""

from __future__ import annotations

import contextlib
import hashlib
import itertools
import json
import logging
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from curo import providers
from curo.redis_client import get_redis
from curo.schemas.api import (
    AudienceCard,
    MetricChanges,
    PhaseOut,
    PublicMetrics,
    ReelCard,
    ReelInsights,
    TimelinePoint,
    TopCommentOut,
)
from curo.schemas.tasks import T10, T10Input
from curo.services import audience, phases, validator
from curo.services.arrows import arrows_for, baseline_n
from curo.services.metrics import Baseline, ReelSeries, compute_baselines, count_at, reel_lifts
from curo.services.records import load_series
from curo.services.text import reel_title
from curo.services.top_comment import top_comment

log = logging.getLogger("curo.insights")

SEEN_LATE_H = 48.0
THIN_BASELINE = 20
EXPLANATION_TTL_S = 7 * 24 * 3600


def tone_for(shortcode: str) -> int:
    return int(hashlib.md5(shortcode.encode()).hexdigest(), 16) % 4


@dataclass
class AccountData:
    account_id: UUID
    followers: int | None
    rows: dict[str, dict[str, Any]]  # reel id → reel row
    series: dict[str, ReelSeries]
    baselines: dict[tuple[str, str], Baseline]
    predictions: dict[str, dict[str, float]]  # reel id → simulated 7-day values

    def seen_late(self, reel_id: str) -> bool:
        r = self.rows[reel_id]
        return (r["first_seen_at"] - r["posted_at"]).total_seconds() / 3600 > SEEN_LATE_H


def load_account(conn, account_id: UUID) -> AccountData:
    account = conn.execute(
        "select followers from public.accounts where id = %s", (account_id,)
    ).fetchone()
    rows = {
        str(r["id"]): r
        for r in conn.execute(
            "select * from public.reels where account_id = %s", (account_id,)
        ).fetchall()
    }
    series = {s.reel_id: s for s in load_series(conn, [account_id])[account_id]}
    # Simulations linked to a posted reel give the expected values (Phase 7 fills them).
    predictions: dict[str, dict[str, float]] = {}
    for s in conn.execute(
        """
        select posted_reel_id, predicted from public.simulations
         where posted_reel_id = any(%s) and status = 'done' and predicted is not null
         order by created_at
        """,
        (list(rows),),
    ).fetchall():
        predicted = s["predicted"] or {}
        predictions[str(s["posted_reel_id"])] = {
            m: v["mid"] for m, v in predicted.items() if isinstance(v, dict) and v.get("mid")
        }
    return AccountData(
        account_id=account_id,
        followers=account["followers"] if account else None,
        rows=rows,
        series=series,
        baselines=compute_baselines(list(series.values())),
        predictions=predictions,
    )


# --------------------------------------------------------------------------- Home cards


def reel_card(data: AccountData, reel_id: str) -> ReelCard:
    r, s = data.rows[reel_id], data.series[reel_id]
    latest = s.snaps[-1] if s.snaps else None
    metrics = PublicMetrics(
        views=latest.views if latest else None,
        likes=latest.likes if latest else None,
        comments=latest.comments if latest else None,
        shares=latest.shares if latest else None,
    )
    changes, compared = MetricChanges(), None
    if latest is not None:
        arrows = arrows_for(
            metrics.model_dump(), latest.age_h, data.baselines, data.predictions.get(reel_id)
        )
        changes = MetricChanges(**{m: a.percent for m, a in arrows.items()})
        if arrows:
            compared = (
                "simulation"
                if any(a.compared_with == "simulation" for a in arrows.values())
                else "usual"
            )
    return ReelCard(
        id=r["id"],
        shortcode=r["shortcode"],
        permalink=r["permalink"],
        title=reel_title(r["caption"]),
        posted_at=r["posted_at"],
        duration_s=float(r["duration_s"]) if r["duration_s"] is not None else None,
        tone=tone_for(r["shortcode"]),
        metrics=metrics,
        changes=changes,
        compared_with=compared,
        last_snapshot_at=r["posted_at"] + timedelta(hours=latest.age_h) if latest else None,
        snapshots=len(s.snaps),
        seen_late=data.seen_late(reel_id),
        likes_hidden=r["likes_hidden"],
        comments_disabled=r["comments_disabled"],
        is_paid_partnership=r["is_paid_partnership"],
    )


def latest_cards(data: AccountData, limit: int) -> list[ReelCard]:
    live = sorted(
        (r for r in data.rows.values() if not r["is_deleted"]),
        key=lambda r: r["posted_at"],
        reverse=True,
    )[:limit]
    return [reel_card(data, str(r["id"])) for r in live]


# --------------------------------------------------------------------------- phase


def phase_for(data: AccountData, reel_id: str) -> tuple[PhaseOut | None, list[str]]:
    s = data.series[reel_id]
    notes: list[str] = []
    tracked = [
        x
        for rid, x in data.series.items()
        if not data.seen_late(rid) and len(x.snaps) >= 2 and not x.paid
    ]
    stats = phases.phase_stats([phases.timeline(x.snaps, data.followers, True) for x in tracked])
    late = data.seen_late(reel_id)
    tl = phases.timeline(s.snaps, data.followers, from_posting=not late)
    current = None if late else (tl[-1][2] if tl else None)
    estimated = current is None
    if current is None:
        if not s.snaps:
            return None, notes
        current = phases.estimate_by_age(stats, s.age_now_h)
        if len(s.snaps) == 1:
            notes.append("Phase estimated from one snapshot.")
        else:
            days = max(
                1,
                round((data.rows[reel_id]["first_seen_at"] - s.posted_at).total_seconds() / 86400),
            )
            notes.append(
                f"Curo first saw this reel {days} day{'s' if days != 1 else ''} after it was posted, "
                "so its phase is estimated from its age."
            )
    views = s.snaps[-1].views if s.snaps else None
    return (
        PhaseOut(
            id=current,
            label=phases.LABELS[current],
            description=phases.description(current, views, data.followers),
            usual_range=phases.usual_range(stats, current),
            estimated=estimated,
            views_per_follower=round(views / data.followers, 2)
            if views and data.followers
            else None,
            timeline=[
                TimelinePoint(age_h=round(a, 2), velocity=round(v, 2), phase=p) for a, v, p in tl
            ],
        ),
        notes,
    )


# --------------------------------------------------------------------------- audience


def follower_jump(conn, data: AccountData, reel_id: str) -> tuple[float | None, bool]:
    """Follower growth in the 2 days after posting ÷ the usual rate, and whether this reel
    brought most of the creator's new views in that time."""
    s = data.series[reel_id]
    if s.age_now_h < 48:
        return None, False
    snaps = conn.execute(
        """
        select taken_at, followers from public.account_snapshots
         where account_id = %s and followers is not null order by taken_at
        """,
        (data.account_id,),
    ).fetchall()
    if len(snaps) < 3:
        return None, False
    start, end = s.posted_at, s.posted_at + timedelta(hours=48)

    def followers_at(t: datetime) -> float | None:
        for a, b in itertools.pairwise(snaps):
            if a["taken_at"] <= t <= b["taken_at"]:
                span = (b["taken_at"] - a["taken_at"]).total_seconds()
                k = (t - a["taken_at"]).total_seconds() / span if span else 1.0
                return a["followers"] + (b["followers"] - a["followers"]) * k
        return None

    f0, f1 = followers_at(start), followers_at(end)
    rates = [
        (b["followers"] - a["followers"]) / ((b["taken_at"] - a["taken_at"]).total_seconds() / 3600)
        for a, b in itertools.pairwise(snaps)
        if b["taken_at"] > a["taken_at"] and not (start <= b["taken_at"] and a["taken_at"] <= end)
    ]
    usual = sorted(rates)[len(rates) // 2] if rates else None
    if f0 is None or f1 is None or not usual or usual <= 0:
        return None, False
    ratio = ((f1 - f0) / 48) / usual
    gains = {}
    for rid, x in data.series.items():
        a0, a1 = (
            (start - x.posted_at).total_seconds() / 3600,
            (end - x.posted_at).total_seconds() / 3600,
        )
        if a1 <= 0:
            continue
        v1 = count_at(x.snaps, "views", a1)
        v0 = 0.0 if a0 <= 0 else count_at(x.snaps, "views", a0)
        if v0 is not None and v1 is not None:
            gains[rid] = v1 - v0
    total = sum(gains.values())
    return round(ratio, 1), bool(total) and gains.get(reel_id, 0) / total >= 0.5


def evidence_for(conn, data: AccountData, reel_id: str) -> tuple[audience.Evidence, list[dict]]:
    comments = conn.execute(
        """
        select c.text, c.like_count, c.reply_count, c.is_creator, c.is_bot, c.sentiment, c.intent,
               c.tags_friend, c.theme_key, t.label as theme_label
          from public.comments c left join public.comment_themes t on t.id = c.theme_id
         where c.reel_id = %s
        """,
        (reel_id,),
    ).fetchall()
    labelled = [c for c in comments if c["intent"] and not c["is_bot"] and not c["is_creator"]]
    themes = Counter(c["theme_label"] for c in labelled if c["theme_label"])
    dna = conn.execute(
        "select production, transcript from public.reel_dna where reel_id = %s", (reel_id,)
    ).fetchone()
    ratio, most = follower_jump(conn, data, reel_id)
    ev = audience.Evidence(
        comments=len(labelled),
        intents=dict(Counter(c["intent"] for c in labelled)),
        tags=sum(1 for c in labelled if c["tags_friend"] or c["intent"] == "tags_friend"),
        part_two=sum(1 for c in labelled if c["theme_key"] == "wants a part 2"),
        top_theme=themes.most_common(1)[0] if themes else None,
        ending=dna["production"].get("ending") if dna else None,
        cta=dna["production"].get("cta_type") if dna else None,
        payoff_s=(dna["transcript"] or {}).get("first_payoff_s") if dna else None,
        follower_ratio=ratio,
        brought_most_views=most,
    )
    for key in ("ending", "cta"):
        if getattr(ev, key) == "unknown":
            setattr(ev, key, None)
    return ev, comments


def explain(card: audience.Card) -> str:
    """One plain sentence from T10, checked for new numbers, cached by its facts."""
    llm = providers.get_llm()
    key = (
        "curo:t10:"
        + hashlib.sha1(json.dumps([card.key, card.facts, llm.version(T10)]).encode()).hexdigest()
    )
    try:
        cached = get_redis().get(key)
        if cached:
            return cached.decode() if isinstance(cached, bytes) else cached
    except Exception:  # the cache is a convenience
        log.warning("explanation cache unavailable", exc_info=True)

    def write() -> str:
        return llm.run(T10, T10Input(kind=card.key, title=card.title, facts=card.facts)).text

    text, source = validator.checked(write, card.facts, lambda: audience.template_sentence(card))
    if source == "template":
        log.info("T10 added a number for %s; using the template sentence", card.key)
    with contextlib.suppress(Exception):  # the cache is a convenience
        get_redis().set(key, text, ex=EXPLANATION_TTL_S)
    return text


# --------------------------------------------------------------------------- the screen


def reel_insights(conn, account_id: UUID, reel_id: UUID) -> ReelInsights | None:
    data = load_account(conn, account_id)
    rid = str(reel_id)
    if rid not in data.rows or data.rows[rid]["is_deleted"]:
        return None
    card = reel_card(data, rid)
    phase, notes = phase_for(data, rid)

    lifts_all = {
        x.reel_id: reel_lifts(x, data.baselines) for x in data.series.values() if not x.paid
    }
    own = reel_lifts(data.series[rid], data.baselines)
    history = {
        m: [lifts[m].lift for r, lifts in lifts_all.items() if r != rid and m in lifts]
        for m in ("comment_rate", "share_rate", "like_rate")
    }
    ev, comments = evidence_for(conn, data, rid)
    cards = audience.select_cards({m: v.lift for m, v in own.items()}, history, ev)
    processed = conn.execute(
        "select exists(select 1 from public.reel_dna where reel_id = %s) as yes", (rid,)
    ).fetchone()["yes"]

    s = data.series[rid]
    if s.snaps:
        n = baseline_n(data.baselines, "views", s.snaps[-1].age_h)
        if n < 3:
            notes.append("Not enough of your reels at this age to compare with yet.")
        elif n < THIN_BASELINE:
            notes.append(f"Compared with {n} of your reels at this age so far.")
    if not processed:
        notes.append("Curo is still watching this reel; more reasons appear once it has.")

    top = top_comment(comments)
    return ReelInsights(
        reel=card,
        phase=phase,
        audience=[
            AudienceCard(
                key=c.key, icon=c.icon, title=c.title, text=explain(c), facts=c.facts, z=c.z
            )
            for c in cards
        ],
        top_comment=TopCommentOut(**top.__dict__) if top else None,
        notes=notes,
        processed=processed,
    )
