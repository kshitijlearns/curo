"""Follower Personas (v2.2): Home's cards, the detail sheet, persona chat and Studio reactions.

- ``GET /v1/personas``: the 4 cards (status "building" while the first build runs).
- ``GET /v1/personas/{id}``, ``GET /v1/personas/{id}/history``.
- ``POST /v1/personas/{id}/chat`` (SSE) and ``GET /v1/personas/{id}/chat``: T28, in character
  but honest; each message counts towards Ask Curo's monthly cap.
- ``POST|GET /v1/projects/{id}/persona-reactions``: each persona's own take on the project's
  current draft (or a named idea), run once per version and cached.
- ``GET /v1/home``: Home's 4 sections in order, each loadable on its own.

Every persona surface carries the label: "Built from your public comments. Personas are
summaries, not real people."
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from collections.abc import Iterator
from datetime import datetime
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from curo import clock, providers, usage
from curo.auth import User, current_user
from curo.db import creator_session, service_connection
from curo.jobs import studio as studio_jobs
from curo.routes.deps import require_creator, rls_conn
from curo.schemas.api import (
    HomeOut,
    HomeSection,
    PersonaCard,
    PersonaChatIn,
    PersonaDetail,
    PersonaHistoryPoint,
    PersonaMessageOut,
    PersonaReactionsIn,
    PersonaReactionsOut,
    PersonasOut,
)
from curo.schemas.tasks import T28, PersonaChatTurn, T28Input
from curo.services import billing, persona_reactions, persona_safety, persona_text
from curo.services import personas as P
from curo.services.insights import tone_for

log = logging.getLogger("curo.personas")
router = APIRouter(prefix="/v1", tags=["personas"])
HISTORY_MONTHS = 6


# ------------------------------------------------------------------ cards


def _when(d: datetime) -> str:
    return f"{d.day} {d:%b}"


def card(r: dict) -> PersonaCard:
    prof = r["profile"] or {}
    ev = prof.get("evidence") or {}
    t = r["thought"] or {}
    meter = int(ev.get("meter") or 3)
    if r["is_starter"]:
        line = f"An early guess from creators in your niche · updated {_when(r['updated_at'])}."
    else:
        line = (
            f"From {r['n_comments']} comments across {r['n_reels']} reels · "
            f"updated {_when(r['updated_at'])}."
        )
    return PersonaCard(
        id=r["id"],
        slot=r["slot"],
        name=r["name"],
        short_name=r["short_name"],
        tagline=r["tagline"],
        share=float(r["share"]),
        share_pct=int(ev.get("share_pct") or round(100 * float(r["share"]))),
        color=r["color"],
        avatar_seed=r["avatar_seed"],
        confidence=r["confidence"],
        is_starter=r["is_starter"],
        mood=ev.get("mood") or P.MOOD_OF_METER[meter],
        meter=meter,
        meter_word=P.MOOD_WORDS[meter],
        thought={
            "thought": t.get("thought") or r["tagline"],
            "mood": t.get("mood") or "neutral",
            "loves": t.get("loves") or prof.get("loves", [])[:2],
            "wants_more": t.get("wants_more") or prof.get("wants_more", [])[:2],
        },
        n_comments=r["n_comments"],
        n_reels=r["n_reels"],
        evidence_line=line,
        updated_at=r["updated_at"],
    )


def _active(conn, creator_id) -> list[dict]:
    return conn.execute(
        """
        select * from public.follower_personas
         where creator_id = %s and retired_at is null order by slot
        """,
        (creator_id,),
    ).fetchall()


@router.get("/personas", response_model=PersonasOut)
def personas(conn: psycopg.Connection = Depends(rls_conn)) -> PersonasOut:
    creator = require_creator(conn)
    rows = _active(conn, creator["id"])
    if len(rows) < P.K:
        return PersonasOut(status="building", label=P.LABEL)
    cards = [card(r) for r in rows]
    return PersonasOut(
        status="ready",
        summary=None if rows[0]["is_starter"] else P.loving_summary([c.meter for c in cards]),
        early_guess=rows[0]["is_starter"],
        label=P.LABEL,
        personas=cards,
    )


def _own(conn, persona_id: UUID) -> dict:
    require_creator(conn)
    row = conn.execute(
        "select * from public.follower_personas where id = %s", (persona_id,)
    ).fetchone()
    if row is None:  # RLS: someone else's persona is simply not found
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Persona not found")
    return row


def _history(conn, persona_id: UUID) -> list[PersonaHistoryPoint]:
    rows = conn.execute(
        """
        select period, share, mood, sentiment, n_comments from public.persona_history
         where persona_id = %s order by period desc limit %s
        """,
        (persona_id, HISTORY_MONTHS),
    ).fetchall()
    return [
        PersonaHistoryPoint(
            period=r["period"],
            share=float(r["share"]),
            mood=r["mood"],
            sentiment=None if r["sentiment"] is None else float(r["sentiment"]),
            n_comments=r["n_comments"],
        )
        for r in reversed(rows)
    ]


@router.get("/personas/{persona_id}", response_model=PersonaDetail)
def persona(persona_id: UUID, conn: psycopg.Connection = Depends(rls_conn)) -> PersonaDetail:
    r = _own(conn, persona_id)
    prof = r["profile"] or {}
    ev = prof.get("evidence") or {}
    fav = ev.get("favourite_reels") or []
    shortcodes = {
        str(x["id"]): x["shortcode"]
        for x in conn.execute(
            "select id, shortcode from public.reels where id = any(%s::uuid[])",
            ([f["id"] for f in fav],),
        ).fetchall()
    }

    def traits(key: str) -> list[dict]:
        texts = prof.get(key, [])
        evid = prof.get(f"{key}_evidence") or []
        return [
            {"text": t, "evidence": evid[i] if i < len(evid) else None} for i, t in enumerate(texts)
        ]

    return PersonaDetail(
        **card(r).model_dump(),
        comes_for=prof.get("comes_for", []),
        loves=traits("loves"),
        wants_more=prof.get("wants_more", []),
        turn_offs=traits("turn_offs"),
        engagement_style=prof.get("engagement_style", ""),
        voice=prof.get("voice", ""),
        typical_comment=prof.get("typical_comment", ""),
        language=[
            {
                "language": x["language"],
                "name": x.get("name") or x["language"],
                "share": x.get("share"),
            }
            for x in prof.get("language", [])
        ],
        places=ev.get("places") or [],
        favourite_reels=[
            {
                "id": f["id"],
                "title": f["title"],
                "comments": f["comments"],
                "tone": tone_for(shortcodes.get(str(f["id"]), str(f["id"]))),
            }
            for f in fav
            if str(f["id"]) in shortcodes
        ],
        facts=ev.get("facts") or [],
        history=_history(conn, persona_id),
        label=P.LABEL,
    )


@router.get("/personas/{persona_id}/history", response_model=list[PersonaHistoryPoint])
def history(
    persona_id: UUID, conn: psycopg.Connection = Depends(rls_conn)
) -> list[PersonaHistoryPoint]:
    _own(conn, persona_id)
    return _history(conn, persona_id)


# ------------------------------------------------------------------ Home


@router.get("/home", response_model=HomeOut)
def home(user: User = Depends(current_user)) -> HomeOut:
    """Home's sections, in order (v2.2 §5.1); each loads from its own endpoint."""
    return HomeOut(
        sections=[
            HomeSection(
                id="personas", title="What your followers think of you", endpoint="/v1/personas"
            ),
            HomeSection(
                id="recap", title="Insights: your Creator Recap", endpoint="/v1/recaps/latest"
            ),
            HomeSection(
                id="opportunities", title="Opportunity areas", endpoint="/v1/opportunities"
            ),
            HomeSection(id="trends", title="Trending for you", endpoint="/v1/trends"),
        ]
    )


