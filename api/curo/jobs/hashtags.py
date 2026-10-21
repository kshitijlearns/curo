"""collect_hashtags (MVP doc §9): daily, the public hashtag pages linked to creators' niches
and upcoming festivals. Cached and refreshed at most daily; shared across creators."""

from __future__ import annotations

from collections import Counter
from datetime import timedelta
from typing import Any

from psycopg.types.json import Jsonb

from curo import clock, providers
from curo.db import service_connection
from curo.jobs import JobContext, job
from curo.providers.public_data.base import PublicDataError
from curo.services import topics

PAGE_LIMIT = 300  # recent reels requested per page
REFRESH_AFTER_H = 20
FESTIVAL_HORIZON_DAYS = 30
OWN_TAGS = 10


def creator_niche(conn, account_id) -> str | None:
    """The creator's niche, from the broad cluster most of their understood reels share."""
    row = conn.execute(
        """
        select d.content->>'cluster' as cluster, count(*) as n
          from public.reel_dna d join public.reels r on r.id = d.reel_id
         where r.account_id = %s and d.content->>'cluster' <> 'unknown'
         group by 1 order by 2 desc limit 1
        """,
        (account_id,),
    ).fetchone()
    return topics.NICHE_OF_CLUSTER.get(row["cluster"]) if row else None


def upcoming_festivals(
    conn, niche: str | None, today, horizon: int = FESTIVAL_HORIZON_DAYS
) -> list[dict]:
    rows = conn.execute(
        """
        select * from public.festival_calendar
         where ends_on >= %s and starts_on <= %s order by starts_on
        """,
        (today, today + timedelta(days=horizon)),
    ).fetchall()
    return [r for r in rows if niche is None or not r["niches"] or niche in r["niches"]]


def tags_for_creator(conn, creator_id, account_id) -> set[str]:
    """The creator's most-used tags and upcoming festivals' (v2: no peers)."""
    own = Counter(
        t
        for r in conn.execute(
            "select hashtags from public.reels where account_id = %s order by posted_at desc limit 30",
            (account_id,),
        ).fetchall()
        for t in r["hashtags"]
    )
    out = {t for t, _ in own.most_common(OWN_TAGS)}
    for f in upcoming_festivals(conn, creator_niche(conn, account_id), clock.now().date()):
        out |= {t for t in topics.keyword_tags(f["keywords"]) if t}
    return out


def tags_to_watch(conn) -> set[str]:
    out: set[str] = set()
    for c in conn.execute(
        "select id, account_id from public.creators where account_id is not null"
    ).fetchall():
        out |= tags_for_creator(conn, c["id"], c["account_id"])
    return out


@job("collect_hashtags")
def collect_hashtags(ctx: JobContext) -> dict[str, Any]:
    with service_connection() as conn:
        tags = sorted(ctx.payload.get("tags") or tags_to_watch(conn))
    return {"tags": len(tags), "fetched": fetch_pages(tags)}


def fetch_pages(tags: list[str]) -> int:
    """Read each hashtag page that is more than a day old into the shared cache."""
    provider = providers.get_public_data()
    now = clock.now()
    with service_connection() as conn:
        fresh = {
            r["tag"]
            for r in conn.execute(
                "select tag from public.hashtag_pages where fetched_at > %s",
                (now - timedelta(hours=REFRESH_AFTER_H),),
            ).fetchall()
        }
    fetched = 0
    for tag in tags:
        if tag in fresh:
            continue
        try:
            page = provider.get_hashtag_page(tag, limit=PAGE_LIMIT)
        except PublicDataError:
            continue  # a missed page is simply older; nothing is invented
        recent = [r for r in page.recent if r.posted_at <= now]
        oldest = (
            min((r.posted_at for r in recent), default=None) if len(recent) >= PAGE_LIMIT else None
        )
        counts = topics.daily_counts([r.posted_at for r in recent], now, oldest)
        summaries = [
            {
                "shortcode": r.shortcode,
                "owner": r.owner_username,
                "posted_at": r.posted_at.isoformat(),
                "views": r.views,
                "caption": (r.caption or "")[:200],
                "hashtags": r.hashtags[:10],
            }
            for r in (page.top + recent[:60])
        ]
        with service_connection() as conn:
            previous = conn.execute(
                "select daily_counts from public.hashtag_pages where tag = %s for update", (tag,)
            ).fetchone()
            counts = topics.merge_counts(previous["daily_counts"] if previous else {}, counts)
            conn.execute(
                """
                insert into public.hashtag_pages
                  (tag, fetched_at, post_count, top_reel_ids, recent_reel_ids, reel_count_7d, reels, daily_counts)
                values (%s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (tag) do update set
                  fetched_at = excluded.fetched_at, post_count = excluded.post_count,
                  top_reel_ids = excluded.top_reel_ids, recent_reel_ids = excluded.recent_reel_ids,
                  reel_count_7d = excluded.reel_count_7d, reels = excluded.reels,
                  daily_counts = excluded.daily_counts
                """,
                (
                    tag,
                    now,
                    page.post_count,
                    [r.shortcode for r in page.top],
                    [r.shortcode for r in recent[:60]],
                    sum(1 for r in recent if r.posted_at > now - timedelta(days=7)),
                    Jsonb(summaries),
                    Jsonb(counts),
                ),
            )
        fetched += 1
    return fetched
