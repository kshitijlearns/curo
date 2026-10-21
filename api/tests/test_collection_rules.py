"""Pure collection rules: text helpers, data quality and the snapshot schedule."""

from datetime import UTC, datetime, timedelta

from curo.services.data_quality import Counts, clean_snapshot
from curo.services.schedule import (
    ReelState,
    comment_read_due,
    discovery_due,
    due_shortcodes,
    interval_h,
    is_due,
    is_paused,
    planned_snapshots,
)
from curo.services.text import hashtags_in, is_emoji_only, mask_mentions, mentions_in, reel_title

T0 = datetime(2027, 8, 1, tzinfo=UTC)


# ---------------------------------------------------------------- text


def test_hashtags_and_mentions():
    caption = (
        "One kurta, five dupattas #DupattaStyling #ethnicstyling #dupattastyling @Glowlab.example"
    )
    assert hashtags_in(caption) == ["dupattastyling", "ethnicstyling"]
    assert mentions_in(caption) == ["glowlab.example"]


def test_mentions_are_masked_so_no_third_party_handle_is_stored():
    assert mask_mentions("@riya.k this is so you, ask @meera_s") == "@… this is so you, ask @…"


def test_emoji_only_comments():
    assert is_emoji_only("😍😍")
    assert is_emoji_only("🔥 🔥")
    assert not is_emoji_only("so pretty 😍")


def test_reel_title_from_caption():
    assert reel_title(
        "3 mistakes ruining your aesthetic reel 🎥 Number 2 is the one #reeltips"
    ) == ("3 mistakes ruining your aesthetic reel")
    assert reel_title("Get ready with me: Navratri edition ✨ lehenga, jhumkas #grwm") == (
        "Get ready with me: Navratri edition"
    )
    assert reel_title("Thrift haul under ₹2,000 🛍️ everything I found") == "Thrift haul under ₹2,000"
    assert reel_title("#ad") == "Untitled reel"


# ---------------------------------------------------------------- data quality (MVP doc §4)


def test_hidden_likes_missing_shares_and_comments_off_stay_null_never_zero():
    clean = clean_snapshot(Counts(1000, None, None, None), Counts(800, None, None, None))
    assert clean.counts == Counts(1000, None, None, None)
    assert not clean.flagged


def test_lower_snapshot_keeps_previous_value_and_is_flagged():
    clean = clean_snapshot(Counts(950, 40, 10, 5), Counts(1000, 38, 12, 5))
    assert clean.counts == Counts(1000, 40, 12, 5)
    assert clean.flagged
    assert clean.flag_reason == "views_decreased,comments_decreased"


def test_count_that_becomes_hidden_is_unknown_not_carried_over():
    # likes were public, now hidden: unknown (None), not the old value and not 0
    clean = clean_snapshot(Counts(2000, None, 20, 9), Counts(1500, 60, 15, 7))
    assert clean.counts.likes is None


def test_first_snapshot_has_nothing_to_compare():
    assert not clean_snapshot(Counts(10, 1, 0, 0), None).flagged


# ---------------------------------------------------------------- schedule (v2, PLAN_V2 §4.3)


def test_schedule_6h_to_48h_daily_to_day_7_weekly_to_day_30_then_stop():
    assert interval_h(0) == 6
    assert interval_h(47.9) == 6
    assert interval_h(48) == 24
    assert interval_h(7 * 24) == 168
    assert interval_h(29 * 24) == 168
    assert interval_h(30 * 24) is None  # stop at day 30


def test_a_reel_gets_18_planned_snapshots():
    ages = planned_snapshots()
    assert ages == [0, 6, 12, 18, 24, 30, 36, 42, 48, 72, 96, 120, 144, 168, 336, 504, 672, 720]
    assert len(ages) == 18


def test_due_follows_the_interval():
    posted = T0
    assert is_due(posted, None, posted + timedelta(hours=1))  # never snapshotted
    last = posted + timedelta(hours=1)
    assert not is_due(posted, last, posted + timedelta(hours=5))  # the 6-hour mark not reached
    assert is_due(posted, last, posted + timedelta(hours=6))  # at the planned 6 h
    week = posted + timedelta(hours=144)
    assert not is_due(posted, week, posted + timedelta(hours=160))
    assert is_due(posted, week, posted + timedelta(hours=168))  # exactly 7 days, for baselines
    old = T0 - timedelta(days=32)
    assert not is_due(old, None, T0)  # past day 30: not tracked


def test_batch_lists_only_due_reels():
    now = T0 + timedelta(days=10)
    reels = [
        ReelState("fresh", now - timedelta(hours=13), now - timedelta(hours=7)),  # 12 h: due
        ReelState("day5", now - timedelta(hours=123), now - timedelta(hours=2)),  # next at 144 h
        ReelState("day21", now - timedelta(days=21), now - timedelta(days=7)),  # 21 d: due
    ]
    assert due_shortcodes(reels, now) == ["fresh", "day21"]


def test_new_reel_check_every_12_hours():
    assert discovery_due(None, T0)
    assert not discovery_due(T0 - timedelta(hours=6), T0)
    assert discovery_due(T0 - timedelta(hours=12), T0)


def test_comments_are_re_read_only_at_24_hours_and_7_days():
    assert not comment_read_due(T0, 0, T0 + timedelta(hours=23))
    assert comment_read_due(T0, 0, T0 + timedelta(hours=24))
    assert not comment_read_due(T0, 1, T0 + timedelta(days=6))
    assert comment_read_due(T0, 1, T0 + timedelta(days=7))
    assert not comment_read_due(T0, 2, T0 + timedelta(days=60))  # never a third time


def test_a_creator_away_14_days_is_paused():
    assert not is_paused(None, T0, 14)
    assert not is_paused(T0 - timedelta(days=13), T0, 14)
    assert is_paused(T0 - timedelta(days=14), T0, 14)