# ------------------------------------------------------------------ Studio reactions


def _reactions(
    conn, creator_id: UUID, project: dict, body: PersonaReactionsIn, run: bool, version: int | None
):
    rows = persona_reactions.active_rows(conn, creator_id)
    if len(rows) < P.K:
        return PersonaReactionsOut(status="building", label=P.LABEL)
    target = studio_jobs.persona_target(conn, project, body.target_type, body.target_id)
    if target is not None and version is not None and target.type != "idea":
        # An earlier version of the same draft (by default, the type on screen now).
        target = studio_jobs.persona_target(conn, project, target.type, None, version)
    if target is None:
        return PersonaReactionsOut(status="none", label=P.LABEL)
    if run:
        opinions = persona_reactions.react(creator_id, rows, target, "studio_personas")
    else:
        opinions = list(
            persona_reactions.cached(conn, [str(r["id"]) for r in rows], target).values()
        )
    out = persona_reactions.out(opinions, rows)
    return PersonaReactionsOut(
        status="ready" if out["reactions"] else "none",
        target_type=target.type,
        target_id=target.id,
        target_version=target.version,
        reactions=out["reactions"],
        summary=out["summary"] or None,
        audience=out["audience"],
        label=P.LABEL,
    )


def _project(conn, project_id: UUID) -> dict:
    require_creator(conn)
    p = conn.execute("select * from public.projects where id = %s", (project_id,)).fetchone()
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return p


