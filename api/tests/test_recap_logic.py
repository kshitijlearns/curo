"""The Creator Recap's facts, rules and copy (v2.1 §3, §7), checked against hand calculations."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from curo.providers.llm.mock_recap import t23
from curo.schemas.tasks import RecapSlideIn, T23Input
from curo.services import recap as R
from curo.services import recap_config as C
from curo.services.validator import new_numbers

IST = ZoneInfo("Asia/Kolkata")
END = date(2027, 8, 23)


def reel(i: int, day: date, hour: int = 19, views=None, likes=None, comments=None, shares=None,
         caption="A reel", dna=None, hashtags=(), audio=None) -> R.Reel:  # fmt: skip
    return R.Reel(
        id=f"r{i:03d}",
        title=caption[:40],
        posted=datetime(day.year, day.month, day.day, hour, tzinfo=IST),
        views=views,
        likes=likes,
        comments=comments,
        shares=shares,
        caption=caption,
        hashtags=list(hashtags),
        audio_name=audio,
        dna=dna,
    )


def data(reels, followers, posts, kind="first", **kw) -> R.RecapInput:
    start = END - timedelta(days=89)
    return R.RecapInput(
        kind=kind,
        period_start=kw.pop("start", start),
        period_end=kw.pop("end", END),
        handle=kw.pop("handle", "someone"),
        followers=followers,
        total_posts=posts,
        reels=reels,
        history=kw.pop("history", reels),
        today=END,
        **kw,
    )


# ---------------------------------------------------------------- numbers


@pytest.mark.parametrize(
    ("n", "grouped", "short"),
    [
        (0, "0", "0"),
        (999, "999", "999"),
        (1_000, "1,000", "1K"),
        (12_345, "12,345", "12.3K"),
        (248_300, "2,48,300", "2.5L"),
        (1_234_567, "12,34,567", "12.3L"),
        (12_345_678, "1,23,45,678", "1.2Cr"),
    ],
)
def test_indian_number_formatting(n, grouped, short):
    assert R.fmt_in(n) == grouped
    assert R.fmt_short(n) == short


# ---------------------------------------------------------------- level and modifiers


@pytest.mark.parametrize(
    ("followers", "level"),
    [
        (0, "The Spark"), (100, "The Spark"), (101, "The Explorer"), (1_000, "The Explorer"),
        (1_001, "The Community Builder"), (10_000, "The Community Builder"),
        (10_001, "The Rising Voice"), (50_000, "The Rising Voice"), (50_001, "The Trendsetter"),
        (100_000, "The Trendsetter"), (100_001, "The Influencer"), (500_000, "The Influencer"),
        (500_001, "The Star"), (1_000_000, "The Star"), (1_000_001, "The Icon"),
    ],
)  # fmt: skip
def test_level_thresholds_at_every_boundary(followers, level):
    assert R.level_for(followers)[0] == level


def test_level_is_unknown_without_a_follower_count():
    assert R.level_for(None) is None


def test_modifiers():
    week = [reel(i, END - timedelta(days=d)) for i, d in enumerate(range(0, 28, 2))]  # 14 reels
    assert R.modifier_for(9, week, END) == "Just getting started"
    dense = [reel(i, END - timedelta(days=d % 28)) for i, d in enumerate(range(0, 28 * 4, 7))]
    dense += [reel(100 + i, END - timedelta(days=d)) for i, d in enumerate(range(0, 28))]
    assert R.modifier_for(50, dense, END) == "Consistency champ"  # ≥ 4 reels each of 4 weeks
    assert R.modifier_for(120, week, END) == "Seasoned creator"
    assert R.modifier_for(50, week, END) is None


# ---------------------------------------------------------------- archetypes


def test_archetype_from_dna_and_ties_use_the_fixed_order():
    story = {"narrative": "story_arc", "format": "vlog"}
    teach = {"narrative": "list", "format": "tutorial"}
    reels = [reel(i, END - timedelta(days=i * 5), dna=story if i % 2 else teach) for i in range(8)]
    best, runner, ev = R.archetype_for(data(reels, 5_000, 40))
    # 4 storytelling and 4 teaching reels: a tie at 0.5, the earlier in the fixed order wins.
    assert ev["scores"]["storyteller"] == ev["scores"]["teacher"] == 0.5
    assert best == "storyteller" and runner == "teacher"
    assert ev["evidence"]["source"] == "video analysis"


def test_archetype_from_captions_when_dna_isnt_ready():
    reels = [reel(i, END - timedelta(days=i * 3), caption="3 tips to style a dupatta")
             for i in range(6)]  # fmt: skip
    best, _r, ev = R.archetype_for(data(reels, 800, 12))
    assert best == "teacher" and ev["evidence"]["source"] == "captions and hashtags"


def test_night_owl_and_conversation_starter():
    late = [reel(i, END - timedelta(days=i * 4), hour=22) for i in range(6)]
    assert R.archetype_for(data(late, 800, 12))[0] == "night_owl"
    hist = [reel(i, END - timedelta(days=200 + i), views=1000, likes=50, comments=5, shares=5)
            for i in range(10)]  # fmt: skip
    now = [reel(50 + i, END - timedelta(days=i * 4), hour=12, views=1000, likes=50,
                comments=15, shares=5) for i in range(6)]  # fmt: skip
    d = data(now, 2_000, 40, history=hist + now)
    scores, _ = R.archetype_scores(d)
    assert scores["conversation_starter"] > 0.9  # comments per view 2× usual: the strongest lift


# ---------------------------------------------------------------- comparisons


def test_comparison_lands_between_2_and_50_closest_to_10():
    assert R.comparison_for(248_300) == {
        "label": "a 30,000-seat cricket stadium",
        "times": 8,
        "note": "a mid-size cricket stadium",
    }
    assert R.comparison_for(400)["label"] == "a 40-seat classroom"  # 10× a classroom
    assert R.comparison_for(50) is None  # nothing fits 2–50×


# ---------------------------------------------------------------- three creators


def beginner() -> R.RecapInput:
    """60 followers, 6 reels, a handful of comments."""
    reels = [reel(i, END - timedelta(days=12 * i), views=[90, 140, 60, 210, 75, 120][i],
                  likes=[9, 12, 5, 20, 6, 10][i], comments=[1, 2, 0, 3, 1, 1][i])
             for i in range(6)]  # fmt: skip
    return data(reels, 60, 6, handle="newcreator",
                comments=[R.Comment("so cute!", 2)] * 5)  # fmt: skip


def mid() -> R.RecapInput:
    """The demo creator's shape: about 48K followers, 20 reels in the period, chatty audience."""
    reels = []
    for i in range(20):
        v = 30_000 + 2_500 * i
        reels.append(reel(i, END - timedelta(days=4 * i), hour=19 if i % 3 else 9, views=v,
                          likes=v // 25, comments=v // 300, shares=v // 400,
                          caption="One kurta, five dupattas" if i == 19 else f"Look {i}",
                          dna={"narrative": "list", "format": "multi_look", "visual_style": "warm_light"}))  # fmt: skip
    comments = [R.Comment(f"where is this from {i} 💖", likes=i, language="hinglish" if i % 3 else "en")
                for i in range(60)]  # fmt: skip
    return data(
        reels, 48_200, 220, handle="curo.demo", comments=comments,
        themes=[R.Theme("Asks where it's from", 0.16, 30), R.Theme("Part 2 please", 0.04, 8)],
        groups=[R.Group("Festive styling", 1.6, 7), R.Group("Hauls", 0.9, 5)],
        cards=[R.Card("hook_type", "question", "views", 1.8, 6)], opportunities=5,
    )  # fmt: skip


