"""Studio step 2: the script and its notes (logic doc §10).

1. Length: the duration band in which the creator's reels of this format get the most views
   per follower — compared at the same age (each reel's views lift), so a reel posted last
   week and one posted last month are measured fairly.
2. Structure: the beat order of the creator's strongest reels of the format — a hook, a setup
   if they use one, the items (looks, tips, steps; as many as the idea names, else as many as
   those reels had) and their usual ending, unless the idea aims at a behaviour that needs a
   different one (comments → a choice question, likes → the finished result, shares → a line
   to send to a friend).
3. Word budget: the creator's speaking speed × the length (2.6 words/s × 32 s ≈ 83 words).
4. The writing itself is T7's, in the creator's voice; this module plans it and checks it.
5. Notes: T8 labels lines; only labels a pattern card supports are kept, and they're worded
   as associations ("Curo links this kind of line with more comments for you").

Revisions rewrite only the beats an action touches and keep every other beat word for word.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field

from curo.schemas.tasks import BeatPlan, VoiceProfile
from curo.schemas.taxonomy import label_for
from curo.services.voice import seconds_for, word_count

BANDS = ((0, 15), (15, 25), (25, 35), (35, 45), (45, 60), (60, 90))
DEFAULT_SECONDS = 30.0
MIN_BAND_REELS = 2
SHARE = {"hook": 0.15, "setup": 0.10, "ending": 0.15}  # items share the rest equally
MIN_BEAT_WORDS = 3
ITEM_NOUN = {
    "multi_look": "look",
    "lookbook": "look",
    "listicle": "tip",
    "tutorial": "step",
    "grwm": "step",
    "haul": "find",
    "before_after": "change",
}
NUMBER_WORDS = {
    "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10,
}  # fmt: skip
_NUMBERED = re.compile(r"\b(?:look|tip|step|mistake|item|part)s?\s*(?:number\s*)?(\d+)", re.I)
ENDINGS = {
    "comments": ("choice_question", "a choice question to the audience"),
    "likes": ("final_look", "land on the finished result"),
    "shares": ("share_prompt", "a line people will want to send to a friend"),
    "views": ("recap", "a quick recap that loops back to the start"),
}
# The creator's own endings, as a beat's purpose.
ENDING_PURPOSE = {
    "choice_question": ENDINGS["comments"][1],
    "open_question": "an open question to the audience",
    "final_look": ENDINGS["likes"][1],
    "recap": ENDINGS["views"][1],
    "reveal": ENDINGS["likes"][1],
    "loop": ENDINGS["views"][1],
}


# ------------------------------------------------------------------ 1. length


@dataclass
class ReelLength:
    format: str | None
    duration_s: float | None
    views_lift: float | None  # views ÷ the creator's usual at the same age


@dataclass
class Band:
    low: int
    high: int
    seconds: float  # the target: the median length of the creator's reels in the band
    n: int
    basis: str  # what it rests on, for the creator


def length_band(reels: list[ReelLength], fmt: str) -> Band:
    """The band with the highest median views per follower among the creator's reels of this
    format (at least two reels in it); else across all their reels; else 25–35 s."""
    for pool, basis in (
        ([r for r in reels if r.format == fmt], f"your {fmt.replace('_', ' ')} reels"),
        (reels, "all your reels"),
    ):
        scored = []
        for low, high in BANDS:
            inside = [
                r
                for r in pool
                if r.duration_s is not None
                and r.views_lift is not None
                and low <= float(r.duration_s) < high
            ]
            if len(inside) >= MIN_BAND_REELS:
                vpf = statistics.median(r.views_lift for r in inside)  # type: ignore[misc]
                secs = statistics.median(float(r.duration_s) for r in inside)  # type: ignore[arg-type]
                scored.append((vpf, low, high, secs, len(inside)))
        if scored:
            _vpf, low, high, secs, n = max(scored)
            return Band(low, high, round(secs), n, basis)
    return Band(25, 35, DEFAULT_SECONDS, 0, "a usual reel length (not enough of your reels yet)")


# ------------------------------------------------------------------ 2. structure


def count_in_idea(text: str) -> int | None:
    """ "3 different ways", "three looks" → 3."""
    for m in re.finditer(r"\b(\d+|" + "|".join(NUMBER_WORDS) + r")\b", text.lower()):
        token = m.group(1)
        n = int(token) if token.isdigit() else NUMBER_WORDS[token]
        if 2 <= n <= 8:
            return n
    return None


def items_in(transcript_text: str, onscreen: list[str]) -> int | None:
    numbers = [int(m) for t in onscreen for m in _NUMBERED.findall(t)]
    numbers += [int(m) for m in _NUMBERED.findall(transcript_text)]
    return max(numbers) if numbers else None


@dataclass
class Example:
    """One of the creator's strongest reels of the format."""

    text: str  # transcript
    onscreen: list[str] = field(default_factory=list)
    ending: str | None = None


