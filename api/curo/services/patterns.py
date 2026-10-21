"""Pattern cards (logic doc §5 step 8, "Why patterns are shrunk toward a prior").

For each DNA value, compare the lift of reels that have it with reels that don't:
effect = median lift with ÷ median lift without, per metric. The creator's own effect is then
blended with the effect seen across similar creators, giving the creator more weight as their
reel count grows:

    effect = (n · creator effect + k · similar-creator effect) / (n + k),   k = 10

A card is "yours" only when n ≥ 8 and the effect holds in a statistical test (two-sided
Mann–Whitney U on log lifts, Benjamini–Hochberg q ≤ 0.10 across all the creator's
comparisons, so testing many features at once doesn't manufacture patterns). Otherwise it is
labelled "seen across similar creators", and only shown when the similar-creator effect itself
holds. Cards say "associated with", never "causes".

Like is compared with like (DECISIONS D42): when the creator's reels fall into sub-clusters,
each reel is compared with the reels of its own sub-cluster that don't have the value (its
lift ÷ their median lift). A card therefore reflects a choice made within the same kind of
content ("choice-question endings draw more comments"), not a difference between topics
("hauls get fewer shares"), which the sub-cluster lifts already show. A sub-cluster whose
reels all share the value can't say anything about it and is left out of that comparison.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Iterable
from dataclasses import dataclass, field

from scipy.stats import mannwhitneyu

from curo.services.metrics import LIFT_METRICS

K_PRIOR = 10
MIN_YOURS_N = 8
MIN_GROUP_N = 3
FDR_Q = 0.10
MIN_SHOWN_CHANGE = 0.10  # |effect − 1| below this isn't worth a card


@dataclass
class Row:
    """One reel: its feature values and its lifts per metric."""

    reel_id: str
    features: dict[str, str]
    lifts: dict[str, float]


@dataclass
class Effect:
    feature: str
    value: str
    metric: str
    n: int
    n_without: int
    effect: float
    p_value: float
    median_with: float
    median_without: float
    reel_ids: list[str] = field(default_factory=list)
    q_value: float = 1.0

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.feature, self.value, self.metric)

    @property
    def holds(self) -> bool:
        return self.n >= MIN_YOURS_N and self.q_value <= FDR_Q


@dataclass
class Card:
    feature: str
    value: str
    metric: str
    effect: float
    creator_effect: float | None
    prior_effect: float | None
    n: int
    n_without: int
    p_value: float | None
    confidence: str
    scope: str  # "yours" | "similar_creators"
    evidence: dict = field(default_factory=dict)


def shrink(n: int, creator_effect: float, prior_effect: float, k: int = K_PRIOR) -> float:
    return (n * creator_effect + k * prior_effect) / (n + k)


def creator_weight(n: int, k: int = K_PRIOR) -> float:
    """How much of the blended effect is the creator's own: 10 reels → 50%, 40 → 80%."""
    return n / (n + k)


def bh_qvalues(pvalues: list[float]) -> list[float]:
    """Benjamini–Hochberg adjusted p-values (q-values), in the input order."""
    m = len(pvalues)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: pvalues[i])
    q = [0.0] * m
    running = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        running = min(running, pvalues[i] * m / rank)
        q[i] = min(1.0, running)
    return q


MIN_REFERENCE = 2  # reels without the value a sub-cluster needs to serve as a reference


def compare_within(
    with_: list[Row], without: list[Row], metric: str, strata: dict[str, str]
) -> tuple[list[tuple[str, float]], list[float]]:
    """Lifts relative to the median of same-sub-cluster reels without the value. Reels in no
    sub-cluster form one "rest" group. Groups with fewer than 2 reels without the value can't
    serve as a reference and are left out."""
    by_stratum: dict[str, tuple[list[Row], list[Row]]] = {}
    for r in with_:
        by_stratum.setdefault(strata.get(r.reel_id, "rest"), ([], []))[0].append(r)
    for r in without:
        by_stratum.setdefault(strata.get(r.reel_id, "rest"), ([], []))[1].append(r)
    a: list[tuple[str, float]] = []
    b: list[float] = []
    for w, wo in by_stratum.values():
        if len(wo) < MIN_REFERENCE:
            continue
        ref = statistics.median(r.lifts[metric] for r in wo)
        if ref <= 0:
            continue
        a += [(r.reel_id, r.lifts[metric] / ref) for r in w]
        b += [r.lifts[metric] / ref for r in wo]
    return a, b


