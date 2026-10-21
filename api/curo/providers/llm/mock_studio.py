"""Mock stand-ins for the Studio tasks (T6–T8, T11–T13): deterministic, schema-valid, and
built only from what each task is given — the evidence pack, the plan, the creator's own
transcripts and pattern cards. Real Claude replaces them through the same schemas.
"""

from __future__ import annotations

import re

from curo.schemas.tasks import (
    BeatPlan,
    CaptionOut,
    EvidenceItem,
    FrameOut,
    IdeaCandidate,
    NoteLabel,
    T6Input,
    T6Output,
    T7Input,
    T7Output,
    T8Input,
    T8Output,
    T11Input,
    T11Output,
    T12Input,
    T12Output,
    T13Input,
    T13Output,
)

# ====================================================================== T6 · idea candidates

FORMAT_CUES = (
    (r"\bgrwm\b|get ready", "grwm"),
    (r"\bhaul\b", "haul"),
    (r"\b(?:tips?|mistakes?)\b", "listicle"),
    (r"\bhow to\b|\bstep", "tutorial"),
    (r"\bvs\b|before|after|last year", "before_after"),
    (r"\b(?:ways|same outfit|one outfit|one \w+, \w+)\b", "multi_look"),
    (r"\blooks?\b|outfits?|styl", "lookbook"),
    (r"\bday in|vlog|tried\b", "vlog"),
)
HOOK_CUES = (
    (r"\?", "question"),
    (r"mistake", "mistake"),
    (r"\bhow (?:to|i)\b", "how_to"),
    (r"₹|budget|under\b|cheap", "budget"),
    (r"\bvs\b|before|after|last year", "before_after"),
    (r"\b\d+\b|\b(?:two|three|four|five)\b", "number_list"),
    (r"reveal|wait for|first", "reveal"),
    (r"\bi tried\b|story", "story"),
)
TARGET_CUES = (
    (r"comment|which|pick|\?|tell me|vote", "comments"),
    (r"send|share|friend|tag", "shares"),
    (r"final look|reveal|result", "likes"),
)


def _first(cues, text: str, default: str) -> str:
    low = text.lower()
    return next((v for p, v in cues if re.search(p, low)), default)


def _short(data: T6Input) -> str:
    """What the idea is about in a word or two: the festival's first keyword, else the topic."""
    for k in data.keywords:
        if k and " " not in k.strip():
            return k.strip().capitalize()
    if data.festival:
        return data.festival
    return (data.topic or "this").strip()


def _ids(items: list[EvidenceItem], *kinds: str) -> list[str]:
    return [e.id for e in items if e.kind in kinds]


FORMAT_IDEAS = {
    # format → (title, angle, hook type, description)
    "multi_look": (
        "Styling the same outfit 3 different ways for {s}",
        "one item, many looks",
        "number_list",
        "One outfit, three looks for {s} — the format your audience already shares and likes most.",
    ),
    "lookbook": (
        "3 {s} looks for every day of the festival",
        "a look for each occasion",
        "number_list",
        "Three finished looks, one per occasion, shot the way your lookbooks usually are.",
    ),
    "grwm": (
        "Get ready with me for {f}",
        "getting ready, start to finish",
        "relatable",
        "Your get-ready-with-me format, built around the festival morning.",
    ),
    "listicle": (
        "3 mistakes to avoid when filming your {s} looks",
        "filming tips for festive looks",
        "mistake",
        "Your tips format, pointed at the reels everyone is about to make.",
    ),
    "haul": (
        "{s} haul: what’s worth buying this year",
        "what to buy, what to skip",
        "curiosity_gap",
        "A haul of festival pieces with an honest hit-or-miss verdict on each.",
    ),
    "tutorial": (
        "How to style {s} looks in 3 steps",
        "a step-by-step styling",
        "how_to",
        "A short how-to your audience can follow along with.",
    ),
}
THEME_IDEAS = (
    # words in the theme → (title, angle, format, hook type, target, description)
    (
        r"where",
        "Where every piece of my {s} look is from",
        "where it’s from",
        "lookbook",
        "question",
        "comments",
        "Answers the question your comments ask most: where each piece is from.",
    ),
    (
        r"price|budget|cost",
        "3 {s} looks on a budget",
        "festive looks on a budget",
        "lookbook",
        "budget",
        "shares",
        "Budget versions your audience keeps asking for, styled your way.",
    ),
    (
        r"camera|edit|film|light",
        "How I film my {s} looks at home",
        "behind the camera",
        "tutorial",
        "how_to",
        "shares",
        "Answers the camera and editing questions in your comments.",
    ),
    (
        r"part 2|part two|more",
        "Part 2: more ways to wear it for {s}",
        "the follow-up people asked for",
        "multi_look",
        "number_list",
        "views",
        "The part 2 your comments keep asking for.",
    ),
    (
        r"festive",
        "The {s} looks you asked for",
        "requested festive looks",
        "lookbook",
        "relatable",
        "comments",
        "Festive looks, because your audience asked for them.",
    ),
)


