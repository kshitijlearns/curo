"""Arrows, phases, audience cards, top comment and the no-new-numbers check (logic doc §6–7)."""

import pytest

from curo.providers.llm.mock import MockLLMProvider
from curo.schemas.tasks import T10, T10Input
from curo.services import audience, phases, validator
from curo.services.arrows import FLAT_BAND, Arrow, arrows_for, change, growth_share
from curo.services.metrics import Baseline, Snap
from curo.services.top_comment import top_comment


def b(median, n=10):
    return Baseline(median, median, median, n)


# ---------------------------------------------------------------- arrows


def test_the_logic_docs_worked_example_up_32_percent():
    """ "3 mistakes" is 3 days old with 90K views; the Simulator predicted 95K by day 7; this
    creator's reels reach 72% of their 7-day views by day 3: 95K × 0.72 = 68.4K → +32%."""
    baselines = {("views_share_7d", "3d"): b(0.72), ("views_share_7d", "7d"): b(1.0)}
    arrows = arrows_for({"views": 90_000}, 72, baselines, prediction_7d={"views": 95_000})
    a = arrows["views"]
    assert a.expected == pytest.approx(68_400)
    assert a.percent == 32 and a.direction == "up" and a.compared_with == "simulation"


def test_without_a_simulation_the_usual_at_the_same_age():
    baselines = {("views", "1d"): b(10_000), ("views", "3d"): b(20_000)}
    a = arrows_for({"views": 15_000, "likes": None}, 24, baselines)
    assert a["views"].expected == 10_000 and a["views"].percent == 50
    assert a["views"].compared_with == "usual"
    assert "likes" not in a  # hidden likes: no arrow, never a zero


def test_small_changes_are_flat_and_thin_history_gives_no_arrow():
    assert Arrow("views", 104, 100, change(104, 100), "usual").direction == "flat"
    assert Arrow("views", 94, 100, change(94, 100), "usual").direction == "down"
    assert FLAT_BAND == 0.05
    thin = {("views", "1d"): b(10_000, n=2), ("views", "3d"): b(20_000, n=2)}
    assert arrows_for({"views": 15_000}, 24, thin) == {}


def test_growth_share_beyond_seven_days_is_the_full_prediction():
    baselines = {("views_share_7d", "3d"): b(0.72), ("views_share_7d", "7d"): b(1.0)}
    assert growth_share(baselines, 72) == pytest.approx(0.72)
    assert growth_share(baselines, 400) == 1.0


# ---------------------------------------------------------------- phases


def snaps(points):
    return [Snap(a, views=v) for a, v in points]


FOLLOWERS = 10_000


def phase_of(points, followers=FOLLOWERS, from_posting=True):
    tl = phases.timeline(snaps(points), followers, from_posting)
    return tl[-1][2]


def test_testing_while_young_and_below_the_follower_count():
    assert phase_of([(3, 500), (6, 1500)]) == "testing"
    # Past the follower count already: no longer just followers, so the velocity rules apply.
    assert phase_of([(3, 6000), (6, 12_000)]) != "testing"


def test_growing_when_velocity_rose():
    # 500/h, then 1000/h, then 2000/h after the first day.
    assert phase_of([(24, 12_000), (36, 24_000), (48, 48_000)]) == "growing"


def test_peak_slowing_and_long_tail():
    base = [(24, 12_000), (36, 36_000)]  # 500/h then 2000/h (peak)
    assert phase_of([*base, (48, 55_000)]) == "peak"  # 1583/h: within 80%, not rising
    assert phase_of([*base, (48, 50_000)]) == "peak"  # 1167/h: 58%, not rising (D11)
    assert phase_of([*base, (48, 45_000)]) == "slowing"  # 750/h: below half
    tail = [*base, (48, 45_000), (72, 46_000), (96, 46_500), (120, 46_700)]
    assert phase_of(tail) == "longtail"  # below 10% of the peak for 48 hours
    assert phase_of([*base, (48, 45_000), (72, 46_000)]) == "slowing"  # not 48 hours yet


def test_precedence_testing_before_everything():
    # Rising fast but still under a day old and below the follower count.
    assert phase_of([(3, 300), (6, 1500), (12, 6000)]) == "testing"


def test_a_late_reel_is_estimated_from_the_creators_usual_timeline():
    tl = phases.timeline(
        snaps([(24, 12_000), (36, 36_000), (48, 45_000), (120, 46_700)]), FOLLOWERS, True
    )
    stats = phases.phase_stats([tl, tl])
    assert phases.estimate_by_age(stats, 10) == "testing"
    assert phases.estimate_by_age(stats, 2000) == "longtail"


def test_usual_range_wording():
    stats = phases.PhaseStats(
        durations={
            "peak": [30, 40, 60, 70],
            "growing": [3, 5],
            "testing": [],
            "slowing": [],
            "longtail": [],
        },
        starts={
            "longtail": [200, 240, 260],
            "peak": [],
            "growing": [],
            "testing": [],
            "slowing": [],
        },
    )
    assert phases.usual_range(stats, "peak") == "1 – 3 days"
    assert phases.usual_range(stats, "growing") == "4 hours"  # quartiles 3.5 h and 4.5 h
    assert phases.usual_range(stats, "longtail") == "Day 10+"
    assert phases.usual_range(stats, "slowing") is None  # not enough reels to say


