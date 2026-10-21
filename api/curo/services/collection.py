"""Store public collection results: accounts, reels, snapshots and comments.

Every write is an upsert, so running a job twice never duplicates data. Data-quality
rules (services/data_quality.py) are applied to every snapshot. Commenter handles are used
here to filter friend tags and the creator's own replies, then dropped: they're never stored.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import psycopg

from curo.providers.public_data import CommentData, ProfileData, ReelData
from curo.services.data_quality import Counts, clean_snapshot
from curo.services.text import hashtags_in, mask_mentions, mentions_in


def upsert_account(conn: psycopg.Connection, profile: ProfileData, now: datetime) -> UUID:
    """Create or refresh an account and save a follower snapshot."""
    row = conn.execute(
        """
        insert into public.accounts as a
          (username, full_name, bio, followers, following, posts, category, is_private,
           status, last_collected_at)
        values (%(username)s, %(full_name)s, %(bio)s, %(followers)s, %(following)s, %(posts)s,
                %(category)s, false, 'active', %(now)s)
        on conflict (username) do update set
          full_name = excluded.full_name, bio = excluded.bio,
          followers = coalesce(excluded.followers, a.followers),
          following = coalesce(excluded.following, a.following),
          posts = coalesce(excluded.posts, a.posts),
          category = excluded.category, is_private = false,
          status = case when a.status = 'opted_out' then a.status else 'active' end,
          last_collected_at = excluded.last_collected_at
        returning id
        """,
        {**profile.model_dump(), "username": profile.username.lower(), "now": now},
    ).fetchone()
    account_id = row["id"]
    conn.execute(
        """
        insert into public.account_snapshots (account_id, taken_at, followers, following, posts)
        values (%s, %s, %s, %s, %s) on conflict (account_id, taken_at) do nothing
        """,
        (account_id, now, profile.followers, profile.following, profile.posts),
    )
    return account_id


def set_account_status(conn: psycopg.Connection, username: str, status: str) -> UUID | None:
    row = conn.execute(
        "update public.accounts set status = %s, is_private = %s where username = %s returning id",
        (status, status == "private", username.lower()),
    ).fetchone()
    return row["id"] if row else None


@dataclass
class StoredReel:
    id: UUID
    shortcode: str
    permalink: str
    is_new: bool
    comments: int | None


def upsert_reel(
    conn: psycopg.Connection, account_id: UUID, reel: ReelData, now: datetime, source: str
) -> StoredReel:
    """Insert or refresh a reel and record a cleaned metric snapshot."""
    hashtags = reel.hashtags or hashtags_in(reel.caption)
    mentions = reel.mentions or mentions_in(reel.caption)
    row = conn.execute(
        """
        insert into public.reels as r
          (account_id, ig_media_id, shortcode, permalink, posted_at, duration_s, caption,
           hashtags, mentions, audio_name, is_paid_partnership, video_url, thumb_url,
           first_seen_at, likes_hidden, comments_disabled)
        values (%(account_id)s, %(ig_media_id)s, %(shortcode)s, %(permalink)s, %(posted_at)s,
                %(duration_s)s, %(caption)s, %(hashtags)s, %(mentions)s, %(audio_name)s,
                %(is_paid_partnership)s, %(video_url)s, %(thumb_url)s, %(now)s,
                %(likes_hidden)s, %(comments_disabled)s)
        on conflict (ig_media_id) do update set
          caption = excluded.caption, hashtags = excluded.hashtags, mentions = excluded.mentions,
          audio_name = excluded.audio_name, is_paid_partnership = excluded.is_paid_partnership,
          video_url = excluded.video_url, thumb_url = excluded.thumb_url,
          likes_hidden = excluded.likes_hidden, comments_disabled = excluded.comments_disabled,
          is_deleted = false, deleted_at = null
        returning id, (xmax = 0) as inserted
        """,
        {
            **reel.model_dump(),
            "account_id": account_id,
            "hashtags": hashtags,
            "mentions": mentions,
            "now": now,
        },
    ).fetchone()
    reel_id = row["id"]

    prev = conn.execute(
        """
        select views, likes, comments, shares from public.metric_snapshots
         where reel_id = %s and taken_at < %s order by taken_at desc limit 1
        """,
        (reel_id, now),
    ).fetchone()
    clean = clean_snapshot(
        Counts(reel.views, reel.likes, reel.comments, reel.shares),
        Counts(**prev) if prev else None,
    )
    age_h = max(0.0, (now - reel.posted_at).total_seconds() / 3600)
    c = clean.counts
    conn.execute(
        """
        insert into public.metric_snapshots
          (reel_id, taken_at, age_hours, views, likes, comments, shares, flagged, flag_reason, source)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        on conflict (reel_id, taken_at) do nothing
        """,
        (
            reel_id,
            now,
            round(age_h, 2),
            c.views,
            c.likes,
            c.comments,
            c.shares,
            clean.flagged,
            clean.flag_reason,
            source,
        ),
    )
    return StoredReel(reel_id, reel.shortcode, reel.permalink, bool(row["inserted"]), c.comments)


def mark_deleted(
    conn: psycopg.Connection, account_id: UUID, shortcodes: list[str], now: datetime
) -> int:
    """Reels we asked for that the vendor no longer returns: mark deleted, keep snapshots."""
    if not shortcodes:
        return 0
    rows = conn.execute(
        """
        update public.reels set is_deleted = true, deleted_at = %s
         where account_id = %s and shortcode = any(%s) and not is_deleted
        returning id
        """,
        (now, account_id, shortcodes),
    ).fetchall()
    return len(rows)


def store_comments(
    conn: psycopg.Connection, reel_id: UUID, comments: list[CommentData], owner_username: str
) -> int:
    """Upsert comments. Handles are read here (own replies, friend tags), then dropped."""
    owner = owner_username.lower()
    count = 0
    for c in comments:
        author = (c.author_handle or "").lower().lstrip("@")
        tagged = [m for m in mentions_in(c.text) if m != owner]
        conn.execute(
            """
            insert into public.comments as cm
              (reel_id, ig_comment_id, text, posted_at, like_count, reply_count, is_creator, tags_friend)
            values (%s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (ig_comment_id) do update set
              like_count = excluded.like_count, reply_count = excluded.reply_count
            """,
            (
                reel_id,
                c.ig_comment_id,
                mask_mentions(c.text),
                c.posted_at,
                c.like_count,
                c.reply_count,
                author == owner,
                bool(tagged),
            ),
        )
        count += 1
    return count


def stored_comment_count(conn: psycopg.Connection, reel_id: UUID) -> int:
    return conn.execute(
        "select count(*) as n from public.comments where reel_id = %s", (reel_id,)
    ).fetchone()["n"]


def needs_comment_refresh(stored: int, public_count: int | None, limit: int) -> bool:
    """Re-read comments when the public count has grown noticeably past what we hold."""
    if public_count is None or stored >= limit:
        return False
    return public_count > stored * 1.1 + 5