@router.post("/projects/{project_id}/persona-reactions", response_model=PersonaReactionsOut)
def run_reactions(
    project_id: UUID,
    body: PersonaReactionsIn | None = None,
    conn: psycopg.Connection = Depends(rls_conn),
) -> PersonaReactionsOut:
    """Each persona's reaction to the current draft: cached per version, else T27 now. Part
    of the project's credit; never counted as a revision by itself."""
    p = _project(conn, project_id)
    return _reactions(conn, p["creator_id"], p, body or PersonaReactionsIn(), True, None)


@router.get("/projects/{project_id}/persona-reactions", response_model=PersonaReactionsOut)
def get_reactions(
    project_id: UUID,
    version: int | None = None,
    target_type: str | None = Query(None, pattern="^(idea|script|storyboard|caption)$"),
    target_id: UUID | None = None,
    conn: psycopg.Connection = Depends(rls_conn),
) -> PersonaReactionsOut:
    """The cached reactions only (never calls the model)."""
    p = _project(conn, project_id)
    body = PersonaReactionsIn(target_type=target_type, target_id=target_id)  # type: ignore[arg-type]
    return _reactions(conn, p["creator_id"], p, body, False, version)


# ------------------------------------------------------------------ persona chat (T28)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str, ensure_ascii=False)}\n\n"


def _context(conn, creator_id: UUID, persona_id: UUID, kind: str, cid: UUID | None) -> str | None:
    """The draft or simulation the chat is about, as text."""
    if cid is None:
        return None
    if kind == "studio":
        p = conn.execute(
            "select * from public.projects where id = %s and creator_id = %s", (cid, creator_id)
        ).fetchone()
        t = studio_jobs.persona_target(conn, p) if p else None
        return f"{t.type}: {t.idea}. {t.draft or ''}".strip() if t else None
    if kind == "simulator":
        s = conn.execute(
            "select result from public.simulations where id = %s and creator_id = %s",
            (cid, creator_id),
        ).fetchone()
        groups = ((s or {}).get("result") or {}).get("audience", {}).get("personas") or []
        g = next((x for x in groups if x["persona_id"] == str(persona_id)), None)
        return f"In the simulation: {g['takeaway']}" if g else None
    return None


_SENTENCE = re.compile(r"(?<=[.!?])\s+")


