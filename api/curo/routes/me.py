"""GET /v1/me — profile, follower count, counts and the Saved badge. DELETE /v1/me — delete the
account and all its data (logic doc §17; services/deletion.py)."""

from __future__ import annotations

from datetime import timedelta

import psycopg
from fastapi import APIRouter, Depends, status

from curo import clock, events
from curo.auth import User, current_user
from curo.db import creator_session, service_connection
from curo.routes.deps import rls_conn
from curo.schemas.api import AccountOut, CreatorOut, DeletionStarted, Me
from curo.services import deletion

router = APIRouter(prefix="/v1", tags=["me"])


@router.get("/me", response_model=Me)
def get_me(user: User = Depends(current_user), conn: psycopg.Connection = Depends(rls_conn)) -> Me:
    creator = conn.execute("select * from public.creators where user_id = auth.uid()").fetchone()
    me = Me(user_id=user.id, email=user.email, now=clock.now())
    if creator is None:
        return me
    me.creator = CreatorOut(**creator)
    _seen(creator)
    if creator["account_id"]:
        account = conn.execute(
            "select * from public.accounts where id = %s", (creator["account_id"],)
        ).fetchone()
        if account:
            me.account = AccountOut(**account)
            me.reels = conn.execute(
                "select count(*) as n from public.reels where account_id = %s and not is_deleted",
                (creator["account_id"],),
            ).fetchone()["n"]
            last_onboarding = conn.execute(
                """
                select status from public.jobs where creator_id = %s and type = 'onboard_public'
                 order by created_at desc limit 1
                """,
                (creator["id"],),
            ).fetchone()
            me.onboarded = (
                me.reels > 0 or last_onboarding is None or last_onboarding["status"] == "succeeded"
            )
    me.saved_opportunities = conn.execute(
        "select count(*) as n from public.opportunities where status = 'saved'"
    ).fetchone()["n"]
    me.drafts = conn.execute(
        "select count(*) as n from public.projects where status = 'saved'"
    ).fetchone()["n"]
    me.saved_count = me.saved_opportunities + me.drafts
    return me


@router.delete("/me", status_code=status.HTTP_202_ACCEPTED, response_model=DeletionStarted)
def delete_me(user: User = Depends(current_user)) -> DeletionStarted:
    """Delete the account and everything CURO holds about it. The app signs out straight away;
    the deletion runs as the cleanup job (immediately, and the daily run finishes any that
    stopped part-way)."""
    with creator_session(user.id) as conn:
        creator = conn.execute(
            "select id from public.creators where user_id = auth.uid()"
        ).fetchone()
    if creator is None:  # signed in, never onboarded: only the sign-in to remove
        with service_connection() as conn:
            conn.execute("delete from auth.users where id = %s", (user.id,))
            events.record(conn, None, "account_deleted", {"reels": 0, "projects": 0})
        return DeletionStarted(status="deleted", job_id=None)
    return DeletionStarted(status="deleting", job_id=deletion.request(creator["id"]))


def _seen(creator: dict) -> None:
    """The creator opened the app: note it (at most hourly), and resume collection for a paused
    creator with one catch-up run (PLAN_V2 §4.3)."""
    now = clock.now()
    last = creator.get("last_seen_at")
    if creator.get("paused_at") is None and last is not None and now - last < timedelta(hours=1):
        return
    with service_connection() as conn:
        conn.execute(
            "update public.creators set last_seen_at = %s, paused_at = null where id = %s",
            (now, creator["id"]),
        )
    if creator.get("paused_at") is not None and creator.get("account_id"):
        from curo.queue import enqueue

        enqueue(
            "snapshot_account",
            {"account_id": str(creator["account_id"]), "refresh": True},
            creator_id=creator["id"],
            idempotency_key=f"resume:{creator['id']}:{now:%Y%m%dT%H}",
        )