def _generate(data: T6Input) -> list[IdeaCandidate]:
    s, f = _short(data), data.festival or _short(data)
    ev = data.evidence
    trend_ids = [i for i in _ids(ev, "trend") if not i.startswith("trend:card:")][:1]
    opp_ids = _ids(ev, "opportunity")
    out: list[IdeaCandidate] = []
    # Proven: one per sub-cluster, in its usual format.
    for g in [e for e in ev if e.kind == "subcluster"]:
        if not g.format or g.format not in FORMAT_IDEAS:
            continue
        title, angle, hook, desc = FORMAT_IDEAS[g.format]
        out.append(
            IdeaCandidate(
                text=title.format(s=s, f=f),
                description=desc.format(s=s),
                angle=angle,
                format=g.format,
                hook_type=hook,
                target_behaviour=_behaviour(g),
                evidence_ids=[g.id, *trend_ids, *opp_ids],
            )
        )
    # Adapted: a trending angle from the niche's feed made the creator's own, and the
    # year-on-year comparison for a dated event.
    cards = [e for e in ev if e.id.startswith("trend:card:")]
    if cards:
        lead = cards[0]
        name = lead.text.removeprefix("Trending in your niche: ").split(".")[0]
        out.append(
            IdeaCandidate(
                text=f"My take on {name.lower()}",
                description=(
                    f"Take the angle picking up in your niche ({name.lower()}) and make it "
                    "yours: your styling, your voice, the final look first."
                ),
                angle="trend adapted",
                format="lookbook",
                hook_type="reveal",
                target_behaviour="views",
                evidence_ids=[lead.id, *trend_ids],
            )
        )
    if data.festival and trend_ids:
        out.append(
            IdeaCandidate(
                text=f"What I wore for {s} last year vs this year",
                description=(
                    "A side-by-side of last year’s festive look and this year’s — what changed, "
                    "what stayed, and why."
                ),
                angle="last year vs this year",
                format="before_after",
                hook_type="before_after",
                target_behaviour="comments",
                evidence_ids=trend_ids + _ids(ev, "subcluster")[:1],
            )
        )
    # Explore: what the audience asks for.
    for t in [e for e in ev if e.kind == "theme"]:
        text = t.text.lower()
        for pattern, title, angle, fmt, hook, target, desc in THEME_IDEAS:
            if re.search(pattern, text):
                out.append(
                    IdeaCandidate(
                        text=title.format(s=s),
                        description=desc,
                        angle=angle,
                        format=fmt,
                        hook_type=hook,
                        target_behaviour=target,
                        evidence_ids=[t.id, *trend_ids],
                    )
                )
                break
    # Rising tags, in the format that works best for the creator.
    strongest = next((g for g in ev if g.kind == "subcluster" and g.format), None)
    for tr in [e for e in ev if e.kind == "trend" and e.id.startswith("trend:tag:")][:2]:
        tag = tr.id.split(":", 2)[2]
        out.append(
            IdeaCandidate(
                text=f"{s} looks for #{tag}",
                description=f"Your version of what’s rising under #{tag}, in your strongest format.",
                angle=f"riding #{tag}",
                format=strongest.format if strongest else (data.creator_formats or ["lookbook"])[0],
                hook_type="reveal",
                target_behaviour="views",
                evidence_ids=[tr.id] + ([strongest.id] if strongest else []),
            )
        )
    seen, unique = set(), []
    for c in out:
        if c.text not in seen:
            seen.add(c.text)
            unique.append(c)
    return unique[: data.count]


