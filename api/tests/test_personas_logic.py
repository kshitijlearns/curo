"""Follower Personas (v2.2): the pure parts — clustering, profiles, starters, identity matching,
the persona score and A, the avatar algorithm and the safety checks. No database, no models."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from curo.providers.embedding.mock import MockEmbeddingProvider
from curo.providers.llm import mock_personas
from curo.schemas.tasks import (
    PersonaBrief,
    PersonaGroupIn,
    T25Input,
    T27Input,
    T28Input,
    T29Input,
    ThoughtIn,
)
from curo.services import persona_avatar, persona_safety, persona_text, validator
from curo.services import personas as P

NOW = datetime(2027, 8, 23, 10, tzinfo=UTC)
REPO = Path(__file__).resolve().parents[2]


def _comments(spec: list[tuple[str, str, int]], reel_ids=("r1", "r2", "r3", "r4", "r5", "r6")):
    """[(text, intent, count)] → labelled comments with mock vectors, spread over reels."""
    emb = MockEmbeddingProvider()
    out = []
    i = 0
    for text, intent, n in spec:
        for k in range(n):
            t = f"{text} {k % 3}"
            out.append(
                P.PComment(
                    id=f"c{i}",
                    reel_id=reel_ids[i % len(reel_ids)],
                    text=t,
                    intent=intent,
                    sentiment="positive" if intent in ("praise", "tags_friend") else "neutral",
                    language="en",
                    posted=NOW - timedelta(days=i % 40),
                    vector=emb.embed([t])[0],
                )
            )
            i += 1
    return out


def _reels(ids=("r1", "r2", "r3", "r4", "r5", "r6")):
    return {
        r: P.PReel(
            id=r,
            title=f"Reel {r}",
            posted=NOW - timedelta(days=5 * k),
            format=("multi_look", "talking_head", "tutorial")[k % 3],
            group=("Festive looks", "Everyday outfits")[k % 2],
            views=10_000 + 1000 * k,
            likes=800 + 50 * k,
            comments=60,
            shares=40 + 30 * k,
        )
        for k, r in enumerate(ids)
    }


SPEC = [
    ("where is this kurta from price please", "question", 40),
    ("saving this for the wedding next month", "plans_to_save", 30),
    ("obsessed with this look you never miss", "praise", 30),
    ("tagging my best friend we need this", "tags_friend", 20),
]


# ------------------------------------------------------------------ clustering


def test_always_exactly_four_groups_ordered_by_share():
    comments, reels = _comments(SPEC), _reels()
    built = P.build(comments, reels, NOW)
    assert len(built.profiles) == 4 and len(built.centroids) == 4
    shares = [p.share for p in built.profiles]
    assert shares == sorted(shares, reverse=True)
    assert sum(shares) == pytest.approx(1.0)
    assert sum(p.share_pct for p in built.profiles) == 100
    assert sorted(set(built.labels)) == [0, 1, 2, 3]


def test_every_group_keeps_at_least_eight_percent():
    # One dominant group, two medium and a tiny one (3%): the tiny one can't stand alone.
    spec = [
        ("where is this kurta from price please", "question", 120),
        ("saving this for the wedding", "plans_to_save", 40),
        ("obsessed with this look", "praise", 34),
        ("disagree the colour is wrong", "disagreement", 6),
    ]
    built = P.build(_comments(spec), _reels(), NOW)
    assert len(built.profiles) == 4
    assert min(p.share for p in built.profiles) >= P.MIN_SHARE - 1e-9


def test_min_share_rule_on_planted_labels():
    rng = np.random.default_rng(0)
    x = rng.normal(size=(100, 5))
    w = np.ones(100)
    labels = np.asarray([0] * 70 + [1] * 25 + [2] * 3 + [3] * 2)
    fixed = P.enforce_min_share(x, w, labels)
    shares = np.bincount(fixed, minlength=4) / 100
    assert len(set(fixed.tolist())) == 4 and shares.min() >= 0.08


def test_recent_comments_weigh_more():
    comments = _comments(SPEC)
    comments[0].posted = NOW - timedelta(days=200)
    w = P.weights(comments, _reels(), NOW)
    assert w[0] == P.OLD_WEIGHT and w[1] == 1.0


def test_the_same_data_gives_the_same_personas():
    a = P.build(_comments(SPEC), _reels(), NOW)
    b = P.build(_comments(SPEC), _reels(), NOW)
    assert a.labels == b.labels and [p.share for p in a.profiles] == [p.share for p in b.profiles]


# ------------------------------------------------------------------ profiles


def test_profile_facts_match_hand_calculation():
    comments, reels = _comments(SPEC), _reels()
    mine = [c for c in comments if c.intent == "question"]
    p = P.profile(1, mine, comments, 0.4, 40, reels, len(comments), NOW)
    assert p.n_comments == 40 and p.intents == [("question", 1.0)]
    assert p.n_reels == 6
    # Lift: the comment-weighted mean of (reel share rate ÷ median share rate).
    usual = P.medians(list(reels.values()))
    counts = {r: sum(1 for c in mine if c.reel_id == r) for r in reels}
    expect = sum(
        n * (reels[r].shares / reels[r].views) / usual["shares"] for r, n in counts.items()
    )
    expect /= sum(counts.values())
    assert p.lifts["shares"] == pytest.approx(expect)
    assert "40% of your comments come from this group." in p.facts
    assert "100% of their comments ask questions." in p.facts
    # Every number a persona may say is in its facts.
    for f in p.facts:
        assert not validator.new_numbers(f, p.facts)


def test_love_and_turn_off_come_from_over_and_under_indexing():
    reels = _reels()
    everyone = _comments(SPEC)
    # This group only comments on multi-look reels (r1, r4).
    mine = [c for c in everyone if c.reel_id in ("r1", "r4")]
    p = P.profile(1, mine, everyone, 0.3, 30, reels, len(everyone), NOW)
    assert [i.value for i in p.loves if i.kind == "format"] == ["multi_look"]
    assert {i.value for i in p.turn_offs if i.kind == "format"} >= {"talking_head", "tutorial"}
    assert "as often as everyone else" in P.item_evidence(p.loves[0])
    assert P.item_evidence(p.turn_offs[0]).startswith("Only 0% of this group")


def test_confidence_from_data_volume():
    assert P.confidence_for(30, 30, False) == "low"
    assert P.confidence_for(100, 40, False) == "medium"
    assert P.confidence_for(400, 120, False) == "high"
    assert P.confidence_for(400, 10, False) == "medium"  # a thin persona drops a step
    assert P.is_thin(39, 10) and P.is_thin(200, 4) and not P.is_thin(40, 5)


def test_mood_meter_reads_sentiment_and_lift():
    assert P.meter(0.9, {"shares": 1.6}) == 5
    assert P.meter(-0.6, {"shares": 0.5}) == 1
    assert P.MOOD_OF_METER[P.meter(None, {})] == "neutral"


# ------------------------------------------------------------------ starters


def test_starter_personas_below_the_data_threshold():
    s = P.starter("fashion", ["Festive looks"], [("hinglish", 0.7), ("en", 0.3)])
    assert len(s) == 4 and [x["slot"] for x in s] == [1, 2, 3, 4]
    assert sum(x["share_pct"] for x in s) == 100
    assert len({x["name"] for x in s}) == 4
    assert "your festive looks reels" in s[0]["comes_for"]
    shaped = P.starter("fashion", [], [("en", 1.0)], priors={"tags_friend": 0.9})
    assert shaped[0]["intent"] == "tags_friend"  # niche priors move the shares


# ------------------------------------------------------------------ identity across months


def test_matching_keeps_identity_at_cosine_point_eight():
    rng = np.random.default_rng(1)
    prev = [list(rng.normal(size=16)) for _ in range(4)]
    # Same groups, slightly moved and reordered; the last one is new.
    cur = [
        list(np.asarray(prev[2]) + 0.05 * rng.normal(size=16)),
        list(np.asarray(prev[0]) + 0.05 * rng.normal(size=16)),
        list(np.asarray(prev[1]) + 0.05 * rng.normal(size=16)),
        list(rng.normal(size=16)),
    ]
    m = P.match(prev, cur)
    assert m == {0: 2, 1: 0, 2: 1}
    assert P.colours({0: "pink", 1: "blue", 2: "lavender"}) == ["pink", "blue", "lavender", "ink"]
    assert P.colours({}) == list(P.COLORS)


# ------------------------------------------------------------------ the idea score's A


def test_a_is_the_share_weighted_persona_score_worked_example():
    fits = [
        P.PersonaFit("a", "The Festive Planner", "Festive Planner", 0.31, None, None),
        P.PersonaFit("b", "The Budget Stylist", "Budget Stylist", 0.27, None, None),
        P.PersonaFit("c", "The Loyal Fan", "Loyal Fan", 0.23, None, None),
        P.PersonaFit("d", "The Friend Tagger", "Friend Tagger", 0.19, None, None),
    ]
    scores = {"a": 0.82, "b": 0.48, "c": 0.70, "d": 0.61}
    # By hand: (0.31×0.82 + 0.27×0.48 + 0.23×0.70 + 0.19×0.61) / 1.00
    #        = 0.2542 + 0.1296 + 0.1610 + 0.1159 = 0.6607
    assert P.audience_part(scores, fits) == pytest.approx(0.6607)
    assert P.blend(80, 50, 0.5) == 65 and P.blend(None, 50, 0.5) == 50
    assert [P.reaction_for(s) for s in (82, 61, 48, 20)] == [
        "watch_all",
        "watch",
        "scroll_past",
        "skip",
    ]
    line = P.summary(
        [
            ("The Festive Planner", "watch_all", 0.31),
            ("The Budget Stylist", "scroll_past", 0.27),
            ("The Loyal Fan", "watch", 0.23),
            ("The Friend Tagger", "watch", 0.19),
        ]
    )
    assert line == "3 of 4 follower groups are in. The Budget Stylist isn’t sure."
    assert P.loving_summary([5, 4, 4, 2]) == (
        "3 of 4 of your follower groups are loving your recent reels."
    )


def test_code_fit_rewards_topic_requests_and_loved_formats():
    emb = MockEmbeddingProvider()
    fit = P.PersonaFit(
        "a",
        "The Budget Stylist",
        "Budget Stylist",
        0.3,
        None,
        emb.embed(["budget kurta looks under price affordable"])[0],
        ask_words=P.words_of("budget versions price links"),
        love_formats={"multi_look"},
        off_formats={"talking_head"},
    )
    good = "3 budget kurta looks with price"
    bad = "my morning routine talking about life"
    g, gp = P.code_fit(emb.embed([good])[0], good, "multi_look", fit)
    b, bp = P.code_fit(emb.embed([bad])[0], bad, "talking_head", fit)
    assert g > b and gp["asks"] == 1 and gp["love"] == 1 and bp["off"] == 1


# ------------------------------------------------------------------ the avatar


def test_avatar_dots_are_deterministic_and_match_the_web_fixture():
    fixture = json.loads((REPO / "web/src/lib/avatar.fixture.json").read_text(encoding="utf-8"))
    assert fixture == json.loads(json.dumps(persona_avatar.fixture()))
    for seed in (1, 42, 123456):
        dots = persona_avatar.dots(seed)
        assert 18 <= len(dots) <= 40 and dots == persona_avatar.dots(seed)
        assert {d.r for d in dots} <= set(persona_avatar.DOT_R)
        assert all(0.4 <= d.opacity <= 1.0 for d in dots)
    svg = persona_avatar.svg(42, "pink", "love")
    assert 'stroke="#E4E4EC"' in svg  # light colours get the hairline ring
    assert 'stroke="#E4E4EC"' not in persona_avatar.svg(42, "blue")


# ------------------------------------------------------------------ safety


PLANTED = [
    ("Mostly college students who love festive looks.", "age"),
    ("She plans every outfit weeks ahead.", "gender"),
    ("A group of Hindu viewers planning Diwali.", "religion"),
    ("Upper-caste families who shop online.", "caste"),
    ("Mostly North Indians.", "ethnicity"),
    ("Queer viewers who love bold looks.", "sexuality"),
    ("Pregnant viewers looking for comfy fits.", "health"),
    ("Low-income shoppers hunting deals.", "income"),
    ("Right-wing commenters.", "politics"),
    ("Lives in Bandra and shops nearby.", "location"),
]


@pytest.mark.parametrize(("text", "attr"), PLANTED)
def test_sensitive_attribute_check_catches_planted_examples(text, attr):
    assert attr in persona_safety.keyword_flags(text)
    assert not persona_safety.safe([text], classifier=False)


@pytest.mark.parametrize(
    "text",
    [
        "Loves budget looks and festive outfits.",
        "Comes for your ethnic wear and Diwali looks.",
        "Mentions Mumbai and Pune.",
        "Aap ka style best hai!",
        "Rich colours and poor lighting don't bother them.",
        "Reels they comment on also get 1.4× your usual shares.",
    ],
)
def test_content_traits_and_topics_pass(text):
    assert not persona_safety.keyword_flags(text)


def test_the_classifier_pass_catches_implications():
    flags = mock_personas.t29(T29Input(texts=["Fine text.", "Every aunty in my building."])).flags
    assert {(f.index, f.attribute) for f in flags} >= {(1, "gender"), (1, "location")}


def test_no_new_numbers_catches_a_planted_number_in_each_persona_task():
    facts = ["31% of your comments come from this group."]
    assert validator.new_numbers("I'm 31% of your comments.", facts) == set()
    assert validator.new_numbers("I'm 45% of your comments.", facts) == {45.0}
    assert not persona_safety.safe(
        ["Reels with 3 looks win."], numbers_from=facts, classifier=False
    )


# ------------------------------------------------------------------ the mocks (and fallbacks)


def _group(i: int, intent: str, theme: str) -> PersonaGroupIn:
    return PersonaGroupIn(
        key=f"g{i}",
        facts=[f"{40 - 5 * i}% of your comments come from this group."],
        data={
            "intents": [{"intent": intent, "share": 0.6}],
            "themes": [{"label": theme, "share": 0.2}],
            "loves": [],
            "turn_offs": [],
        },
    )


def test_mock_personas_are_distinct_kind_and_safe():
    groups = [
        _group(1, "question", "asks price"),
        _group(2, "plans_to_save", "wants festive looks"),
        _group(3, "praise", "praise"),
        _group(4, "question", "asks price"),  # a lookalike group still gets its own name
    ]
    out = mock_personas.t25(T25Input(niche="fashion", main_language="en", groups=groups))
    names = [p.name for p in out.personas]
    assert len(set(names)) == 4 and names[0] == "The Budget Stylist"
    for p, g in zip(out.personas, groups, strict=True):
        texts = [p.name, p.tagline, *p.comes_for, *p.loves, *p.wants_more, *p.turn_offs,
                 p.engagement_style, p.voice, p.typical_comment]  # fmt: skip
        assert persona_safety.safe(texts, numbers_from=g.facts)


def test_mock_thoughts_reactions_and_chat_stay_in_bounds():
    t = persona_text.thought_template(
        ThoughtIn(
            key="g1",
            name="The Festive Planner",
            voice="warm",
            facts=["x"],
            mood_hint="unsure",
            loves=["festive looks"],
            wants_more=["prices"],
        )
    )
    assert len(t.thought) <= 140 and t.mood == "unsure" and "prices" in t.thought
    b = PersonaBrief(key="p1", name="The Festive Planner", loves=["festive looks"],
                     wants_more=["prices on screen"], turn_offs=["long intros"])  # fmt: skip
    r = mock_personas.t27(
        T27Input(target_type="idea", idea="Festive looks for Navratri", personas=[b])
    )
    assert r.reactions[0].key == "p1" and 0 <= r.reactions[0].score <= 100
    honest = mock_personas.t28(T28Input(persona=b, question="How many of you are there exactly?"))
    assert honest.answer.startswith(persona_text.HONEST)
