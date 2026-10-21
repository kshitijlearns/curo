"""Posted reels CURO thinks came from a simulation or draft (logic doc §15 step 2: "asks the
creator to confirm the match"). Confirmed, Home's arrows compare the reel with its
simulation and the accuracy record counts it.

The MVP doc's endpoint list has no route for this; the confirmation it asks for needs one
(DECISIONS D108).
"""

from __future__ import annotations

from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status

from curo import clock, events
from curo.jobs.lifecycle import confirm
from curo.routes.deps import require_creator, rls_conn
from curo.schemas.api import ReelMatch
from curo.services.text import reel_title

router = APIRouter(prefix="/v1/matches", tags=["learning loop"])


def _out(conn: psycopg.Connection, m: dict) -> ReelMatch:
    reel = conn.execute(
        "select caption, posted_at from public.reels where id = %s", (m["reel_id"],)
    ).fetchone()
    title = None
    if m["project_id"]:
        p = conn.execute(
            "select title from public.projects where id = %s", (m["project_id"],)
        ).fetchone()
        title = p["title"] if p else None
    score = None
    if m["simulation_id"]:
        s = conn.execute(
            "select score from public.simulations where id = %s", (m["simulation_id"],)
        ).fetchone()
        score = s["score"] if s else None
    return ReelMatch(
        id=m["id"],
        reel_id=m["reel_id"],
        reel_title=reel_title(reel["caption"] or "") if reel else "",
        posted_at=reel["posted_at"] if reel else None,
        simulation_id=m["simulation_id"],
        simulation_score=score,
        project_id=m["project_id"],
        project_title=title,
        reasons=m["reasons"] or [],
        status=m["status"],
    )


def _own(conn: psycopg.Connection, match_id: UUID) -> dict:
    m = conn.execute("select * from public.reel_matches where id = %s", (match_id,)).fetchone()
    if m is None:  # RLS: someone else's reads as missing
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Match not found")
    return m


@router.get("", response_model=list[ReelMatch])
def pending(conn: psycopg.Connection = Depends(rls_conn)) -> list[ReelMatch]:
    require_creator(conn)
    rows = conn.execute(
        "select * from public.reel_matches where status = 'pending' order by created_at desc"
    ).fetchall()
    return [_out(conn, m) for m in rows]


@router.post("/{match_id}/confirm", response_model=ReelMatch)
def confirm_match(match_id: UUID, conn: psycopg.Connection = Depends(rls_conn)) -> ReelMatch:
    creator = require_creator(conn)
    m = _own(conn, match_id)
    if m["status"] != "confirmed":
        confirm(conn, m)
        events.record(conn, creator["id"], "match_confirmed", {"match_id": str(match_id)})
    return _out(conn, _own(conn, match_id))


@router.post("/{match_id}/reject", response_model=ReelMatch)
def reject_match(match_id: UUID, conn: psycopg.Connection = Depends(rls_conn)) -> ReelMatch:
    creator = require_creator(conn)
    m = _own(conn, match_id)
    if m["status"] == "pending":
        conn.execute(
            "update public.reel_matches set status = 'rejected', decided_at = %s where id = %s",
            (clock.now(), match_id),
        )
        events.record(conn, creator["id"], "match_rejected", {"match_id": str(match_id)})
    return _out(conn, _own(conn, match_id))