def _behaviour(item: EvidenceItem) -> str:
    """The behaviour a sub-cluster is strongest on, read from its fact line."""
    best, best_lift = "views", 0.0
    for name, behaviour in (
        ("views", "views"),
        ("likes per view", "likes"),
        ("shares per view", "shares"),
        ("comments per view", "comments"),
    ):
        m = re.search(r"(\d+(?:\.\d+)?)× " + name, item.text)
        if m and float(m.group(1)) > best_lift:
            best, best_lift = behaviour, float(m.group(1))
    return best


def _keep_note(data: T6Input) -> list[IdeaCandidate]:
    """A creator's note: its core thought kept, framed in their formats."""
    note = data.creator_input.strip().rstrip(".!?…")  # type: ignore[union-attr]
    cap = note[0].upper() + note[1:] if note else note
    x = note[0].lower() + note[1:] if note else note
    s = _short(data)
    subs = [e for e in data.evidence if e.kind == "subcluster"]
    trend = _ids(data.evidence, "trend")[:1]
    frames = (
        (f"{cap} — in three quick looks", "multi_look", "number_list", "views"),
        (f"I tried {x} for {s}. Here’s how it went.", "vlog", "story", "comments"),
        (
            f"{cap}: what I planned vs what actually happened",
            "before_after",
            "before_after",
            "comments",
        ),
        (f"Get ready with me: {x}", "grwm", "relatable", "comments"),
        (f"{cap}: 3 things I’d do differently", "listicle", "mistake", "shares"),
    )
    out = []
    for text, fmt, hook, target in frames:
        cited = [g.id for g in subs if g.format == fmt] or [g.id for g in subs[:1]]
        out.append(
            IdeaCandidate(
                text=text,
                description=f"Built from your note “{note}”.",
                angle=x[:80],
                format=fmt,
                hook_type=hook,
                target_behaviour=target,
                evidence_ids=cited + trend,
            )
        )
    return out


def _read(data: T6Input) -> list[IdeaCandidate]:
    """The creator's own idea, as written, described (for the validate chat)."""
    text = data.creator_input.strip()  # type: ignore[union-attr]
    low = text.lower()
    fmt = _first(FORMAT_CUES, low, "talking_head")
    cited = [
        e.id
        for e in data.evidence
        if (e.kind == "subcluster" and e.format == fmt)
        or (e.kind in ("theme", "trend") and _overlap(e.text, low))
    ]
    return [
        IdeaCandidate(
            text=text[:160],
            description="Your own idea.",
            angle=text[:80],
            format=fmt,
            hook_type=_first(HOOK_CUES, low, "bold_claim"),
            target_behaviour=_first(TARGET_CUES, low, "views"),
            evidence_ids=cited,
        )
    ]


def _overlap(a: str, b: str) -> bool:
    stop = {"your", "comments", "recent", "starts", "days"}
    words = set(re.findall(r"[a-z]{4,}", a.lower())) - stop
    return any(w in b for w in words)


def t6(data: T6Input) -> T6Output:
    if data.mode == "read" and data.creator_input:
        return T6Output(candidates=_read(data))
    if data.creator_input:
        return T6Output(candidates=_keep_note(data))
    return T6Output(candidates=_generate(data) or _read_fallback(data))


def _read_fallback(data: T6Input) -> list[IdeaCandidate]:
    first = data.evidence[0]
    return [
        IdeaCandidate(
            text=f"{_short(data)}, your way",
            angle="your usual format",
            format=(data.creator_formats or ["talking_head"])[0],
            evidence_ids=[first.id],
        )
    ]


# ====================================================================== T7 · the script

NOUNS = {
    "multi_look": "Look",
    "lookbook": "Look",
    "listicle": "Tip",
    "tutorial": "Step",
    "grwm": "Step",
}
_ITEM_LINE = re.compile(r"(?:^|\.\s)([^.]*?\bnumber\s*\d+:\s*([^.]+)\.)", re.I)
FILLER = re.compile(
    r"\b(?:I wore it|I'm wearing an?|I’m wearing an?|Let me show you|until you’ve seen this|"
    r"until you've seen this|Trust me,?)\s*",
    re.I,
)
ENDING_ASKS = (
    (r"send|share|friend|tag", "a line people will want to send to a friend"),
    (r"comment|question|ask|pick|choose|vote", "a choice question to the audience"),
    (r"final look|result|finished", "land on the finished result"),
    (r"save", "a save prompt"),
)


