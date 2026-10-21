"""What the creator wants from a chat message (logic doc §14: "A small classifier first decides
what the creator wants, for example 'explain', 'change the script' or 'what if'. It then picks
the tool. If the request is unclear, the assistant asks one short question.")

The classifier is code: it is fast, free and testable, and it runs before any model is called.
It decides which tools the assistant may use; the model then picks among them.

- explain   a question about the creator's records ("why this hook?", "which reel did best?")
- change    an instruction to change the draft ("make the hook punchier")
- what_if   a hypothetical to re-score ("what if I end with a send prompt?")
- remember  a stated preference ("never suggest dance trends")
- forget    removing one ("forget that")
- hidden    a question about what isn't public (saves, reach, …): answered plainly, no model
- unclear   too little to go on: one short question back, no model
"""

from __future__ import annotations

import re

from curo.schemas.tasks import Intent

# A question about what isn't public. "Make the ending a save prompt" is not one.
HIDDEN = re.compile(
    r"\b(?:saves|save rate|how many (?:people )?saved|saved by|"
    r"(?:my|the|its|estimated|expected|how much|predicted) reach|impressions?|"
    r"watch[- ]?time|retention|skip rate|demographics?|age groups?|follower split|"
    r"who (?:watched|saw))\b",
    re.I,
)
# The same, in something Curo is about to say (quoted text, such as a caption, is left out).
HIDDEN_CLAIM = re.compile(
    r"\b(?:saves|saved by|(?:your|its|the|their) reach|impressions|watch[- ]?time|"
    r"retention|skip rate|demographics?)\b",
    re.I,
)
QUOTED = re.compile(r"“[^”]*”|\"[^\"]*\"")
FORGET = re.compile(
    r"^\s*(?:please\s+)?forget\b|\bdelete (?:that|the|my) (?:memory|note|preference)|"
    r"\bstop remembering\b|\bdon'?t remember\b",
    re.I,
)
REMEMBER_STRONG = re.compile(
    r"^\s*(?:please\s+)?(?:remember|note that|keep in mind)\b|\bfrom now on\b|"
    r"\b(?:never|don'?t|do not|stop)(?: ever)? (?:suggest|show|give|recommend)(?:ing)?\b",
    re.I,
)
REMEMBER_WEAK = re.compile(r"^\s*i (?:always|never|prefer|hate|don'?t like|only|usually) ", re.I)
WHAT_IF = re.compile(
    r"\bwhat if\b|\bwhat would happen\b|\bwhat about (?:ending|opening|adding|cutting|using|"
    r"starting|trimming)\b|\bwould it (?:do|be|get|score|perform|land)\b|"
    r"\bif i (?:changed?|add(?:ed)?|cut|used?|made|make|end(?:ed)?|open(?:ed)?|start(?:ed)?|"
    r"trim(?:med)?|shorten(?:ed)?|swap(?:ped)?|put|show(?:ed)?)\b",
    re.I,
)
CHANGE_VERB = (
    r"(?:make|change|rewrite|redo|shorten|lengthen|expand|cut|trim|add|remove|drop|replace|"
    r"swap|use|try|turn|fix|tighten|switch|move|end|open|start|write|give me)"
)
POLITE_CHANGE = re.compile(rf"^\s*(?:can|could|would|will) you (?:please )?{CHANGE_VERB}\b", re.I)
IMPERATIVE = re.compile(rf"^\s*(?:please\s+)?{CHANGE_VERB}\b", re.I)
QUESTION = re.compile(
    r"\?\s*$|^\s*(?:why|what|which|how|when|where|who|is|are|was|were|does|do|did|can|could|"
    r"should|would|will|has|have|tell me|explain|show me|compare)\b",
    re.I,
)
FILLER = {
    "", "ok", "okay", "hmm", "hm", "yes", "no", "yeah", "nah", "k", "thanks", "thank you",
    "cool", "nice", "?", "huh", "what", "and", "so",
}  # fmt: skip

# Screens whose own step handles a change request (the Studio's revision flows).
STUDIO_SCREENS = {
    "studio:validate",
    "studio:ideas",
    "studio:idea",
    "studio:script",
    "studio:storyboard",
    "studio:caption",
}


def classify(message: str, screen: str) -> Intent:
    text = message.strip()
    if text.lower().strip(" .!?") in FILLER:
        return "unclear"
    if HIDDEN.search(text):
        return "hidden"
    if FORGET.search(text):
        return "forget"
    if REMEMBER_STRONG.search(text):
        return "remember"
    if WHAT_IF.search(text):
        return "what_if"
    if POLITE_CHANGE.search(text):
        return "change"
    if QUESTION.search(text):
        return "explain"
    if REMEMBER_WEAK.search(text):
        return "remember"
    if screen in STUDIO_SCREENS:
        return "change"  # an instruction for this step ("shorter", "use a tripod")
    if IMPERATIVE.search(text):
        return "change"
    return "explain"


def handoff(intent: Intent, screen: str) -> bool:
    """A change on a Studio screen goes to that step's own revision (its job and T13 routing),
    which keeps each step's screen in one place; everything else is answered here."""
    return intent == "change" and screen in STUDIO_SCREENS


UNCLEAR_REPLY = (
    "Do you want me to explain something on this screen, or change it? For example: "
    "“why this hook?” or “make it shorter”."
)
HIDDEN_REPLY = (
    "Saves, reach, impressions and watch time aren’t public, so Curo can’t see or estimate "
    "them. Curo works with what anyone can see: views, likes, comments and shares, each "
    "against your own usual."
)
