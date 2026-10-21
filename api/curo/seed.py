"""Seed loader: reference data and the demo creator.

    python -m curo.seed calendar            # load the festival calendar
    python -m curo.seed demo [--reset]      # replay the demo creator's collection

The demo replay loads the fixture dataset through the SAME code path a real scrape uses:
it sets CURO's clock 14 days before the dataset's anchor, onboards @curo.demo with the real
``onboard_public`` job, then steps the clock forward hour by hour running the real
scheduler. Reels posted during those 14 days get genuine snapshot histories from their
first hours; older reels are "seen late". Finally the clock returns to FAKE_NOW.

Sign in as demo@curo.local to see it, or sign up with any email and enter @curo.demo.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time
from datetime import timedelta

from curo import clock
from curo.config import REPO_ROOT, get_settings
from curo.db import service_connection

DEMO_EMAIL = "demo@curo.local"
DEMO_HANDLE = "curo.demo"
FIXTURES = REPO_ROOT / "fixtures" / "data"
PAUSE_KEY = "curo:scheduler:paused"


def load_calendar() -> int:
    events = json.loads((FIXTURES / "festivals.json").read_text(encoding="utf-8"))
    with service_connection() as conn:
        for e in events:
            conn.execute(
                """
                insert into public.festival_calendar
                  (id, name, starts_on, ends_on, regions, niches, keywords, verified)
                values (%(id)s, %(name)s, %(starts_on)s, %(ends_on)s, %(regions)s, %(niches)s,
                        %(keywords)s, %(verified)s)
                on conflict (id) do update set name = excluded.name, starts_on = excluded.starts_on,
                  ends_on = excluded.ends_on, regions = excluded.regions, niches = excluded.niches,
                  keywords = excluded.keywords, verified = excluded.verified
                """,
                e,
            )
    return len(events)


def ensure_user(email: str):
    with service_connection() as conn:
        return conn.execute(
            """
            insert into auth.users (email) values (%s)
            on conflict (email) do update set email = excluded.email returning id
            """,
            (email,),
        ).fetchone()["id"]


def _demo_account_id():
    with service_connection() as conn:
        return conn.execute(
            "select id from public.accounts where username = %s", (DEMO_HANDLE,)
        ).fetchone()["id"]


def reset_demo() -> None:
    """Remove the demo creator and every fixture account (cascades to their data)."""
    meta = json.loads((FIXTURES / "meta.json").read_text(encoding="utf-8"))
    usernames = [meta["demo_handle"], *meta.get("peers", [])]
    with service_connection() as conn:
        conn.execute("delete from auth.users where email = %s", (DEMO_EMAIL,))
        conn.execute("delete from public.accounts where username = any(%s)", (usernames,))
        conn.execute("delete from public.jobs where creator_id is null")
        # The replay starts 14 days earlier: pages fetched "later" would otherwise look fresh.
        conn.execute("delete from public.hashtag_pages")


def seed_demo(
    days: float = 14, step_h: float = 1.0, reset: bool = False, quiet: bool = False
) -> dict:
    # Jobs run in this process, one after another, at each replayed moment.
    os.environ["QUEUE_MODE"] = "inline"
    get_settings.cache_clear()
    settings = get_settings()
    if settings.provider("public_data") != "mock":
        raise SystemExit("The demo replay needs the mock public-data provider (MOCK_MODE=true).")

    from curo.jobs.scheduler import tick
    from curo.providers.public_data.mock import MockPublicDataProvider
    from curo.queue import enqueue
    from curo.redis_client import get_redis

    def say(msg: str) -> None:
        if not quiet:
            print(msg, flush=True)

    anchor = MockPublicDataProvider().anchor
    with service_connection() as conn:
        existing = conn.execute(
            "select c.id from public.creators c join auth.users u on u.id = c.user_id where u.email = %s",
            (DEMO_EMAIL,),
        ).fetchone()
    if existing and not reset:
        raise SystemExit("The demo is already seeded. Run with --reset to replay it from scratch.")
    if reset:
        reset_demo()

    n_events = load_calendar()
    say(f"festival calendar: {n_events} events")

    with contextlib.suppress(Exception):  # pause the live scheduler so it doesn't race the replay
        get_redis().set(PAUSE_KEY, "seed", ex=3600)
    started = time.monotonic()
    try:
        user_id = ensure_user(DEMO_EMAIL)
        with service_connection() as conn:
            creator_id = conn.execute(
                """
                insert into public.creators (user_id, ig_username) values (%s, %s)
                on conflict (user_id) do update set ig_username = excluded.ig_username
                returning id
                """,
                (user_id, DEMO_HANDLE),
            ).fetchone()["id"]

        t = anchor - timedelta(days=days)
        clock.set_time(t, frozen=True)
        say(f"onboarding @{DEMO_HANDLE} at {t.isoformat()}")
        enqueue(
            "onboard_public",
            {"username": DEMO_HANDLE},
            creator_id=creator_id,
            idempotency_key=f"seed:onboard:{creator_id}:{t:%Y%m%dT%H%M}",
        )
        enqueue("collect_hashtags", {}, idempotency_key=f"seed:hashtags:{t:%Y%m%dT%H%M}")
        runs = 0
        while t < anchor:
            t = min(anchor, t + timedelta(hours=step_h))
            clock.set_time(t, frozen=True)
            runs += sum(1 for name in tick(t) if name.startswith("snapshot_account"))
            if not quiet and t.hour == 0 and t.minute < step_h * 60:
                say(f"  {t:%Y-%m-%d}  snapshot runs so far: {runs}")
        # Bring the learned data up to the anchor moment (the nightly run was hours ago).
        account_id = _demo_account_id()
        stamp = f"{t:%Y%m%dT%H%M}"
        for job_type, payload, key in (
            ("label_comments", {"account_id": str(account_id)}, f"seed:label:{account_id}"),
            ("recompute_learning", {"priors": True}, "seed:priors"),
            ("recompute_learning", {"account_id": str(account_id)}, f"seed:learn:{account_id}"),
            ("collect_hashtags", {}, "seed:hashtags"),
            ("trend_feed", {}, "seed:trends"),
            ("build_opportunities", {"creator_id": str(creator_id)}, f"seed:opps:{creator_id}"),
        ):
            enqueue(job_type, payload, idempotency_key=f"{key}:{stamp}")
    finally:
        clock.reset()
        with contextlib.suppress(Exception):
            get_redis().delete(PAUSE_KEY)

    with service_connection() as conn:
        counts = conn.execute(
            """
            select
              (select count(*) from public.reels r join public.accounts a on a.id = r.account_id
                where a.username = %(h)s) as reels,
              (select count(*) from public.metric_snapshots m join public.reels r on r.id = m.reel_id
                 join public.accounts a on a.id = r.account_id where a.username = %(h)s) as snapshots,
              (select count(*) from public.comments c join public.reels r on r.id = c.reel_id
                 join public.accounts a on a.id = r.account_id where a.username = %(h)s) as comments,
              (select count(*) from public.reel_dna d join public.reels r on r.id = d.reel_id
                 join public.accounts a on a.id = r.account_id where a.username = %(h)s) as with_dna,
              (select count(*) from public.pattern_cards p join public.accounts a on a.id = p.account_id
                where a.username = %(h)s) as pattern_cards
            """,
            {"h": DEMO_HANDLE},
        ).fetchone()
    summary = {**counts, "snapshot_runs": runs, "seconds": round(time.monotonic() - started, 1)}
    say(f"done: {summary}")
    if settings.fake_now is None or clock.to_utc(settings.fake_now) != anchor:
        say(f"note: set FAKE_NOW={anchor.isoformat()} in .env to see the demo at its anchor time")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CURO seed loader")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("calendar")
    p_demo = sub.add_parser("demo")
    p_demo.add_argument("--reset", action="store_true")
    p_demo.add_argument("--days", type=float, default=14)
    args = parser.parse_args(argv)
    if args.cmd == "calendar":
        print(f"loaded {load_calendar()} festival events")
    else:
        seed_demo(days=args.days, reset=args.reset)
    return 0


if __name__ == "__main__":
    sys.exit(main())
