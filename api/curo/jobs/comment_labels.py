"""label_comments (MVP doc §9; logic doc §5 step 4): bot filter, sentiment, intent, friend
tags and theme grouping. Runs after each new reel and nightly as a batch."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from curo import clock, providers
from curo.db import service_connection
from curo.jobs import JobContext, job
from curo.schemas.tasks import T3, T4, CommentIn, T3Input, T4Input
from curo.services.comments import MIN_THEME_N, group_themes, language_of, theme_key

BATCH = 200  # T3 takes up to 200 comments per call
THEME_REELS = 30  # themes are read across the creator's last 30 reels (logic doc §8)


def label_version() -> str:
    return providers.get_llm().version(T3)


@job("label_comments")
def label_comments(ctx: JobContext) -> dict[str, Any]:
    account_id = UUID(str(ctx.payload["account_id"]))
    reel_id = ctx.payload.get("reel_id")
    version = label_version()
    llm = providers.get_llm()

    with service_connection() as conn:
        rows = conn.execute(
            """
            select c.id, c.text from public.comments c
              join public.reels r on r.id = c.reel_id
             where r.account_id = %s and (%s::uuid is null or r.id = %s::uuid)
               and not c.is_creator
               and (c.labelled_at is null or c.label_version is distinct from %s)
             order by c.id
            """,
            (account_id, reel_id, reel_id, version),
        ).fetchall()
        is_creator = conn.execute(
            "select exists(select 1 from public.creators where account_id = %s) as yes",
            (account_id,),
        ).fetchone()["yes"]

    chunks = [rows[i : i + BATCH] for i in range(0, len(rows), BATCH)]
    inputs = [
        T3Input(comments=[CommentIn(id=str(r["id"]), text=r["text"]) for r in chunk])
        for chunk in chunks
    ]
    labelled = 0
    now = clock.now()
    for chunk, out in zip(chunks, llm.run_batch(T3, inputs), strict=True):
        texts = {str(r["id"]): r["text"] for r in chunk}
        with service_connection() as conn:
            for label in out.labels:
                if label.id not in texts:
                    continue  # never trust an id the model invented
                conn.execute(
                    """
                    update public.comments set is_bot = %s, sentiment = %s, intent = %s,
                           theme_key = %s, language = %s, labelled_at = %s, label_version = %s
                     where id = %s
                    """,
                    (
                        label.is_bot,
                        label.sentiment,
                        label.intent,
                        None if label.is_bot else theme_key(label.theme),
                        language_of(texts[label.id]),
                        now,
                        version,
                        label.id,
                    ),
                )
                labelled += 1

    themes = rebuild_themes(account_id) if is_creator else 0
    if is_creator and themes:
        from curo.jobs.follower_ideas import queue_follower_ideas

        queue_follower_ideas(account_id, f"labels:{ctx.job_id}")
    return {"labelled": labelled, "themes": themes}


def rebuild_themes(account_id: UUID) -> int:
    """Group the requests and questions on the creator's last 30 reels into themes, name each
    with T4, and record each theme's share of all (non-bot) comments on those reels."""
    with service_connection() as conn:
        rows = conn.execute(
            """
            with recent as (
              select id from public.reels
               where account_id = %s and not is_deleted
               order by posted_at desc limit %s
            )
            select c.id, c.text, c.intent, c.theme_key
              from public.comments c
             where c.reel_id in (select id from recent)
               and not c.is_creator and c.labelled_at is not null and not coalesce(c.is_bot, false)
            """,
            (account_id, THEME_REELS),
        ).fetchall()
        old = {
            r["key"]: r["id"]
            for r in conn.execute(
                "select id, key from public.comment_themes where account_id = %s", (account_id,)
            ).fetchall()
        }
    total = len(rows)
    text_of = {str(r["id"]): r["text"] for r in rows}
    groups = [
        g
        for g in group_themes(
            [(str(r["id"]), r["intent"], r["theme_key"]) for r in rows],
            providers.get_embedding().embed,
        )
        if len(g.comment_ids) >= MIN_THEME_N
    ]
    llm = providers.get_llm()
    now = clock.now()
    with service_connection() as conn:
        conn.execute(
            """
            update public.comments set theme_id = null
             where theme_id in (select id from public.comment_themes where account_id = %s)
            """,
            (account_id,),
        )
        kept = []
        for g in groups:
            # By text, not by id: ids are random, and the name must not change run to run.
            samples = sorted(g.comment_ids, key=lambda c: (text_of[c], c))[:12]
            label = llm.run(
                T4, T4Input(kind="comments", samples=[text_of[c] for c in samples])
            ).label
            row = conn.execute(
                """
                insert into public.comment_themes
                  (account_id, key, label, kind, share, n, sample_comment_ids, computed_at)
                values (%s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (account_id, key) do update set
                  label = excluded.label, kind = excluded.kind, share = excluded.share,
                  n = excluded.n, sample_comment_ids = excluded.sample_comment_ids,
                  computed_at = excluded.computed_at
                returning id
                """,
                (
                    account_id,
                    g.key,
                    label,
                    g.kind,
                    round(len(g.comment_ids) / total, 4) if total else 0.0,
                    len(g.comment_ids),
                    samples[:5],
                    now,
                ),
            ).fetchone()
            kept.append(g.key)
            conn.execute(
                "update public.comments set theme_id = %s where id = any(%s::uuid[])",
                (row["id"], g.comment_ids),
            )
        stale = [k for k in old if k not in kept]
        if stale:
            conn.execute(
                "delete from public.comment_themes where account_id = %s and key = any(%s)",
                (account_id, stale),
            )
    return len(groups)
