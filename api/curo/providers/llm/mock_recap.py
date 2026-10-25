"""Mock T23 (recap copy): template lines built only from the input."""

from __future__ import annotations

from curo.schemas.tasks import RecapLine, T23Input, T23Output
from curo.services import recap


def t23(data: T23Input) -> T23Output:
    out = []
    for s in data.slides:
        head, sub = recap.template_copy(s.slide_id, s.data or {"display": s.facts})
        out.append(RecapLine(slide_id=s.slide_id, headline=head[:60], subline=sub[:90]))
    return T23Output(slides=out)
