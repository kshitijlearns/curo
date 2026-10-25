"""build_recap (v2.1 §3.8): load a period's data, build the Creator Recap, write its lines.

Steps: compute facts (services/recap.py) → choose slides → T23 writes the copy in one call →
every line is checked by the no-new-numbers validator (one retry, then the template line) →
store. The first recap ("your story so far") is enqueued by onboarding as soon as the newest
reels and their comments are in; the monthly one by the scheduler for the previous calendar
month in the creator's time zone. Recaps are free on every plan.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from psycopg.types.json import Jsonb

from curo import clock, providers
from curo.db import service_connection
from curo.jobs import JobContext, JobFailed, job
from curo.jobs.hashtags import creator_niche
from curo.queue import enqueue
from curo.schemas.tasks import T23, RecapSlideIn, T23Input
from curo.services import recap as R
from curo.services import recap_config as C
from curo.services import validator
from curo.services.text import reel_title

VERSION = "recap-v1"


# ------------------------------------------------------------------ periods


def first_period(today: date, earliest: date | None) -> tuple[date, date]:
    start = today - timedelta(days=C.FIRST_RECAP_DAYS - 1)
    if earliest and earliest > start:
        start = earliest
    return start, today


def previous_month(today: date) -> tuple[date, date]:
    first_this = today.replace(day=1)
    end = first_this - timedelta(days=1)
    return end.replace(day=1), end


# ------------------------------------------------------------------ loading


def _reels(conn, account_id: UUID, tz: ZoneInfo) -> list[R.Reel]:
    rows = conn.execute(
        """
        select r.id, r.caption, r.hashtags, r.audio_name, r.posted_at, r.is_paid_partnership,
               s.views, s.likes, s.comments, s.shares, d.content, d.production
          from public.reels r
          left join public.reel_dna d on d.reel_id = r.id
          left join lateral (
            select views, likes, comments, shares from public.metric_snapshots m
             where m.reel_id = r.id and not m.flagged order by m.taken_at desc limit 1
          ) s on true
         where r.account_id = %s and not r.is_deleted
         order by r.posted_at, r.id
        """,
        (account_id,),
    ).fetchall()
    out = []
    for r in rows:
        dna = None
        if r["content"] or r["production"]:
            dna = {**(r["content"] or {}), **(r["production"] or {})}
        out.append(
            R.Reel(
                id=str(r["id"]),
                title=reel_title(r["caption"] or "") or "Untitled reel",
                posted=r["posted_at"].astimezone(tz),
                views=r["views"],
                likes=r["likes"],
                comments=r["comments"],
                shares=r["shares"],
                caption=r["caption"] or "",
                hashtags=list(r["hashtags"] or []),
                audio_name=r["audio_name"],
                paid=r["is_paid_partnership"],
                dna=dna,
            )
        )
    return out


def load(conn, creator_id: UUID, kind: str, period: tuple[date, date] | None) -> R.RecapInput:
    c = conn.execute(
        """
        select c.id, c.account_id, c.timezone, c.ig_username, a.username, a.followers, a.posts
          from public.creators c left join public.accounts a on a.id = c.account_id
         where c.id = %s
        """,
        (creator_id,),
    ).fetchone()
    if c is None or c["account_id"] is None:
        raise JobFailed("This creator has no Instagram account collected yet.")
    tz = ZoneInfo(c["timezone"] or "Asia/Kolkata")
    today = clock.now().astimezone(tz).date()
    history = _reels(conn, c["account_id"], tz)
    if period is None:
        earliest = min((r.posted.date() for r in history), default=None)
        period = first_period(today, earliest) if kind == "first" else previous_month(today)
    start, end = period
    reels = [r for r in history if start <= r.posted.date() <= end]
    ids = [UUID(r.id) for r in reels]
    comments = (
        conn.execute(
            """
            select text, like_count, language from public.comments
             where reel_id = any(%s) and not is_creator and not coalesce(is_bot, false)
            """,
            (ids,),
        ).fetchall()
        if ids
        else []
    )
    themes = conn.execute(
        "select label, share, n from public.comment_themes where account_id = %s",
        (c["account_id"],),
    ).fetchall()
    groups = conn.execute(
        """
        select label, (lifts->'views'->>'lift')::float as lift, coalesce(array_length(reel_ids, 1), 0) as n
          from public.subclusters where account_id = %s
        """,
        (c["account_id"],),
    ).fetchall()
    cards = conn.execute(
        """
        select feature, value, metric, effect, n from public.pattern_cards
         where account_id = %s and scope = 'yours'
        """,
        (c["account_id"],),
    ).fetchall()
    follower_start = follower_end = views_older = None
    previous = None
    if kind == "monthly":
        lo = datetime.combine(start, datetime.min.time(), tz)
        hi = datetime.combine(end + timedelta(days=1), datetime.min.time(), tz)
        snaps = conn.execute(
            """
            select followers from public.account_snapshots
             where account_id = %s and taken_at >= %s and taken_at < %s and followers is not null
             order by taken_at
            """,
            (c["account_id"], lo, hi),
        ).fetchall()
        if len(snaps) >= 2:
            follower_start, follower_end = snaps[0]["followers"], snaps[-1]["followers"]
        older = conn.execute(
            """
            select sum(g) as gained from (
              select max(m.views) - min(m.views) as g
                from public.metric_snapshots m join public.reels r on r.id = m.reel_id
               where r.account_id = %s and r.posted_at < %s
                 and m.taken_at >= %s and m.taken_at < %s and m.views is not null
                 and not m.flagged
               group by m.reel_id having count(*) >= 2
            ) x
            """,
            (c["account_id"], lo, lo, hi),
        ).fetchone()
        views_older = int(older["gained"]) if older and older["gained"] else None
        prev = conn.execute(
            """
            select facts from public.recaps
             where creator_id = %s and kind = 'monthly' and status = 'ready' and period_start < %s
             order by period_start desc limit 1
            """,
            (creator_id, start),
        ).fetchone()
        if prev:
            pf = prev["facts"] or {}
            previous = {
                "views": (pf.get("views_total") or {}).get("views"),
                "reels": (pf.get("posting") or {}).get("reels"),
            }
    opportunities = conn.execute(
        "select count(*) as n from public.opportunities where creator_id = %s and status in ('active', 'saved')",
        (creator_id,),
    ).fetchone()["n"]
    personas, previous_shares = _personas(conn, creator_id, kind, start)
    niche = creator_niche(conn, c["account_id"])
    trend_tags: set[str] = set()
    if niche:
        for t in conn.execute(
            "select hashtags from public.trend_cards where niche = %s", (niche,)
        ).fetchall():
            trend_tags |= {h.lower() for h in t["hashtags"]}
    return R.RecapInput(
        kind=kind,
        period_start=start,
        period_end=end,
        handle=c["username"] or c["ig_username"],
        followers=c["followers"],
        total_posts=c["posts"],
        reels=reels,
        history=history,
        comments=[R.Comment(x["text"], x["like_count"], x["language"]) for x in comments],
        themes=[R.Theme(t["label"], float(t["share"]), t["n"]) for t in themes],
        groups=[R.Group(g["label"], g["lift"], g["n"]) for g in groups],
        cards=[
            R.Card(k["feature"], k["value"], k["metric"], float(k["effect"]), k["n"]) for k in cards
        ],
        follower_start=follower_start,
        follower_end=follower_end,
        views_older_gained=views_older,
        previous=previous,
        opportunities=opportunities,
        trend_tags=trend_tags,
        today=today,
        personas=personas,
        persona_previous=previous_shares,
    )


def _personas(conn, creator_id: UUID, kind: str, start: date) -> tuple[list[dict], dict | None]:
    """The 4 personas for "Meet your followers", and (monthly) each one's share last month."""
    rows = conn.execute(
        """
        select id, name, short_name, tagline, share, color, avatar_seed, is_starter, profile,
               thought
          from public.follower_personas
         where creator_id = %s and retired_at is null order by slot
        """,
        (creator_id,),
    ).fetchall()
    if len(rows) != 4:
        return [], None
    out = []
    for r in rows:
        prof = r["profile"] or {}
        out.append(
            {
                "id": str(r["id"]),
                "name": r["name"],
                "short_name": r["short_name"],
                "tagline": r["tagline"],
                "share": float(r["share"]),
                "share_pct": int(
                    (prof.get("evidence") or {}).get("share_pct") or round(100 * float(r["share"]))
                ),
                "color": r["color"],
                "avatar_seed": r["avatar_seed"],
                "is_starter": r["is_starter"],
                "comes_for": prof.get("comes_for", []),
                "thought": (r["thought"] or {}).get("thought") or r["tagline"],
            }
        )
    previous = None
    if kind == "monthly":
        hist = conn.execute(
            """
            select persona_id, share from public.persona_history
             where creator_id = %s and period = %s
            """,
            (creator_id, start.replace(day=1)),
        ).fetchall()
        if hist:
            previous = {str(h["persona_id"]): float(h["share"]) for h in hist}
    return out, previous


