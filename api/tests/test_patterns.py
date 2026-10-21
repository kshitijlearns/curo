"""Pattern cards: shrinkage toward the prior, the statistical test, like-for-like comparison."""

import math
import random

import pytest

from curo.services import patterns
from curo.services.patterns import Row, bh_qvalues, build_cards, creator_weight, effects, shrink

# ---------------------------------------------------------------- the logic doc's worked examples


def test_shrinkage_creator_weight_is_half_at_10_reels_and_80_percent_at_40():
    assert creator_weight(10) == pytest.approx(0.5)
    assert creator_weight(40) == pytest.approx(0.8)


def test_shrinkage_formula():
    # (n · creator + k · similar creators) / (n + k), k = 10
    assert shrink(10, 1.6, 1.0) == pytest.approx(1.3)
    assert shrink(40, 1.6, 1.0) == pytest.approx(1.48)
    assert shrink(10, 1.6, 1.4) == pytest.approx(1.5)


def test_benjamini_hochberg_q_values():
    # Sorted 0.01, 0.03, 0.04, 0.5 → raw p·m/rank 0.04, 0.06, 0.0533, 0.5 → running minimum
    # from the largest: 0.5, 0.0533, 0.0533, 0.04.
    q = bh_qvalues([0.01, 0.04, 0.03, 0.5])
    assert q == pytest.approx([0.04, 0.04 * 4 / 3, 0.04 * 4 / 3, 0.5])
    assert bh_qvalues([]) == []


# ---------------------------------------------------------------- mining


def planted(n=40, seed=7):
    """Reels where choice-question endings carry 1.7× comments, plus a noise feature."""
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        choice = i % 2 == 0
        lift = math.exp(rng.gauss(0, 0.15)) * (1.7 if choice else 1.0)
        rows.append(
            Row(
                f"r{i}",
                {
                    "ending": "choice_question" if choice else "final_look",
                    "camera": rng.choice(["tripod", "handheld"]),
                },
                {"comment_rate": lift},
            )
        )
    return rows


def test_a_planted_pattern_is_found_and_noise_is_not():
    found = {e.key: e for e in effects(planted(), metrics=["comment_rate"])}
    e = found[("ending", "choice_question", "comment_rate")]
    assert e.effect == pytest.approx(1.7, rel=0.15)
    assert e.holds and e.n == 20
    noise = [v for k, v in found.items() if k[0] == "camera"]
    assert noise and not any(v.holds for v in noise)


def test_too_few_reels_on_either_side_means_no_comparison():
    rows = planted(n=6)
    assert effects(rows[:5], metrics=["comment_rate"]) == []


def test_like_is_compared_with_like_within_sub_clusters():
    """A feature that only marks a topic (every haul is handheld) says nothing within a
    sub-cluster; a choice made inside sub-clusters (the ending) still shows."""
    rng = random.Random(3)
    rows, strata = [], {}
    for i in range(48):
        haul = i < 16
        choice = i % 2 == 0
        lift = (0.4 if haul else 1.0) * (1.7 if choice else 1.0) * math.exp(rng.gauss(0, 0.1))
        rid = f"r{i}"
        strata[rid] = "hauls" if haul else ("festive" if i < 32 else "grwm")
        rows.append(
            Row(
                rid,
                {
                    "camera": "handheld" if haul else "tripod",
                    "ending": "choice_question" if choice else "final_look",
                },
                {"comment_rate": lift},
            )
        )
    raw = {e.key: e for e in effects(rows, metrics=["comment_rate"])}
    assert raw[("camera", "tripod", "comment_rate")].holds  # confounded without strata
    within = {e.key: e for e in effects(rows, metrics=["comment_rate"], strata=strata)}
    assert ("camera", "tripod", "comment_rate") not in within
    assert within[("ending", "choice_question", "comment_rate")].effect == pytest.approx(
        1.7, rel=0.1
    )


# ---------------------------------------------------------------- cards


def eff(feature, value, metric, n, effect, q, n_without=20):
    e = patterns.Effect(
        feature, value, metric, n, n_without, effect, q, effect, 1.0, [f"r{i}" for i in range(n)]
    )
    e.q_value = q
    return e


def test_yours_needs_eight_reels_and_a_passing_test():
    own = [
        eff("ending", "choice_question", "comment_rate", 14, 1.6, 0.001),
        eff("hook_type", "reveal", "views", 6, 2.0, 0.001),  # too few reels
        eff("cta_type", "save_prompt", "share_rate", 12, 1.5, 0.4),  # doesn't hold
    ]
    cards = {(c.feature, c.value): c for c in build_cards(own, {}, {})}
    card = cards[("ending", "choice_question")]
    assert card.scope == "yours" and card.n == 14
    assert card.effect == pytest.approx(
        shrink(14, 1.6, 1.0), abs=0.001
    )  # no prior: toward no effect
    assert card.creator_effect == pytest.approx(1.6) and card.prior_effect is None
    assert ("hook_type", "reveal") not in cards and ("cta_type", "save_prompt") not in cards


def test_similar_creators_fill_in_where_the_creator_has_little_evidence():
    prior = eff("hook_type", "reveal", "views", 40, 1.9, 0.001)
    own = [eff("hook_type", "reveal", "views", 5, 1.2, 0.3)]
    cards = build_cards(own, {prior.key: prior}, {("hook_type", "reveal"): 5})
    (card,) = cards
    assert card.scope == "similar_creators"
    assert card.effect == pytest.approx(shrink(5, 1.2, 1.9), abs=0.001)
    # A value the creator never used: shown from the similar-creator effect alone.
    cards = build_cards([], {prior.key: prior}, {})
    assert cards[0].scope == "similar_creators" and cards[0].n == 0 and cards[0].effect == 1.9


def test_tiny_effects_are_not_cards():
    own = [eff("ending", "recap", "comment_rate", 20, 1.04, 0.001)]
    assert build_cards(own, {}, {}) == []
