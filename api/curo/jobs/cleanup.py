"""cleanup (MVP doc §9: daily; "deletes peer videos after DNA extraction, expires past-window
opportunities, carries out deletion requests").

With a ``creator_id`` it carries out that creator's deletion request straight away (DELETE
/v1/me). The daily run also:
- finishes any deletion request still pending;
- deletes simulation uploads older than 90 days (MVP doc risks table), and uploads that were
  never simulated after a day;
- deletes tracked creators' videos left behind (process_reel deletes them as soon as their
  DNA is stored; this catches a run that stopped part-way);
- expires opportunities whose dated window has passed (the nightly build does too).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from curo import clock, providers
from curo.config import get_settings
from curo.db import service_connection
from curo.jobs import JobContext, job
from curo.services import deletion

UPLOAD_DAYS = 90
ORPHAN_UPLOAD = timedelta(days=1)


@job("cleanup")
def cleanup(ctx: JobContext) -> dict[str, Any]:
    if ctx.payload.get("creator_id"):
        return deletion.delete_creator(UUID(str(ctx.payload["creator_id"])))
    now = clock.now()
    out: dict[str, Any] = {}

    with service_connection() as conn:
        pending = conn.execute(
            "select id from public.creators where deletion_requested_at is not null"
        ).fetchall()
    out["deleted_accounts"] = [deletion.delete_creator(r["id"]) for r in pending]
    out["uploads_deleted"] = _old_uploads(now)
    out["peer_videos_deleted"] = _peer_videos()
    with service_connection() as conn:
        out["opportunities_expired"] = conn.execute(
            """
            update public.opportunities set status = 'expired'
             where status = 'active' and window_ends_on < %s
            """,
            (now.date(),),
        ).rowcount
    return out


def _old_uploads(now) -> int:
    settings = get_settings()
    videos = settings.storage_bucket_videos
    storage = providers.get_storage()
    removed = 0
    with service_connection() as conn:
        old = conn.execute(
            """
            select id, video_path from public.simulations
             where video_path is not null and created_at < %s
            """,
            (now - timedelta(days=UPLOAD_DAYS),),
        ).fetchall()
        in_use = {
            r["video_path"]
            for r in conn.execute(
                "select video_path from public.simulations where video_path is not null"
            ).fetchall()
        }
    for r in old:
        storage.delete(videos, r["video_path"])
        with service_connection() as conn:
            conn.execute(
                "update public.simulations set video_path = null where id = %s", (r["id"],)
            )
        removed += 1
    # Uploaded but never simulated (the creator picked another video, or left). Files carry
    # real timestamps, so their age is measured in real time, not CURO's clock.
    real_now = datetime.now(UTC)
    for o in storage.list(videos, "uploads/"):
        if o.path not in in_use and o.created_at < real_now - ORPHAN_UPLOAD:
            storage.delete(videos, o.path)
            removed += 1
    return removed


def _peer_videos() -> int:
    videos = get_settings().storage_bucket_videos
    storage = providers.get_storage()
    with service_connection() as conn:
        rows = conn.execute(
            """
            select r.id, r.video_path from public.reels r
             where r.video_path is not null
               and exists (select 1 from public.reel_dna d where d.reel_id = r.id)
               and not exists (select 1 from public.creators c where c.account_id = r.account_id)
            """
        ).fetchall()
    for r in rows:
        storage.delete(videos, r["video_path"])
        with service_connection() as conn:
            conn.execute("update public.reels set video_path = null where id = %s", (r["id"],))
    return len(rows)
