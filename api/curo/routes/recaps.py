"""The Creator Recap (v2.1; v2.2 adds the "Meet your followers" slides).

``GET /v1/recaps/latest`` (null while there is none), ``GET /v1/recaps``,
``GET /v1/recaps/{id}``, ``POST /v1/recaps/{id}/viewed``, ``GET /v1/recaps/{id}/share-image``
(a 1080×1920 SVG; the web app makes the PNG).
"""

from __future__ import annotations

from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Response, status

from curo import clock
from curo.config import get_settings
from curo.routes.deps import require_creator, rls_conn
from curo.schemas.api import Recap, RecapSummary
from curo.services import recap_share

router = APIRouter(tags=["recap"])


def _label(row: dict) -> str:
    if row["kind"] == "first":
        return "Your story so far"
    return row["period_start"].strftime("%B %Y")


def _summary(row: dict) -> dict:
    facts = row["facts"] or {}
    return {
        "id": row["id"],
        "kind": row["kind"],
        "period_start": row["period_start"],
        "period_end": row["period_end"],
        "period_label": _label(row),
        "status": row["status"],
        "creator_level": row["creator_level"],
        "level_modifier": row["level_modifier"],
        "archetype": row["archetype"],
        "archetype_runner_up": row["archetype_runner_up"],
        "stats": facts.get("stats") or [],
        "viewed_at": row["viewed_at"],
        "is_new": row["status"] == "ready" and row["viewed_at"] is None,
        "created_at": row["created_at"],
    }


def _own(conn: psycopg.Connection, recap_id: UUID) -> dict:
    row = conn.execute("select * from public.recaps where id = %s", (recap_id,)).fetchone()
    if row is None:  # RLS: someone else's recap reads as missing
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recap not found")
    return row


def _full(conn: psycopg.Connection, row: dict) -> Recap:
    handle = conn.execute(
        """
        select a.username from public.creators c join public.accounts a on a.id = c.account_id
         where c.id = %s
        """,
        (row["creator_id"],),
    ).fetchone()
    return Recap(
        **_summary(row),
        handle=handle["username"] if handle else None,
        slides=row["slides"] or [],
        archetype_evidence=row["archetype_evidence"] or {},
    )


@router.get("/v1/recaps/latest", response_model=Recap | None)
def latest(conn: psycopg.Connection = Depends(rls_conn)) -> Recap | None:
    """The newest recap (ready or still building), or null before the first one."""
    require_creator(conn)
    row = conn.execute(
        """
        select * from public.recaps where status <> 'failed'
         order by (status = 'ready') desc, period_end desc, created_at desc limit 1
        """
    ).fetchone()
    return _full(conn, row) if row else None


@router.get("/v1/recaps", response_model=list[RecapSummary])
def all_recaps(conn: psycopg.Connection = Depends(rls_conn)) -> list[RecapSummary]:
    require_creator(conn)
    rows = conn.execute(
        "select * from public.recaps where status = 'ready' order by period_end desc, created_at desc"
    ).fetchall()
    return [RecapSummary(**_summary(r)) for r in rows]


@router.get("/v1/recaps/{recap_id}", response_model=Recap)
def one(recap_id: UUID, conn: psycopg.Connection = Depends(rls_conn)) -> Recap:
    require_creator(conn)
    return _full(conn, _own(conn, recap_id))


@router.post("/v1/recaps/{recap_id}/viewed", response_model=RecapSummary)
def viewed(recap_id: UUID, conn: psycopg.Connection = Depends(rls_conn)) -> RecapSummary:
    require_creator(conn)
    _own(conn, recap_id)
    row = conn.execute(
        """
        update public.recaps set viewed_at = coalesce(viewed_at, %s) where id = %s returning *
        """,
        (clock.now(), recap_id),
    ).fetchone()
    return RecapSummary(**_summary(row))


@router.get(
    "/v1/recaps/{recap_id}/share-image",
    response_class=Response,
    responses={200: {"content": {"image/svg+xml": {}}, "description": "1080×1920 share card"}},
)
def share_image(recap_id: UUID, conn: psycopg.Connection = Depends(rls_conn)) -> Response:
    require_creator(conn)
    full = _full(conn, _own(conn, recap_id))
    if full.status != "ready":
        raise HTTPException(status.HTTP_409_CONFLICT, "This recap is still being built")
    body = recap_share.svg(
        full.handle or "",
        full.period_label,
        [s.model_dump() for s in full.stats],
        full.creator_level,
        full.level_modifier,
        full.archetype,
        get_settings().web_url,
        next((s.facts.get("personas") for s in full.slides if s.slide_id == "share_card"), None),
    )
    return Response(
        body, media_type="image/svg+xml", headers={"Cache-Control": "private, max-age=300"}
    )