def structure(
    fmt: str, idea_text: str, target: str, examples: list[Example]
) -> list[tuple[str, str]]:
    """(role, purpose) per beat."""
    n = count_in_idea(idea_text)
    if n is None:
        counts = [c for e in examples if (c := items_in(e.text, e.onscreen))]
        n = round(statistics.median(counts)) if counts else 3
    n = max(2, min(n, 6))
    noun = ITEM_NOUN.get(fmt, "part")
    beats: list[tuple[str, str]] = [("hook", "the promise, in the first seconds")]
    if _has_setup(examples):
        beats.append(("setup", "a quick setup before the first " + noun))
    beats += [("item", f"{noun} {k} of {n}") for k in range(1, n + 1)]
    beats.append(("ending", ending_purpose(target, examples)))
    return beats


def ending_purpose(target: str, examples: list[Example]) -> str:
    """The idea's behaviour decides when it needs a particular ending; otherwise the ending the
    creator's strongest reels of the format use most."""
    if target in ("comments", "likes", "shares"):
        return ENDINGS[target][1]
    endings = [e.ending for e in examples if e.ending in ENDING_PURPOSE]
    if endings:
        return ENDING_PURPOSE[max(set(endings), key=lambda x: (endings.count(x), x))]
    return ENDINGS["views"][1]


def _has_setup(examples: list[Example]) -> bool:
    """Two of the strongest reels say something between the hook and the first item."""
    with_setup = 0
    for e in examples:
        sentences = re.split(r"(?<=[.!?])\s+", e.text)
        if len(sentences) > 2 and not _NUMBERED.search(sentences[1]):
            with_setup += 1
    return with_setup >= 2


def plan(beats: list[tuple[str, str]], budget: int) -> list[BeatPlan]:
    """Split the word budget: hook 15%, setup 10%, ending 15%, the items the rest equally."""
    fixed = sum(SHARE.get(role, 0) for role, _ in beats if role != "item")
    items = sum(1 for role, _ in beats if role == "item")
    out = []
    for i, (role, purpose) in enumerate(beats, start=1):
        share = SHARE[role] if role in SHARE else (1 - fixed) / max(items, 1)
        out.append(
            BeatPlan(
                id=f"b{i}",
                role=role,  # type: ignore[arg-type]
                purpose=purpose,
                words=max(MIN_BEAT_WORDS, round(budget * share)),
            )
        )
    return out


# ------------------------------------------------------------------ 3. timing


def fmt_time(seconds: float) -> str:
    s = round(seconds)
    return f"{s // 60}:{s % 60:02d}"


def timings(texts: list[str], voice: VoiceProfile) -> list[tuple[float, float]]:
    """Each beat's start and end: its words at the creator's speaking speed."""
    out, t = [], 0.0
    for text in texts:
        d = seconds_for(word_count(text), voice)
        out.append((round(t, 1), round(t + d, 1)))
        t += d
    return out


# ------------------------------------------------------------------ 5. notes

