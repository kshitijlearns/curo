"""The no-new-numbers check (MVP doc §10).

Text a creator will trust (T5, T10, T12, T14) may only contain numbers that appear in the
facts it was written from. After each call the backend extracts every number in the output
and checks it against the facts; if one is new it regenerates once, then falls back to a
template sentence built from the facts alone.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable

# 1.2K, 41%, 1.4×, ₹2,000, 3rd, 0:32 → their numbers
_NUMBER = re.compile(r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)\s*([kKmM](?![a-zA-Z]))?")
_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "twenty": 20, "hundred": 100,
    "thousand": 1000, "half": 0.5, "twice": 2, "double": 2, "triple": 3,
}  # fmt: skip
_WORD = re.compile(r"\b(" + "|".join(_WORDS) + r")\b", re.IGNORECASE)


def numbers_in(text: str) -> set[float]:
    """Every number written in the text, normalised (1.2K → 1200, 41% → 41)."""
    out: set[float] = set()
    for digits, suffix in _NUMBER.findall(text or ""):
        value = float(digits.replace(",", ""))
        if suffix:
            value *= 1000 if suffix.lower() == "k" else 1_000_000
        out.add(round(value, 3))
    for word in _WORD.findall(text or ""):
        out.add(float(_WORDS[word.lower()]))
    return out


def new_numbers(text: str, facts: Iterable[str]) -> set[float]:
    """Numbers in ``text`` that none of the facts contain. One is always allowed ("one look")."""
    allowed = set().union(*(numbers_in(f) for f in facts)) if facts else set()
    return {n for n in numbers_in(text) - allowed if n != 1.0}


def checked(
    write: Callable[[], str], facts: list[str], fallback: Callable[[], str]
) -> tuple[str, str]:
    """Run ``write``; if its text has a number the facts don't, try once more, then use the
    template. Returns (text, source) with source "model", "model_retry" or "template"."""
    for source in ("model", "model_retry"):
        text = write()
        if not new_numbers(text, facts):
            return text, source
    return fallback(), "template"
