"""POST /v1/reels/refresh: pull to refresh on Home.

v2 (PLAN_V2 §4.2) removed Home's carousel (GET /v1/reels) and the Insights page
(GET /v1/reels/{id}/insights) from the app API. The per-reel data still feeds the Simulator's
calibration, Ask Curo and the learning jobs."""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from curo import clock
from curo.auth import User, current_user
from curo.db import creator_session
from curo.jobs.collect import REFRESH_MIN_AGE_H
from curo.queue import enqueue
from curo.routes.deps import require_creator
from curo.schemas.api import RefreshOut

router = APIRouter(prefix="/v1/reels", tags=["reels"])


@router.post("/refresh", response_model=RefreshOut)
def refresh(user: User = Depends(current_user)):
    """Pull to refresh: a new snapshot only if the last one is older than 3 hours."""
    with creator_session(user.id) as conn:
        creator = require_creator(conn)
        last = None
        if creator["account_id"]:
            last = conn.execute(
                """
                select max(m.taken_at) as last from public.metric_snapshots m
                  join public.reels r on r.id = m.reel_id where r.account_id = %s
                """,
                (creator["account_id"],),
            ).fetchone()["last"]
    now = clock.now()
    if creator["account_id"] is None or (last and now - last < timedelta(hours=REFRESH_MIN_AGE_H)):
        return RefreshOut(status="fresh", last_snapshot_at=last)
    job_id = enqueue(
        "snapshot_account",
        {"account_id": str(creator["account_id"]), "refresh": True},
        creator_id=creator["id"],
        idempotency_key=f"refresh:{creator['account_id']}:{now:%Y%m%dT%H}",
    )
    return JSONResponse(
        RefreshOut(status="queued", job_id=job_id, last_snapshot_at=last).model_dump(mode="json"),
        status_code=status.HTTP_202_ACCEPTED,
    )
