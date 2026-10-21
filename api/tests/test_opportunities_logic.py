"""Opportunity scoring, merging and momentum (logic doc §8; v2 PLAN_V2 §4.1, no peers)."""

from datetime import UTC, date, datetime, timedelta

import pytest

from curo.services import opportunities as opp
from curo.services import topics

TODAY = date(2027, 8, 23)


# ---------------------------------------------------------------- the score formula


def test_the_v2_worked_example_ganpati_is_7_6_of_10():
    """PLAN_V2 §4.1: F 0.66, D 0.80, T 1.00, O 0.55 →
    0.35×0.66 + 0.25×0.80 + 0.25×1.00 + 0.15×0.55 = 0.231 + 0.200 + 0.250 + 0.0825 = 0.7635."""
    parts = {"F": 0.66, "D": 0.80, "T": 1.00, "O": 0.55}
    total = sum(opp.WEIGHTS[k] * v for k, v in parts.items())
    assert total == pytest.approx(0.7635)
    assert round(10 * total, 1) == 7.6
    assert opp.WEIGHTS == {"F": 0.35, "D": 0.25, "T": 0.25, "O": 0.15}
    assert "P" not in opp.PART_NAMES


def test_timeliness_window_peaks_7_to_14_days_before_and_drops_after():
    assert opp.window_credit(12, during=False) == 1.0
    assert opp.window_credit(7, during=False) == 1.0
    assert opp.window_credit(30, during=False) == pytest.approx(0.4)
    assert opp.window_credit(3, during=False) == pytest.approx(0.6 + 0.4 * 3 / 7)
    assert opp.window_credit(0, during=True) == 0.5
    assert opp.window_credit(-2, during=False) == 0.0


def test_lift_credit_half_at_usual_full_at_one_and_a_half():
    assert opp.lift_credit(1.0) == 0.5
    assert opp.lift_credit(1.5) == 1.0
    assert opp.lift_credit(0.4) == 0.0
    assert opp.lift_credit(None) == 0.5


def ctx(_unused=None, **kw):
    return opp.Context(
        today=TODAY,
        subclusters=kw.get("subclusters", []),
        creator_formats=kw.get("formats", {}),
        comments=kw.get("comments", []),
        comment_regions=kw.get("regions", {}),
        hashtag_growth=kw.get("growth", {}),
        hashtag_reels_7d=kw.get("reels_7d", {}),
    )


def test_openness_reads_the_trend_cards_saturation_else_the_hashtags_recent_reels():
    from_feed = opp.Candidate(
        "trend:tag:festivelook",
        "trend",
        {"festivelook"},
        anchors={"festivelook"},
        hashtags={"festivelook"},
        trend={"key": "tag:festivelook", "saturation": "low", "momentum": 1.8},
    )
    assert opp.part_o(from_feed, ctx()).value == 0.9
    by_tag = opp.Candidate("tag:x", "trend", {"x"}, anchors={"x"}, hashtags={"ganpatioutfit"})
    part = opp.part_o(by_tag, ctx(reels_7d={"ganpatioutfit": 120}))
    assert part.value == 0.6  # 50–199 new reels in a week: medium
    assert part.facts == ["#ganpatioutfit had 120 new reels in the last 7 days (medium)."]
    # Nothing measures it: neither open nor crowded.
    unmeasured = opp.Candidate("theme:asks the price", "audience", {"price", "please"})
    assert opp.part_o(unmeasured, ctx()).value == 0.7


def test_timeliness_uses_the_trend_cards_momentum_when_no_hashtag_is_indexed():
    c = opp.Candidate(
        "trend:format:grwm",
        "trend",
        {"grwm"},
        anchors={"grwm"},
        trend={"key": "format:grwm", "momentum": 2.1, "why_rising": "More GRWM posts this week."},
    )
    part = opp.part_t(c, ctx())
    assert part.value == pytest.approx((2.1 - 1) / 1.25)


def test_timeliness_uses_the_festival_window_and_posting_momentum():
    fest = {
        "name": "Ganesh Chaturthi",
        "starts_on": date(2027, 9, 4),
        "ends_on": date(2027, 9, 14),
        "regions": ["IN", "IN-MH"],
    }
    c = opp.Candidate(
        "festival:g",
        "trend",
        {"ganpati"},
        anchors={"ganpati"},
        hashtags={"ganpatioutfit"},
        festival=fest,
    )
    part = opp.part_t(c, ctx([], growth={"ganpatioutfit": 2.1}))
    assert part.value == pytest.approx(0.6 * 1.0 + 0.4 * (2.1 - 1) / 1.25)
    assert part.facts[0] == "Ganesh Chaturthi starts in 12 days."


def test_places_in_comments_matching_a_regional_festival_raise_demand():
    fest = {
        "name": "G",
        "starts_on": date(2027, 9, 4),
        "ends_on": date(2027, 9, 14),
        "regions": ["IN", "IN-MH"],
    }
    c = opp.Candidate("festival:g", "trend", {"ganpati"}, anchors={"ganpati"}, festival=fest)
    comments = [
        {
            "text": "ganpati outfit next please",
            "intent": "request",
            "theme_key": None,
            "reel_id": "r",
        }
    ] + [{"text": "so pretty", "intent": "praise", "theme_key": None, "reel_id": "r"}] * 19
    here = opp.part_d(c, None, ctx([], comments=comments, regions={"IN-MH": 3}))
    elsewhere = opp.part_d(c, None, ctx([], comments=comments, regions={"IN-DL": 3}))
    assert here.value > elsewhere.value
    assert "5.0% of your recent comments ask about it." in here.facts


