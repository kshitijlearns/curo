"""After posting (logic doc §15, the learning loop; MVP doc §9 jobs).

``match_posted_reel``: when a snapshot finds a new reel of the creator's, suggest which
simulation or draft it came from; the creator confirms (or not) on Home.

``accuracy_report`` (weekly): for confirmed reels seven days old, compare the counts at day 7
with the stored estimate, and update the creator's accuracy record (which also widens future
ranges when estimates keep missing).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from curo import clock, events, providers
from curo.db import service_connection
from curo.jobs import JobContext, job
from curo.queue import enqueue
from curo.services import accuracy, matching
from curo.services.metrics import count_at
from curo.services.records import load_series
from curo.services.text import reel_title


def queue_match(reel_id: UUID, creator_id: UUID) -> None:
    enqueue(
        "match_posted_reel",
        {"reel_id": str(reel_id)},
        creator_id=creator_id,
        idempotency_key=f"match:{reel_id}",
    )


def _caption_of(conn, simulation: dict | None, project_id) -> str:
    if simulation and simulation["caption"]:
        return simulation["caption"]
    if project_id:
        caps = conn.execute(
            """
            select options, chosen from public.captions where project_id = %s
             order by version desc limit 1
            """,
            (project_id,),
        ).fetchone()
        if caps and caps["chosen"] is not None and caps["options"]:
            return caps["options"][min(caps["chosen"], len(caps["options"]) - 1)]["text"]
    return ""


@job("match_posted_reel")
def match_posted_reel(ctx: JobContext) -> dict[str, Any]:
    reel_id = UUID(str(ctx.payload["reel_id"]))
    with service_connection() as conn:
        reel = conn.execute(
            """
            select r.id, r.caption, r.duration_s, r.posted_at, c.id as creator_id
              from public.reels r join public.creators c on c.account_id = r.account_id
             where r.id = %s
            """,
            (reel_id,),
        ).fetchone()
        if reel is None:
            return {"skipped": "not a creator's reel"}
        if conn.execute(
            "select 1 from public.reel_matches where reel_id = %s", (reel_id,)
        ).fetchone():
            return {"skipped": "already matched"}
        since = reel["posted_at"] - timedelta(days=matching.WINDOW_DAYS)
        sims = conn.execute(
            """
            select id, project_id, caption, video_meta, created_at from public.simulations
             where creator_id = %s and status = 'done' and posted_reel_id is null
               and created_at between %s and %s
               and not exists (select 1 from public.reel_matches m
                                where m.simulation_id = simulations.id and m.status <> 'rejected')
            """,
            (reel["creator_id"], since, reel["posted_at"]),
        ).fetchall()
        drafts = conn.execute(
            """
            select p.id, p.updated_at from public.projects p
             where p.creator_id = %s and p.posted_reel_id is null and p.status in ('active', 'saved')
               and p.updated_at between %s and %s
               and not exists (select 1 from public.simulations s where s.project_id = p.id)
               and not exists (select 1 from public.reel_matches m
                                where m.project_id = p.id and m.status <> 'rejected')
            """,
            (reel["creator_id"], since, reel["posted_at"]),
        ).fetchall()
        captions = [_caption_of(conn, s, s["project_id"]) for s in sims] + [
            _caption_of(conn, None, d["id"]) for d in drafts
        ]
    texts = [reel_title(reel["caption"] or ""), *(reel_title(c) for c in captions)]
    vectors = providers.get_embedding().embed([t or "-" for t in texts])
    reel_vec, cand_vecs = vectors[0], vectors[1:]
    candidates = [
        matching.Candidate(
            str(s["id"]),
            str(s["project_id"]) if s["project_id"] else None,
            v if c else None,
            (s["video_meta"] or {}).get("duration_s"),
            s["created_at"],
        )
        for s, c, v in zip(sims, captions[: len(sims)], cand_vecs[: len(sims)], strict=True)
    ] + [
        matching.Candidate(None, str(d["id"]), v if c else None, None, d["updated_at"])
        for d, c, v in zip(drafts, captions[len(sims) :], cand_vecs[len(sims) :], strict=True)
    ]
    found = matching.best(
        reel_vec if reel["caption"] else None,
        float(reel["duration_s"]) if reel["duration_s"] is not None else None,
        reel["posted_at"],
        candidates,
    )
    if found is None:
        return {"matched": None, "candidates": len(candidates)}
    with service_connection() as conn:
        row = conn.execute(
            """
            insert into public.reel_matches
              (creator_id, reel_id, simulation_id, project_id, score, reasons, created_at)
            values (%s, %s, %s, %s, %s, %s, %s)
            on conflict (reel_id) do nothing returning id
            """,
            (
                reel["creator_id"],
                reel_id,
                found.candidate.simulation_id,
                found.candidate.project_id,
                found.score,
                Jsonb(found.reasons),
                clock.now(),
            ),
        ).fetchone()
    return {"matched": str(row["id"]) if row else None, "score": found.score}


def confirm(conn, match: dict) -> None:
    """The creator said yes: the reel is the simulated (or drafted) one."""
    now = clock.now()
    conn.execute(
        "update public.reel_matches set status = 'confirmed', decided_at = %s where id = %s",
        (now, match["id"]),
    )
    if match["simulation_id"]:
        conn.execute(
            "update public.simulations set posted_reel_id = %s where id = %s",
            (match["reel_id"], match["simulation_id"]),
        )
    if match["project_id"]:
        conn.execute(
            """
            update public.projects set posted_reel_id = %s, status = 'posted', updated_at = %s
             where id = %s
            """,
            (match["reel_id"], now, match["project_id"]),
        )


# ====================================================================== accuracy_report


@job("accuracy_report")
def accuracy_report(ctx: JobContext) -> dict[str, Any]:
    with service_connection() as conn:
        creators = conn.execute(
            """
            select id, account_id from public.creators
             where account_id is not null and (%s::uuid is null or id = %s::uuid)
            """,
            (ctx.payload.get("creator_id"), ctx.payload.get("creator_id")),
        ).fetchall()
    checked = 0
    for c in creators:
        checked += _report(c["id"], c["account_id"])
    return {"creators": len(creators), "checked": checked}


def _report(creator_id: UUID, account_id: UUID) -> int:
    now = clock.now()
    with service_connection() as conn:
        sims = conn.execute(
            """
            select id, posted_reel_id, predicted from public.simulations
             where creator_id = %s and posted_reel_id is not null and in_range is null
               and predicted is not null and predicted <> '{}'::jsonb
            """,
            (creator_id,),
        ).fetchall()
        series = {s.reel_id: s for s in load_series(conn, [account_id])[account_id]}
    checked = 0
    for sim in sims:
        s = series.get(str(sim["posted_reel_id"]))
        if s is None or s.age_now_h < accuracy.SEVEN_DAYS_H:
            continue  # not a week old yet
        actual = {m: count_at(s.snaps, m, accuracy.SEVEN_DAYS_H) for m in accuracy.COUNTS}
        in_range, detail = accuracy.check(sim["predicted"], actual)
        if in_range is None:
            continue
        with service_connection() as conn:
            conn.execute(
                "update public.simulations set actual = %s, in_range = %s where id = %s",
                (Jsonb(detail), in_range, sim["id"]),
            )
            events.record(conn, creator_id, "estimate_checked", {"in_range": in_range})
        checked += 1
    with service_connection() as conn:
        results = [
            r["in_range"]
            for r in conn.execute(
                """
                select in_range from public.simulations
                 where creator_id = %s and in_range is not null order by created_at desc limit %s
                """,
                (creator_id, accuracy.RECORD),
            ).fetchall()
        ]
        conn.execute(
            "update public.creators set accuracy = %s where id = %s",
            (Jsonb({**accuracy.record(results), "updated_at": now.isoformat()}), creator_id),
        )
    return checked
