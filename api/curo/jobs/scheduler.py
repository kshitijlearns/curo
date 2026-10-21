"""What is due now: the scheduler's tick (MVP doc §4, §9).

Called every few seconds by the scheduler process, and step by step by the seed replay.
It reads CURO's clock, so time travel moves the schedule too. Each tick:

* snapshots: one batched ``snapshot_account`` per account with reels due;
* learning: ``recompute_learning`` for an account once its processed reels have settled
  (nothing of it still queued or running) and something changed since its last run;
* nightly (02:00 in DEFAULT_TIMEZONE): the comment-labelling batch, a catch-up for reels that
  should have DNA but don't, every account's learning (snapshots move baselines), and the
  similar-creator priors;
* jobs saved while Redis was unreachable are handed to the worker again (``curo.queue``).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from curo import clock
from curo.config import get_settings
from curo.db import service_connection
from curo.queue import enqueue_new, redispatch_orphans
from curo.services.schedule import ReelState, discovery_due, due_shortcodes

NIGHTLY_HOUR = 2
DEEP_REELS = 30  # a creator's newest 30 reels always have DNA (MVP doc §9)


def due_accounts(now: datetime) -> list[tuple[UUID, str]]:
    """Active accounts with something to collect: a reel due, or a new-reel check due."""
    with service_connection() as conn:
        accounts = conn.execute(
            """
            select a.id, coalesce(a.last_discovered_at, a.last_collected_at) as last_discovered_at
              from public.accounts a join public.creators c on c.account_id = a.id
             where a.status = 'active' and c.paused_at is null
            """
        ).fetchall()
        if not accounts:
            return []
        reels = conn.execute(
            """
            select r.account_id, r.shortcode, r.posted_at,
                   (select max(m.taken_at) from public.metric_snapshots m where m.reel_id = r.id) as last_taken
              from public.reels r
             where r.account_id = any(%s) and not r.is_deleted and r.posted_at > %s
            """,
            ([a["id"] for a in accounts], now - timedelta(days=91)),
        ).fetchall()
    by_account: dict[UUID, list[ReelState]] = {}
    for r in reels:
        by_account.setdefault(r["account_id"], []).append(
            ReelState(r["shortcode"], r["posted_at"], r["last_taken"])
        )
    out = []
    for a in accounts:
        if due_shortcodes(by_account.get(a["id"], []), now) or discovery_due(
            a["last_discovered_at"], now
        ):
            out.append((a["id"], "creator"))
    return out


def _has_open(account_id: UUID, types: tuple[str, ...]) -> bool:
    with service_connection() as conn:
        return conn.execute(
            """
            select exists(select 1 from public.jobs
                           where status in ('queued', 'running') and type = any(%s)
                             and payload->>'account_id' = %s) as yes
            """,
            (list(types), str(account_id)),
        ).fetchone()["yes"]


def _queue(out: list[str], label: str, job_type: str, payload: dict, key: str) -> None:
    if enqueue_new(job_type, payload, idempotency_key=key):
        out.append(label)


def snapshot_tick(now: datetime) -> list[str]:
    window = f"{now:%Y%m%dT%H}{now.minute // 15}"
    out: list[str] = []
    for account_id, _role in due_accounts(now):
        if _has_open(account_id, ("snapshot_account",)):
            continue
        _queue(
            out,
            f"snapshot_account:{account_id}",
            "snapshot_account",
            {"account_id": str(account_id)},
            f"snapshot:{account_id}:{window}",
        )
    return out


def learning_tick(now: datetime) -> list[str]:
    """Learning for accounts whose DNA changed since their last learning run, once nothing
    for them is still being processed (so a batch of 30 reels triggers one run, not 30)."""
    with service_connection() as conn:
        rows = conn.execute(
            """
            select a.id from public.accounts a
             where exists (
                   select 1 from public.reel_dna d join public.reels r on r.id = d.reel_id
                    where r.account_id = a.id
                      and d.updated_at > coalesce(
                          (select max(j.finished_at) from public.jobs j
                            where j.type = 'recompute_learning' and j.status = 'succeeded'
                              and j.payload->>'account_id' = a.id::text),
                          '-infinity'::timestamptz))
               and not exists (
                   select 1 from public.jobs j
                    where j.status in ('queued', 'running')
                      and j.type in ('process_reel', 'recompute_learning')
                      and j.payload->>'account_id' = a.id::text)
            """
        ).fetchall()
    window = f"{now:%Y%m%dT%H}{now.minute // 15}"
    out: list[str] = []
    for r in rows:
        _queue(
            out,
            f"recompute_learning:{r['id']}",
            "recompute_learning",
            {"account_id": str(r["id"])},
            f"learn:{r['id']}:{window}",
        )
    return out


def nightly_tick(now: datetime) -> list[str]:
    local = now.astimezone(ZoneInfo(get_settings().default_timezone))
    if local.hour != NIGHTLY_HOUR:
        return []
    day = f"{local:%Y%m%d}"
    out: list[str] = []
    with service_connection() as conn:
        done = conn.execute(
            "select 1 from public.jobs where idempotency_key = %s", (f"nightly:priors:{day}",)
        ).fetchone()
    if done:  # tonight's batch is already queued
        return []
    with service_connection() as conn:
        unlabelled = conn.execute(
            """
            select distinct r.account_id from public.comments c join public.reels r on r.id = c.reel_id
             where c.labelled_at is null and not c.is_creator
            """
        ).fetchall()
        missing_dna = conn.execute(
            """
            select r.id, r.account_id from public.creators cr
              join lateral (
                select id, account_id from public.reels
                 where account_id = cr.account_id and not is_deleted
                 order by posted_at desc limit %s) r on true
             where not exists (select 1 from public.reel_dna d where d.reel_id = r.id)
            """,
            (DEEP_REELS,),
        ).fetchall()
        learners = conn.execute(
            """
            select distinct r.account_id from public.reel_dna d join public.reels r on r.id = d.reel_id
             union
            select account_id from public.creators where account_id is not null
            """
        ).fetchall()
        creators = conn.execute(
            "select id from public.creators where account_id is not null and paused_at is null"
        ).fetchall()
    for r in unlabelled:
        aid = r["account_id"]
        _queue(
            out,
            f"label_comments:{aid}",
            "label_comments",
            {"account_id": str(aid)},
            f"nightly:label:{aid}:{day}",
        )
    for r in missing_dna:
        _queue(
            out,
            f"process_reel:{r['id']}",
            "process_reel",
            {"reel_id": str(r["id"]), "account_id": str(r["account_id"])},
            f"nightly:process:{r['id']}:{day}",
        )
    # Priors first: each creator's run blends its own effects with them.
    _queue(
        out,
        "recompute_learning:priors",
        "recompute_learning",
        {"priors": True},
        f"nightly:priors:{day}",
    )
    for r in learners:
        aid = r["account_id"]
        _queue(
            out,
            f"recompute_learning:{aid}",
            "recompute_learning",
            {"account_id": str(aid)},
            f"nightly:learn:{aid}:{day}",
        )
    # Trend data, then each creator's opportunities (logic doc §8: refreshed every night).
    _queue(out, "collect_hashtags", "collect_hashtags", {}, f"nightly:hashtags:{day}")
    # The shared trend feed, once per niche (PLAN_V2 §4.4).
    _queue(out, "trend_feed", "trend_feed", {}, f"nightly:trends:{day}")
    for c in creators:
        _queue(
            out,
            f"build_opportunities:{c['id']}",
            "build_opportunities",
            {"creator_id": str(c["id"])},
            f"nightly:opps:{c['id']}:{day}",
        )
    # Deletion requests, old uploads, leftover videos (MVP doc §9: daily).
    _queue(out, "cleanup", "cleanup", {}, f"nightly:cleanup:{day}")
    if local.weekday() == 0:
        # Estimates against what posted reels did at day 7 (MVP doc §9: weekly).
        _queue(out, "accuracy_report", "accuracy_report", {}, f"weekly:accuracy:{day}")
    return out


def tick(now: datetime | None = None) -> list[str]:
    """Enqueue whatever is due. Returns "type:target" for each job this tick created or
    handed over again."""
    now = now or clock.now()
    pause_inactive(now)
    return redispatch_orphans(now) + snapshot_tick(now) + learning_tick(now) + nightly_tick(now)


def pause_inactive(now: datetime) -> int:
    """Creators who haven't opened the app in INACTIVE_PAUSE_DAYS stop being collected and
    processed (PLAN_V2 §4.3). Their next sign-in resumes them with one catch-up run."""
    with service_connection() as conn:
        return conn.execute(
            """
            update public.creators set paused_at = %s
             where paused_at is null and last_seen_at is not null and last_seen_at < %s
            """,
            (now, now - timedelta(days=get_settings().inactive_pause_days)),
        ).rowcount
