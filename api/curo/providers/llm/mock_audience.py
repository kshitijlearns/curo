"""Mock stand-ins for the AI audience (T17–T22): deterministic, built only from the input.

Each agent's reaction comes from a random generator seeded on (run, agent number), shaped by
the persona's traits, how well the video matches its interests, how soon the video gets to its
payoff and whether it asks for a comment, a share or a save. So a tighter take (payoff at 1 s,
a send prompt) is watched longer and shared more, and the demo's take1 → take2 moves the
score — without the mock ever seeing a real result.

Comments and reasons are written without digits: what a creator reads may only carry numbers
from its input facts (the validator), and an agent's comment has none.
"""

from __future__ import annotations

import hashlib
import random
import re

from curo.schemas.tasks import (
    Persona,
    Reaction,
    Segment,
    T17Input,
    T17Output,
    T18Input,
    T18Output,
    T19Input,
    T19Output,
    T20Input,
    T20Output,
    T21Input,
    T21Output,
    T22Input,
    T22Output,
    ThreadAction,
)
from curo.services import agents

# ------------------------------------------------------------------ T17 · segments

# (key, label, description, interests, base share, traits: patience, liker, commenter, sharer, saver)
BASE_SEGMENTS = [
    (
        "loyal_fan",
        "Loyal fan",
        "Follows the creator closely and watches most reels to the end.",
        ["your style", "behind the scenes"],
        0.22,
        (0.8, 0.75, 0.35, 0.25, 0.2),
    ),
    (
        "idea_saver",
        "Idea saver",
        "Watches for looks and ideas to try later; saves what is useful.",
        ["how to", "ideas", "tips"],
        0.18,
        (0.6, 0.5, 0.15, 0.2, 0.6),
    ),
    (
        "festive_planner",
        "Festive planner",
        "Plans outfits and looks around festivals and occasions.",
        ["festival", "festive", "ganpati", "diwali", "occasion"],
        0.16,
        (0.55, 0.55, 0.3, 0.45, 0.45),
    ),
    (
        "budget_shopper",
        "Budget shopper",
        "Wants prices, links and where to buy; asks in the comments.",
        ["price", "budget", "link", "shop", "haul"],
        0.14,
        (0.45, 0.4, 0.5, 0.3, 0.35),
    ),
    (
        "casual_scroller",
        "Casual scroller",
        "Scrolls fast and stays only if something happens in the first seconds.",
        ["quick", "funny", "relatable"],
        0.20,
        (0.2, 0.3, 0.05, 0.15, 0.05),
    ),
    (
        "fellow_creator",
        "Fellow creator",
        "Makes reels too; watches how it was shot and edited.",
        ["reel tips", "editing", "lighting", "camera"],
        0.10,
        (0.6, 0.45, 0.3, 0.2, 0.4),
    ),
]
THEME_HINTS = {  # a comment theme's words → the segment it grows
    "price": "budget_shopper",
    "link": "budget_shopper",
    "where": "budget_shopper",
    "buy": "budget_shopper",
    "festive": "festive_planner",
    "festival": "festive_planner",
    "ganpati": "festive_planner",
    "how": "idea_saver",
    "tutorial": "idea_saver",
    "steps": "idea_saver",
    "edit": "fellow_creator",
    "camera": "fellow_creator",
    "light": "fellow_creator",
}


def t17(data: T17Input) -> T17Output:
    weights = {k: share for k, _l, _d, _i, share, _t in BASE_SEGMENTS}
    for theme in data.themes:
        words = set(re.findall(r"[a-z]+", theme.label.lower()))
        for w in sorted(words):
            if w in THEME_HINTS:
                weights[THEME_HINTS[w]] += theme.share
                break
    total = sum(weights.values())
    segments = [
        Segment(
            key=k,
            label=label,
            share=round(weights[k] / total, 4),
            description=desc,
            interests=interests,
        )
        for k, label, desc, interests, _s, _t in BASE_SEGMENTS
    ]
    return T17Output(segments=segments)


# ------------------------------------------------------------------ T18 · personas

LOOKS = [
    "a college student",
    "a working professional",
    "a homemaker who plans ahead",
    "a small-town shopper",
    "a big-city commuter",
    "a weekend shopper",
]
HABITS = [
    "watches on the way to work",
    "scrolls late at night",
    "saves ideas into folders",
    "sends reels to a sister",
    "reads every caption",
    "skips anything slow",
]


def _rng(*parts: object) -> random.Random:
    seed = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:16]
    return random.Random(int(seed, 16))


def t18(data: T18Input) -> T18Output:
    base = next((t for k, *_r, t in BASE_SEGMENTS if k == data.segment.key), (0.5,) * 5)
    out = []
    for i in range(data.count):
        no = data.first_agent_no + i
        r = _rng("persona", data.segment.key, no)

        patience, liker, commenter, sharer, saver = (
            round(min(1.0, max(0.0, v + r.uniform(-0.15, 0.15))), 3) for v in base
        )
        out.append(
            Persona(
                agent_no=no,
                persona_text=(
                    f"{data.segment.label}: {r.choice(LOOKS)} who {r.choice(HABITS)}. "
                    f"{data.segment.description}"
                ),
                patience=patience,
                liker=liker,
                commenter=commenter,
                sharer=sharer,
                saver=saver,
            )
        )
    return T18Output(personas=out)