def _plain(text: str) -> str:
    """A line without its filler words ("I'm wearing a", "Let me show you")."""
    return re.sub(r"\s+", " ", FILLER.sub("", text)).strip(" .,:")


def _details(examples: list[str]) -> list[str]:
    """What the creator says in each item of their strongest reels ("I wore it belted with a
    potli bag"), in order, without repeats."""
    out: list[str] = []
    for text in examples:
        for _line, detail in _ITEM_LINE.findall(text):
            d = detail.strip()
            if d and d not in out:
                out.append(d)
    return out


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _creator_line(examples: list[str], pattern: str) -> str | None:
    for text in examples:
        for s in _sentences(text):
            if re.search(pattern, s, re.I):
                return s
    return None


def _count_word(n: int) -> str:
    return {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}.get(n, str(n))


def _hook(data: T7Input, n: int, variant: int) -> str:
    idea = data.idea.strip().rstrip(".!?")
    topic = (data.topic or "").split()[0] if data.topic else "this"
    if data.action == "rewrite_hook" and re.search(
        r"final look|finished look|result first", data.direction or "", re.I
    ):
        # Asked to open on the result: show the last look, then go back to the start.
        return f"This is the final {topic} look. Now watch one outfit get here."
    options = [
        f"{idea}. Let me show you.",
        f"Same outfit, {_count_word(n)} {topic} looks — wait for the last one.",
        f"Don’t buy anything new for {topic} until you’ve seen this.",
        f"POV: you have one outfit and {_count_word(n)} {topic} plans.",
    ]
    return options[variant % len(options)]


def _ending(purpose: str, n: int, examples: list[str], variant: int) -> str:
    counted = ", ".join(_count_word(k) for k in range(1, n)) + f" or {_count_word(n)}"
    tell = _creator_line(examples, r"tell me in the comments") or "Tell me in the comments."
    if "choice" in purpose or "question" in purpose:
        options = [
            f"Which look would you pick, {counted}? {tell}",
            f"{counted.capitalize()} — which one are you wearing? {tell}",
        ]
    elif "friend" in purpose:
        options = [
            "Send this to the friend you’re getting ready with.",
            "Send this to your festive twin — and tell me your pick.",
        ]
    elif "save" in purpose:
        options = ["Save this for festival week.", "Save this for when you’re getting ready."]
    elif "finished" in purpose:
        options = [
            _creator_line(examples, r"that'?s the final look") or "And that’s the final look.",
            "And that’s the final look — done.",
        ]
    else:
        options = [
            "Quick recap, and save this for later.",
            "That’s all of them — save this for festival week.",
        ]
    return options[variant % len(options)]


def _item(noun: str, k: int, details: list[str], variant: int, tone: str) -> str:
    detail = details[(k - 1 + variant) % len(details)] if details else "styled a new way"
    if tone == "conversational":
        lead = {1: "First up", 2: "Then", 3: "And for the last one"}.get(k, "Next")
        return f"{lead}: {detail[0].lower() + detail[1:]}."
    return f"{noun} number {k}: {detail}."


def _shorten(text: str) -> str:
    """Keep the first clause, without filler words or a trailing "with …"."""
    head = re.split(r"[,—–]| because ", text)[0]
    label, _, rest = head.partition(":")
    body = _plain(rest or label)
    body = re.split(r"\s+with\s+", body)[0] if len(body.split()) > 4 else body
    line = f"{label}: {body}" if rest else body
    end = "?" if "?" in head or text.rstrip().endswith("?") else "."
    return (line[0].upper() + line[1:]).rstrip(".?") + end if line else text


def _expand(text: str, role: str) -> str:
    if role == "item":
        return text.rstrip(".") + " — easy to copy with what you already own."
    if role == "hook":
        return text.rstrip(".") + ". Stay till the end."
    return text


