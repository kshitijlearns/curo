"""trend_feed (PLAN_V2 §4.4): daily, per niche — read the niche's hashtag pages and its coming
festivals, measure what's picking up, and have T16 word 3–6 trend cards. Shared by every
creator in the niche; nothing is fetched per creator."""

from __future__ import annotations

from collections import Counter
from typing import Any

from psycopg.types.json import Jsonb

from curo import clock, providers
from curo.db import service_connection
from curo.jobs import JobContext, job
from curo.jobs.hashtags import fetch_pages, upcoming_festivals
from curo.schemas.tasks import T16, T16Input
from curo.services import topics, trends, validator


def _pages(conn, tags: list[str], niche_tags: set[str], today) -> list[trends.Page]:
    rows = conn.execute(
        "select tag, daily_counts, reel_count_7d, post_count, reels from public.hashtag_pages "
        "where tag = any(%s) order by tag",
        (tags,),
    ).fetchall()
    out = []
    for r in rows:
        reels = r["reels"] or []
        co = Counter(
            t.lower()
            for x in reels
            for t in set(x.get("hashtags") or [])
            if t.lower() != r["tag"] and t.lower() not in niche_tags
        )
        out.append(
            trends.Page(
                tag=r["tag"],
                growth=topics.growth(r["daily_counts"] or {}, today),
                reels_7d=r["reel_count_7d"],
                post_count=r["post_count"],
                captions=[x.get("caption", "") for x in reels if x.get("caption")][:10],
                co_tags=co,
            )
        )
    return out


def write_card(niche_label: str, c: trends.Candidate) -> dict[str, Any]:
    data = T16Input(
        niche=niche_label,
        kind=c.kind,  # type: ignore[arg-type]
        label=c.label,
        hashtags=c.hashtags[:5],
        facts=c.facts[:6] or [f"{c.label} is turning up in this niche."],
        sample_captions=c.captions[:5],
    )
    llm = providers.get_llm()
    out = None

    def write() -> str:
        nonlocal out
        out = llm.run(T16, data)
        return " ".join([out.name, out.summary, out.why_rising, *out.example_angles])

    _text, source = validator.checked(write, [*data.facts, c.label, *c.hashtags], lambda: "")
    if source == "template" or out is None:
        return {
            "name": c.label,
            "summary": data.facts[0],
            "why_rising": data.facts[0],
            "example_angles": [f"Your take on {c.label}", f"{c.label} in your own style"],
        }
    return out.model_dump()


@job("trend_feed")
def trend_feed(ctx: JobContext) -> dict[str, Any]:
    now = clock.now()
    today = now.date()
    with service_connection() as conn:
        niches = conn.execute(
            "select * from public.niches where %s::text is null or key = %s order by key",
            (ctx.payload.get("niche"), ctx.payload.get("niche")),
        ).fetchall()
    built: dict[str, int] = {}
    for n in niches:
        with service_connection() as conn:
            festivals = upcoming_festivals(conn, n["key"], today, trends.FESTIVAL_LEAD_DAYS)
        festival_tags = sorted({t for f in festivals for t in topics.keyword_tags(f["keywords"])})
        tags = sorted(set(n["hashtags"]) | set(festival_tags))
        fetch_pages(tags)
        with service_connection() as conn:
            pages = _pages(conn, tags, set(n["hashtags"]), today)
        cands = trends.candidates(pages, festivals, today)
        keys = []
        for c in cands:
            words = write_card(n["label"], c)
            with service_connection() as conn:
                conn.execute(
                    """
                    insert into public.trend_cards
                      (niche, key, name, summary, why_rising, example_angles, window_start,
                       window_end, momentum, saturation, evidence, hashtags, created_at)
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    on conflict (niche, key) do update set
                      name = excluded.name, summary = excluded.summary,
                      why_rising = excluded.why_rising, example_angles = excluded.example_angles,
                      window_start = excluded.window_start, window_end = excluded.window_end,
                      momentum = excluded.momentum, saturation = excluded.saturation,
                      evidence = excluded.evidence, hashtags = excluded.hashtags,
                      created_at = excluded.created_at
                    """,
                    (
                        n["key"],
                        c.key,
                        words["name"],
                        words["summary"],
                        words["why_rising"],
                        Jsonb(words["example_angles"]),
                        c.window_start,
                        c.window_end,
                        c.momentum,
                        c.saturation,
                        Jsonb({"kind": c.kind, "facts": c.facts}),
                        c.hashtags,
                        now,
                    ),
                )
            keys.append(c.key)
        with service_connection() as conn:  # yesterday's cards that no longer hold go
            conn.execute(
                "delete from public.trend_cards where niche = %s and not (key = any(%s))",
                (n["key"], keys),
            )
        built[n["key"]] = len(keys)
    return {"niches": built}
