"""Template persona text, built from code facts only (v2.2 §10).

These are the mocks for T25–T28 and the fallbacks when a model's output fails the
no-new-numbers check or the sensitive-attribute check twice. They never contain a number (so
they always pass the validator) and never name a sensitive attribute.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from curo.schemas.tasks import (
    PersonaBrief,
    PersonaGroupIn,
    PersonaReaction,
    PersonaThought,
    ThoughtIn,
    Would,
    WrittenPersona,
)
from curo.services.personas import NICHE_NOUNS, REACTION_WORDS, reaction_for, words_of

# Names by what a group's comments are about (checked first), then by their main intent.
THEME_NAMES = [
    (r"price|budget|cheap|afford|cost|under|sale|deal", ("The Budget Stylist", "Budget Stylist")),
    (r"festiv|festival|ganpati|diwali|navratri|eid|puja|wedding|mehendi|haldi|occasion",
     ("The Festive Planner", "Festive Planner")),
    (r"where|link|buy|shop|brand|store|available", ("The Smart Shopper", "Smart Shopper")),
    (r"how|tutorial|steps|tips|learn|explain", ("The Eager Learner", "Eager Learner")),
]  # fmt: skip
INTENT_NAMES = {
    "question": [("The Curious Asker", "Curious Asker"), ("The Detail Seeker", "Detail Seeker")],
    "request": [("The Idea Requester", "Idea Requester"), ("The Wishlist Keeper", "Wishlist Keeper")],
    "plans_to_save": [("The Idea Saver", "Idea Saver"), ("The Weekend Planner", "Weekend Planner")],
    "tags_friend": [("The Friend Tagger", "Friend Tagger"), ("The Group-Chat Sharer", "Group-Chat Sharer")],
    "praise": [("The Loyal Fan", "Loyal Fan"), ("The Cheerleader", "Cheerleader")],
    "thats_me": [("The Same-Here Crowd", "Same-Here Crowd"), ("The Relater", "Relater")],
    "disagreement": [("The Honest Critic", "Honest Critic"), ("The Second Opinion", "Second Opinion")],
    "other": [("The Quiet Watcher", "Quiet Watcher"), ("The Casual Scroller", "Casual Scroller")],
}  # fmt: skip
SPARE = [("The Regular", "Regular"), ("The Explorer", "Explorer"), ("The Browser", "Browser")]
TAGLINES = {
    "The Budget Stylist": "Wants the look without the big spend.",
    "The Festive Planner": "Plans every festival look weeks ahead.",
    "The Smart Shopper": "Always asking where it’s from.",
    "The Eager Learner": "Here to pick up how you do it.",
    "The Curious Asker": "Wants the details behind every reel.",
    "The Detail Seeker": "Reads the caption, then asks for more.",
    "The Idea Requester": "Has a list of reels they want from you.",
    "The Wishlist Keeper": "Keeps asking for the next version.",
    "The Idea Saver": "Saves your ideas to try later.",
    "The Weekend Planner": "Bookmarks reels for their next free day.",
    "The Friend Tagger": "Sends your reels to the group chat.",
    "The Group-Chat Sharer": "Shares first, comments later.",
    "The Loyal Fan": "Shows up for every post and cheers you on.",
    "The Cheerleader": "Leaves the warmest comments under your reels.",
    "The Same-Here Crowd": "Sees themselves in your reels.",
    "The Relater": "Comments “literally me” and means it.",
    "The Honest Critic": "Tells you what they’d change, kindly.",
    "The Second Opinion": "Likes to weigh in with their own take.",
    "The Quiet Watcher": "Watches a lot, says a little.",
    "The Casual Scroller": "Stops only when something catches the eye.",
}
TYPICAL = {
    "question": ("Where is this from? Need the details!", "Yeh kahan se liya? Details do na!"),
    "request": ("Please do a version of this for everyday!", "Iska everyday version bhi banao na!"),
    "plans_to_save": ("Saving this to try next weekend!", "Save kar liya, next weekend try karenge!"),
    "tags_friend": ("This is so us, we have to try it!", "Yeh toh bilkul hum hain, try karna padega!"),
    "praise": ("Obsessed with this, you never miss!", "Uff, too good yaar, you never miss!"),
    "thats_me": ("This is literally me every single time.", "Literally me, har baar yahi hota hai."),
    "disagreement": ("Nice, but I’d have gone with a different colour.", "Nice, but colour thoda alag hota toh better."),
    "other": ("Love this one!", "Love this one yaar!"),
}  # fmt: skip
ENGAGE = {
    "question": "Mostly asks questions in the comments and waits for your reply.",
    "request": "Asks for new versions and follow-ups.",
    "plans_to_save": "Says they’ll save it or try it; comes back for the steps.",
    "tags_friend": "Tags friends and sends reels on more than they comment.",
    "praise": "Leaves warm comments and emojis; rarely asks questions.",
    "thats_me": "Replies “same” and shares the moments that feel like theirs.",
    "disagreement": "Weighs in with their own take, politely.",
    "other": "Reacts briefly when something catches the eye.",
}
DEFAULT_WANTS = {
    "question": "details in the caption",
    "request": "follow-up reels",
    "plans_to_save": "save-worthy round-ups",
    "tags_friend": "reels made to share",
    "praise": "more of your everyday reels",
    "thats_me": "more relatable moments",
    "disagreement": "a little more variety",
    "other": "quick, eye-catching reels",
}
DEFAULT_OFFS = {
    "question": "reels that skip the details",
    "request": "reels that never follow up",
    "plans_to_save": "reels that rush the steps",
    "tags_friend": "reels with nothing to react to",
    "praise": "long gaps between posts",
    "thats_me": "reels that feel staged",
    "disagreement": "the same idea twice in a row",
    "other": "slow starts",
}
DEFAULT_LOVES = {
    "question": ["reels that answer “where” and “how”", "details in the caption"],
    "request": ["reels that follow up on requests", "new takes on your best ideas"],
    "plans_to_save": ["clear step-by-step reels", "round-ups worth saving"],
    "tags_friend": ["relatable moments", "reels made to share"],
    "praise": ["your signature style", "behind-the-scenes moments"],
    "thats_me": ["everyday moments", "honest takes"],
    "disagreement": ["fresh ideas", "honest comparisons"],
    "other": ["quick reveals", "eye-catching openings"],
}


def _clean_theme(label: str) -> str:
    """ "asks where to buy" → "where to buy"; "wants budget versions" → "budget versions"."""
    words = label.strip().rstrip(".").split()
    if words and words[0].lower() in ("asks", "ask", "wants", "want", "requests", "asking"):
        words = words[1:]
    return " ".join(words) or label


def _hash(*parts: object) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:8], 16)


def main_intents(d: dict[str, Any]) -> list[str]:
    """The group's intents, most common first — "other" (no clear intent) only when nothing
    else reaches 15% of its comments."""
    items = d.get("intents") or []
    clear = [
        i["intent"] for i in items if i["intent"] != "other" and (i.get("share") or 0.15) >= 0.15
    ]
    return clear + [i["intent"] for i in items if i["intent"] not in clear] or ["other"]


def pick_names(groups: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Distinct, kind names: a theme name first, else the main intent's, else a spare."""
    used: set[str] = set()
    out = []
    for g in groups:
        themes = " ".join(t["label"] for t in g.get("themes", [])).lower()
        intents = main_intents(g)
        options = [n for pat, n in THEME_NAMES if re.search(pat, themes)]
        for i in intents:
            options += INTENT_NAMES.get(i, INTENT_NAMES["other"])
        options += SPARE
        name = next(n for n in options if n[0] not in used)
        used.add(name[0])
        out.append(name)
    return out