NOTE_TITLES = {
    "hook": "Strong hook",
    "comments": "Drives comments",
    "likes": "Drives likes",
    "shares": "Encourages shares",
}
NOTE_BEHAVIOUR = {
    "hook": "people watching past the first seconds",
    "comments": "more comments",
    "likes": "more likes",
    "shares": "more shares",
}
# Which pattern cards can back which note (logic doc §10 table). Never "saves".
SUPPORT: dict[str, tuple[str, set[tuple[str, str | None]]]] = {
    "hook": ("views", {("hook_type", None), ("opening_style", None), ("payoff_band", "under_2s")}),
    "comments": (
        "comment_rate",
        {
            ("ending", "choice_question"),
            ("ending", "open_question"),
            ("cta_type", "comment_prompt"),
            ("core_tension", "choice_dilemma"),
        },
    ),
    "likes": (
        "like_rate",
        {
            ("ending", "final_look"),
            ("payoff_band", "under_2s"),
            ("opening_style", "final_look_first"),
        },
    ),
    "shares": (
        "share_rate",
        {("cta_type", "share_prompt"), ("core_tension", "relatable_struggle")},
    ),
}
METRIC_WORDS = {
    "views": "views",
    "like_rate": "likes per view",
    "comment_rate": "comments per view",
    "share_rate": "shares per view",
}


@dataclass
class NoteCard:
    id: str
    feature: str
    value: str
    metric: str
    effect: float
    n: int
    scope: str


def supports(note_type: str, card: NoteCard) -> bool:
    metric, features = SUPPORT[note_type]
    if card.metric != metric or card.effect <= 1.0:
        return False
    return (card.feature, card.value) in features or (card.feature, None) in features


# How a value reads after "your reels with …", where its label doesn't.
WITH = {
    "final_look": "the final look at the end",
    "final_look_first": "the final look first",
    "relatable_struggle": "a relatable struggle",
    "choice_dilemma": "a choice at their heart",
    "under_2s": "the payoff in the first 2 seconds",
}


def note(note_type: str, card: NoteCard) -> dict:
    """The note on a line and the evidence behind it, worded as an association."""
    what = WITH.get(card.value) or label_for(card.value)
    what = what[0].lower() + what[1:]
    metric = METRIC_WORDS[card.metric]
    if card.scope == "yours":
        evidence = (
            f"Your reels with {what} got {card.effect:.2f}× your usual {metric} ({card.n} reels)."
        )
        who = "for you"
    else:
        evidence = (
            f"Based on creators like you: reels with {what} got {card.effect:.2f}× the "
            f"usual {metric}."
        )
        who = "for creators like you"
    return {
        "type": note_type,
        "title": NOTE_TITLES[note_type],
        "desc": f"Curo links this kind of line with {NOTE_BEHAVIOUR[note_type]} {who}.",
        "evidence": evidence,
        "card_id": card.id,
    }


def keep_supported(
    labels: list[tuple[str, str, str]], cards: dict[str, NoteCard]
) -> dict[str, dict]:
    """T8's labels (beat id, note type, card id) → the notes CURO shows, one per beat: only
    those whose card exists and backs the note type."""
    out: dict[str, dict] = {}
    for beat_id, note_type, card_id in labels:
        card = cards.get(card_id)
        if beat_id in out or card is None or not supports(note_type, card):
            continue
        out[beat_id] = note(note_type, card)
    return out


def candidate_cards(cards: list[NoteCard]) -> list[NoteCard]:
    """The cards T8 may cite: those that can back some note."""
    return [c for c in cards if any(supports(t, c) for t in SUPPORT)]


# ------------------------------------------------------------------ revisions


def merge_revision(
    previous: list[dict], written: dict[str, str], targets: set[str]
) -> tuple[list[dict], list[str]]:
    """Beats after a targeted revision: targeted beats take the new text, every other beat
    stays word for word. Returns the beats and the ids that actually changed."""
    out, changed = [], []
    for b in previous:
        text = written.get(b["id"]) if b["id"] in targets else None
        if text and text != b["text"]:
            out.append({**b, "text": text})
            changed.append(b["id"])
        else:
            out.append(dict(b))
    return out, changed


def split_own(text: str) -> list[tuple[str, str]]:
    """The creator's own script: one beat per line (or per sentence if it's one paragraph);
    the first is the hook and the last the ending. Text is kept exactly as written."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        lines = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
    if not lines:
        return []
    if len(lines) == 1:
        return [("hook", lines[0])]
    return [("hook", lines[0])] + [("item", ln) for ln in lines[1:-1]] + [("ending", lines[-1])]
