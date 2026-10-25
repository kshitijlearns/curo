"""Mock T25–T29 (Follower Personas): deterministic templates built only from the input facts.

The same templates are the real tasks' fallbacks (services/persona_text.py), so the mock's
output always passes the number check and the sensitive-attribute check.
"""

from __future__ import annotations

from curo.schemas.tasks import (
    SensitiveFlag,
    T25Input,
    T25Output,
    T26Input,
    T26Output,
    T27Input,
    T27Output,
    T28Input,
    T28Output,
    T29Input,
    T29Output,
)
from curo.services import persona_text


def t25(data: T25Input) -> T25Output:
    hinglish = (data.main_language or "") == "hinglish"
    names = persona_text.pick_names([g.data for g in data.groups])
    return T25Output(
        personas=[
            persona_text.write_template(g, n, data.niche, hinglish)
            for g, n in zip(data.groups, names, strict=True)
        ]
    )


def t26(data: T26Input) -> T26Output:
    return T26Output(thoughts=[persona_text.thought_template(p) for p in data.personas])


def t27(data: T27Input) -> T27Output:
    return T27Output(
        reactions=[
            persona_text.reaction_template(p, data.idea, data.draft, data.target_type)
            for p in data.personas
        ]
    )


def t28(data: T28Input) -> T28Output:
    return T28Output(answer=persona_text.chat_template(data.persona, data.question, data.context))


def t29(data: T29Input) -> T29Output:
    return T29Output(
        flags=[
            SensitiveFlag(index=i, attribute=a)  # type: ignore[arg-type]
            for i, a in persona_text.classify_template(data.texts)
        ]
    )