def _noun(niche: str | None, i: int) -> str:
    return NICHE_NOUNS.get(niche or "lifestyle", NICHE_NOUNS["lifestyle"])[i]


def write_template(
    group: PersonaGroupIn, name: tuple[str, str], niche: str | None, hinglish: bool
) -> WrittenPersona:
    d = group.data
    intent = main_intents(d)[0]
    loves: list[str] = []
    seen: set[str] = set()
    for i in d.get("loves", []):
        # A topic and a format can name the same thing ("Hauls" reels, haul reels): keep one.
        stem = {w.rstrip("s") for w in re.findall(r"[a-z]+", i["label"].lower())}
        if stem & seen:
            continue
        seen |= stem
        loves.append(
            f"{i['label']} reels" if i["kind"] == "format" else f"your “{i['label']}” reels"
        )
    loves = loves[:4]
    loves = (loves + [x for x in DEFAULT_LOVES[intent] if x not in loves])[: max(2, len(loves))]
    wants = [_clean_theme(t["label"]) for t in d.get("themes", [])][:2] or [DEFAULT_WANTS[intent]]
    offs = [
        f"{i['label']} reels" if i["kind"] == "format" else f"your “{i['label']}” reels"
        for i in d.get("turn_offs", [])
    ][:3] or [DEFAULT_OFFS[intent]]
    comes = [f"your {t.lower()} reels" for t in d.get("comes_for_hint", [])[:2]]
    comes += [f"your {_noun(niche, 0)}", _noun(niche, 2)]
    comes = list(dict.fromkeys(comes))[:4]
    engage = ENGAGE[intent]
    if d.get("tags_friend", 0) >= 0.1 and intent != "tags_friend":
        engage += " Often tags a friend."
    voice = "warm and chatty, a little Hinglish (“yaar”)" if hinglish else "warm, practical, short"
    keep = (group.keep_name, group.keep_short_name)
    nm, short = keep if keep[0] and keep[1] else name
    return WrittenPersona(
        key=group.key,
        name=nm,
        short_name=short,
        tagline=TAGLINES.get(nm, "A group of people who keep coming back to your reels."),
        comes_for=comes,
        loves=loves,
        wants_more=wants[:3],
        turn_offs=offs,
        engagement_style=engage[:160],
        voice=voice,
        typical_comment=TYPICAL.get(intent, TYPICAL["other"])[1 if hinglish else 0],
    )


