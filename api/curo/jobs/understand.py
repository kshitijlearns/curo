"""process_reel (MVP doc §9; logic doc §5 steps 1–3 and 5): store the raw material,
understand the video (T1), extract the DNA (T2) and embed it.

Every reel goes through the same steps — the creator's, a peer's, or (Phase 7) an upload —
so the Simulator's view of a draft matches Home's view of a posted reel.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from curo import clock, providers
from curo.config import get_settings
from curo.db import service_connection
from curo.jobs import JobContext, JobFailed, job
from curo.providers.public_data.base import MediaUnavailable
from curo.schemas.tasks import T1, T2, T1Input, T1Output, T2Input
from curo.services import dna


def pipeline_version() -> str:
    """Which models made a reel's DNA; a change means the reel is processed again."""
    video, llm, emb = providers.get_video(), providers.get_llm(), providers.get_embedding()
    return f"{T1.tag}:{video.model}|{llm.version(T2)}|{emb.model}"


def vector_literal(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


@dataclass
class Understood:
    t1: T1Output
    content: dict[str, Any]
    production: dict[str, Any]
    confidence: dict[str, float]
    vector: list[float]


def understand_video(
    bucket: str,
    path: str,
    duration_s: float | None,
    caption: str,
    hashtags: list[str],
    progress=None,
) -> Understood:
    """Steps 2, 3 and 5 for one stored video: watch it (T1), extract its DNA (T2; anything
    under 0.6 confidence becomes unknown) and embed it. A posted reel and a Simulator upload
    go through exactly this, so the two are described the same way."""
    if progress:
        progress(step="understanding")
    t1 = providers.get_video().understand(T1Input(bucket=bucket, path=path, duration_s=duration_s))
    if progress:
        progress(step="dna")
    out = providers.get_llm().run(
        T2, T2Input(understanding=t1, caption=caption, hashtags=hashtags, duration_s=duration_s)
    )
    content, production, confidence = dna.apply_confidence(out)
    vector = providers.get_embedding().embed([dna.embedding_text(caption, t1)])[0]
    return Understood(t1, content, production, confidence, vector)


def _fetch(reel: dict[str, Any]) -> bytes:
    """Download the video; if the vendor's link has expired, ask for the reel again to get a
    fresh link (MVP doc §5: media links expire)."""
    public = providers.get_public_data()
    try:
        return public.download(reel["video_url"] or "")
    except MediaUnavailable:
        fresh = public.get_reels_by_shortcodes(reel["username"], [reel["shortcode"]])
        if not fresh or not fresh[0].video_url:
            raise
        with service_connection() as conn:
            conn.execute(
                "update public.reels set video_url = %s, thumb_url = %s where id = %s",
                (fresh[0].video_url, fresh[0].thumb_url, reel["id"]),
            )
        return public.download(fresh[0].video_url)


@job("process_reel")
def process_reel(ctx: JobContext) -> dict[str, Any]:
    reel_id = UUID(str(ctx.payload["reel_id"]))
    settings = get_settings()
    storage = providers.get_storage()
    version = pipeline_version()

    with service_connection() as conn:
        reel = conn.execute(
            """
            select r.*, a.username,
                   exists(select 1 from public.creators c where c.account_id = r.account_id) as is_creator,
                   d.model_version as done_version
              from public.reels r
              join public.accounts a on a.id = r.account_id
              left join public.reel_dna d on d.reel_id = r.id
             where r.id = %s
            """,
            (reel_id,),
        ).fetchone()
    if reel is None:
        return {"skipped": "missing"}
    if reel["done_version"] == version and not ctx.payload.get("force"):
        return {"skipped": "already processed"}
    if reel["is_deleted"]:
        return {"skipped": "deleted"}

    # 1. Store the raw material (links expire, so copy the files now).
    ctx.progress(step="download")
    videos = settings.storage_bucket_videos
    video_path = reel["video_path"]
    if not video_path or not storage.exists(videos, video_path):
        try:
            data = _fetch(reel)
        except MediaUnavailable as exc:
            raise JobFailed("This reel's video is no longer available.") from exc
        video_path = storage.put(
            videos, f"{reel['account_id']}/{reel['shortcode']}.mp4", data, "video/mp4"
        )
        thumb_path = None
        if reel["thumb_url"]:
            try:
                thumb = providers.get_public_data().download(reel["thumb_url"])
                thumb_path = storage.put(
                    settings.storage_bucket_thumbs,
                    f"{reel['account_id']}/{reel['shortcode']}.jpg",
                    thumb,
                    "image/jpeg",
                )
            except MediaUnavailable:
                pass  # the thumbnail is optional
        with service_connection() as conn:
            conn.execute(
                "update public.reels set video_path = %s, thumb_path = coalesce(%s, thumb_path) where id = %s",
                (video_path, thumb_path, reel_id),
            )

    # 2–5. Understand the video (T1), extract the DNA (T2), embed it.
    duration = float(reel["duration_s"]) if reel["duration_s"] is not None else None
    u = understand_video(
        videos, video_path, duration, reel["caption"], reel["hashtags"], ctx.progress
    )
    t1, content, production, confidence, vector = (
        u.t1,
        u.content,
        u.production,
        u.confidence,
        u.vector,
    )
    embedder = providers.get_embedding()

    now = clock.now()
    with service_connection() as conn:
        conn.execute(
            """
            insert into public.reel_dna
              (reel_id, content, production, transcript, confidence, model_version, created_at, updated_at)
            values (%s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (reel_id) do update set
              content = excluded.content, production = excluded.production,
              transcript = excluded.transcript, confidence = excluded.confidence,
              model_version = excluded.model_version, updated_at = excluded.updated_at
            """,
            (
                reel_id,
                Jsonb(content),
                Jsonb(production),
                Jsonb(t1.model_dump()),
                Jsonb(confidence),
                version,
                now,
                now,
            ),
        )
        conn.execute(
            """
            insert into public.reel_embeddings (reel_id, embedding, model, created_at)
            values (%s, %s::vector, %s, %s)
            on conflict (reel_id) do update set
              embedding = excluded.embedding, model = excluded.model, created_at = excluded.created_at
            """,
            (reel_id, vector_literal(vector), embedder.model, now),
        )
        if not reel["is_creator"]:
            # Privacy (logic doc §17): peers' raw videos go once their DNA is extracted.
            conn.execute("update public.reels set video_path = null where id = %s", (reel_id,))
    if not reel["is_creator"]:
        storage.delete(videos, video_path)

    unknown = sorted(k for part in (content, production) for k, v in part.items() if v == "unknown")
    return {"reel_id": str(reel_id), "version": version, "unknown_fields": unknown}