# ------------------------------------------------------------------ copy


def write_copy(data: R.RecapInput, built: R.Recap) -> dict[str, dict]:
    """T23 in one call; each line checked against its slide's facts (retry once, then template)."""
    langs = [c.language for c in data.comments if c.language]
    main_lang = max(set(langs), key=langs.count) if langs else None
    period = built.facts["intro"]["period"]
    slides_in = [
        RecapSlideIn(
            slide_id=s,
            facts=(built.facts[s]["display"] or ["—"])[:8],
            data={k: v for k, v in built.facts[s].items() if k not in ("how",)},
        )
        for s in built.slides
    ]
    payload = T23Input(
        handle=data.handle, period=period, comment_language=main_lang, slides=slides_in
    )
    llm = providers.get_llm()
    out: dict[str, dict] = {}
    pending = set(built.slides)
    for attempt in ("model", "model_retry"):
        if not pending:
            break
        try:
            lines = {line.slide_id: line for line in llm.run(T23, payload).slides}
        except Exception:
            lines = {}
        for s in list(pending):
            line = lines.get(s)
            facts = [*built.facts[s]["display"], f"@{data.handle}", period]
            if line and not validator.new_numbers(f"{line.headline} {line.subline}", facts):
                out[s] = {"headline": line.headline, "subline": line.subline, "source": attempt}
                pending.discard(s)
    for s in pending:
        head, sub = R.template_copy(s, built.facts[s])
        out[s] = {"headline": head, "subline": sub, "source": "template"}
    return out