def large() -> R.RecapInput:
    reels = [reel(i, END - timedelta(days=3 * i), views=2_000_000 + 10_000 * i,
                  likes=80_000, comments=4_000, shares=12_000) for i in range(30)]  # fmt: skip
    return data(reels, 1_200_000, 900, handle="bigname", opportunities=3)


@pytest.mark.parametrize("make", [beginner, mid, large])
def test_every_creator_gets_5_to_12_slides_with_no_missing_number_as_zero(make):
    d = make()
    built = R.build(d)
    assert C.MIN_SLIDES <= len(built.slides) <= C.MAX_SLIDES
    assert built.slides[0] == "intro" and built.slides[-3:] == [
        "creator_type",
        "share_card",
        "next_up",
    ]
    for s in built.slides:
        assert built.facts[s] is not None and built.facts[s]["display"]
    # Every mock T23 line passes the no-new-numbers check against its slide's facts.
    payload = T23Input(
        handle=d.handle, period="x",
        slides=[RecapSlideIn(slide_id=s, facts=built.facts[s]["display"], data=built.facts[s])
                for s in built.slides],
    )  # fmt: skip
    for line in t23(payload).slides:
        facts = [*built.facts[line.slide_id]["display"], f"@{d.handle}"]
        assert not new_numbers(f"{line.headline} {line.subline}", facts), line


