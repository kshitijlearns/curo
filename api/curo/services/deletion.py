"""Deleting a creator's account and data (MVP doc §7: DELETE /v1/me; logic doc §17: "Delete a
creator's data on request, and offer that in settings").

What goes:
- Their sign-in. Every record keyed to them goes with it (projects, ideas, scripts,
  storyboards, captions, simulations, chat, memory, opportunities, tracked creators, jobs,
  events).
- Their uploads and the videos and covers CURO stored for their reels.
- Everything CURO collected about their own public account: reels, snapshots, comments,
  DNA, embeddings, baselines, patterns, sub-clusters, comment themes.

What stays: the account's username, marked ``opted_out``, so CURO doesn't collect it again,
not even as another creator's tracked creator (a suppression list, not data about them).
One anonymous ``account_deleted`` event records that it happened.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from curo import events, providers
from curo.config import get_settings
from curo.db import service_connection
from curo.providers.storage.base import StorageError

log = logging.getLogger("curo.deletion")

ACCOUNT_TABLES = (
    "baselines",
    "pattern_cards",
    "subclusters",
    "comment_themes",
    "account_snapshots",
)


def delete_creator(creator_id: UUID) -> dict[str, Any]:
    settings = get_settings()
    videos, thumbs = settings.storage_bucket_videos, settings.storage_bucket_thumbs
    with service_connection() as conn:
        c = conn.execute(
            "select id, user_id, account_id from public.creators where id = %s", (creator_id,)
        ).fetchone()
        if c is None:
            return {"skipped": "already deleted"}
        account_id = c["account_id"]
        files = [
            (bucket, r[col])
            for r in conn.execute(
                "select video_path, thumb_path from public.reels where account_id = %s",
                (account_id,),
            ).fetchall()
            for bucket, col in ((videos, "video_path"), (thumbs, "thumb_path"))
            if r[col]
        ]
        files += [
            (videos, r["video_path"])
            for r in conn.execute(
                "select video_path from public.simulations where creator_id = %s and video_path is not null",
                (creator_id,),
            ).fetchall()
        ]
        counts = {
            "reels": conn.execute(
                "select count(*) as n from public.reels where account_id = %s", (account_id,)
            ).fetchone()["n"],
            "projects": conn.execute(
                "select count(*) as n from public.projects where creator_id = %s", (creator_id,)
            ).fetchone()["n"],
            "simulations": conn.execute(
                "select count(*) as n from public.simulations where creator_id = %s", (creator_id,)
            ).fetchone()["n"],
        }

    # Files first: if this run stops part-way, the next one still finds the rows to go by.
    storage = providers.get_storage()
    files += [(videos, o.path) for o in storage.list(videos, f"uploads/{creator_id}/")]
    removed = 0
    for bucket, path in dict.fromkeys(files):
        try:
            storage.delete(bucket, path)
            removed += 1
        except StorageError as exc:  # outside the bucket or already gone: nothing to remove
            log.warning("could not delete %s/%s: %s", bucket, path, exc)

    with service_connection() as conn:
        if account_id:
            conn.execute("delete from public.reels where account_id = %s", (account_id,))
            for table in ACCOUNT_TABLES:
                conn.execute(f"delete from public.{table} where account_id = %s", (account_id,))
            conn.execute(
                """
                update public.accounts
                   set status = 'opted_out', full_name = null, bio = null, followers = null,
                       following = null, posts = null, category = null
                 where id = %s
                """,
                (account_id,),
            )
        # The sign-in goes, and every record keyed to the creator with it (on delete cascade).
        conn.execute("delete from auth.users where id = %s", (c["user_id"],))
        events.record(conn, None, "account_deleted", {**counts, "files": removed})
    return {"deleted": str(creator_id), **counts, "files": removed}


def request(creator_id: UUID) -> UUID:
    """Mark the request and start carrying it out (the cleanup job, on the priority queue)."""
    from curo import clock
    from curo.queue import enqueue

    with service_connection() as conn:
        conn.execute(
            "update public.creators set deletion_requested_at = coalesce(deletion_requested_at, %s) where id = %s",
            (clock.now(), creator_id),
        )
    # No creator_id on the job: it outlives the creator it deletes.
    return enqueue(
        "cleanup", {"creator_id": str(creator_id)}, idempotency_key=f"delete:{creator_id}"
    )