def _short(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(",;:")
    return cut + "…"


def thought_template(t: ThoughtIn) -> PersonaThought:
    love = (t.loves or ["your reels"])[0]
    want = (t.wants_more or ["more of this"])[0]
    lines = {
        "love": f"Your {_bare(love)} are exactly why I follow you. Keep them coming!",
        "like": f"I’m here for your {_bare(love)}. Add {want} and I’m hooked.",
        "neutral": f"I come for your {_bare(love)}. Show me {want} and I’ll stay longer.",
        "unsure": f"I scroll past when there’s no {want}. Your {_bare(love)} still pull me in.",
        "skip": f"I’m not feeling it lately. Give me {want} and I’ll be back.",
    }
    mood = t.mood_hint if t.mood_hint in lines else "neutral"
    return PersonaThought(
        key=t.key,
        thought=_short(lines[mood], 140),
        mood=mood,
        loves=(t.loves or ["your reels"])[:2],
        wants_more=(t.wants_more or [])[:2],
    )


def _bare(phrase: str) -> str:
    return re.sub(r"^your\s+", "", phrase.strip(), flags=re.IGNORECASE)


def opinion_for(p: PersonaBrief, reaction: str) -> str:
    """A first-person line that says what the reaction says (no numbers)."""
    love = _bare((p.loves or ["your reels"])[0])
    want = (p.wants_more or ["a clearer payoff"])[0]
    opinion = {
        "watch_all": f"I’d watch this to the end: it’s the {love} I come for.",
        "watch": f"I’d watch this. It’s close to the {love} I like.",
        "scroll_past": f"I might scroll past. I come for {love}, and this feels further away.",
        "skip": "I’d skip this one. It isn’t what I follow you for.",
    }[reaction]
    if reaction != "watch_all":
        opinion += f" Show me {want} and you’ve got me."
    return _short(opinion, 280)


def reaction_template(
    p: PersonaBrief, idea: str, draft: str | None, target: str
) -> PersonaReaction:
    """A deterministic reaction from keyword overlap with what the persona loves and skips."""
    text = f"{idea} {draft or ''}"
    mine = words_of(text)
    likes = words_of(" ".join(p.loves + p.comes_for + p.wants_more))
    dislikes = words_of(" ".join(p.turn_offs))
    hits, misses = len(mine & likes), len(mine & dislikes)
    jitter = _hash(p.key, idea, target) % 17 - 8
    score = max(5, min(95, 48 + 12 * min(hits, 3) - 14 * min(misses, 2) + jitter))
    reaction = reaction_for(score)
    want = (p.wants_more or ["a clearer payoff"])[0]
    opinion = opinion_for(p, reaction)
    return PersonaReaction(
        key=p.key,
        reaction=reaction,  # type: ignore[arg-type]
        score=score,
        would=Would(
            like=score >= 45,
            comment=score >= 60 and _hash(p.key, "c", idea) % 2 == 0,
            share=score >= 70,
            save=score >= 65,
        ),
        opinion=_short(opinion, 280),
        win_them_over=_short(f"Add {want}.", 120),
        evidence_ids=[e.id for e in p.evidence[:2]],
    )


HONEST = "I’m a summary of your comments, so I can’t tell you that."


def chat_template(p: PersonaBrief, question: str, context: str | None) -> str:
    q = question.lower()
    love = _bare((p.loves or ["your reels"])[0])
    want = (p.wants_more or ["more of this"])[0]
    off = (p.turn_offs or ["slow starts"])[0]
    if re.search(r"\b(who are you|real|age|old|where do you live|name|gender|religion|vote)\b", q):
        return f"{HONEST} I’m {p.name}: what a group of your commenters has in common."
    if re.search(r"\b(how many|number|percent|%|exact)\b", q):
        return f"{HONEST} What I can say is that I keep coming back for {love}."
    if re.search(r"\bshare|send\b", q):
        return (
            f"I’d send it on if it felt made for someone I know. {want.capitalize()} would do it."
        )
    if re.search(r"\bwhy|skip|scroll\b", q):
        return f"I scroll past {off}. I stay for {love}."
    if re.search(r"\bnext|want|more|make\b", q):
        return f"Next, I’d love {want}. And keep the {love} coming."
    if context:
        return f"From what I see in this draft: lead with {love}, and don’t forget {want}."
    return f"I come for {love}. If you give me {want}, I’m there."


# The classifier's mock: implications a word list misses (T29).
IMPLIED = {
    "age": r"\b(college[- ]?going|hostel|exam season|retired|pension|grandkids?)\b",
    "gender": r"\b(aunty|aunties|auntie|bhabhi|didi|bhaiya|bride[- ]to[- ]be|groom[- ]to[- ]be|newlywed)\b",
    "income": r"\b(tight budget every month|paycheck|emi[s]?)\b",
    "health": r"\b(new mum|new mom|on medication|diet for)\b",
    "location": r"\b(my area|my building|my society)\b",
}


def classify_template(texts: list[str]) -> list[tuple[int, str]]:
    from curo.services.persona_safety import keyword_flags

    out = []
    for i, t in enumerate(texts):
        for attr in sorted(keyword_flags(t)):
            out.append((i, attr))
        for attr, pat in IMPLIED.items():
            if re.search(pat, t or "", re.IGNORECASE):
                out.append((i, attr))
    return out


__all__ = [
    "REACTION_WORDS",
    "chat_template",
    "classify_template",
    "pick_names",
    "reaction_template",
    "thought_template",
    "write_template",
]