# ------------------------------------------------------------------ the job


def queue_recap(creator_id: UUID, kind: str, key: str | None = None) -> UUID:
    return enqueue(
        "build_recap",
        {"creator_id": str(creator_id), "kind": kind},
        creator_id=creator_id,
        idempotency_key=key or f"recap:{creator_id}:{kind}:{clock.now():%Y%m%d}",
    )


@job("build_recap")
def build_recap(ctx: JobContext) -> dict[str, Any]:
    creator_id = UUID(str(ctx.payload["creator_id"]))
    kind = ctx.payload.get("kind", "first")
    period = None
    if ctx.payload.get("period_start") and ctx.payload.get("period_end"):
        period = (
            date.fromisoformat(ctx.payload["period_start"]),
            date.fromisoformat(ctx.payload["period_end"]),
        )
    ctx.progress(step="recap", message="Building your recap")
    # v2.2: the personas first (a fast build for the first recap; this month's for a monthly).
    from curo.jobs.personas import ensure_for_recap

    ensure_for_recap(creator_id, kind)
    with service_connection() as conn:
        data = load(conn, creator_id, kind, period)
        if kind == "first":
            # One "your story so far" per creator: a rebuild replaces it.
            conn.execute(
                "delete from public.recaps where creator_id = %s and kind = 'first' and period_start <> %s",
                (creator_id, data.period_start),
            )
        row = conn.execute(
            """
            insert into public.recaps (creator_id, kind, period_start, period_end, status, version)
            values (%s, %s, %s, %s, 'building', %s)
            on conflict (creator_id, kind, period_start) do update set status = 'building',
              period_end = excluded.period_end, error = null
            returning id
            """,
            (creator_id, kind, data.period_start, data.period_end, VERSION),
        ).fetchone()
    recap_id = row["id"]
    try:
        built = R.build(data)
        copy = write_copy(data, built)
    except Exception as exc:
        with service_connection() as conn:
            conn.execute(
                "update public.recaps set status = 'failed', error = %s where id = %s",
                (str(exc)[:500], recap_id),
            )
        raise
    slides = [
        {
            "slide_id": s,
            "facts": {k: v for k, v in built.facts[s].items()},
            "copy": copy[s],
            "visual": built.visuals[s],
        }
        for s in built.slides
    ]
    facts = {s: f for s, f in built.facts.items() if f is not None}
    facts["stats"] = built.stats
    with service_connection() as conn:
        conn.execute(
            """
            update public.recaps set status = 'ready', facts = %s, slides = %s,
                   creator_level = %s, level_modifier = %s, archetype = %s,
                   archetype_runner_up = %s, archetype_evidence = %s, viewed_at = null
             where id = %s
            """,
            (
                Jsonb(facts),
                Jsonb(slides),
                built.level,
                built.modifier,
                built.archetype,
                built.runner_up,
                Jsonb(built.evidence),
                recap_id,
            ),
        )
    ctx.progress(step="recap_ready", message="Your recap is ready")
    return {"recap_id": str(recap_id), "slides": len(slides)}


def monthly_tick(now: datetime) -> list[str]:
    """On the 1st (or as soon as an active creator is back), last month's recap for every
    active creator who was already on CURO by then."""
    out = []
    with service_connection() as conn:
        creators = conn.execute(
            """
            select c.id, c.timezone, c.created_at from public.creators c
             where c.account_id is not null and c.paused_at is null
            """
        ).fetchall()
        for c in creators:
            today = now.astimezone(ZoneInfo(c["timezone"] or "Asia/Kolkata")).date()
            start, end = previous_month(today)
            if c["created_at"].date() > end:
                continue  # joined after that month: their first recap covers it
            have = conn.execute(
                """
                select 1 from public.recaps
                 where creator_id = %s and kind = 'monthly' and period_start = %s
                """,
                (c["id"], start),
            ).fetchone()
            if have:
                continue
            enqueue(
                "build_recap",
                {"creator_id": str(c["id"]), "kind": "monthly"},
                creator_id=c["id"],
                idempotency_key=f"recap:{c['id']}:monthly:{start:%Y-%m}",
            )
            out.append(f"build_recap:{c['id']}")
    return out