@router.post(
    "/personas/{persona_id}/chat",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": "The reply, streamed"}},
)
def chat(
    persona_id: UUID, body: PersonaChatIn, user: User = Depends(current_user)
) -> StreamingResponse:
    with creator_session(user.id) as conn:
        row = _own(conn, persona_id)
        creator_id = row["creator_id"]
        context = _context(conn, creator_id, persona_id, body.context_type, body.context_id)
        past = conn.execute(
            """
            select role, content from public.persona_messages
             where persona_id = %s and context_type = %s
               and context_id is not distinct from %s
             order by seq desc limit 10
            """,
            (persona_id, body.context_type, body.context_id),
        ).fetchall()
    spent = _spend(creator_id)

    def events() -> Iterator[str]:
        if spent is not None:
            yield _sse("error", spent)
            return
        try:
            answer = _answer(row, body.message.strip(), context, list(reversed(past)))
            with service_connection() as conn:
                conn.execute(
                    """
                    insert into public.persona_messages
                      (creator_id, persona_id, context_type, context_id, role, content, created_at)
                    values (%s, %s, %s, %s, 'user', %s, %s)
                    """,
                    (
                        creator_id,
                        persona_id,
                        body.context_type,
                        body.context_id,
                        body.message.strip(),
                        clock.now(),
                    ),
                )
                mid = conn.execute(
                    """
                    insert into public.persona_messages
                      (creator_id, persona_id, context_type, context_id, role, content, created_at)
                    values (%s, %s, %s, %s, 'persona', %s, %s) returning id
                    """,
                    (
                        creator_id,
                        persona_id,
                        body.context_type,
                        body.context_id,
                        answer,
                        clock.now(),
                    ),
                ).fetchone()["id"]
            for part in _SENTENCE.split(answer):
                if part:
                    yield _sse("delta", {"text": part + " "})
            yield _sse("done", {"message_id": str(mid), "text": answer, "label": P.LABEL})
        except Exception:
            log.exception("persona chat failed")
            yield _sse("error", {"message": "This persona couldn’t answer just now. Try again."})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _answer(row: dict, question: str, context: str | None, past: list[dict]) -> str:
    """T28 with the number and sensitive-attribute checks (one retry, then the template)."""
    b = persona_reactions.brief(row)
    facts = [*b.facts, *(e.text for e in b.evidence), context or ""]
    data = T28Input(
        persona=b,
        context=context,
        history=[PersonaChatTurn(role=m["role"], content=m["content"]) for m in past],
        question=question,
    )
    with usage.feature("persona_chat"):
        for _attempt in range(2):
            try:
                answer = providers.get_llm().run(T28, data).answer
            except Exception:
                log.warning("T28 failed", exc_info=True)
                continue
            if persona_safety.safe([answer], numbers_from=facts):
                return answer
    return persona_text.chat_template(b, question, context)


def _spend(creator_id: UUID) -> dict | None:
    """One Ask Curo message from this month's allowance (persona chat shares the cap)."""
    with service_connection() as conn:
        try:
            billing.spend(conn, creator_id, "chat", f"persona_chat:{uuid.uuid4()}", clock.now())
        except billing.OutOfCredits as exc:
            return {
                "code": "out_of_credits",
                "resource": "chat",
                "plan": exc.plan,
                "message": exc.message,
            }
    return None


@router.get("/personas/{persona_id}/chat", response_model=list[PersonaMessageOut])
def chat_history(
    persona_id: UUID,
    context_type: str = Query("home", pattern="^(home|studio|simulator)$"),
    context_id: UUID | None = None,
    conn: psycopg.Connection = Depends(rls_conn),
) -> list[PersonaMessageOut]:
    _own(conn, persona_id)
    rows = conn.execute(
        """
        select id, role, content, created_at from public.persona_messages
         where persona_id = %s and context_type = %s and context_id is not distinct from %s
         order by seq desc limit 40
        """,
        (persona_id, context_type, context_id),
    ).fetchall()
    return [PersonaMessageOut(**r) for r in reversed(rows)]
