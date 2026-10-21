"""The Simulator's AI audience (v2, PLAN_V2 §4.5): personas, calibration and one run.

* ``ensure_personas``: once per creator a month — T17 splits the audience into 4–8 segments
  from their comment themes (never handles), T18 writes SIM_AGENTS personas across them.
* ``ensure_calibration``: once per persona version — 200 agents watch 5 of the creator's past
  reels (their stored T1 understanding); the agents' rates against the real ones give k_m.
* ``run_audience``: SIM_AGENTS agents watch the new video in batches (T19), the engaged ones
  read the top comments (T20), and the result is predicted, scored and explained (T21).

Every AI text a creator reads goes through the number validator; agent comments carry no
numbers at all. Nothing branches on MOCK_MODE: the provider factory picks the model.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from curo import clock, providers
from curo.config import get_settings
from curo.db import service_connection
from curo.jobs.hashtags import creator_niche
from curo.schemas.tasks import (
    T17,
    T18,
    T19,
    T20,
    T21,
    AgentBrief,
    AudienceTheme,
    Reaction,
    Segment,
    T17Input,
    T18Input,
    T19Input,
    T20Input,
    T21Input,
    ThreadComment,
    TimedPoint,
    Timeline,
)
from curo.services import agents as crowd
from curo.services import validator

CALIBRATION_AGENTS = 200
CALIBRATION_REELS = 5
THREAD_COMMENTS = 10
FEED_COMMENTS = 30


def version_now() -> str:
    return f"{clock.now():%Y-%m}"


# ------------------------------------------------------------------ personas


def ensure_personas(creator_id: UUID) -> str:
    """The creator's persona version for this month, built if missing."""
    version = version_now()
    with service_connection() as conn:
        have = conn.execute(
            "select count(*) as n from public.audience_personas where creator_id = %s and version = %s",
            (creator_id, version),
        ).fetchone()["n"]
        if have:
            return version
        creator = conn.execute(
            """
            select c.account_id, a.followers from public.creators c
              join public.accounts a on a.id = c.account_id where c.id = %s
            """,
            (creator_id,),
        ).fetchone()
        themes = (
            conn.execute(
                """
                select t.label, t.share,
                       array(select c.text from public.comments c
                              where c.id = any(t.sample_comment_ids) limit 3) as samples
                  from public.comment_themes t where t.account_id = %s
                 order by t.share desc, t.label limit 12
                """,
                (creator["account_id"],),
            ).fetchall()
            if creator
            else []
        )
        langs = (
            conn.execute(
                """
                select c.language, count(*) as n from public.comments c
                  join public.reels r on r.id = c.reel_id
                 where r.account_id = %s and c.language is not null and not c.is_creator
                 group by c.language
                """,
                (creator["account_id"],),
            ).fetchall()
            if creator
            else []
        )
        niche = creator_niche(conn, creator["account_id"]) if creator else "lifestyle"
    total = sum(x["n"] for x in langs) or 1
    llm = providers.get_llm()
    seg_out = llm.run(
        T17,
        T17Input(
            niche=niche,
            themes=[
                AudienceTheme(
                    key=f"theme{i}",
                    label=t["label"],
                    share=float(t["share"]),
                    samples=[s for s in (t["samples"] or [])][:3],
                )
                for i, t in enumerate(themes)
            ],
            language_mix={x["language"]: round(x["n"] / total, 2) for x in langs},
            followers=creator["followers"] if creator else None,
        ),
    )
    n = get_settings().sim_agents
    counts = crowd.allocate(seg_out.segments, n)
    rows, next_no = [], 1
    for seg in seg_out.segments:
        out = llm.run(
            T18, T18Input(segment=seg, niche=niche, count=counts[seg.key], first_agent_no=next_no)
        )
        for p in out.personas[: counts[seg.key]]:
            rows.append((seg, p))
        next_no += counts[seg.key]
    with service_connection() as conn:
        for seg in seg_out.segments:
            conn.execute(
                """
                insert into public.audience_segments
                  (creator_id, version, key, label, share, description, interests)
                values (%s, %s, %s, %s, %s, %s, %s)
                on conflict (creator_id, version, key) do nothing
                """,
                (
                    creator_id,
                    version,
                    seg.key,
                    seg.label,
                    seg.share,
                    seg.description,
                    seg.interests,
                ),
            )
        with conn.cursor() as cur:
            cur.executemany(
                """
                insert into public.audience_personas
                  (creator_id, version, agent_no, segment, persona_text, traits)
                values (%s, %s, %s, %s, %s, %s) on conflict do nothing
                """,
                [
                    (
                        creator_id,
                        version,
                        p.agent_no,
                        seg.key,
                        p.persona_text,
                        Jsonb(
                            {
                                "patience": p.patience,
                                "liker": p.liker,
                                "commenter": p.commenter,
                                "sharer": p.sharer,
                                "saver": p.saver,
                            }
                        ),
                    )
                    for seg, p in rows
                ],
            )
    return version


