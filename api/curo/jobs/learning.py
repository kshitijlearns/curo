"""recompute_learning (MVP doc §9; logic doc §5 steps 5, 7, 8): baselines, sub-clusters and
pattern cards. Runs once a batch of processed reels settles, and nightly (snapshots move
baselines). ``{"priors": true}`` rebuilds the cross-creator priors from all creators' own reels."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from curo import clock, providers
from curo.db import service_connection
from curo.jobs import JobContext, job
from curo.jobs.understand import vector_literal
from curo.queue import enqueue
from curo.schemas.tasks import T4, T4Input
from curo.services import dna as dna_svc
from curo.services import patterns, voice
from curo.services.assistant import memory
from curo.services.metrics import (
    AGE_BUCKETS,
    Baseline,
    Lift,
    ReelSeries,
    compute_baselines,
    reel_lifts,
)
from curo.services.records import load_dna, load_series, load_vectors
from curo.services.subclusters import find_groups, group_lifts, match_previous, nearest_to_centroid
from curo.services.text import reel_title


def mining_rows(
    series: list[ReelSeries], baselines: dict, dna_rows: dict[str, dict[str, Any]]
) -> tuple[list[patterns.Row], dict[str, dict[str, Lift]]]:
    """Reels with DNA and at least one lift, ready for pattern mining (paid excluded)."""
    rows: list[patterns.Row] = []
    lifts_by_reel: dict[str, dict[str, Lift]] = {}
    for s in series:
        lifts = reel_lifts(s, baselines)
        if lifts:
            lifts_by_reel[s.reel_id] = lifts
        d = dna_rows.get(s.reel_id)
        if s.paid or d is None or not lifts:
            continue
        feats = dna_svc.features(d["content"], d["production"], d["transcript"], d["duration_s"])
        rows.append(patterns.Row(s.reel_id, feats, {m: v.lift for m, v in lifts.items()}))
    return rows, lifts_by_reel


# --------------------------------------------------------------------------- steps


def save_baselines(conn, account_id: UUID, baselines: dict[tuple[str, str], Baseline]) -> None:
    now = clock.now()
    for (metric, bucket), b in baselines.items():
        conn.execute(
            """
            insert into public.baselines (account_id, metric, age_bucket, median, p25, p75, n, computed_at)
            values (%s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (account_id, metric, age_bucket) do update set
              median = excluded.median, p25 = excluded.p25, p75 = excluded.p75,
              n = excluded.n, computed_at = excluded.computed_at
            """,
            (account_id, metric, bucket, b.median, b.p25, b.p75, b.n, now),
        )


def save_subclusters(
    conn,
    account_id: UUID,
    vectors: dict[str, list[float]],
    lifts_by_reel: dict[str, dict[str, Lift]],
    titles: dict[str, str],
    paid: set[str],
) -> list[dict[str, Any]]:
    groups = find_groups(vectors)
    old = {
        str(r["id"]): [str(x) for x in r["reel_ids"]]
        for r in conn.execute(
            "select id, reel_ids from public.subclusters where account_id = %s", (account_id,)
        ).fetchall()
    }
    keep = match_previous([g.reel_ids for g in groups], old)
    llm = providers.get_llm()
    now = clock.now()
    saved = []
    for i, g in enumerate(groups):
        samples = [titles[r] for r in nearest_to_centroid(g, vectors) if titles.get(r)]
        label = llm.run(T4, T4Input(kind="reels", samples=samples or ["(untitled)"])).label
        lifts = group_lifts([r for r in g.reel_ids if r not in paid], lifts_by_reel)
        params = (label, vector_literal(g.centroid), g.reel_ids, Jsonb(lifts), now)
        if i in keep:
            conn.execute(
                """
                update public.subclusters set label = %s, centroid = %s::vector, reel_ids = %s::uuid[],
                       lifts = %s, computed_at = %s where id = %s
                """,
                (*params, keep[i]),
            )
            sid = keep[i]
        else:
            sid = conn.execute(
                """
                insert into public.subclusters (account_id, label, centroid, reel_ids, lifts, computed_at)
                values (%s, %s, %s::vector, %s::uuid[], %s, %s) returning id
                """,
                (account_id, *params),
            ).fetchone()["id"]
        saved.append(
            {
                "id": str(sid),
                "label": label,
                "n": len(g.reel_ids),
                "lifts": lifts,
                "reel_ids": g.reel_ids,
            }
        )
    stale = [sid for sid in old if sid not in keep.values()]
    if stale:
        conn.execute("delete from public.subclusters where id = any(%s::uuid[])", (stale,))
    return saved


def load_priors(conn) -> dict[tuple[str, str, str], patterns.Effect]:
    rows = conn.execute(
        "select * from public.pattern_cards where account_id is null and scope = 'similar_creators'"
    ).fetchall()
    out = {}
    for r in rows:
        ev = r["evidence"] or {}
        e = patterns.Effect(
            feature=r["feature"],
            value=r["value"],
            metric=r["metric"],
            n=r["n"],
            n_without=r["n_without"] or 0,
            effect=r["effect"],
            p_value=r["p_value"] if r["p_value"] is not None else 1.0,
            median_with=ev.get("median_lift_with") or 0.0,
            median_without=ev.get("median_lift_without") or 0.0,
        )
        e.q_value = ev.get("q_value", 1.0)
        out[e.key] = e
    return out


def save_cards(conn, account_id: UUID | None, cards: list[patterns.Card]) -> None:
    now = clock.now()
    for c in cards:
        conn.execute(
            """
            insert into public.pattern_cards
              (account_id, feature, value, metric, effect, creator_effect, prior_effect, n, n_without,
               p_value, confidence, scope, evidence, computed_at)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (account_id, feature, value, metric) do update set
              effect = excluded.effect, creator_effect = excluded.creator_effect,
              prior_effect = excluded.prior_effect, n = excluded.n, n_without = excluded.n_without,
              p_value = excluded.p_value, confidence = excluded.confidence, scope = excluded.scope,
              evidence = excluded.evidence, computed_at = excluded.computed_at
            """,
            (
                account_id,
                c.feature,
                c.value,
                c.metric,
                c.effect,
                c.creator_effect,
                c.prior_effect,
                c.n,
                c.n_without,
                c.p_value,
                c.confidence,
                c.scope,
                Jsonb(c.evidence),
                now,
            ),
        )
    # Cards that no longer hold are removed.
    keys = [[c.feature, c.value, c.metric] for c in cards]
    conn.execute(
        """
        delete from public.pattern_cards p
         where p.account_id is not distinct from %s
           and not exists (
             select 1 from jsonb_array_elements(%s::jsonb) k
              where k->>0 = p.feature and k->>1 = p.value and k->>2 = p.metric)
        """,
        (account_id, json.dumps(keys)),
    )


# --------------------------------------------------------------------------- the job


@job("recompute_learning")
def recompute_learning(ctx: JobContext) -> dict[str, Any]:
    if ctx.payload.get("priors"):
        return recompute_priors()
    account_id = UUID(str(ctx.payload["account_id"]))
    with service_connection() as conn:
        is_creator = conn.execute(
            "select exists(select 1 from public.creators where account_id = %s) as yes",
            (account_id,),
        ).fetchone()["yes"]
        series = load_series(conn, [account_id])[account_id]
        baselines = compute_baselines(series)
        save_baselines(conn, account_id, baselines)
    result: dict[str, Any] = {
        "reels": len(series),
        "baseline_n": {b: baselines[("views", b)].n for b in AGE_BUCKETS},
    }
    if not is_creator:
        return result

    with service_connection() as conn:
        dna_rows = load_dna(conn, [account_id])
        vectors = load_vectors(conn, account_id)
        rows, lifts_by_reel = mining_rows(series, baselines, dna_rows)
        titles = {rid: reel_title(d["caption"]) for rid, d in dna_rows.items()}
        paid = {s.reel_id for s in series if s.paid}
        groups = save_subclusters(conn, account_id, vectors, lifts_by_reel, titles, paid)
        priors = load_priors(conn)
        strata = {rid: g["id"] for g in groups for rid in g["reel_ids"]}
        own = patterns.effects(rows, strata=strata)
        counts = Counter((f, v) for r in rows for f, v in r.features.items())
        cards = patterns.build_cards(own, priors, counts)
        save_cards(conn, account_id, cards)
        # How the creator talks, from their transcripts (the Studio writes in it).
        profile = voice.profile(d["transcript"] for d in dna_rows.values())
        conn.execute(
            "update public.creators set voice_profile = %s where account_id = %s",
            (Jsonb(profile.model_dump()), account_id),
        )
        # Creator memory learned from behaviour (logic doc §14).
        creator = conn.execute(
            "select id from public.creators where account_id = %s", (account_id,)
        ).fetchone()
        learned = memory.save_learned(conn, creator["id"]) if creator else []
    from curo.jobs.follower_ideas import queue_follower_ideas

    queue_follower_ideas(account_id, f"learning:{ctx.job_id}")
    # A new creator shouldn't wait for the nightly run to see opportunity areas.
    with service_connection() as conn:
        fresh = conn.execute(
            """
            select c.id from public.creators c
             where c.account_id = %s
               and not exists (select 1 from public.opportunities o where o.creator_id = c.id)
            """,
            (account_id,),
        ).fetchall()
    for c in fresh:
        enqueue(
            "build_opportunities",
            {"creator_id": str(c["id"])},
            creator_id=c["id"],
            idempotency_key=f"opps:first:{c['id']}",
        )
    result.update(
        {
            "learned_memory": learned,
            "processed": len(dna_rows),
            "mined": len(rows),
            "subclusters": [{"label": g["label"], "n": g["n"]} for g in groups],
            "cards": {
                "yours": sum(c.scope == "yours" for c in cards),
                "similar_creators": sum(c.scope == "similar_creators" for c in cards),
            },
        }
    )
    return result


def recompute_priors() -> dict[str, Any]:
    """Cross-creator priors ("based on creators like you"), pooled from every CURO creator's own
    reels, each lift against its own account's baseline (v2: no peers). Stored with account_id
    NULL; a creator with few reels leans on them (cold start, PLAN_V2 §4.1)."""
    with service_connection() as conn:
        account_ids = [
            r["id"]
            for r in conn.execute(
                """
                select a.id from public.accounts a
                 where exists(select 1 from public.creators c where c.account_id = a.id)
                   and exists(select 1 from public.reel_dna d join public.reels r on r.id = d.reel_id
                              where r.account_id = a.id)
                """
            ).fetchall()
        ]
        if not account_ids:
            conn.execute("delete from public.pattern_cards where account_id is null")
            return {"accounts": 0, "priors": 0}
        all_series = load_series(conn, account_ids)
        dna_rows = load_dna(conn, account_ids)
    rows: list[patterns.Row] = []
    for account_id in account_ids:
        series = all_series[account_id]
        account_rows, _ = mining_rows(series, compute_baselines(series), dna_rows)
        rows += account_rows
    found = patterns.effects(rows)
    cards = [
        patterns.Card(
            feature=e.feature,
            value=e.value,
            metric=e.metric,
            effect=round(e.effect, 3),
            creator_effect=None,
            prior_effect=round(e.effect, 3),
            n=e.n,
            n_without=e.n_without,
            p_value=round(e.p_value, 4),
            confidence="high"
            if e.n >= 30 and e.q_value <= 0.01
            else "medium"
            if e.holds
            else "low",
            scope="similar_creators",
            evidence={
                "median_lift_with": round(e.median_with, 3),
                "median_lift_without": round(e.median_without, 3),
                "q_value": round(e.q_value, 4),
                "accounts": len(account_ids),
            },
        )
        for e in found
    ]
    with service_connection() as conn:
        save_cards(conn, None, cards)
    return {"accounts": len(account_ids), "reels": len(rows), "priors": len(cards)}