# ------------------------------------------------------------------ T19 · reactions

COMMENTS = {
    "loyal_fan": ["Obsessed with this one", "You never miss", "Love how you styled it"],
    "idea_saver": ["Saving this for later", "Need a full tutorial on this", "Trying this soon"],
    "festive_planner": [
        "Perfect for the festive week",
        "Wearing this for the puja",
        "Which look for the evening?",
    ],
    "budget_shopper": ["Price please?", "Link for the kurta?", "Where is this from?"],
    "casual_scroller": ["Nice", "Cute", "Okay this is good"],
    "fellow_creator": [
        "That transition is clean",
        "What do you light this with?",
        "The pacing works",
    ],
}


def _interest(agent_interests: list[str], text: str) -> float:
    text = text.lower()
    hits = sum(1 for i in agent_interests if i.lower() in text)
    return 1.0 if hits >= 2 else 0.75 if hits == 1 else 0.45


def t19(data: T19Input) -> T19Output:
    tl = data.timeline
    duration = tl.duration_s or 15.0
    payoff = tl.payoff_s if tl.payoff_s is not None else min(4.0, duration)
    text = " ".join([tl.caption, *(p.what for p in tl.points)])
    out = []
    for a in data.agents:
        r = _rng(data.run_key, a.agent_no)
        attention = 0.55 * a.patience + 0.45 * _interest(a.interests, text)
        late = max(0.0, payoff - 1.5)  # seconds the payoff waits beyond the first beat
        p_skip = min(0.9, max(0.04, 0.62 - 0.55 * attention + 0.07 * late))
        if r.random() < p_skip:
            watch = round(min(duration, r.uniform(0.4, min(3.0, payoff + 0.5))), 1)
            out.append(
                Reaction(
                    agent_no=a.agent_no,
                    watch_until_s=watch,
                    skipped=True,
                    reason=(
                        "Scrolled on before anything happened"
                        if watch < payoff
                        else "Saw the result and moved on"
                    ),
                )
            )
            continue
        frac = min(1.0, max(0.15, 0.4 + 0.6 * attention + r.uniform(-0.2, 0.25) - 0.03 * late))
        watch = round(duration * frac, 1)
        done = frac >= 0.9
        liked = r.random() < a.liker * (0.35 + 0.55 * frac)
        commented = r.random() < a.commenter * (0.12 + (0.3 if tl.has_question else 0.0))
        shared = r.random() < a.sharer * (0.08 + (0.3 if tl.has_share_prompt else 0.0)) * frac
        saved = r.random() < a.saver * (0.12 + (0.25 if tl.has_save_prompt else 0.0)) * frac
        out.append(
            Reaction(
                agent_no=a.agent_no,
                watch_until_s=watch,
                skipped=False,
                liked=liked,
                commented=commented,
                comment_text=r.choice(COMMENTS.get(a.segment, COMMENTS["casual_scroller"]))
                if commented
                else None,
                shared=shared,
                saved=saved,
                reason=(
                    "Watched to the end for the final look"
                    if done
                    else "Lost interest halfway through"
                    if frac < 0.6
                    else "Watched most of it"
                ),
            )
        )
    return T19Output(reactions=out)


# ------------------------------------------------------------------ T20 · thread round

REPLIES = ["Same question!", "Agreed", "Following for the answer", "This is so true"]


def t20(data: T20Input) -> T20Output:
    actions = []
    if not data.comments:
        return T20Output(actions=[])
    for a in data.agents:
        r = _rng(data.run_key, "thread", a.agent_no)
        target = data.comments[int(r.random() * len(data.comments))]
        if target.agent_no == a.agent_no:
            continue
        if r.random() < 0.3 + 0.4 * a.liker:
            reply = r.choice(REPLIES) if r.random() < a.commenter * 0.5 else None
            actions.append(
                ThreadAction(
                    agent_no=a.agent_no, reply_to=target.agent_no, liked=True, reply_text=reply
                )
            )
    return T20Output(actions=actions)


# ------------------------------------------------------------------ T21 · explain


def t21(data: T21Input) -> T21Output:
    """The service tags each fact with where it belongs and when; the mock keeps the first three
    of each, word for word (so every number in them is an input number)."""
    return agents.template_explanation(data.facts)


# ------------------------------------------------------------------ T22 · talk to an agent


def t22(data: T22Input) -> T22Output:
    p, r = data.persona, data.reaction
    q = data.question.lower()
    who = p.segment_label.lower()
    if r.skipped:
        why = f"I scrolled on early. {r.reason}."
    elif r.watch_until_s >= (data.timeline.duration_s or 0) * 0.9:
        why = f"I watched it all the way through. {r.reason}."
    else:
        why = f"I watched part of it, then moved on. {r.reason}."
    if "why" in q or "skip" in q or "stop" in q:
        answer = why
    elif "change" in q or "better" in q or "improve" in q:
        answer = (
            "Show me the final result in the very first moment, then tell me how you got there. "
            "And ask me something at the end so I want to reply."
        )
    elif "share" in q or "send" in q:
        answer = (
            "I shared it — it felt made for someone I know."
            if r.shared
            else "I didn't send it to anyone. Tell me who it's for and I might."
        )
    else:
        answer = f"As a {who}, {why[0].lower()}{why[1:]}"
    return T22Output(answer=answer)