def load_agents(conn, creator_id: UUID, version: str) -> tuple[list[AgentBrief], dict[str, str]]:
    segs = {
        s["key"]: s
        for s in conn.execute(
            "select * from public.audience_segments where creator_id = %s and version = %s",
            (creator_id, version),
        ).fetchall()
    }
    agents = [
        AgentBrief(
            agent_no=p["agent_no"],
            segment=p["segment"],
            segment_label=segs[p["segment"]]["label"] if p["segment"] in segs else p["segment"],
            persona_text=p["persona_text"],
            interests=list(segs[p["segment"]]["interests"]) if p["segment"] in segs else [],
            **{k: float(v) for k, v in p["traits"].items()},
        )
        for p in conn.execute(
            """
            select agent_no, segment, persona_text, traits from public.audience_personas
             where creator_id = %s and version = %s order by agent_no
            """,
            (creator_id, version),
        ).fetchall()
    ]
    return agents, {k: s["label"] for k, s in segs.items()}


def segments(conn, creator_id: UUID, version: str) -> list[Segment]:
    return [
        Segment(
            key=s["key"],
            label=s["label"],
            share=float(s["share"]),
            description=s["description"],
            interests=list(s["interests"]),
        )
        for s in conn.execute(
            """
            select * from public.audience_segments where creator_id = %s and version = %s
             order by share desc, key
            """,
            (creator_id, version),
        ).fetchall()
    ]


def react(run_key: str, tl: Timeline, agents: list[AgentBrief]) -> list[Reaction]:
    """T19 in batches of SIM_AGENT_BATCH; an agent the model left out is left out."""
    llm, size = providers.get_llm(), get_settings().sim_agent_batch
    known = {a.agent_no for a in agents}
    out: list[Reaction] = []
    for i in range(0, len(agents), size):
        batch = agents[i : i + size]
        res = llm.run(T19, T19Input(run_key=run_key, timeline=tl, agents=batch))
        out += [r for r in res.reactions if r.agent_no in known]
    seen: set[int] = set()
    return [r for r in out if not (r.agent_no in seen or seen.add(r.agent_no))]


# ------------------------------------------------------------------ calibration


def past_reels(conn, account_id: UUID) -> list[dict]:
    """The creator's past reels with their latest public counts (missing stays missing)."""
    return [
        dict(r)
        for r in conn.execute(
            """
            select r.id, r.caption, d.transcript, s.views, s.likes, s.comments, s.shares
              from public.reels r
              left join public.reel_dna d on d.reel_id = r.id
              join lateral (
                select views, likes, comments, shares from public.metric_snapshots m
                 where m.reel_id = r.id and not m.flagged order by m.taken_at desc limit 1
              ) s on true
             where r.account_id = %s and not r.is_deleted and not coalesce(r.is_paid_partnership, false)
             order by r.posted_at desc, r.id
            """,
            (account_id,),
        ).fetchall()
    ]


