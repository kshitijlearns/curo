"""The sensitive-attribute check for persona text (v2.2 §1.2, §10).

Personas never state or imply age, gender, religion, caste, ethnicity, sexuality, health,
income bracket, political views or exact location. Every persona text a creator reads (T25,
T26, T27, T28 outputs) passes two checks:

1. ``keyword_flags``: a word list (fast, deterministic, always on).
2. T29, a cheap classifier pass (Claude Haiku) for what a word list misses ("as a new mum").

A flagged output is regenerated once, then replaced by a template built from code facts.
Topics people mention are allowed ("mentions Mumbai and Pune"), and so are festivals, weddings
and "budget" as content traits; "ethnic wear" is a style of clothing, not an ethnicity, and
"aap" is Hindi for "you". Words with an everyday meaning ("rich colours", "poor lighting") are
only flagged in their sensitive sense.
"""

from __future__ import annotations

import re

from curo.services import validator

# attribute → patterns (word-bounded, case-insensitive)
SENSITIVE: dict[str, tuple[str, ...]] = {
    "age": (
        r"\d{1,2}[- ]?(?:year|yr)s?[- ]?olds?",
        r"teen(?:ager|age)?s?",
        r"aged? \d",
        r"in (?:their|my|your) (?:teens|twenties|thirties|forties|fifties|\d0s)",
        r"gen[- ]?z",
        r"millennials?",
        r"boomers?",
        r"(?:college|school|university) (?:students?|kids?|girls?|boys?)",
        r"students?",
        r"young(?:er|sters?)?",
        r"elderly",
        r"seniors?",
        r"middle[- ]aged",
    ),
    "gender": (
        r"wom[ae]n",
        r"girls?",
        r"ladies",
        r"lady",
        r"females?",
        r"males?",
        r"guys",
        r"boys?",
        r"(?<!wo)men",
        r"(?<!wo)man",
        r"moms?",
        r"mums?",
        r"mothers?",
        r"dads?",
        r"fathers?",
        r"wives",
        r"wife",
        r"husbands?",
        r"she",
        r"her",
        r"hers",
        r"he",
        r"him",
        r"his",
        r"feminine",
        r"masculine",
        r"gender",
    ),
    "religion": (
        r"hindus?",
        r"muslims?",
        r"christians?",
        r"sikhs?",
        r"jains?",
        r"buddhists?",
        r"parsis?",
        r"religio(?:n|us)",
        r"devout",
        r"believers?",
    ),
    "caste": (r"castes?", r"brahmins?", r"dalits?", r"upper[- ]caste", r"lower[- ]caste"),
    "ethnicity": (
        r"ethnicity",
        r"ethnic (?:group|origin|background)s?",
        r"races?",
        r"racial",
        r"north indians?",
        r"south indians?",
        r"fair[- ]skinned",
        r"dark[- ]skinned",
    ),
    "sexuality": (
        r"gay",
        r"lesbians?",
        r"bisexual",
        r"queer",
        r"lgbtq?\+?",
        r"straight (?:people|folks|women|men)",
        r"sexuality",
        r"sexual orientation",
    ),
    "health": (
        r"pregnan(?:t|cy)",
        r"diabet(?:es|ic)",
        r"disab(?:led|ility|ilities)",
        r"illness(?:es)?",
        r"disorders?",
        r"depress(?:ed|ion)",
        r"anxiety",
        r"pcos",
        r"cancer",
        r"mental health",
        r"overweight",
        r"obese",
    ),
    "income": (
        r"income",
        r"salar(?:y|ied|ies)",
        r"rich (?:people|folks|kids|families|crowd)",
        r"wealthy",
        r"affluent",
        r"poor (?:people|folks|families)",
        r"middle[- ]class",
        r"low[- ]income",
        r"high[- ]income",
        r"can'?t afford",
        r"(?:am|is|are) broke",
    ),
    "politics": (
        r"politic(?:s|al)",
        r"bjp",
        r"congress",
        r"left[- ]wing",
        r"right[- ]wing",
        r"liberals",
        r"conservatives",
        r"voters?",
    ),
    "location": (
        r"lives? in",
        r"living in",
        r"based in",
        r"stays? in",
        r"from (?:the )?(?:city|town|village) of",
        r"pin ?codes?",
        r"home address",
        r"neighbou?rhood",
    ),
}
_PATTERNS = {
    attr: re.compile(r"(?<![\w-])(?:" + "|".join(pats) + r")(?![\w-])", re.IGNORECASE)
    for attr, pats in SENSITIVE.items()
}


def keyword_flags(text: str) -> set[str]:
    """The sensitive attributes a text names, by the word list."""
    return {attr for attr, pat in _PATTERNS.items() if pat.search(text or "")}


def classify(texts: list[str]) -> list[set[str]]:
    """T29 (Claude Haiku): attributes each text states or implies. If the classifier can't run,
    the keyword list alone decides (it already ran)."""
    from curo import providers
    from curo.schemas.tasks import T29, T29Input

    out: list[set[str]] = [set() for _ in texts]
    todo = [i for i, t in enumerate(texts) if t and t.strip()]
    for start in range(0, len(todo), 40):
        batch = todo[start : start + 40]
        try:
            res = providers.get_llm().run(T29, T29Input(texts=[texts[i] for i in batch]))
        except Exception:
            continue
        for f in res.flags:
            if 0 <= f.index < len(batch):
                out[batch[f.index]].add(f.attribute)
    return out


def flags(texts: list[str], classifier: bool = True) -> list[set[str]]:
    """Keyword list, then (for what passed it) the classifier."""
    out = [keyword_flags(t) for t in texts]
    if classifier:
        passed = [i for i, f in enumerate(out) if not f]
        for i, f in zip(passed, classify([texts[i] for i in passed]), strict=True):
            out[i] |= f
    return out


def safe(texts: list[str], numbers_from: list[str] | None = None, classifier: bool = True) -> bool:
    """True when no text names a sensitive attribute and (with ``numbers_from``) none carries a
    number its facts don't."""
    if numbers_from is not None and any(validator.new_numbers(t, numbers_from) for t in texts):
        return False
    return not any(flags(texts, classifier=classifier))