def effects(
    rows: list[Row], metrics: Iterable[str] = LIFT_METRICS, strata: dict[str, str] | None = None
) -> list[Effect]:
    """Every (feature, value, metric) with at least 3 reels on each side, with BH q-values.
    With ``strata``, reels are compared within their sub-cluster (see the module note)."""
    values_by_feature: dict[str, set[str]] = {}
    for r in rows:
        for f, v in r.features.items():
            values_by_feature.setdefault(f, set()).add(v)
    out: list[Effect] = []
    for feature in sorted(values_by_feature):
        for value in sorted(values_by_feature[feature]):
            for metric in metrics:
                with_ = [r for r in rows if r.features.get(feature) == value and metric in r.lifts]
                without = [
                    r
                    for r in rows
                    if feature in r.features and r.features[feature] != value and metric in r.lifts
                ]
                if strata:
                    pairs, b = compare_within(with_, without, metric, strata)
                    ids, a = [p[0] for p in pairs], [p[1] for p in pairs]
                else:
                    ids = [r.reel_id for r in with_]
                    a = [r.lifts[metric] for r in with_]
                    b = [r.lifts[metric] for r in without]
                if len(a) < MIN_GROUP_N or len(b) < MIN_GROUP_N or min(a + b) <= 0:
                    continue
                m_with, m_without = statistics.median(a), statistics.median(b)
                la, lb = [math.log(x) for x in a], [math.log(x) for x in b]
                try:
                    p = float(mannwhitneyu(la, lb, alternative="two-sided").pvalue)
                except ValueError:  # all values identical
                    p = 1.0
                if math.isnan(p):
                    p = 1.0
                out.append(
                    Effect(
                        feature=feature,
                        value=value,
                        metric=metric,
                        n=len(a),
                        n_without=len(b),
                        effect=m_with / m_without,
                        p_value=p,
                        median_with=m_with,
                        median_without=m_without,
                        reel_ids=ids,
                    )
                )
    for e, q in zip(out, bh_qvalues([e.p_value for e in out]), strict=True):
        e.q_value = q
    return out


def _confidence(n: int, q: float) -> str:
    if n >= 15 and q <= 0.01:
        return "high"
    if n >= MIN_YOURS_N and q <= FDR_Q:
        return "medium"
    return "low"


def _round(x: float | None) -> float | None:
    return None if x is None else round(x, 3)


def build_cards(
    own: list[Effect],
    priors: dict[tuple[str, str, str], Effect],
    own_counts: dict[tuple[str, str], int],
) -> list[Card]:
    """The creator's cards: own effects blended with the prior; plus patterns that hold across
    similar creators for values the creator has (almost) never used."""
    cards: list[Card] = []
    seen: set[tuple[str, str, str]] = set()
    for e in own:
        prior = priors.get(e.key)
        prior_effect = prior.effect if prior else 1.0  # no outside evidence: assume no effect
        blended = shrink(e.n, e.effect, prior_effect)
        if e.holds:
            scope, confidence = "yours", _confidence(e.n, e.q_value)
        elif prior is not None and prior.holds:
            scope, confidence = "similar_creators", _confidence(prior.n, prior.q_value)
        else:
            continue
        if abs(blended - 1.0) < MIN_SHOWN_CHANGE:
            continue
        seen.add(e.key)
        cards.append(
            Card(
                feature=e.feature,
                value=e.value,
                metric=e.metric,
                effect=round(blended, 3),
                creator_effect=_round(e.effect),
                prior_effect=_round(prior.effect) if prior else None,
                n=e.n,
                n_without=e.n_without,
                p_value=_round(e.p_value),
                confidence=confidence,
                scope=scope,
                evidence={
                    "median_lift_with": _round(e.median_with),
                    "median_lift_without": _round(e.median_without),
                    "q_value": _round(e.q_value),
                    "creator_weight": round(creator_weight(e.n), 3),
                    "reel_ids": e.reel_ids[:12],
                    "prior_n": prior.n if prior else 0,
                },
            )
        )
    for key, prior in priors.items():
        if key in seen or not prior.holds:
            continue
        n = own_counts.get((prior.feature, prior.value), 0)
        if n >= MIN_GROUP_N:
            continue  # the creator has enough of their own reels: decided above
        if abs(prior.effect - 1.0) < MIN_SHOWN_CHANGE:
            continue
        cards.append(
            Card(
                feature=prior.feature,
                value=prior.value,
                metric=prior.metric,
                effect=round(prior.effect, 3),
                creator_effect=None,
                prior_effect=_round(prior.effect),
                n=n,
                n_without=0,
                p_value=None,
                confidence=_confidence(prior.n, prior.q_value),
                scope="similar_creators",
                evidence={"prior_n": prior.n, "q_value": _round(prior.q_value)},
            )
        )
    return sorted(cards, key=lambda c: (c.scope != "yours", -abs(math.log(c.effect)), c.feature))