def real_rates(r: dict, usual_views: float | None) -> dict[str, float | None]:
    views = r["views"]
    out: dict[str, float | None] = {
        "views": (views / usual_views) if views and usual_views else None
    }
    for m in ("likes", "comments", "shares"):
        out[m] = (r[m] / views) if views and r[m] is not None else None
    return out


def past_engagement(reels: list[dict]) -> list[float]:
    out = []
    for r in reels:
        rates = real_rates(r, None)
        e = crowd.engagement(rates)
        if e is not None:
            out.append(e)
    return out


def ensure_calibration(
    creator_id: UUID, version: str, usual_views: float | None
) -> dict[str, crowd.Factor]:
    with service_connection() as conn:
        rows = conn.execute(
            "select * from public.persona_calibrations where creator_id = %s and version = %s",
            (creator_id, version),
        ).fetchall()
        if rows:
            return {
                r["metric"]: crowd.Factor(
                    r["metric"],
                    float(r["factor"]) if r["factor"] is not None else None,
                    float(r["low"]) if r["low"] is not None else None,
                    float(r["high"]) if r["high"] is not None else None,
                    r["n"],
                )
                for r in rows
            }
        account_id = conn.execute(
            "select account_id from public.creators where id = %s", (creator_id,)
        ).fetchone()["account_id"]
        agents, _ = load_agents(conn, creator_id, version)
        reels = [r for r in past_reels(conn, account_id) if r["transcript"]][:CALIBRATION_REELS]
    # A spread of the audience: every fifth agent, up to 200.
    step = max(1, len(agents) // CALIBRATION_AGENTS)
    sample = agents[::step][:CALIBRATION_AGENTS]
    pairs: dict[str, list[tuple[float | None, float | None]]] = {m: [] for m in crowd.METRICS}
    for r in reels:
        tl = crowd.timeline(r["transcript"], r["caption"] or "")
        got = crowd.rates(react(f"calibrate:{creator_id}:{version}:{r['id']}", tl, sample))
        real = real_rates(r, usual_views)
        for m in crowd.METRICS:
            pairs[m].append((real[m], got.rate(m)))
    factors = crowd.calibrate(pairs)
    with service_connection() as conn:
        for f in factors.values():
            conn.execute(
                """
                insert into public.persona_calibrations
                  (creator_id, version, metric, factor, low, high, n)
                values (%s, %s, %s, %s, %s, %s, %s) on conflict do nothing
                """,
                (creator_id, version, f.metric, f.k, f.low, f.high, f.n),
            )
    return factors


# ------------------------------------------------------------------ one run


def run_audience(
    simulation_id: UUID,
    creator_id: UUID,
    t1,
    caption: str,
    duration_s: float | None,
    usual_views: float | None,
    progress=None,
) -> dict[str, Any]:
    if progress:
        progress(step="audience")
    version = ensure_personas(creator_id)
    factors = ensure_calibration(creator_id, version, usual_views)
    with service_connection() as conn:
        agents, labels = load_agents(conn, creator_id, version)
        account_id = conn.execute(
            "select account_id from public.creators where id = %s", (creator_id,)
        ).fetchone()["account_id"]
        past_e = past_engagement(past_reels(conn, account_id))
        segs = segments(conn, creator_id, version)
    tl = crowd.timeline(t1, caption, duration_s)
    if progress:
        progress(step="agents")
    reactions = react(str(simulation_id), tl, agents)
    segment_of = {a.agent_no: a.segment for a in agents}
    brief = {a.agent_no: a for a in agents}

    # The thread round: engaged agents read the top comments.
    commented = [r for r in reactions if r.commented and r.comment_text]
    threads: dict[int, list[dict]] = {}
    likes_on: dict[int, int] = {}
    if commented:
        top = commented[:THREAD_COMMENTS]
        engaged = [brief[r.agent_no] for r in reactions if r.liked and not r.skipped][:100]
        res = providers.get_llm().run(
            T20,
            T20Input(
                run_key=str(simulation_id),
                timeline=tl,
                comments=[ThreadComment(agent_no=r.agent_no, text=r.comment_text) for r in top],
                agents=engaged,
            ),
        )
        on = {r.agent_no for r in top}
        for a in res.actions:
            if a.reply_to not in on:
                continue
            if a.liked:
                likes_on[a.reply_to] = likes_on.get(a.reply_to, 0) + 1
            if a.reply_text:
                threads.setdefault(a.reply_to, []).append(
                    {
                        "agent_no": a.agent_no,
                        "segment": labels.get(segment_of.get(a.agent_no, ""), ""),
                        "text": a.reply_text,
                    }
                )

    got = crowd.rates(reactions)
    curve = crowd.skip_curve(reactions, tl.duration_s)
    preds = crowd.predict(got, factors, usual_views)
    calibrated = {p.metric: p.rate for p in preds}
    e = crowd.engagement(calibrated)
    score = crowd.engagement_score(e, past_e)
    fact_lines = crowd.facts(got, curve, reactions, tl, labels, segment_of)
    explain = explain_run(fact_lines, tl.duration_s)

    feed = sorted(commented, key=lambda r: (-likes_on.get(r.agent_no, 0), r.agent_no))
    comments = [
        {
            "agent_no": r.agent_no,
            "segment": labels.get(segment_of[r.agent_no], segment_of[r.agent_no]),
            "text": r.comment_text,
            "likes": likes_on.get(r.agent_no, 0),
            "replies": threads.get(r.agent_no, []),
        }
        for r in feed[:FEED_COMMENTS]
    ]
    with service_connection() as conn:
        conn.execute(
            "delete from public.simulation_agents where simulation_id = %s", (simulation_id,)
        )
        with conn.cursor() as cur:
            cur.executemany(
                """
                insert into public.simulation_agents (simulation_id, agent_no, segment, reaction, thread)
                values (%s, %s, %s, %s, %s)
                """,
                [
                    (
                        simulation_id,
                        r.agent_no,
                        segment_of[r.agent_no],
                        Jsonb(r.model_dump()),
                        Jsonb(threads.get(r.agent_no, [])),
                    )
                    for r in reactions
                ],
            )
    return {
        "persona_version": version,
        "timeline": tl.model_dump(),
        "agents": got.n,
        "watched": got.watched,
        "counts": {
            "likes": got.likes,
            "comments": got.comments,
            "shares": got.shares,
            "saves": got.saves,
        },
        "segments": [
            {"key": s.key, "label": s.label, "share": s.share, "description": s.description}
            for s in segs
        ],
        "predictions": [
            {
                "metric": p.metric,
                "rate": _r(p.rate),
                "low": _r(p.low),
                "high": _r(p.high),
                "count": p.count,
                "count_low": p.count_low,
                "count_high": p.count_high,
                "simulated": p.simulated,
            }
            for p in preds
        ],
        "calibration": {m: {"factor": _r(f.k), "reels": f.n} for m, f in sorted(factors.items())},
        "engagement": _r(e),
        "engagement_score": score,
        "past_reels_scored": len(past_e),
        "skip_curve": curve,
        "explain": explain,
        "comments": comments,
        "label": "Simulated by CURO's AI audience. Not real comments.",
    }


def _r(x: float | None) -> float | None:
    return None if x is None else round(x, 5)


def explain_run(fact_lines: list[str], duration_s: float | None) -> dict[str, list[dict]]:
    """T21, with the number check on every point; a failed point falls back to the fact."""
    plain = [f.split("] ", 1)[1] if "] " in f else f for f in fact_lines]
    try:
        out = providers.get_llm().run(T21, T21Input(facts=fact_lines[:40], duration_s=duration_s))
    except Exception:
        out = crowd.template_explanation(fact_lines)

    def clean(points: list[TimedPoint]) -> list[dict]:
        kept = []
        for p in points:
            text, _src = validator.checked(lambda p=p: p.text, plain, lambda: "")
            if text:
                kept.append({"text": text, "at_s": p.at_s})
        return kept

    return {
        "working": clean(out.working),
        "holding": clean(out.holding),
        "edits": clean(out.edits),
    }
