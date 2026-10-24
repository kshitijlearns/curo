"""build_follower_ideas (v2.1 §5.4): rebuild "What your followers will love" for one creator.

Runs after each recap and weekly. Candidates and scoring in services/follower_ideas.py; T24
names each kept idea, with the no-new-numbers check (one retry, then a template line).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from curo import providers
from curo.db import service_connection
from curo.jobs import JobContext, job
from curo.schemas.tasks import T24, T24Input
from curo.schemas.taxonomy import label_for
from curo.services import follower_ideas as F
from curo.services import validator
from curo.services.text import mask_mentions, reel_title


def _segments(conn, creator_id: UUID) -> list[dict]:
    rows = conn.execute(
        """
        select key, label, share, description, interests from public.audience_segments
         where creator_id = %s and version = (
           select max(version) from public.audience_segments where creator_id = %s)
        """,
        (creator_id, creator_id),
    ).fetchall()
    return [{**r, "share": float(r["share"]), "interests": list(r["interests"])} for r in rows]


@job("build_follower_ideas")
def build_follower_ideas(ctx: JobContext) -> dict[str, Any]:
    creator_id = UUID(str(ctx.payload["creator_id"]))
    with service_connection() as conn:
        c = conn.execute(
            "select account_id from public.creators where id = %s", (creator_id,)
        ).fetchone()
        if c is None or c["account_id"] is None:
            return {"skipped": "no account"}
        account_id = c["account_id"]
        themes = [
            {
                "label": t["label"],
                "share": float(t["share"]),
                "n": t["n"],
                "samples": [mask_mentions(s) for s in (t["samples"] or [])],
            }
            for t in conn.execute(
                """
                select t.label, t.share, t.n,
                       array(select c.text from public.comments c
                              where c.id = any(t.sample_comment_ids) limit 2) as samples
                  from public.comment_themes t where t.account_id = %s
                """,
                (account_id,),
            ).fetchall()
        ]
        groups = conn.execute(
            """
            select label, (lifts->'views'->>'lift')::float as lift,
                   coalesce(array_length(reel_ids, 1), 0) as n
              from public.subclusters where account_id = %s
            """,
            (account_id,),
        ).fetchall()
        cards = [
            {**k, "effect": float(k["effect"])}
            for k in conn.execute(
                """
                select feature, value, metric, effect, n from public.pattern_cards
                 where account_id = %s and scope = 'yours'
                """,
                (account_id,),
            ).fetchall()
        ]
        segments = _segments(conn, creator_id)
        recent = conn.execute(
            """
            select caption, hashtags from public.reels where account_id = %s and not is_deleted
             order by posted_at desc limit 10
            """,
            (account_id,),
        ).fetchall()
        opps = conn.execute(
            """
            select name, score from public.opportunities
             where creator_id = %s and status in ('active', 'saved')
            """,
            (creator_id,),
        ).fetchall()

    candidates = (
        F.from_themes(themes, segments or None)
        + F.from_groups([dict(g) for g in groups], segments or None)
        + F.from_cards(cards, label_for)
        + F.from_segments(segments)
    )
    embedder = providers.get_embedding()
    if candidates:
        for cand, v in zip(
            candidates, embedder.embed([f"{c.topic} {c.segment}" for c in candidates]), strict=True
        ):
            cand.vector = v
    recent_v = (
        embedder.embed([f"{reel_title(r['caption'])} {' '.join(r['hashtags'])}" for r in recent])
        if recent
        else []
    )
    opp_v = embedder.embed([o["name"] for o in opps]) if opps else []
    kept = F.rank(
        candidates,
        recent_v,
        [(v, float(o["score"]) / 10) for v, o in zip(opp_v, opps, strict=True)],
    )

    llm = providers.get_llm()
    rows = []
    for c in kept:
        data = T24Input(
            kind=c.kind, topic=c.topic, segment=c.segment, facts=c.facts, examples=c.examples
        )

        def write(data=data) -> str:
            out = llm.run(T24, data)
            return f"{out.title}\n{out.why}"

        def fallback(c=c) -> str:
            title, why = F.template(c.kind, c.topic, c.segment, c.facts)
            return f"{title}\n{why}"

        text, source = validator.checked(write, c.facts, fallback)
        title, _, why = text.partition("\n")
        rows.append((c, title.strip()[:60], why.strip()[:160], source))

    with service_connection() as conn:
        conn.execute(
            "delete from public.follower_ideas where creator_id = %s and status = 'active'",
            (creator_id,),
        )
        for c, title, why, source in rows:
            conn.execute(
                """
                insert into public.follower_ideas
                  (creator_id, key, title, why, evidence, segment, score, parts)
                values (%s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (creator_id, key) do update set title = excluded.title,
                  why = excluded.why, evidence = excluded.evidence, segment = excluded.segment,
                  score = excluded.score, parts = excluded.parts, status = 'active',
                  created_at = now()
                """,
                (
                    creator_id,
                    c.key,
                    title,
                    why,
                    Jsonb(
                        {"kind": c.kind, "facts": c.facts, "examples": c.examples, "copy": source}
                    ),
                    c.segment,
                    c.score,
                    Jsonb(c.parts),
                ),
            )
    return {"ideas": len(rows), "candidates": len(candidates)}


def queue_follower_ideas(account_id, reason: str) -> None:
    """Rebuild "What your followers will love" when what it reads has changed (v2.1)."""
    from curo.db import service_connection
    from curo.queue import enqueue

    with service_connection() as conn:
        creators = conn.execute(
            "select id from public.creators where account_id = %s", (account_id,)
        ).fetchall()
    for c in creators:
        enqueue(
            "build_follower_ideas",
            {"creator_id": str(c["id"])},
            creator_id=c["id"],
            idempotency_key=f"follower_ideas:{c['id']}:{reason}",
        )
