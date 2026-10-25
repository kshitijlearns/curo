"""The Simulator's AI audience (v2, PLAN_V2 §4.5; v2.2 §8): personas, calibration and one run.

* ``ensure_personas``: once per Follower Persona build — the 1,000 agents are drawn from the
  creator's 4 Follower Personas by share (T18 writes each agent as a variation of its persona;
  ``audience_personas.persona_id``). The personas replaced T17's segments.
* ``ensure_calibration``: once per agent version — 200 agents watch 5 of the creator's past
  reels (their stored T1 understanding); the agents' rates against the real ones give k_m,
  overall and per persona (a persona falls back to the overall factor without enough reels).
* ``run_audience``: SIM_AGENTS agents watch the new video in batches (T19), the engaged ones
  read the top comments (T20), the result is predicted, scored and explained (T21), and each
  persona's agents are summarised in "How each follower group reacted" with that persona's own
  opinion (T27 on its results).

Every AI text a creator reads goes through the number validator; agent comments carry no
numbers at all. Nothing branches on MOCK_MODE: the provider factory picks the model.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from curo import providers
from curo.config import get_settings
from curo.db import service_connection
from curo.jobs import personas as persona_jobs
from curo.jobs.hashtags import creator_niche
from curo.schemas.tasks import (
    T18,
    T19,
    T20,
    T21,
    AgentBrief,
    Reaction,
    Segment,
    T18Input,
    T19Input,
    T20Input,
    T21Input,
    ThreadComment,
    TimedPoint,
    Timeline,
)
from curo.services import agents as crowd
from curo.services import persona_reactions, validator
from curo.services import personas as P

CALIBRATION_AGENTS = 200
CALIBRATION_REELS = 5
MIN_PERSONA_REELS = 3  # past reels a persona needs for its own calibration factor
THREAD_COMMENTS = 10
FEED_COMMENTS = 30
TRAITS = ("patience", "liker", "commenter", "sharer", "saver")


# ------------------------------------------------------------------ personas → agents


def segment_key(persona_id: object) -> str:
    return "p" + str(persona_id).replace("-", "")[:12]


def persona_segment(row: dict) -> Segment:
    """A Follower Persona as the Simulator draws agents from it: its traits are the middle of
    its agents' range, from how its group engages (code)."""
    prof = row["profile"] or {}
    ev = prof.get("evidence") or {}
    intents = {
        i["intent"]: (i["share"] if i["share"] is not None else 0.6)
        for i in ev.get("intents") or []
    }
    lifts = ev.get("lifts") or {}
    positive = ev.get("positive")
    meter = ev.get("meter") or 3
    talk = sum(intents.get(k, 0) for k in ("question", "request", "thats_me", "disagreement"))
    traits = {
        "patience": P.clamp(0.35 + 0.08 * meter),
        "liker": P.clamp(0.35 + 0.45 * (positive if positive is not None else 0.6)),
        "commenter": P.clamp(0.15 + 0.6 * talk),
        "sharer": P.clamp(
            0.12
            + 0.7 * max(ev.get("tags_friend") or 0, intents.get("tags_friend", 0))
            + (0.1 if (lifts.get("shares") or 0) > 1.2 else 0)
        ),
        "saver": P.clamp(0.12 + 0.7 * intents.get("plans_to_save", 0)),
    }
    interests = [*prof.get("comes_for", []), *prof.get("loves", [])]
    top = (ev.get("intents") or [{"intent": None}])[0]["intent"]
    return Segment(
        key=segment_key(row["id"]),
        label=row["short_name"][:40],
        share=max(0.0001, float(row["share"])),
        description=row["tagline"][:300],
        interests=[i[:60] for i in interests][:6],
        intent=top,
        traits={k: round(v, 3) for k, v in traits.items()},
    )


