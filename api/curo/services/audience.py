"""What your audience thinks (logic doc §7): cards that explain behaviour, not just numbers.

1. Lift of each public rate (likes, comments, shares per view) at the reel's age.
2. A z-score against the creator's own history: how unusual that lift is for them.
3. Up to three cards with |z| ≥ 0.75, always including the strongest positive one; if a rate
   is clearly low (z ≤ −1) one card must be about it. Comment-based cards fill the slots no
   rate needs.
4. Each card carries computed facts (its reason, from comments and DNA); T10 turns them into
   one plain sentence, and the no-new-numbers check keeps it to the facts' numbers.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field

Z_SHOWN = 0.75
Z_CLEARLY_LOW = -1.0
MIN_HISTORY = 5
MAX_CARDS = 3
TAGGING_SHARE = 0.10  # "10% or more of comments tag another account"
THEME_SHARE = 0.20  # a single request/question theme this common on the reel earns a card
FOLLOWER_JUMP = 2.0  # follower growth this many times faster than usual

RATE_CARDS = {
    "comment_rate": (
        "comments",
        "Comments are driving engagement",
        "Comments are quieter than usual",
    ),
    "share_rate": ("shares", "Shares are higher than usual", "Shares are lower than usual"),
    "like_rate": ("likes", "Likes per view are high", "Likes per view are low"),
}
RATE_NAMES = {"comment_rate": "Comments", "share_rate": "Shares", "like_rate": "Likes"}


@dataclass
class Card:
    key: str  # e.g. "comments_high", "tagging_friends"
    icon: str  # comments | shares | likes | views
    title: str
    facts: list[str]
    z: float | None = None


@dataclass
class Evidence:
    """What comments and DNA say about this reel (counts over its labelled, non-bot comments)."""

    comments: int = 0
    intents: dict[str, int] = field(default_factory=dict)
    tags: int = 0
    part_two: int = 0
    top_theme: tuple[str, int] | None = None  # (label, comments)
    ending: str | None = None
    cta: str | None = None
    payoff_s: float | None = None
    follower_ratio: float | None = None  # follower growth after posting ÷ usual
    brought_most_views: bool = False


def zscore(lift: float | None, history: list[float]) -> float | None:
    """How unusual a lift is for this creator, from the log lifts of their other reels."""
    if lift is None or lift <= 0 or len(history) < MIN_HISTORY:
        return None
    logs = [math.log(h) for h in history if h > 0]
    if len(logs) < MIN_HISTORY:
        return None
    sd = statistics.stdev(logs)
    if sd == 0:
        return None
    return (math.log(lift) - statistics.fmean(logs)) / sd


def _pct(n: int, total: int) -> int:
    return round(100 * n / total) if total else 0


def _lift_fact(metric: str, lift: float) -> str:
    return f"{RATE_NAMES[metric]} per view are {lift:.1f}× your usual."


def _rate_facts(metric: str, lift: float, high: bool, ev: Evidence) -> list[str]:
    facts = [_lift_fact(metric, lift)]
    total = ev.comments
    if metric == "comment_rate":
        ending = []
        if ev.ending in ("choice_question", "open_question"):
            ending = ["The reel ends on a question."]
        elif ev.ending and not high:
            ending = ["The reel doesn’t end on a question."]
        mix = []
        for intent, words in (
            ("thats_me", "say the reel describes them"),
            ("question", "are questions"),
            ("disagreement", "disagree"),
        ):
            n = ev.intents.get(intent, 0)
            if total and n / total >= 0.10:
                mix.append(f"{_pct(n, total)}% of comments {words}.")
        # High: what people wrote explains it best. Low: whether the reel invited comments.
        facts += mix + ending if high else ending + mix
    elif metric == "share_rate":
        if total and ev.tags:
            facts.append(f"{_pct(ev.tags, total)}% of comments tag a friend.")
        elif total:
            facts.append("No comments tag a friend.")
        if ev.cta == "share_prompt":
            facts.append("The reel asks viewers to send it to a friend.")
        elif ev.cta and not high:
            facts.append("The reel doesn’t ask viewers to send it on.")
    elif metric == "like_rate" and ev.payoff_s is not None:
        if high or ev.payoff_s <= 2:
            facts.append(f"The first payoff comes at {ev.payoff_s:.1f} seconds.")
        else:
            facts.append(f"The intro runs {ev.payoff_s:.1f} seconds before the first payoff.")
    return facts


def comment_cards(ev: Evidence) -> list[Card]:
    """Cards from comments and followers, used to fill slots no unusual rate needs."""
    cards = []
    if ev.follower_ratio and ev.follower_ratio >= FOLLOWER_JUMP and ev.brought_most_views:
        facts = [
            f"Your follower count grew {ev.follower_ratio:.1f}× faster than usual in the 2 days after posting.",
            "This reel brought most of your new views in that time.",
        ]
        if ev.part_two:
            facts.append(f"{ev.part_two} comments ask for a part 2.")
        cards.append(Card("followers_jumped", "views", "Your follower count jumped", facts))
    if ev.comments and ev.tags / ev.comments >= TAGGING_SHARE:
        cards.append(
            Card(
                "tagging_friends",
                "views",
                "People are tagging friends",
                [f"{_pct(ev.tags, ev.comments)}% of comments tag another account."],
            )
        )
    if ev.top_theme and ev.comments and ev.top_theme[1] / ev.comments >= THEME_SHARE:
        label, n = ev.top_theme
        verb, _, rest = label.partition(" ")
        phrase = {"asks": "ask", "wants": "want"}.get(verb.lower(), verb.lower()) + (
            f" {rest}" if rest else ""
        )
        cards.append(
            Card(
                "theme",
                "comments",
                f"Comments {phrase}",
                [f"{_pct(n, ev.comments)}% of comments on this reel {phrase}."],
            )
        )
    return cards


def select_cards(
    lifts: dict[str, float], history: dict[str, list[float]], ev: Evidence
) -> list[Card]:
    candidates: list[Card] = []
    for metric, (icon, high_title, low_title) in RATE_CARDS.items():
        z = zscore(lifts.get(metric), history.get(metric, []))
        if z is None or abs(z) < Z_SHOWN:
            continue
        high = z > 0
        candidates.append(
            Card(
                f"{icon}_{'high' if high else 'low'}",
                icon,
                high_title if high else low_title,
                _rate_facts(metric, lifts[metric], high, ev),
                round(z, 2),
            )
        )
    chosen: list[Card] = []
    positives = [c for c in candidates if c.z and c.z > 0]
    if positives:  # always the strongest positive one
        chosen.append(max(positives, key=lambda c: c.z))
    clearly_low = [c for c in candidates if c.z is not None and c.z <= Z_CLEARLY_LOW]
    if clearly_low and not any(c.z is not None and c.z <= Z_CLEARLY_LOW for c in chosen):
        chosen.append(min(clearly_low, key=lambda c: c.z))
    for c in sorted(candidates, key=lambda c: -abs(c.z or 0)):
        if len(chosen) >= MAX_CARDS:
            break
        if c not in chosen:
            chosen.append(c)
    for c in comment_cards(ev):
        if len(chosen) >= MAX_CARDS:
            break
        chosen.append(c)
    return chosen


def template_sentence(card: Card) -> str:
    """The fallback when a written sentence brings in a number of its own: the facts as-is."""
    return " ".join(card.facts[1:3]) if len(card.facts) > 1 else card.facts[0]
