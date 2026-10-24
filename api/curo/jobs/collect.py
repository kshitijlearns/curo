"""Public collection jobs: onboard_public and snapshot_account (MVP doc §4, §9).

v2 (PLAN_V2 §4.3): only the creator's own public account is collected, with cost controls:
50 reels of metadata at onboarding, comments on the newest 30 (``COMMENT_LIMIT``, default
100), follow-up comment reads only for newer comments at about 24 h and 7 days, discovery
every 12 h. A creator away for 14 days is paused (the scheduler skips them).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

from curo import clock, providers
from curo.config import get_settings
from curo.db import service_connection
from curo.jobs import JobContext, JobFailed, job
from curo.providers.public_data import AccountNotFound, PrivateAccount
from curo.queue import enqueue
from curo.services import collection as store
from curo.services.schedule import (
    DISCOVERY_LIMIT,
    ReelState,
    comment_read_due,
    discovery_due,
    due_shortcodes,
)

ONBOARD_REELS = 50  # latest 50 reels with their numbers
ONBOARD_DEEP = 30  # the newest 30 get comments now (and the pipeline later)
REFRESH_MIN_AGE_H = 3  # POST /v1/reels/refresh only re-scrapes data older than this


@job("onboard_public")
def onboard_public(ctx: JobContext) -> dict[str, Any]:
    """A creator typed their username: check it's public, collect the profile, the latest
    50 reels and comments on the newest 30. Home fills in from the first write."""
    username = ctx.payload["username"].lower().lstrip("@")
    provider = providers.get_public_data()
    now = clock.now()

    ctx.progress(step="profile", message=f"Checking @{username}")
    try:
        profile = provider.get_profile(username)
    except PrivateAccount as exc:
        raise JobFailed(
            "CURO can only read public profiles. Make your account public or try another one."
        ) from exc
    except AccountNotFound as exc:
        raise JobFailed("We couldn't find that account. Check the spelling?") from exc

    with service_connection() as conn:
        account_id = store.upsert_account(conn, profile, now)
        if ctx.creator_id:
            conn.execute(
                "update public.creators set account_id = %s, ig_username = %s where id = %s",
                (account_id, username, ctx.creator_id),
            )
            # A creator onboarding a handle that deleted its data before chose to come back.
            conn.execute(
                "update public.accounts set status = 'active' where id = %s and status = 'opted_out'",
                (account_id,),
            )

    ctx.progress(step="reels", message="Collecting your latest reels")
    reels = provider.get_reels(username, limit=ONBOARD_REELS)
    with service_connection() as conn:
        stored = [store.upsert_reel(conn, account_id, r, now, "onboarding") for r in reels]
    ctx.progress(
        step="comments",
        reels_found=len(stored),
        comments_done=0,
        comments_total=min(ONBOARD_DEEP, len(stored)),
    )

    recap_queued = False
    for i, (reel, data) in enumerate(zip(stored[:ONBOARD_DEEP], reels[:ONBOARD_DEEP], strict=True)):
        if not data.comments_disabled:
            comments = provider.get_comments(reel.permalink, get_settings().comment_limit)
            with service_connection() as conn:
                store.store_comments(conn, reel.id, comments, username)
        ctx.progress(comments_done=i + 1)
        if i + 1 == RECAP_AFTER_COMMENTS:
            recap_queued = _queue_first_recap(ctx)
    if not recap_queued:
        _queue_first_recap(ctx)

    # Understanding (MVP doc §9): the newest 30 reels are processed; comments are labelled.
    queue_understanding(account_id, [r.id for r in stored[:ONBOARD_DEEP]], ctx.creator_id)
    enqueue(
        "label_comments",
        {"account_id": str(account_id)},
        creator_id=ctx.creator_id,
        idempotency_key=f"label:{account_id}:{ctx.job_id}",
    )

    ctx.progress(step="ready", message="Your reels are in")
    return {"account_id": str(account_id), "reels": len(stored), "followers": profile.followers}


RECAP_AFTER_COMMENTS = 10  # the first recap needs only the newest reels' comments (v2.1 §2)


def _queue_first_recap(ctx: JobContext) -> bool:
    """The first Creator Recap, built from fast data while the rest keeps collecting."""
    if not ctx.creator_id:
        return False
    from curo.jobs.recap import queue_recap

    ctx.progress(step="recap", message="Building your recap")
    queue_recap(ctx.creator_id, "first", key=f"recap:{ctx.creator_id}:first:{ctx.job_id}")
    return True


def queue_understanding(account_id: UUID, reel_ids: list[UUID], creator_id: UUID | None) -> None:
    """Queue process_reel for each reel, once per reel and pipeline version."""
    from curo.jobs.understand import pipeline_version

    version = pipeline_version()
    for reel_id in reel_ids:
        enqueue(
            "process_reel",
            {"reel_id": str(reel_id), "account_id": str(account_id)},
            creator_id=creator_id,
            idempotency_key=f"process:{reel_id}:{version}",
        )


@job("snapshot_account")
def snapshot_account(ctx: JobContext) -> dict[str, Any]:
    """One batched scrape for an account: every reel that's due, a check for new reels, and
    the follower count. Never one run per reel (every snapshot is a paid result)."""
    account_id = UUID(str(ctx.payload["account_id"]))
    refresh = bool(ctx.payload.get("refresh"))
    provider = providers.get_public_data()
    now = clock.now()

    with service_connection() as conn:
        account = conn.execute(
            "select id, username, status, last_collected_at, last_discovered_at from public.accounts where id = %s",
            (account_id,),
        ).fetchone()
        if account is None or account["status"] != "active":
            return {"skipped": account["status"] if account else "missing"}
        creator = conn.execute(
            "select id from public.creators where account_id = %s", (account_id,)
        ).fetchone()
        if creator is None:
            return {"skipped": "not a creator's account"}  # v2 collects own accounts only
        rows = conn.execute(
            """
            select r.id, r.shortcode, r.permalink, r.posted_at, r.comment_reads,
                   (select max(m.taken_at) from public.metric_snapshots m where m.reel_id = r.id) as last_taken
              from public.reels r
             where r.account_id = %s and not r.is_deleted
             order by r.posted_at desc
            """,
            (account_id,),
        ).fetchall()
    username = account["username"]
    states = [ReelState(r["shortcode"], r["posted_at"], r["last_taken"]) for r in rows]
    due = due_shortcodes(states, now)
    if refresh:  # pull-to-refresh: also the carousel's reels, if their data is 3 h old
        stale_before = now - timedelta(hours=REFRESH_MIN_AGE_H)
        for r in rows[:10]:
            if r["shortcode"] not in due and (
                r["last_taken"] is None or r["last_taken"] < stale_before
            ):
                due.append(r["shortcode"])
    discover = refresh or discovery_due(
        account["last_discovered_at"] or account["last_collected_at"], now
    )

    try:
        profile = provider.get_profile(username)
    except PrivateAccount:
        return _account_gone(username, "private")
    except AccountNotFound:
        return _account_gone(username, "deleted")

    fetched = provider.get_reels_by_shortcodes(username, due) if due else []
    latest = provider.get_reels(username, limit=DISCOVERY_LIMIT) if discover else []

    known = {r["shortcode"] for r in rows}
    source = "refresh" if refresh else "schedule"
    with service_connection() as conn:
        store.upsert_account(conn, profile, now)
        snapped = [store.upsert_reel(conn, account_id, r, now, source) for r in fetched]
        returned = {r.shortcode for r in fetched}
        deleted = store.mark_deleted(conn, account_id, [s for s in due if s not in returned], now)
        new = [
            store.upsert_reel(conn, account_id, r, now, "discovery")
            for r in latest
            if r.shortcode not in known
        ]
        if discover:
            conn.execute(
                "update public.accounts set last_discovered_at = %s where id = %s",
                (now, account_id),
            )

    # Comments: a first read for new reels; then only newer comments, at about 24 h and 7 days.
    limit = get_settings().comment_limit
    reads = {r["shortcode"]: r for r in rows}
    comment_reads = 0
    for reel in new:
        if reel.comments is None:  # comments turned off
            continue
        comments = provider.get_comments(reel.permalink, limit)
        with service_connection() as conn:
            store.store_comments(conn, reel.id, comments, username)
        comment_reads += 1
    for reel in snapped:
        row = reads.get(reel.shortcode)
        if row is None or reel.comments is None:
            continue
        if not comment_read_due(row["posted_at"], row["comment_reads"], now):
            continue
        with service_connection() as conn:
            newest = conn.execute(
                "select max(posted_at) as t from public.comments where reel_id = %s", (reel.id,)
            ).fetchone()["t"]
        comments = provider.get_comments(reel.permalink, limit, since=newest)
        with service_connection() as conn:
            store.store_comments(conn, reel.id, comments, username)
            conn.execute(
                "update public.reels set comment_reads = comment_reads + 1 where id = %s",
                (reel.id,),
            )
        comment_reads += 1

    # New reels go through the same understanding pipeline (logic doc §5).
    queue_understanding(account_id, [r.id for r in new], creator["id"])
    for reel in new:
        enqueue(
            "label_comments",
            {"account_id": str(account_id), "reel_id": str(reel.id)},
            idempotency_key=f"label:{reel.id}:{now:%Y%m%dT%H%M}",
        )
    if new:  # was it one the creator simulated or drafted? (logic doc §15)
        from curo.jobs.lifecycle import queue_match

        for reel in new:
            queue_match(reel.id, creator["id"])

    return {
        "snapshots": len(snapped),
        "new_reels": [r.shortcode for r in new],
        "deleted": deleted,
        "comment_reads": comment_reads,
        "followers": profile.followers,
    }


def _account_gone(username: str, status: str) -> dict[str, Any]:
    """The creator's account turned private or was deleted: stop collecting. Its history stays;
    the app tells the creator collection stopped."""
    with service_connection() as conn:
        store.set_account_status(conn, username, status)
    return {"stopped": status}