def t7(data: T7Input) -> T7Output:
    beats = data.beats
    n = sum(1 for b in beats if b.role == "item") or 1
    noun = NOUNS.get(data.format, "Part")
    details = _details(data.examples)
    setup_line = None
    for text in data.examples:
        sents = _sentences(text)
        if len(sents) > 2 and "number" not in sents[1].lower():
            setup_line = sents[1]
            break
    everything = data.action in ("write", "regenerate")
    rewrite = {b.id for b in beats} if everything else set(data.rewrite)
    out = []
    k = 0
    for b in beats:
        if b.role == "item":
            k += 1
        if b.id not in rewrite and b.text:
            out.append({"id": b.id, "text": b.text})
            continue
        out.append({"id": b.id, "text": _write_beat(data, b, k, n, noun, details, setup_line)})
    return T7Output(beats=out)


def _write_beat(
    data: T7Input,
    b: BeatPlan,
    k: int,
    n: int,
    noun: str,
    details: list[str],
    setup: str | None,
) -> str:
    v, tone, action = data.variant, data.tone, data.action
    if action == "shorten" and b.text:
        return _shorten(b.text)
    if action == "expand" and b.text:
        return _expand(b.text, b.role)
    if action == "change_tone" and b.text:
        if b.role == "hook":
            return "Okay, so — " + b.text[0].lower() + b.text[1:]
        if b.role == "item":
            return _item(noun, k, details, v, "conversational")
        return b.text.replace("Tell me in the comments.", "Be honest, tell me below.")
    if action == "edit_line" and data.direction:
        said = re.sub(
            r"^(?:please |can you |could you )?(?:make|change|rewrite|edit)\s+(?:the\s+)?"
            r"(?:line|look|beat|tip|step)?\s*\d*\s*(?:to|into|so it says|so)?\s*",
            "",
            data.direction,
            flags=re.I,
        ).strip()
        said = said.rstrip(".") or data.direction.rstrip(".")
        prefix = f"{noun} number {k}: " if b.role == "item" else ""
        return prefix + said[0].upper() + said[1:] + "."
    if b.role == "hook":
        return _hook(data, n, v + (1 if action == "rewrite_hook" else 0))
    if b.role == "setup":
        return setup or "Here’s how I did it."
    if b.role == "item":
        return _item(noun, k, details, v, tone)
    purpose = b.purpose
    if action == "change_ending" and data.direction:
        asked = data.direction.lower()
        purpose = next((p for cue, p in ENDING_ASKS if re.search(cue, asked)), purpose)
    bump = 1 if action == "change_ending" and purpose == b.purpose else 0
    return _ending(purpose, n, data.examples, v + bump)


# ====================================================================== T8 · script notes


def t8(data: T8Input) -> T8Output:
    """Label lines by their wording, citing the strongest card for that kind of line."""

    def best(*pairs: tuple[str, str | None], metric: str) -> str | None:
        fits = [
            c
            for c in data.cards
            if c.metric == metric
            and c.effect > 1
            and any(c.feature == f and (v is None or c.value == v) for f, v in pairs)
        ]
        return max(fits, key=lambda c: c.effect).id if fits else None

    notes = []
    items = [b for b in data.beats if b.role == "item"]
    for b in data.beats:
        low = b.text.lower()
        pick = None
        if b.role == "hook":
            card = best(
                ("hook_type", None),
                ("opening_style", None),
                ("payoff_band", "under_2s"),
                metric="views",
            )
            pick = ("hook", card)
        elif re.search(r"send|share|friend|tag ", low):
            pick = (
                "shares",
                best(
                    ("cta_type", "share_prompt"),
                    ("core_tension", "relatable_struggle"),
                    metric="share_rate",
                ),
            )
        elif "?" in b.text or re.search(r"comment|tell me|which", low):
            pick = (
                "comments",
                best(
                    ("ending", "choice_question"),
                    ("ending", "open_question"),
                    ("cta_type", "comment_prompt"),
                    metric="comment_rate",
                ),
            )
        elif re.search(r"final look|finished|that’s the|that's the", low) or (
            items and b.id == items[-1].id
        ):
            pick = (
                "likes",
                best(
                    ("ending", "final_look"),
                    ("payoff_band", "under_2s"),
                    ("opening_style", "final_look_first"),
                    metric="like_rate",
                ),
            )
        if pick and pick[1]:
            notes.append(NoteLabel(beat_id=b.id, note_type=pick[0], pattern_card_id=pick[1]))
    return T8Output(notes=notes)