def test_beginner_hand_calculation():
    built = R.build(beginner())
    f = built.facts
    assert built.level == "The Spark" and built.modifier == "Just getting started"
    assert f["posting"]["reels"] == 6
    assert f["views_total"]["views"] == 90 + 140 + 60 + 210 + 75 + 120 == 695
    assert f["beyond_followers"]["best_ratio"] == 3.5  # 210 ÷ 60
    assert f["top_reel"]["lift"] == 2.0  # 210 ÷ median(60, 75, 90, 120, 140, 210) = 210 ÷ 105
    assert f["growth"] == {**f["growth"], "milestone": 100, "gap": 40}
    assert f["audience_voice"] is None and f["language_mix"] is None  # < 30 comments: skipped
    assert f["most_shared"] is None  # no public shares: skipped, never 0
    assert f["superpower"] is None and f["top_topic"] is None  # no DNA patterns yet


def test_mid_creator_hand_calculation():
    built = R.build(mid())
    f = built.facts
    assert built.level == "The Rising Voice" and built.modifier == "Seasoned creator"
    total = sum(30_000 + 2_500 * i for i in range(20))
    assert f["views_total"]["views"] == total == 1_075_000
    assert f["views_total"]["views_in"] == "10,75,000"
    assert f["top_reel"]["title"] == "One kurta, five dupattas"
    assert f["top_reel"]["lift"] == round(77_500 / 53_750, 1)  # vs the median of 20 reels
    assert f["superpower"]["effect"] == 1.8 and f["top_topic"]["label"] == "Festive styling"
    assert f["language_mix"]["mix"][0] == {"language": "Hinglish", "share": 0.67}
    assert f["audience_voice"]["emoji"] == "💖"
    assert built.archetype == "The Teacher"  # list narrative in every reel
    assert len(built.slides) == C.MAX_SLIDES  # more slides qualify than fit: capped at 12


def test_large_creator_level_and_beyond_followers():
    built = R.build(large())
    assert built.level == "The Icon" and built.modifier == "Seasoned creator"
    assert built.facts["beyond_followers"]["best_ratio"] == round(2_290_000 / 1_200_000, 1)
    assert built.facts["beyond_followers"]["note"].startswith("Based on public views")


def test_monthly_growth_and_vs_last_month():
    d = mid()
    d.kind = "monthly"
    d.period_start, d.period_end = date(2027, 7, 1), date(2027, 7, 31)
    d.follower_start, d.follower_end = 46_880, 48_200
    d.previous = {"views": 800_000, "reels": 12}
    d.views_older_gained = None
    f = R.slide_facts(d)
    assert (
        f["growth"]["delta"] == 1_320
        and f["growth"]["display"][0] == "+1,320 followers this month."
    )
    assert f["vs_last_month"]["views_change"] == round((1_075_000 - 800_000) / 800_000, 3)
    assert f["intro"]["period"] == "July 2027"


def test_a_comment_with_personal_data_or_a_handle_never_shows():
    kept = R.clean_comments([
        R.Comment("call me 98765 43210"), R.Comment("mail me a@b.co"),
        R.Comment("@riya.k look!"), R.Comment("see www.spam.example"),
    ])  # fmt: skip
    assert [c.text for c in kept] == ["@… look!"]


def test_the_palette_text_pairs_pass_wcag_aa():
    def lum(hex_: str) -> float:
        rgb = [int(hex_[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    for bg, fg in C.BACKGROUNDS:
        a, b = sorted((lum(C.COLOURS[bg]), lum(C.COLOURS[fg])), reverse=True)
        assert (a + 0.05) / (b + 0.05) >= 4.5, (bg, fg)