# ---------------------------------------------------------------- merging and filters


def test_candidates_sharing_a_defining_tag_merge_and_the_first_source_shows():
    fest = opp.Candidate(
        "festival:g",
        "trend",
        {"ganpati"},
        anchors={"ganpati", "ganpatioutfit"},
        festival={"name": "G"},
    )
    yours = opp.Candidate(
        "sub:ganpati",
        "your_content",
        {"ganpati"},
        anchors={"ganpatioutfit", "ganpati"},
        texts=["x"],
    )
    reveal = opp.Candidate(
        "tag:revealfirst", "trend", {"revealfirst"}, anchors={"revealfirst"}, texts=["#revealfirst"]
    )
    merged = opp.merge([reveal, yours, fest], {})
    keys = sorted(c.key for c in merged)
    assert keys == ["festival:g", "tag:revealfirst"]
    ganpati = next(c for c in merged if c.key == "festival:g")
    assert ganpati.tag == "trend"  # trends rank first (logic doc §8; v2 has no peers)


def test_one_mention_does_not_merge_two_topics():
    ganpati = opp.Candidate(
        "peers:g", "competitor", {"ganpati"}, anchors={"ganpati"},
        texts=["Ganpati look #revealfirst", "Ganpati looks", "Ganpati drapes"],
    )  # fmt: skip
    reveal = opp.Candidate(
        "tag:revealfirst", "trend", {"revealfirst"}, anchors={"revealfirst"}, texts=["#revealfirst"]
    )
    assert len(opp.merge([ganpati, reveal], {})) == 2


def test_an_audience_theme_joins_the_topic_its_comments_name():
    festival = opp.Candidate("festival:g", "trend", {"ganpati"}, anchors={"ganpati"})
    theme = opp.Candidate(
        "theme:wants festive looks", "audience", set(), themes=[{"key": "wants festive looks", "label": "Wants festive looks", "share": 0.04, "n": 5, "phrase": "want festive looks"}]
    )  # fmt: skip
    comments = {
        "wants festive looks": [
            {"text": t, "reel_id": "r"}
            for t in (
                "please do one for Ganpati",
                "Ganpati outfit ideas next please",
                "Navratri looks next pls",
            )
        ]
    }
    merged = opp.merge([festival, theme], comments)
    assert len(merged) == 1 and merged[0].themes and merged[0].sources == {"trend", "audience"}


def test_topics_posted_in_the_last_two_weeks_and_unsafe_topics_are_dropped():
    c = opp.Candidate("festival:g", "trend", {"ganpati"}, anchors={"ganpati"})
    assert opp.posted_recently(c, [{"caption": "My Ganpati look", "hashtags": []}])
    assert not opp.posted_recently(c, [{"caption": "Monsoon GRWM", "hashtags": ["grwm"]}])
    risky = opp.Candidate("tag:x", "trend", {"betting"}, anchors={"betting"})
    assert opp.unsafe(risky, set())
    assert opp.unsafe(c, {"ganpati"})  # the creator blocked it


# ---------------------------------------------------------------- momentum in CURO's index


def test_daily_counts_scale_a_partly_seen_day_and_fill_empty_days():
    fetched = datetime(2027, 8, 23, 6, tzinfo=UTC)
    oldest = datetime(2027, 8, 21, 12, tzinfo=UTC)  # the page reaches back to noon on the 21st
    posted = [oldest + timedelta(hours=h) for h in (0, 1, 2, 30)]  # 3 on the 21st, 1 on the 22nd
    counts = topics.daily_counts(posted, fetched, oldest)
    assert counts["2027-08-21"] == [6.0, 0.5]  # 3 reels in half a day → 6 a day
    assert counts["2027-08-22"] == [1.0, 1.0]
    assert "2027-08-23" not in counts  # today isn't over
    merged = topics.merge_counts({"2027-08-21": [9.0, 1.0]}, counts)
    assert merged["2027-08-21"] == [9.0, 1.0]  # the better-covered count wins


def test_growth_is_the_last_7_days_against_the_28_before():
    counts = {
        (TODAY - timedelta(days=d)).isoformat(): [20.0 if d <= 7 else 10.0, 1.0]
        for d in range(1, 36)
    }
    assert topics.growth(counts, TODAY) == 2.0
    assert topics.growth({TODAY.isoformat(): [5.0, 1.0]}, TODAY) is None  # too little history


def test_mentions_matches_words_tags_and_phrases():
    assert topics.mentions("My Ganpati look", [], {"ganpati"})
    assert topics.mentions("look", ["ganpatioutfit"], {"ganpati"})
    assert topics.mentions("Ganesh Chaturthi plans", [], {"ganesh chaturthi"})
    assert not topics.mentions("pandalwala", [], {"pan"})
    assert topics.keyword_tags(["ganpati outfit", "Ganesh Chaturthi"]) == {
        "ganpatioutfit",
        "ganeshchaturthi",
    }


# ---------------------------------------------------------------- peer suggestions
