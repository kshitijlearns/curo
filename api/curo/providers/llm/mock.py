"""Mock language model: deterministic stand-ins for each task, built only from the input.

* T2 reads the T1 description (what was said, shown on screen and seen) with keyword cues and
  reports a confidence that reflects how much evidence it found, so thin or ambiguous videos
  come out "unknown" through the same confidence rule a real model's output goes through.
* T3 labels comments with English, Hinglish and Hindi keyword lists.
* T4 names a group by what most of its samples share.

* T5 names opportunities from their evidence; the Studio tasks (T6–T8, T11–T13) live in
  ``mock_studio``.

No task ever sees the fixture's answers.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable

from pydantic import BaseModel

from curo.providers.mock_text import concepts, count
from curo.schemas.tasks import (
    CommentLabel,
    ContentDNA,
    ProductionDNA,
    T1Output,
    T2Input,
    T2Output,
    T3Input,
    T3Output,
    T4Input,
    T4Output,
    T5Input,
    T5Output,
    T10Input,
    T10Output,
    TaskSpec,
)
from curo.schemas.taxonomy import UNKNOWN

from . import mock_audience, mock_sim, mock_studio, mock_trends
from .base import LLMError, LLMProvider


class MockLLMProvider(LLMProvider):
    name = "mock"

    def model_for(self, task: TaskSpec) -> str:
        return f"mock-{task.tier}-v1"

    def _call(self, task: TaskSpec, data: BaseModel):
        handler: Callable | None = _HANDLERS.get(task.id)
        if handler is None:
            raise LLMError(f"mock has no handler for {task.id}")
        return handler(data)

    def _chat(self, data):
        from curo.providers.llm import mock_chat

        yield from mock_chat.t14(data)


# ====================================================================== T2 · DNA


def _pick(
    scores: dict[str, float], *, fallback: tuple[str, float] | None = None
) -> tuple[str, float]:
    """Best-scoring value and a confidence from the strength of its evidence and the
    strength of the runner-up (a close second means less certainty)."""
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    best_value, best = ranked[0] if ranked else (UNKNOWN, 0.0)
    if best <= 0:
        return fallback or (UNKNOWN, 0.3)
    second = ranked[1][1] if len(ranked) > 1 else 0.0
    conf = 0.45 + 0.17 * min(best, 3.0) - 0.25 * (second / best)
    return best_value, round(max(0.2, min(0.97, conf)), 2)


def _score(text: str, cues: dict[str, tuple[str, float]]) -> dict[str, float]:
    return {value: count(pattern, text) * weight for value, (pattern, weight) in cues.items()}


FORMAT_CUES = {
    "grwm": (r"\bgrwm\b|get(?:ting)? ready with me", 1.0),
    "haul": (r"\bhaul\b|first up, i got|next, i got", 1.0),
    "multi_look": (r"\bsame \w+, look number|restyled for the next look|\bways to wear\b", 1.0),
    "lookbook": (
        r"look number \d+: i'm wearing|turns to show the|full-length shot of the next look",
        1.0,
    ),
    "listicle": (r"\b(?:mistake|tip) number \d|\b(?:mistake|tip) \d\b", 1.0),
    "tutorial": (r"\bstep \d|demonstrates each step", 1.0),
    "before_after": (r"before and after", 1.0),
    "vlog": (r"this morning|day in (?:my|the) life", 1.0),
}
HOOK_CUES = {
    "mistake": (r"mistake|\bwrong\b|ruining|\bstop (?:doing|filming)", 2.0),
    "reveal": (r"final look first|\breveal", 2.0),
    "how_to": (r"\bhere'?s how\b|^how (?:i|to)\b", 2.0),
    "story": (r"so this happened|story time|what i wore", 2.0),
    "curiosity_gap": (r"wait till|wait until|you won'?t believe|worth it|hits and misses", 1.5),
    "budget": (r"₹|\bbudget\b|\bcheap\b", 1.5),
    "relatable": (r"get ready with me|\bgrwm\b|\bpov\b|running late", 1.5),
    "question": (r"^(?:do|does|are|is|have|why do)\b[^.?!]*\?", 1.5),
    "number_list": (
        r"^\W*(?:one|two|three|four|five|six|\d+)\b|\b(?:two|three|four|five|six|nine|\d) "
        r"(?:ways|looks|outfits|drapes|occasions|sarees|dupattas|styles|blouses)\b",
        1.0,
    ),
    "bold_claim": (r"only way|only \w+ you need|trust me", 1.0),
    "before_after": (r"before and after", 1.5),
    "transformation": (r"transform|glow ?up", 1.5),
    "challenge": (r"\bi tried\b|challenge", 1.5),
}
OPENING_CUES = {
    "face_to_camera": (r"talks straight to the camera|speaks to (?:the )?camera", 1.0),
    "final_look_first": (r"finished look is shown first|final look first", 1.0),
    "product_closeup": (r"close-up of the [\w\s-]+ in hand", 1.0),
    "mirror_shot": (r"mirror shot", 1.0),
    "action_mid_shot": (r"already mid-way|mid-way through", 1.0),
    "text_over_broll": (r"text over b-roll", 1.0),
}
NARRATIVE_CUES = {
    "reveal_then_explain": (r"let me show you how|final look first", 2.0),
    "comparison": (r"last year|this year", 1.5),
    "step_by_step": (r"\bstep \d|starting with|now the outfit|quick base", 1.0),
    "list": (r"\b(?:mistake|tip|look) number \d|first up|next, i got", 1.0),
    "day_in_the_life": (r"this morning|tonight", 1.0),
    "story_arc": (r"so this happened|in the end", 1.0),
    "problem_solution": (r"the problem|the fix", 1.0),
    "before_after": (r"before and after", 1.0),
}
ENDING_CUES = {
    "choice_question": (
        r"which (?:one|look|step) (?:would|were|do) you|pick one|which one would you",
        1.0,
    ),
    "recap": (r"\brecap\b", 1.0),
    "final_look": (r"final look", 1.0),
    "reveal": (r"that'?s the reveal|final reveal", 1.0),
    "cliffhanger": (r"part two tomorrow|to be continued", 1.0),
    "open_question": (r"what would you add|let me know", 1.0),
}
CTA_CUES = {
    "save_prompt": (r"\bsave (?:this|it)\b", 1.0),
    "share_prompt": (r"send (?:this|it) to|share (?:this|it) with", 1.0),
    "comment_prompt": (r"tell me in the comments|comment below|comment your", 1.0),
    "part_two_tease": (r"follow for part two", 1.5),
    "follow_prompt": (r"follow for more", 1.0),
}
CAMERA_CUES = {
    "tripod": (r"tripod", 1.0),
    "handheld": (r"handheld", 1.0),
    "mirror_selfie": (r"mirror selfie|filmed in the mirror", 1.0),
    "selfie_handheld": (r"selfie-style|arm'?s length", 1.0),
}
LIGHT_CUES = {
    "warm_light": (r"warm light|warm golden", 1.0),
    "natural_light": (r"daylight|window light", 1.0),
    "bright_even": (r"bright, even light|evenly lit|ring light", 1.0),
    "moody": (r"moody|\bdim\b", 1.0),
    "colourful": (r"colourful|saturated", 1.0),
}
SETTING_CUES = {
    "bedroom": (r"bedroom|wardrobe", 1.0),
    "living_room": (r"living room|on the sofa", 1.0),
    "outdoors": (r"outdoors|on the street|balcony", 1.0),
    "market": (r"market stall|busy market", 1.0),
    "studio": (r"studio backdrop", 1.0),
    "event_venue": (r"decorated (?:pandal|venue)", 1.0),
    "office": (r"office desk", 1.0),
}
# Scored on presence, not repetition: the weights say which tension drives a reel that shows
# several (a budget haul that ends on a question is still about the budget).
TENSION_CUES = {
    "doing_it_wrong": (r"mistake|\bwrong\b|ruining", 3.5),
    "budget_limit": (r"₹|\bbudget\b|\bprice\b|\bhaul\b", 3.0),
    "choice_dilemma": (
        r"which (?:look|one|step) (?:would|were|do) you|pick one|which one would you",
        2.5,
    ),
    "comparison": (r"last year|this year", 2.0),
    "transformation": (r"transform|glow ?up|final look first", 1.5),
    "insider_tip": (r"here'?s how|\bstep \d|secret|\btip number", 1.0),
    "relatable_struggle": (r"running late|humidity|every single time", 1.0),
}
CONTEXT_ORDER = (
    ("wedding", r"wedding|sangeet|haldi|mehendi|shaadi"),
    (
        "festive",
        r"ganpati|ganesh|diwali|navratri|\beid\b|\bholi\b|karva|raksha|independence|christmas"
        r"|visarjan|pandal|dussehra|festive",
    ),
    ("work", r"\boffice\b|\bstudio\b"),
    ("seasonal", r"monsoon|\brain\b"),
    ("sale", r"\bsale\b"),
)
ENTITIES = (
    r"\b(?:lehenga|saree|kurta|dupatta|anarkali|sharara set|kurta set|chaniya choli|jhumkas"
    r"|potli bag|kolhapuri chappals|choker|bangles|earrings|tote bag|juttis|co-ord set|denim jacket"
    r"|blouses?|shirt|sneakers|mumbai|pune|colaba causeway|linking road|hill road|lalbaug)\b"
)


def _hook_text(t1: T1Output) -> str:
    said = t1.transcript_text()
    if said:
        m = re.search(r"^(.+?[.?!])(?:\s|$)", said)
        return (m.group(1) if m else said)[:120]
    return t1.onscreen_text[0].text[:120] if t1.onscreen_text else ""


def t2(data: T2Input) -> T2Output:
    t1 = data.understanding
    duration = t1.duration_s or data.duration_s or 0.0
    said = t1.transcript_text().lower()
    screen = " | ".join(o.text for o in t1.onscreen_text).lower()
    seen = " | ".join(s.description for s in t1.seconds).lower()
    caption = (data.caption + " " + " ".join("#" + h for h in data.hashtags)).lower()
    everything = " | ".join((said, screen, seen, caption))

    opening_seen = " | ".join(s.description for s in t1.seconds if s.t < 2).lower()
    last_word = t1.transcript[-1].t if t1.transcript else 0.0
    hook_said = " ".join(w.word for w in t1.transcript if w.t <= 6.0).lower()
    first_screen = t1.onscreen_text[0].text.lower() if t1.onscreen_text else ""
    end_said = " ".join(w.word for w in t1.transcript if w.t >= last_word - 9.0).lower()
    end_screen = " | ".join(o.text for o in t1.onscreen_text if o.t >= duration - 4).lower()
    end_seen = " | ".join(s.description for s in t1.seconds if s.t >= duration - 3).lower()
    ending_text = " | ".join((end_said, end_screen, end_seen))
    speech = bool(t1.transcript)

    conf: dict[str, float] = {}

    def field(name: str, value_conf: tuple[str, float]) -> str:
        value, c = value_conf
        conf[name] = c
        return value

    # --- production
    fmt = field("format", _pick(_score(everything, FORMAT_CUES)))
    hook_scores = {}
    for source in (hook_said, first_screen):
        for value, s in _score(source, HOOK_CUES).items():
            hook_scores[value] = max(hook_scores.get(value, 0.0), s)
    if t1.audio_type == "trending_audio" and not hook_said:
        # No voice over a trending sound: the sound is the hook, unless the on-screen title
        # carries a strong hook of its own.
        strong = {v: s for v, s in hook_scores.items() if s and HOOK_CUES[v][1] >= 1.5}
        hook_scores = strong or {"trend_audio": 2.0}
    hook = field("hook_type", _pick(hook_scores))
    opening = field("opening_style", _pick(_score(opening_seen, OPENING_CUES)))
    narrative = field("narrative", _pick(_score(said + " | " + seen, NARRATIVE_CUES)))
    ending_fallback = ("abrupt", 0.66) if speech else None
    ending = field("ending", _pick(_score(ending_text, ENDING_CUES), fallback=ending_fallback))
    cta = field(
        "cta_type",
        _pick(
            _score(said + " | " + screen, CTA_CUES),
            fallback=("none", 0.7 if (speech or screen) else 0.3),
        ),
    )
    if speech:
        first = count(r"\b(?:i|i'm|i've|my|me|mine)\b", said)
        second = count(r"\b(?:you|your|you're|yours)\b", said)
        total = first + second
        if total == 0:
            pov = field("pov", ("observational", 0.6))
        else:
            value = "first_person" if first > second else "second_person"
            pov = field("pov", (value, round(0.55 + 0.4 * abs(first - second) / total, 2)))
    else:
        pov = field("pov", ("observational", 0.7))
    camera = field("camera", _pick(_score(seen, CAMERA_CUES)))
    audio = field("audio", (t1.audio_type, 0.9) if t1.audio_type else (UNKNOWN, 0.3))
    visual = field("visual_style", _pick(_score(seen, LIGHT_CUES)))
    setting = field("setting", _pick(_score(seen, SETTING_CUES)))
    cuts = None
    if duration and len(t1.shots) > 1:
        cuts = round((len(t1.shots) - 1) / duration * 10, 1)
    conf["cuts_per_10s"] = 0.9 if cuts is not None else 0.3
    hook_text = _hook_text(t1)
    conf["hook_text"] = 0.85 if hook_text else 0.3

    # --- content: what the reel is about, from what is said and written (not camera notes)
    about = " | ".join((said, screen, caption))
    fashion = count(
        r"outfit|\blook\b|wear|style|jacket|shirt|co-ord|earrings|juttis|tote|haul|grwm", about
    )
    k = concepts(about)
    cluster_scores = {
        "fashion_styling": fashion + k["ethnicwear"] + k["restyling"] + k["shopping"],
        "creator_tips": 1.5 * k["filmmaking"],
        "beauty": 0.5 * k["grooming"],
        "food": count(r"recipe|modak|prasad|cook", about),
    }
    total = sum(cluster_scores.values())
    best = max(cluster_scores, key=cluster_scores.get)
    cluster = field(
        "cluster",
        (best, round(min(0.95, 0.4 + 0.6 * cluster_scores[best] / total), 2))
        if total
        else (UNKNOWN, 0.3),
    )
    context, context_conf = "everyday", 0.66
    for value, pattern in CONTEXT_ORDER:
        hits = count(pattern, caption + " | " + said)
        if hits:
            context, context_conf = value, round(min(0.95, 0.62 + 0.1 * hits), 2)
            break
    context = field("context", (context, context_conf))
    if re.search(r"with a friend", seen):
        characters = field("characters", ("creator_with_friend", 0.8))
    elif re.search(r"\bthe creator\b", seen):
        characters = field("characters", ("creator_solo", 0.8))
    else:
        characters = field("characters", (UNKNOWN, 0.4))
    tension_scores = {
        v: (w if count(p, " | ".join((said, screen, caption))) else 0.0)
        for v, (p, w) in TENSION_CUES.items()
    }
    tension = field("core_tension", _pick(tension_scores, fallback=("none", 0.62)))
    entities = list(dict.fromkeys(m.lower() for m in re.findall(ENTITIES, everything)))[:8]
    conf["key_entities"] = 0.8 if entities else 0.3

    return T2Output(
        content=ContentDNA(
            cluster=cluster,
            context=context,
            characters=characters,
            core_tension=tension,
            key_entities=entities,
        ),
        production=ProductionDNA(
            format=fmt,
            hook_type=hook,
            hook_text=hook_text,
            opening_style=opening,
            narrative=narrative,
            ending=ending,
            cta_type=cta,
            pov=pov,
            camera=camera,
            cuts_per_10s=cuts,
            audio=audio,
            visual_style=visual,
            setting=setting,
        ),
        confidence=conf,
    )


# ====================================================================== T3 · comments

BOT = re.compile(
    r"dm (?:us|now|for)|follow back|check my profile|click link|link in bio|earn \$|promote your page"
    r"|want more followers|💯💯💯",
    re.IGNORECASE,
)
REQUEST = re.compile(
    r"part ?2|part two|dusra part|please (?:make|do)|do one for|next (?:please|pls)|version please"
    r"|version bhi|video banao|banao na|dikhao|ideas next|ideas for [\w\s]+ please|kya pehnu",
    re.IGNORECASE,
)
QUESTION = re.compile(
    r"\?|\b(?:where|which|how|what|kahan|kaha|kaise|kitne|kitna)\b|\bkya\b(?! baat)|drop the link"
    r"|link please|कहाँ|कितने|कैसे",
    re.IGNORECASE,
)
THATS_ME = re.compile(
    r"literally me|\bso me\b|this is me|mera haal|same yaar|called out|sirf main|मैं हूँ|me every",
    re.IGNORECASE,
)
SAVE = re.compile(r"saving this|save kar|bookmark", re.IGNORECASE)
DISAGREE = re.compile(
    r"not new|boring|too much|not your best|too loud|seen it|disagree", re.IGNORECASE
)
PRAISE = re.compile(
    r"pretty|\blove\b|obsessed|kya baat|sundar|सुंदर|nail it|beautiful|gorgeous|😍|🔥|❤️|💛|💖",
    re.IGNORECASE,
)
THEMES = (
    ("question", "asks the price", r"price|kitne|kitna|how much|under \d+|कितने|₹"),
    ("question", "asks where it's from", r"where|kahan|kaha|\blink\b|store|market|कहाँ|from\b"),
    ("question", "asks about camera and editing", r"camera|\bapp\b|edit|lighting|lens|transition"),
    ("request", "wants a part 2", r"part ?2|part two|dusra part"),
    ("request", "wants budget versions", r"budget|sasta|under \d+ version|cheap"),
    ("request", "wants festive looks", r"ganpati|navratri|festive|diwali"),
)


def _theme(intent: str, text: str) -> str | None:
    if intent not in ("question", "request"):
        return None
    for kind, label, pattern in THEMES:
        if kind == intent and re.search(pattern, text, re.IGNORECASE):
            return label
    return "other question" if intent == "question" else "other request"


def label_comment(cid: str, text: str) -> CommentLabel:
    t = text.strip()
    if BOT.search(t):
        return CommentLabel(id=cid, is_bot=True, sentiment="neutral", intent="other")
    if t.startswith("@"):
        intent = "tags_friend"
    elif REQUEST.search(t):
        intent = "request"
    elif QUESTION.search(t):
        intent = "question"
    elif THATS_ME.search(t):
        intent = "thats_me"
    elif SAVE.search(t):
        intent = "plans_to_save"
    elif DISAGREE.search(t):
        intent = "disagreement"
    elif PRAISE.search(t):
        intent = "praise"
    else:
        intent = "other"
    if intent == "disagreement":
        sentiment = "negative"
    elif intent in ("praise", "thats_me", "plans_to_save") or PRAISE.search(t):
        sentiment = "positive"
    else:
        sentiment = "neutral"
    return CommentLabel(
        id=cid, is_bot=False, sentiment=sentiment, intent=intent, theme=_theme(intent, t)
    )


def t3(data: T3Input) -> T3Output:
    return T3Output(labels=[label_comment(c.id, c.text) for c in data.comments])


# ====================================================================== T4 · names

REEL_GROUP_CUES = (
    ("Get ready with me", r"\bgrwm\b|get ready with me"),
    ("Hauls", r"\bhaul\b"),
    (
        "Reel-making tips",
        r"\breels?\b|lighting|camera|framing|transitions?|b-roll|angles|editing|blurry",
    ),
    (
        "One item, many looks",
        r"\bsame \w+|\bways\b|\b(?:one|two) [\w\s-]+?, (?:two|three|four|five|six|\d)\b|drapes|occasions",
    ),
    (
        "Festive styling",
        r"ganpati|diwali|navratri|\beid\b|\bholi\b|karva|raksha|independence|festive|wedding|haldi|sangeet|christmas",
    ),
)


def t4(data: T4Input) -> T4Output:
    votes: Counter[str] = Counter()
    for sample in data.samples:
        text = sample.lower()
        if data.kind == "comments":
            for _kind, label, pattern in THEMES:
                if re.search(pattern, text):
                    votes[label[0].upper() + label[1:]] += 1
                    break
        else:
            for label, pattern in REEL_GROUP_CUES:
                if re.search(pattern, text):
                    votes[label] += 1
                    break
    if votes:
        label, n = votes.most_common(1)[0]
        if n / len(data.samples) >= 0.4:
            return T4Output(label=label)
    return T4Output(label="Mixed")


# ====================================================================== T10 · explanations

EXPLANATION_LEADS = {
    "comments_high": "This topic is sparking conversations",
    "comments_low": "Fewer people stopped to comment this time",
    "shares_high": "People are passing this one on",
    "shares_low": "This reel isn’t being sent on much",
    "likes_high": "Viewers liked what they saw",
    "likes_low": "Fewer viewers liked it than usual",
    "tagging_friends": "Tags are the visible sign that people pass a reel on",
    "followers_jumped": "New followers arrived alongside this reel",
    "theme": "Your audience is telling you what they want next",
}


def t10(data: T10Input) -> T10Output:
    """One sentence: a lead for the kind of result, then the most telling fact (the second
    fact when there is one; the first is the headline number the card already shows)."""
    lead = EXPLANATION_LEADS.get(data.kind, data.title)
    fact = (data.facts[1] if len(data.facts) > 1 else data.facts[0]).rstrip(".")
    return T10Output(text=f"{lead}: {fact[0].lower()}{fact[1:]}.")


# ====================================================================== T5 · opportunity names

DRESS_WORDS = ("outfit", "look", "saree", "lehenga", "kurta", "dress", "dupatta", "ethnic")
THEME_NAMES = (
    (r"where", "Where your looks are from"),
    (r"price|budget", "Looks on a budget"),
    (r"camera|editing|lighting", "Your filming setup, explained"),
    (r"part 2", "Part 2 of your best reel"),
    (r"festive", "Festive looks"),
)
TAG_NAMES = (
    (r"reveal", "The final-look-first reveal"),
    (r"mistake", "“Mistakes” explainers"),
    (r"grwm", "Get-ready-with-me"),
    (r"haul", "Hauls"),
    (r"festive", "Festive styling"),
)


def _first_upper(s: str) -> str:
    return s[0].upper() + s[1:] if s else s


def t5(data: T5Input) -> T5Output:
    """A name from the strongest evidence, and sentences that are the facts themselves."""
    words = " ".join(data.keywords + data.hashtags + data.example_titles).lower()
    if data.festival:
        short = (data.keywords[0] if data.keywords else data.festival.split()[0]).capitalize()
        name = (
            f"{short} dress ideas"
            if any(w in words for w in DRESS_WORDS)
            else f"{short} content ideas"
        )
    elif data.follow_up_of:
        name = "Follow up your best reel"
    elif data.themes:
        theme = " ".join(data.themes)
        name = next(
            (n for p, n in THEME_NAMES if re.search(p, theme)), _first_upper(data.themes[0])
        )
    elif data.hashtags:
        tags = " ".join(data.hashtags)
        name = next((n for p, n in TAG_NAMES if re.search(p, tags)), f"#{data.hashtags[0]} reels")
    elif data.subcluster:
        name = f"More {data.subcluster.lower()}"
    else:
        name = _first_upper(" ".join(data.keywords[:3])) or "A new topic"
    description = " ".join(data.lead_facts[:2])
    why = data.fit_facts[0] if data.fit_facts else data.lead_facts[0]
    return T5Output(name=name[:60], description=description[:400], why_it_fits=why[:240])


_HANDLERS: dict[str, Callable] = {
    "T2": t2,
    "T3": t3,
    "T4": t4,
    "T5": t5,
    "T6": mock_studio.t6,
    "T7": mock_studio.t7,
    "T8": mock_studio.t8,
    "T10": t10,
    "T11": mock_studio.t11,
    "T12": mock_studio.t12,
    "T13": mock_studio.t13,
    "T15": mock_sim.t15,
    "T16": mock_trends.t16,
    "T17": mock_audience.t17,
    "T18": mock_audience.t18,
    "T19": mock_audience.t19,
    "T20": mock_audience.t20,
    "T21": mock_audience.t21,
    "T22": mock_audience.t22,
}