def test_beyond_your_followers_only_when_views_pass_twice_the_follower_count():
    assert "beyond your followers" in phases.description("peak", 31_000, FOLLOWERS)
    assert "3×" in phases.description("peak", 31_000, FOLLOWERS)
    assert phases.description("peak", 15_000, FOLLOWERS) == "Views are climbing fast."
    assert phases.description("slowing", 50_000, FOLLOWERS) == "Views are slowing down."


# ---------------------------------------------------------------- audience cards

HISTORY = [0.8, 0.9, 1.0, 1.0, 1.1, 1.2, 0.95, 1.05]


def test_z_scores_need_history():
    assert audience.zscore(1.5, HISTORY) > 2
    assert audience.zscore(1.5, HISTORY[:3]) is None


def test_strongest_positive_always_shown_and_a_clearly_low_rate_gets_a_card():
    lifts = {"comment_rate": 1.4, "share_rate": 0.5, "like_rate": 1.15}
    history = {m: HISTORY for m in lifts}
    ev = audience.Evidence(
        comments=50, intents={"thats_me": 20, "question": 9}, ending="choice_question", cta="none"
    )
    cards = audience.select_cards(lifts, history, ev)
    keys = [c.key for c in cards]
    assert keys[0] == "comments_high"  # strongest positive first
    assert "shares_low" in keys  # z ≤ −1 must be covered
    comments = cards[0]
    assert comments.title == "Comments are driving engagement"
    assert "40% of comments say the reel describes them." in comments.facts
    assert "The reel ends on a question." in comments.facts


def test_comment_cards_fill_free_slots():
    ev = audience.Evidence(comments=100, tags=14, top_theme=("Asks where it's from", 30))
    cards = audience.select_cards({}, {}, ev)
    assert [c.title for c in cards] == [
        "People are tagging friends",
        "Comments ask where it's from",
    ]
    assert cards[1].facts == ["30% of comments on this reel ask where it's from."]


def test_never_more_than_three_cards():
    lifts = {"comment_rate": 2.0, "share_rate": 0.3, "like_rate": 1.8}
    history = {m: HISTORY for m in lifts}
    ev = audience.Evidence(comments=100, tags=30, follower_ratio=4.0, brought_most_views=True)
    assert len(audience.select_cards(lifts, history, ev)) == 3


# ---------------------------------------------------------------- top comment


def test_top_comment_by_likes_then_replies_skipping_own_bots_and_emoji():
    comments = [
        {"text": "😍😍", "like_count": 900, "reply_count": 0},
        {"text": "Thank you!", "like_count": 500, "reply_count": 3, "is_creator": True},
        {"text": "Promote your page DM us", "like_count": 400, "reply_count": 0, "is_bot": True},
        {"text": "where is this from?", "like_count": 50, "reply_count": 2},
        {"text": "love the mustard one", "like_count": 50, "reply_count": 9},
    ]
    top = top_comment(comments)
    assert (top.text, top.likes, top.replies, top.negative) == (
        "love the mustard one",
        50,
        9,
        False,
    )


def test_a_negative_top_comment_is_still_shown_with_a_label():
    top = top_comment(
        [{"text": "Too much filter honestly", "like_count": 80, "sentiment": "negative"}]
    )
    assert top.negative


# ---------------------------------------------------------------- no new numbers


def test_numbers_are_read_however_they_are_written():
    assert validator.numbers_in("1.2K likes, 41% of comments, 1.4× usual, ₹2,000, three looks") == {
        1200.0,
        41.0,
        1.4,
        2000.0,
        3.0,
    }


def test_a_planted_number_is_caught_and_replaced():
    facts = [
        "Comments per view are 1.4× your usual.",
        "41% of comments say the reel describes them.",
    ]
    assert validator.new_numbers("41% of comments relate to it, 1.4× your usual.", facts) == set()
    assert validator.new_numbers("Comments are up 60% and 3× your usual.", facts) == {60.0, 3.0}
    calls = []

    def planted() -> str:
        calls.append(1)
        return "This will get you 10K more views."

    text, source = validator.checked(planted, facts, lambda: facts[1])
    assert (text, source, len(calls)) == (
        facts[1],
        "template",
        2,
    )  # retried once, then the template


def test_the_mock_explanation_uses_only_the_facts():
    facts = [
        "Likes per view are 0.6× your usual.",
        "The intro runs 3.6 seconds before the first payoff.",
    ]
    out = MockLLMProvider().run(
        T10, T10Input(kind="likes_low", title="Likes per view are low", facts=facts)
    )
    assert validator.new_numbers(out.text, facts) == set()
    assert "3.6 seconds" in out.text
