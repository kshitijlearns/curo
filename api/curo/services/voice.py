"""The creator's voice profile (logic doc §10 steps 3–4), measured from their own transcripts.

* Speaking speed: words per second while speaking (first to last word of each reel), the
  median across reels. It turns a script's length into a word budget and a beat's words into
  seconds (2.6 words a second × 32 seconds ≈ 83 words).
* Sentence length: median words per sentence.
* Language: how the transcripts read (English, Hinglish, Hindi, or a mix).
* Phrases: lines the creator keeps coming back to (in at least three reels).
* Energy: how often sentences end in an exclamation.

Nothing here is guessed: with fewer than three transcripts, CURO uses a plain default and
says how many reels the profile rests on.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter
from collections.abc import Iterable

from curo.schemas.tasks import VoiceProfile
from curo.services.comments import language_of

DEFAULT_WPS = 2.5  # used only until three of the creator's transcripts exist
MIN_REELS = 3
MIN_PHRASE_REELS = 3
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[\w'’₹]+", re.UNICODE)


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE.split(text or "") if s.strip()]


def word_count(text: str) -> int:
    return len(_WORD.findall(text or ""))


def speaking_speed(transcript: dict) -> float | None:
    """Words per second between the first and the last spoken word of one reel."""
    words = transcript.get("transcript") or []
    if len(words) < 8:
        return None
    span = float(words[-1]["t"]) - float(words[0]["t"])
    return len(words) / span if span > 2 else None


def _phrases(texts: list[str], n_min: int = 3, n_max: int = 5) -> list[str]:
    """Word sequences (3–5 words) that open a sentence in at least three reels, longest kept."""
    seen: Counter[str] = Counter()
    for text in texts:
        found = set()
        for s in sentences(text):
            words = _WORD.findall(s)
            for n in range(n_min, min(n_max, len(words)) + 1):
                found.add(" ".join(words[:n]))
        seen.update(found)
    common = [p for p, c in seen.items() if c >= MIN_PHRASE_REELS]
    # Keep the longest form of each phrase ("Get ready with me" inside a longer opener).
    longest = [p for p in common if not any(q != p and q.startswith(p) for q in common)]
    return sorted(longest, key=lambda p: (-seen[p], p))[:8]


def profile(transcripts: Iterable[dict]) -> VoiceProfile:
    items = [t for t in transcripts if t and t.get("transcript")]
    texts = [" ".join(w["word"] for w in t["transcript"]) for t in items]
    speeds = [s for t in items if (s := speaking_speed(t)) is not None]
    if len(speeds) < MIN_REELS:
        return VoiceProfile(words_per_second=DEFAULT_WPS, sentence_words=10.0, reels=len(speeds))
    lengths = [word_count(s) for text in texts for s in sentences(text)]
    langs = Counter(lang for text in texts if (lang := language_of(text)))
    total = sum(langs.values()) or 1
    top, n = langs.most_common(1)[0] if langs else ("en", 1)
    language = top if n / total >= 0.7 else "mixed"
    endings = [s[-1] for text in texts for s in sentences(text)]
    bangs = sum(1 for e in endings if e == "!") / max(len(endings), 1)
    energy = "high" if bangs >= 0.3 else "calm" if bangs < 0.05 and len(endings) > 10 else "steady"
    return VoiceProfile(
        words_per_second=round(statistics.median(speeds), 2),
        sentence_words=round(statistics.median(lengths), 1) if lengths else 10.0,
        language=language,  # type: ignore[arg-type]
        phrases=_phrases(texts),
        energy=energy,  # type: ignore[arg-type]
        reels=len(speeds),
    )


def word_budget(seconds: float, voice: VoiceProfile) -> int:
    """Spoken words that fit the length at the creator's speaking speed."""
    return max(1, round(seconds * voice.words_per_second))


def seconds_for(words: int, voice: VoiceProfile, minimum: float = 1.5) -> float:
    return max(minimum, words / voice.words_per_second)