def ensure_personas(creator_id: UUID) -> str:
    """The agents' version for the creator's current Follower Personas, written if missing."""
    with service_connection() as conn:
        rows = persona_jobs.active(conn, creator_id)
        build = persona_jobs.latest_build(conn, creator_id)
    if len(rows) < P.K or build is None:
        persona_jobs.build_now(creator_id, "simulator")
        with service_connection() as conn:
            rows = persona_jobs.active(conn, creator_id)
            build = persona_jobs.latest_build(conn, creator_id)
    version = f"fp{build['version']}"
    with service_connection() as conn:
        have = conn.execute(
            "select count(*) as n from public.audience_personas where creator_id = %s and version = %s",
            (creator_id, version),
        ).fetchone()["n"]
        if have:
            return version
        account = conn.execute(
            "select account_id from public.creators where id = %s", (creator_id,)
        ).fetchone()
        niche = creator_niche(conn, account["account_id"]) if account else None
    segs = [persona_segment(r) for r in rows]
    persona_of = {segment_key(r["id"]): r["id"] for r in rows}
    llm = providers.get_llm()
    n = get_settings().sim_agents
    counts = crowd.allocate(segs, n)
    agents, next_no = [], 1
    for seg in segs:
        out = llm.run(
            T18,
            T18Input(
                segment=seg,
                niche=niche or "lifestyle",
                count=counts[seg.key],
                first_agent_no=next_no,
            ),
        )
        for p in out.personas[: counts[seg.key]]:
            agents.append((seg, p))
        next_no += counts[seg.key]
    with service_connection() as conn:
        for seg in segs:
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
                  (creator_id, version, agent_no, segment, persona_text, traits, persona_id)
                values (%s, %s, %s, %s, %s, %s, %s) on conflict do nothing
                """,
                [
                    (
                        creator_id,
                        version,
                        p.agent_no,
                        seg.key,
                        p.persona_text,
                        Jsonb({k: getattr(p, k) for k in TRAITS}),
                        persona_of[seg.key],
                    )
                    for seg, p in agents
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
            intent=p["intent"],
            persona_id=str(p["persona_id"]) if p["persona_id"] else None,
            **{k: float(v) for k, v in p["traits"].items()},
        )
        for p in conn.execute(
            """
            select a.agent_no, a.segment, a.persona_text, a.traits, a.persona_id,
                   f.profile->'evidence'->'intents'->0->>'intent' as intent
              from public.audience_personas a
              left join public.follower_personas f on f.id = a.persona_id
             where a.creator_id = %s and a.version = %s order by a.agent_no
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


def _factor(r: dict) -> crowd.Factor:
    return crowd.Factor(
        r["metric"],
        float(r["factor"]) if r["factor"] is not None else None,
        float(r["low"]) if r["low"] is not None else None,
        float(r["high"]) if r["high"] is not None else None,
        r["n"],
    )


