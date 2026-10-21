"""Username onboarding (logic doc §3): POST /v1/onboarding/username, GET /v1/onboarding/status."""

from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends, status

from curo import clock
from curo.auth import User, current_user
from curo.db import creator_session
from curo.queue import enqueue
from curo.routes.deps import rls_conn
from curo.schemas.api import JobOut, OnboardingStarted, OnboardingStatus, UsernameIn

router = APIRouter(prefix="/v1/onboarding", tags=["onboarding"])


@router.post("/username", status_code=status.HTTP_202_ACCEPTED, response_model=OnboardingStarted)
def start(body: UsernameIn, user: User = Depends(current_user)) -> OnboardingStarted:
    """Start collecting a public handle. Never asks for an Instagram login."""
    # Commit the creator row first, so the job can see it.
    with creator_session(user.id) as conn:
        creator = conn.execute(
            """
            insert into public.creators as c (user_id, ig_username) values (auth.uid(), %s)
            on conflict (user_id) do update set ig_username = excluded.ig_username,
              account_id = case when c.ig_username = excluded.ig_username then c.account_id end
            returning id
            """,
            (body.username,),
        ).fetchone()
    now = clock.now()
    job_id = enqueue(
        "onboard_public",
        {"username": body.username},
        creator_id=creator["id"],
        idempotency_key=f"onboard:{creator['id']}:{body.username}:{now:%Y%m%dT%H%M}",
    )
    return OnboardingStarted(job_id=job_id, username=body.username)


@router.get("/status", response_model=OnboardingStatus)
def get_status(conn: psycopg.Connection = Depends(rls_conn)) -> OnboardingStatus:
    """Progress for the onboarding screen: reels found, comments read, ready."""
    creator = conn.execute("select * from public.creators where user_id = auth.uid()").fetchone()
    if creator is None:
        return OnboardingStatus(status="not_started")
    job = conn.execute(
        """
        select * from public.jobs where creator_id = %s and type = 'onboard_public'
         order by created_at desc limit 1
        """,
        (creator["id"],),
    ).fetchone()
    if job is None:
        state = "ready" if creator["account_id"] else "not_started"
        return OnboardingStatus(status=state, username=creator["ig_username"])
    if job["status"] == "succeeded" and not creator["account_id"]:
        # The collected account was removed since (e.g. the demo was re-seeded): start over.
        return OnboardingStatus(status="not_started", username=creator["ig_username"])
    progress = job["progress"] or {}
    state = {"queued": "running", "running": "running", "succeeded": "ready", "failed": "failed"}[
        job["status"]
    ]
    processed = 0
    if creator["account_id"]:
        processed = conn.execute(
            """
            select count(*) as n from public.reel_dna d join public.reels r on r.id = d.reel_id
             where r.account_id = %s
            """,
            (creator["account_id"],),
        ).fetchone()["n"]
    return OnboardingStatus(
        status=state,
        username=creator["ig_username"],
        job=JobOut(**job),
        reels_found=progress.get("reels_found", 0),
        comments_done=progress.get("comments_done", 0),
        comments_total=progress.get("comments_total", 0),
        reels_processed=processed,
        message=progress.get("message"),
        error=job["error"],
    )