# ====================================================================== T11 · storyboard

LOOK_ICONS = ("look1", "look2", "look3")
TRANSITIONS = (
    "Snap cut on the beat",
    "Spin transition",
    "Jump cut",
    "Whip pan",
    "Match cut on the hand",
    "Hold, then end card",
)
LIGHT_WORDS = {
    "natural_light": "window light",
    "warm_light": "warm lamp light",
    "bright_even": "even light",
    "moody": "low light",
    "colourful": "coloured lights",
}
PLACE_WORDS = {
    "bedroom": "bedroom",
    "living_room": "living room",
    "outdoors": "outdoors",
    "market": "market",
    "studio": "studio",
    "event_venue": "venue",
    "office": "office",
}
ALT_SHOTS = (
    (
        "Mirror selfie · handheld",
        "mirror_selfie",
        "mirror",
        "Film it as a mirror selfie — phone at chest height, turn once to show the drape.",
    ),
    (
        "Medium-wide · slightly low angle",
        "tripod",
        "look3",
        "Step back for a medium-wide shot from a slightly low angle, and twirl once.",
    ),
    (
        "Walking shot · followed by a friend",
        "handheld",
        "look2",
        "Walk toward the camera while a friend follows you with the phone.",
    ),
)


def _onscreen(text: str, k: int | None) -> str:
    detail = text.split(":", 1)[1] if ":" in text else text
    words = re.sub(r"^(?:a|an|the)\s+", "", _plain(detail), flags=re.I).split()
    short = " ".join(words[:4]).strip(" .,")
    return (f"Look {k} · {short}" if k else short)[:60]


def _frame(data: T11Input, b, k: int | None, variant: int) -> FrameOut:
    cam = (data.toolkit.cameras or ["tripod"])[0]
    place = (data.toolkit.settings or ["unknown"])[0]
    light = (data.toolkit.lighting or ["natural_light"])[0]
    snap = any("snap cut" in d.lower() for d in data.devices)
    reveal = any("final look, then rewind" in d.lower() for d in data.devices)
    where = PLACE_WORDS.get(place, "usual spot")
    common = {"beat_id": b.id, "setting": place, "lighting": light}
    if b.role == "hook":
        if variant % 2 == 1:
            return FrameOut(
                **common,
                shot_type="Overhead · phone on a shelf above",
                camera="tripod",
                instruction=(
                    "Open on a top-down shot of the outfit laid flat, then reach in and pick it up."
                ),
                onscreen_text=_onscreen(b.text, None),
                transition=TRANSITIONS[4],
                icon_key="flatlay",
            )
        if reveal:
            return FrameOut(
                **common,
                shot_type="Medium-wide → close-up",
                camera=cam,
                instruction=(
                    "Open on the final look for one second, then rewind to the plain outfit in "
                    "your hands."
                ),
                onscreen_text="Wait for the last one…",
                transition=TRANSITIONS[1],
                icon_key="rewind",
            )
        return FrameOut(
            **common,
            shot_type="Close-up · handheld",
            camera="handheld",
            instruction="Start close on the outfit detail as you pick it up and say the hook.",
            onscreen_text=_onscreen(b.text, None),
            icon_key="closeup",
        )
    if b.role == "setup":
        return FrameOut(
            **common,
            shot_type="Mid-shot · face to camera",
            camera=cam,
            instruction="Talk straight to the camera for the setup line.",
            transition=TRANSITIONS[2],
            icon_key="closeup",
        )
    if b.role == "item":
        mirror = cam == "mirror_selfie" or variant % 3 == 2
        look = k or 1
        return FrameOut(
            **common,
            shot_type="Mirror selfie · handheld"
            if mirror
            else f"Full-length · {cam.replace('_', ' ')} at chest height",
            camera="mirror_selfie" if mirror else cam,
            instruction=(
                f"Same spot in the {where}, same framing — step in wearing look {look}. "
                "Hold for two beats so it lands."
            ),
            onscreen_text=_onscreen(b.text, look),
            transition=TRANSITIONS[0] if snap else TRANSITIONS[(look + variant) % 4],
            icon_key="mirror" if mirror else LOOK_ICONS[(look - 1) % 3],
            outfit_change=look > 1,
        )
    recap = "recap" in b.text.lower()
    return FrameOut(
        **common,
        shot_type="Edit · split screen of every look"
        if recap
        else "Close-up · eye level, direct to camera",
        camera=cam,
        instruction="End on a split screen of all the looks."
        if recap
        else "Walk up close to the camera and say the last line, counting on your fingers.",
        onscreen_text=_onscreen(b.text, None),
        transition=TRANSITIONS[5],
        icon_key="triptych" if recap else "cta",
    )


