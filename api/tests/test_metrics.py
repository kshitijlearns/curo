"""Values at an age, rates, baselines and lifts (logic doc §4, §5 step 7)."""

from datetime import UTC, datetime, timedelta

import pytest

from curo.services.metrics import (
    AGE_BUCKETS,
    ReelSeries,
    Snap,
    baseline_at,
    compute_baselines,
    count_at,
    metric_at,
    reel_lifts,
)

T0 = datetime(2027, 8, 1, tzinfo=UTC)


def reel(i, snaps, age_now=1000.0, paid=False):
    return ReelSeries(f"r{i}", T0 - timedelta(days=i), age_now, snaps, paid=paid)


def test_value_between_two_snapshots_is_a_straight_line():
    snaps = [Snap(3, views=1000), Snap(9, views=4000)]
    assert count_at(snaps, "views", 6) == pytest.approx(2500)
    assert count_at(snaps, "views", 9) == 4000


def test_never_extrapolated_before_the_first_snapshot_or_after_the_last():
    snaps = [Snap(30, views=5000), Snap(48, views=7000)]
    assert count_at(snaps, "views", 6) is None
    assert count_at(snaps, "views", 60) is None


def test_settled_rule_for_reels_first_seen_after_30_days():
    snaps = [Snap(900, views=80_000), Snap(1068, views=81_000)]
    assert count_at(snaps, "views", AGE_BUCKETS["30d"]) == 80_000
    assert count_at(snaps, "views", AGE_BUCKETS["7d"]) is None


def test_hidden_counts_stay_unknown_and_drop_out_of_rates():
    r = reel(0, [Snap(24, views=10_000, likes=None, comments=30, shares=None)])
    assert metric_at(r, "likes", 24) is None
    assert metric_at(r, "like_rate", 24) is None  # never 0
    assert metric_at(r, "share_rate", 24) is None
    assert metric_at(r, "comment_rate", 24) == pytest.approx(0.003)


def test_baseline_is_the_median_of_the_last_20_reels_at_that_age():
    reels = [
        reel(i, [Snap(24, views=v, likes=v // 25)])
        for i, v in enumerate([1000, 2000, 3000, 4000, 100_000])
    ]
    b = compute_baselines(reels)[("views", "1d")]
    assert (b.median, b.p25, b.p75, b.n) == (3000, 2000, 4000, 5)
    assert compute_baselines(reels)[("like_rate", "1d")].median == pytest.approx(0.04)
    # Only the newest 3 when the window is 3 (reel 0 is the newest).
    assert compute_baselines(reels, window=3)[("views", "1d")].median == 2000


def test_paid_partnerships_and_too_young_reels_are_left_out():
    reels = [
        reel(0, [Snap(24, views=50_000)], paid=True),
        reel(1, [Snap(24, views=1000)]),
        reel(2, [Snap(24, views=3000)]),
        reel(3, [Snap(6, views=9999)], age_now=10),  # hasn't reached a day yet
    ]
    b = compute_baselines(reels)[("views", "1d")]
    assert b.n == 2 and b.median == 2000


def test_growth_curve_share_of_seven_day_views():
    reels = [reel(i, [Snap(72, views=720 + i), Snap(168, views=1000 + i)]) for i in range(3)]
    g = compute_baselines(reels)[("views_share_7d", "3d")]
    assert g.median == pytest.approx(0.72, abs=0.001)  # logic doc §6: 72% by day 3


def test_baseline_between_buckets_and_at_the_edges():
    reels = [
        reel(i, [Snap(a, views=v, likes=v // 20) for a, v in ((6, 1000), (24, 4000), (720, 9000))])
        for i in range(3)
    ]
    base = compute_baselines(reels)
    assert baseline_at(base, "views", 24) == 4000
    # Log-log between 6 h (1000) and 1 d (4000): halfway in log-age gives the geometric mean.
    assert baseline_at(base, "views", 12) == pytest.approx(2000, rel=0.01)
    assert baseline_at(base, "views", 3) is None  # counts aren't estimated before 6 hours
    assert baseline_at(base, "like_rate", 3) == pytest.approx(0.05)  # rates use the 6 h median
    assert baseline_at(base, "views", 2000) == 9000  # beyond 30 days the settled median holds


def test_lift_at_the_reels_latest_age():
    others = [reel(i + 1, [Snap(24, views=4000, likes=160)]) for i in range(4)]
    mine = reel(0, [Snap(24, views=6000, likes=360)])
    base = compute_baselines([mine, *others])
    lifts = reel_lifts(mine, base)
    assert lifts["views"].lift == pytest.approx(6000 / 4000)
    assert lifts["like_rate"].lift == pytest.approx(0.06 / 0.04)
    assert "share_rate" not in lifts  # unknown, so left out