def ensure_calibration(
    creator_id: UUID, version: str, usual_views: float | None
) -> dict[str, dict[str, crowd.Factor]]:
    """Factors per segment ('' = overall, the fallback) and metric."""
    with service_connection() as conn:
        rows = conn.execute(
            "select * from public.persona_calibrations where creator_id = %s and version = %s",
            (creator_id, version),
        ).fetchall()
        if rows:
            out: dict[str, dict[str, crowd.Factor]] = {}
            for r in rows:
                out.setdefault(r["segment"], {})[r["metric"]] = _factor(r)
            return out
        account_id = conn.execute(
            "select account_id from public.creators where id = %s", (creator_id,)
        ).fetchone()["account_id"]
        agents, _ = load_agents(conn, creator_id, version)
        reels = [r for r in past_reels(conn, account_id) if r["transcript"]][:CALIBRATION_REELS]
    # A spread of the audience: every fifth agent, up to 200 (each persona in proportion).
    step = max(1, len(agents) // CALIBRATION_AGENTS)
    sample = agents[::step][:CALIBRATION_AGENTS]
    seg_of = {a.agent_no: a.segment for a in sample}
    keys = sorted({a.segment for a in sample})
    pairs: dict[str, dict[str, list]] = {k: {m: [] for m in crowd.METRICS} for k in ["", *keys]}
    for r in reels:
        tl = crowd.timeline(r["transcript"], r["caption"] or "")
        got_all = react(f"calibrate:{creator_id}:{version}:{r['id']}", tl, sample)
        real = real_rates(r, usual_views)
        for k in ["", *keys]:
            got = crowd.rates([x for x in got_all if not k or seg_of.get(x.agent_no) == k])
            for m in crowd.METRICS:
                pairs[k][m].append((real[m], got.rate(m)))
    factors = {k: crowd.calibrate(v) for k, v in pairs.items()}
    with service_connection() as conn:
        for k, fs in factors.items():
            for f in fs.values():
                conn.execute(
                    """
                    insert into public.persona_calibrations
                      (creator_id, version, segment, metric, factor, low, high, n)
                    values (%s, %s, %s, %s, %s, %s, %s, %s) on conflict do nothing
                    """,
                    (creator_id, version, k, f.metric, f.k, f.low, f.high, f.n),
                )
    return factors


def factors_for(factors: dict[str, dict[str, crowd.Factor]], key: str) -> dict[str, crowd.Factor]:
    """A persona's own factor per metric where it has enough past reels, else the overall."""
    overall = factors.get("", {})
    own = factors.get(key, {})
    return {
        m: own[m] if m in own and own[m].k is not None and own[m].n >= MIN_PERSONA_REELS else f
        for m, f in overall.items()
    }


# ------------------------------------------------------------------ "How each follower group reacted"


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{round(100 * x)}%"


def group_results(
    reactions: list[Reaction],
    agents: list[AgentBrief],
    tl: Timeline,
    factors: dict[str, dict[str, crowd.Factor]],
    personas: list[dict],
) -> list[dict]:
    """One row per persona: its agents' watched-to-end share and calibrated rates (saves are
    simulated), a mood from its engagement against the whole audience, and a takeaway."""
    seg_of = {a.agent_no: a.segment for a in agents}
    duration = tl.duration_s or max((r.watch_until_s for r in reactions), default=0) or 1
    overall = crowd.rates(reactions)
    overall_pred = {p.metric: p.rate for p in crowd.predict(overall, factors.get("", {}), None)}
    overall_e = crowd.engagement(overall_pred)
    out = []
    for row in personas:
        key = segment_key(row["id"])
        mine = [r for r in reactions if seg_of.get(r.agent_no) == key]
        if not mine:
            continue
        got = crowd.rates(mine)
        own = factors_for(factors, key)
        preds = {p.metric: p for p in crowd.predict(got, own, None)}
        rates = {m: preds[m].rate for m in ("likes", "comments", "shares", "saves")}
        to_end = sum(1 for r in mine if not r.skipped and r.watch_until_s >= 0.9 * duration) / len(
            mine
        )
        e = crowd.engagement(rates)
        ratio = (e / overall_e) if e is not None and overall_e else None
        if ratio is None:
            mood = "neutral"
        else:
            mood = (
                "love"
                if ratio >= 1.15
                else "like"
                if ratio >= 0.95
                else "unsure"
                if ratio >= 0.75
                else "skip"
            )
        early = sum(1 for r in mine if r.skipped) / len(mine)
        if mood == "love":
            takeaway = f"Your strongest group for this reel: {_pct(to_end)} watched to the end."
        elif mood == "like":
            takeaway = f"On board: {_pct(to_end)} watched to the end."
        elif tl.payoff_s and tl.payoff_s > 2:
            takeaway = (
                f"{_pct(early)} scrolled on early; the result only shows at {tl.payoff_s:g} s."
            )
        else:
            takeaway = f"Less into this one: {_pct(early)} scrolled on early."
        out.append(
            {
                "persona_id": str(row["id"]),
                "name": row["name"],
                "short_name": row["short_name"],
                "color": row["color"],
                "avatar_seed": row["avatar_seed"],
                "share": float(row["share"]),
                "agents": len(mine),
                "watched_to_end": round(to_end, 4),
                "rates": {m: (None if v is None else round(v, 5)) for m, v in rates.items()},
                "saves_simulated": True,
                "calibration": "own"
                if any(own[m] is not factors.get("", {}).get(m) for m in own)
                else "overall",
                "mood": mood,
                "takeaway": takeaway,
                "facts": [
                    f"{_pct(to_end)} of this group's agents watched to the end.",
                    f"{_pct(early)} of this group's agents scrolled on early.",
                    *(
                        f"Simulated {m} rate in this group: {_pct(v)}."
                        for m, v in rates.items()
                        if v is not None
                    ),
                ],
            }
        )
    return out


def persona_opinions(
    creator_id: UUID, simulation_id: UUID, groups: list[dict], personas: list[dict], idea: str
) -> None:
    """Each persona's own take on its simulated results (T27, cached per simulation)."""
    by_id = {g["persona_id"]: g for g in groups}
    rows = [r for r in personas if str(r["id"]) in by_id]
    if not rows:
        return
    draft = "\n".join(
        f"{by_id[str(r['id'])]['name']}: " + " ".join(by_id[str(r["id"])]["facts"]) for r in rows
    )
    target = persona_reactions.Target(
        type="simulation", id=simulation_id, version=1, idea=idea, draft=draft
    )
    opinions = persona_reactions.react(creator_id, rows, target, "personas")
    by_persona = {str(o["persona_id"]): o for o in opinions}
    for g in groups:
        o = by_persona.get(g["persona_id"])
        if o:
            g["opinion"] = {
                "reaction": o["reaction"],
                "reaction_label": P.REACTION_WORDS[o["reaction"]],
                "opinion": o["opinion"],
                "win_them_over": o["win_them_over"],
            }


def studio_compare(project_id: UUID | None, groups: list[dict]) -> list[str]:
    """ "In Studio, the Budget Stylist was unsure; in the simulation, 61% of them watched to the
    end." — from the project's newest persona reactions."""
    if project_id is None:
        return []
    with service_connection() as conn:
        rows = conn.execute(
            """
            select distinct on (o.persona_id) o.persona_id, o.reaction
              from public.persona_opinions o
             where o.project_id = %s and o.target_type <> 'simulation'
             order by o.persona_id, o.created_at desc
            """,
            (project_id,),
        ).fetchall()
    said = {str(r["persona_id"]): r["reaction"] for r in rows}
    words = {
        "watch_all": "loved it",
        "watch": "was in",
        "scroll_past": "was unsure",
        "skip": "would skip it",
    }
    out = []
    for g in groups:
        if g["persona_id"] in said:
            g["studio_reaction"] = said[g["persona_id"]]
            out.append(
                f"In Studio, {g['name']} {words[said[g['persona_id']]]}; in the simulation, "
                f"{_pct(g['watched_to_end'])} of them watched to the end."
            )
    return out


# ------------------------------------------------------------------ one run


def run_audience(
    simulation_id: UUID,
    creator_id: UUID,
    t1,
    caption: str,
    duration_s: float | None,
    usual_views: float | None,
    progress=None,
    project_id: UUID | None = None,
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
        personas = conn.execute(
            """
            select f.* from public.follower_personas f
             where f.id in (select a.persona_id from public.audience_personas a
                             where a.creator_id = %s and a.version = %s)
             order by f.slot
            """,
            (creator_id, version),
        ).fetchall()
    colour_of = {segment_key(r["id"]): r["color"] for r in personas}
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
                seg = segment_of.get(a.agent_no, "")
                threads.setdefault(a.reply_to, []).append(
                    {
                        "agent_no": a.agent_no,
                        "segment": labels.get(seg, ""),
                        "color": colour_of.get(seg),
                        "text": a.reply_text,
                    }
                )

    got = crowd.rates(reactions)
    curve = crowd.skip_curve(reactions, tl.duration_s)
    overall = factors.get("", {})
    preds = crowd.predict(got, overall, usual_views)
    calibrated = {p.metric: p.rate for p in preds}
    e = crowd.engagement(calibrated)
    score = crowd.engagement_score(e, past_e)
    fact_lines = crowd.facts(got, curve, reactions, tl, labels, segment_of)
    explain = explain_run(fact_lines, tl.duration_s)
    groups = group_results(reactions, agents, tl, factors, personas)
    idea = caption or "This reel"
    try:
        persona_opinions(creator_id, simulation_id, groups, personas, idea)
    except Exception:  # the run's numbers stand without the personas' words
        import logging

        logging.getLogger("curo.personas").exception("simulation persona opinions failed")
    compare = studio_compare(project_id, groups)
    for g in groups:
        g.pop("facts", None)

    feed = sorted(commented, key=lambda r: (-likes_on.get(r.agent_no, 0), r.agent_no))
    comments = [
        {
            "agent_no": r.agent_no,
            "segment": labels.get(segment_of[r.agent_no], segment_of[r.agent_no]),
            "color": colour_of.get(segment_of[r.agent_no]),
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
        "personas": groups,
        "studio_compare": compare,
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
        "calibration": {m: {"factor": _r(f.k), "reels": f.n} for m, f in sorted(overall.items())},
        "engagement": _r(e),
        "engagement_score": score,
        "past_reels_scored": len(past_e),
        "skip_curve": curve,
        "explain": explain,
        "comments": comments,
        "label": "Simulated by CURO's AI audience. Not real comments.",
        "persona_label": P.LABEL,
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