def t11(data: T11Input) -> T11Output:
    current = {f.beat_id: f for f in data.frames}
    targets = set(data.targets) if data.frames else {b.id for b in data.beats}
    out, k = [], 0
    for i, b in enumerate(data.beats):
        if b.role == "item":
            k += 1
        old = current.get(b.id)
        if old is not None and b.id not in targets:
            out.append(old)
            continue
        if data.action == "build" or old is None:
            out.append(_frame(data, b, k or None, data.variant))
        elif data.action == "change_shot":
            label, cam, icon, instr = ALT_SHOTS[(data.variant + i) % len(ALT_SHOTS)]
            update = {
                "shot_type": label,
                "camera": cam,
                "icon_key": icon,
                "instruction": instr,
                "needs_helper": "friend" in instr,
            }
            out.append(old.model_copy(update=update))
        elif data.action == "another_opening":
            out.append(_frame(data, b, None, data.variant + 1))
        elif data.action == "easier":
            update = {
                "instruction": "Easier take: phone propped where it is, step into frame, one take.",
                "shot_type": "One take · phone propped on a shelf",
            }
            out.append(old.model_copy(update=update))
        elif data.action == "change_transition":
            nxt = (
                TRANSITIONS[(TRANSITIONS.index(old.transition) + 1) % len(TRANSITIONS)]
                if old.transition in TRANSITIONS
                else TRANSITIONS[0]
            )
            out.append(old.model_copy(update={"transition": nxt}))
        elif data.action == "visual_treatment":
            light = "warm_light" if old.lighting != "warm_light" else "natural_light"
            instruction = old.instruction.rstrip(".") + f", in {LIGHT_WORDS[light]}."
            out.append(old.model_copy(update={"lighting": light, "instruction": instruction}))
        else:
            out.append(old)
    return T11Output(frames=out)


# ====================================================================== T12 · captions and hashtags


def _clause(text: str) -> str:
    return re.split(r"(?<=[.!?])\s+", text.strip())[0].rstrip(".!?…")


