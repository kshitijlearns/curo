"""Mock T23 (recap copy) and T24 (follower ideas): template lines built only from the input."""

from __future__ import annotations

from curo.schemas.tasks import RecapLine, T23Input, T23Output, T24Input, T24Output
from curo.services import follower_ideas, recap


def t23(data: T23Input) -> T23Output:
    out = []
    for s in data.slides:
        head, sub = recap.template_copy(s.slide_id, s.data or {"display": s.facts})
        out.append(RecapLine(slide_id=s.slide_id, headline=head[:60], subline=sub[:90]))
    return T23Output(slides=out)


def t24(data: T24Input) -> T24Output:
    title, why = follower_ideas.template(data.kind, data.topic, data.segment, data.facts)
    return T24Output(title=title, why=why)