def t12(data: T12Input) -> T12Output:
    hook = _clause(data.hook)
    phrase = data.search_phrases[0] if data.search_phrases else (data.topic or "")
    emoji = " ✨" if data.style.emoji >= 1 else ""
    if data.own_caption:
        text = data.own_caption.strip()
        if data.variant == "polish":
            text = text[0].upper() + text[1:]
            text = text if text.endswith((".", "!", "?")) else text + "."
        return T12Output(captions=[CaptionOut(text=text, job="comments")], hashtags=[])
    items = [
        _plain(_clause(b).split(":", 1)[-1])
        for b in data.beats
        if re.search(r"\bnumber\b|^look|^tip|^step", b, re.I)
    ]
    summary = " · ".join(i[0].upper() + i[1:] for i in items[:4] if i)
    question = data.ending if "?" in data.ending else "Which one is you? Tell me below."
    ask = _clause(question)
    likes = f"{hook}. {summary}. {phrase}{emoji}" if summary else f"{hook}. {phrase}{emoji}"
    caps = {
        "default": [
            CaptionOut(text=f"{hook}.{emoji} {phrase}, sorted. {ask}?", job="comments"),
            CaptionOut(text=likes, job="likes"),
            CaptionOut(
                text=(
                    f"{hook}. Me, every festival, deciding what to wear. Send this to the friend "
                    "you’re getting ready with."
                ),
                job="shares",
            ),
        ],
        "shorter": [
            CaptionOut(text=f"{hook}. Which one?", job="comments"),
            CaptionOut(text=f"{hook}.{emoji}", job="likes"),
            CaptionOut(text=f"{hook}. Send this to your festive twin.", job="shares"),
        ],
        "playful": [
            CaptionOut(
                text=(
                    f"My wardrobe said “nothing to wear”. I said: {hook.lower()}. "
                    "Which one fooled you?"
                ),
                job="comments",
            ),
            CaptionOut(text=f"Plot twist: {hook.lower()}. {phrase}{emoji}", job="likes"),
            CaptionOut(
                text=f"{hook}. Tag the friend who needs this before the festival.", job="shares"
            ),
        ],
        "question": [
            CaptionOut(text=f"{hook}. Which one are you wearing?", job="comments"),
            CaptionOut(text=f"{hook}. Which look should I wear first?", job="likes"),
            CaptionOut(text=f"{hook}. Who are you sending this to?", job="shares"),
        ],
    }
    picks = [h.tag for h in sorted(data.hashtags, key=lambda h: -h.score)][:4]
    phrase_tag = re.sub(r"[^a-z0-9]", "", phrase.lower())
    if phrase_tag and phrase_tag not in picks:
        picks.append(phrase_tag)
    return T12Output(captions=caps.get(data.variant, caps["default"]), hashtags=picks[:5])


# ====================================================================== T13 · routing

SCRIPT_ROUTES = (
    (r"\bhook|open|first line|punch|attention|start", "rewrite_hook"),
    (r"short|trim|tight|faster|cut it|\d+ ?s(?:ec)?", "shorten"),
    (r"long|expand|more detail|slower", "expand"),
    (r"convers|natural|casual|tone|friendly|human", "change_tone"),
    (r"\bend|cta|call to action|outro|last line|comment|save|share|send", "change_ending"),
    (r"\b(?:line|look|beat|tip|step)\s*\d+", "edit_line"),
)
BOARD_ROUTES = (
    (r"easy|easier|simple|alone|myself|tripod|no helper", "easier"),
    (r"pac|faster|slower|tighter|quick", "pacing"),
    (r"transition|cut between|edit", "change_transition"),
    (r"opening|intro|first shot|start", "another_opening"),
    (r"light|colour|color|warm|mood|look of", "visual_treatment"),
)
CAPTION_ROUTES = (
    (r"short|brief|less|tight", "shorter"),
    (r"fun|play|witty|humou?r", "playful"),
    (r"question|ask|comment", "question"),
    (r"polish|fix|tidy|grammar", "polish"),
)


def t13(data: T13Input) -> T13Output:
    low = data.instruction.lower()
    routes = {"script": SCRIPT_ROUTES, "storyboard": BOARD_ROUTES, "caption": CAPTION_ROUTES}.get(
        data.step, ()
    )
    action = next((a for p, a in routes if re.search(p, low)), "")
    targets: list[str] = []
    params: dict[str, str | float] = {}
    if data.step == "script":
        m = re.search(r"\b(?:line|look|beat|tip|step)\s*(\d+)", low)
        if m:
            k = int(m.group(1))
            ids = [i.split(":", 1)[0] for i in data.items]
            looks = [i.split(":", 1)[0] for i in data.items if "number" in i.lower()]
            if "line" in m.group(0) and 1 <= k <= len(ids):
                targets = [ids[k - 1]]
            elif 1 <= k <= len(looks):
                targets = [looks[k - 1]]
            if targets and action != "rewrite_hook":
                action = "edit_line"
        secs = re.search(r"(\d+)\s*(?:s|sec|seconds)\b", low)
        if secs:
            params["seconds"] = float(secs.group(1))
        if not action:
            action = "regenerate"
    elif data.step == "storyboard":
        if "faster" in low or "tight" in low or "quick" in low:
            params["direction"] = "faster"
        elif "slower" in low:
            params["direction"] = "slower"
        action = action or "change_shot"
    else:
        # No request words and a sentence of its own: the creator's caption.
        action = action or ("own" if len(low.split()) >= 6 else "rewrite")
    return T13Output(action=action, targets=targets, params=params)
