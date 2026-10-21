"""The Ask Curo loop (logic doc §14; MVP doc T14 and the no-new-numbers check).

1. Route: the classifier decides what the creator wants. A change on a Studio screen is handed
   to that step's own revision; "unclear" and questions about what isn't public get a fixed
   reply without a model.
2. Remember: the conversation so far for this draft or simulation (project memory) and the
   creator's preferences (creator memory) go to the model with the screen's context.
3. Tools: the model calls the tools the intent allows; CURO runs them on the creator's own
   records and returns facts and sources.
4. Check: the reply streams sentence by sentence, and each sentence is checked before it is
   sent: a number no tool returned (or a claim about saves, reach…) stops it. CURO asks the
   model once more with the problem named; if that fails too, the answer is the tools' own
   facts (the template). The app is told to clear what it showed ("reset").
5. Cite: the final reply carries the records it drew on.

The loop yields (event, data) pairs; the route sends them as server-sent events.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from uuid import UUID

from psycopg.types.json import Jsonb

from curo import clock, events, providers
from curo.db import creator_session
from curo.schemas.tasks import ChatContext, ChatTurn, T14Input, ToolCall
from curo.services import validator
from curo.services.assistant import intent as router
from curo.services.assistant import memory
from curo.services.assistant import tools as T

log = logging.getLogger("curo.assistant")

MAX_TOOL_ROUNDS = 3
HISTORY = 8
MAX_SOURCES = 5
SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


@dataclass
class ChatRequest:
    message: str
    screen: str
    project_id: UUID | None = None
    simulation_id: UUID | None = None
    frame_id: str | None = None


@dataclass
class _State:
    request: ChatRequest
    creator: dict
    intent: str
    context: ChatContext
    messages: list[ChatTurn]
    tools: list
    permitted: set[str]
    allowed_text: list[str]  # the creator's words, memories: numbers here are fine
    facts: list[str] = field(default_factory=list)  # from tools
    sources: list[dict] = field(default_factory=list)
    calls: list[dict] = field(default_factory=list)
    jobs: list[dict] = field(default_factory=list)
    said: list[str] = field(default_factory=list)
    failure: str | None = None

    def check(self, sentence: str) -> str | None:
        """Why a sentence can't be sent, or None."""
        new = validator.new_numbers(sentence, self.allowed_text + self.facts)
        if new:
            shown = ", ".join(f"{n:g}" for n in sorted(new))
            return f"the number {shown} isn’t in any tool result"
        if router.HIDDEN_CLAIM.search(router.QUOTED.sub("", sentence)):
            return (
                "it mentions something that isn’t public (saves, reach, impressions or watch time)"
            )
        return None


def _sentences(buffer: str, final: bool) -> tuple[list[str], str]:
    parts = SENTENCE_END.split(buffer)
    if final:
        return [p.strip() for p in parts if p.strip()], ""
    return [p.strip() for p in parts[:-1] if p.strip()], parts[-1]


# ------------------------------------------------------------------ setting up a turn


def _context_line(conn, project_id, simulation_id) -> tuple[str | None, str | None]:
    project = sim = None
    if project_id:
        p = conn.execute(
            "select title, step from public.projects where id = %s", (project_id,)
        ).fetchone()
        if p:
            project = f"Studio draft “{p['title'] or 'untitled'}”, at the {p['step']} step"
    if simulation_id:
        s = conn.execute(
            "select audience, status from public.simulations where id = %s", (simulation_id,)
        ).fetchone()
        if s:
            sim = f"A simulation of the creator’s recorded reel ({s['status']}), shown for {s['audience']} audiences"
    return project, sim


def _history(conn, creator_id, req: ChatRequest, before: UUID) -> list[ChatTurn]:
    """Project memory: the conversation so far about this simulation, this draft, or (with
    neither) this screen today."""
    if req.simulation_id:
        where, arg = "context->>'simulation_id' = %s", str(req.simulation_id)
    elif req.project_id:
        where, arg = "context->>'project_id' = %s", str(req.project_id)
    else:
        where, arg = "context->>'screen' = %s and created_at > now() - interval '1 day'", req.screen
    rows = conn.execute(
        f"""
        select role, content from public.chat_messages
         where creator_id = %s and {where} and id <> %s and role in ('user', 'assistant')
         order by created_at desc limit %s
        """,
        (creator_id, arg, before, HISTORY),
    ).fetchall()
    return [ChatTurn(role=r["role"], content=r["content"]) for r in reversed(rows)]


def _own(conn, table: str, id_: UUID | None) -> UUID | None:
    if id_ is None:
        return None
    row = conn.execute(f"select id from public.{table} where id = %s", (id_,)).fetchone()
    return row["id"] if row else None  # RLS: another creator's id reads as missing


# ------------------------------------------------------------------ the turn


def turn(user_id: UUID, req: ChatRequest) -> Iterator[tuple[str, dict]]:
    with creator_session(user_id) as conn:
        creator = conn.execute(
            "select * from public.creators where user_id = auth.uid()"
        ).fetchone()
        if creator is None:
            yield "error", {"message": "Start onboarding with your Instagram username first."}
            return
        req.project_id = _own(conn, "projects", req.project_id)
        req.simulation_id = _own(conn, "simulations", req.simulation_id)
        if req.simulation_id and not req.project_id:
            sim = conn.execute(
                "select project_id from public.simulations where id = %s", (req.simulation_id,)
            ).fetchone()
            req.project_id = sim["project_id"] if sim else None
        intent = router.classify(req.message, req.screen)
        context = {
            "screen": req.screen,
            "project_id": str(req.project_id) if req.project_id else None,
            "simulation_id": str(req.simulation_id) if req.simulation_id else None,
        }
        user_row = conn.execute(
            """
            insert into public.chat_messages (creator_id, context, role, content, intent, created_at)
            values (%s, %s, 'user', %s, %s, %s) returning id
            """,
            (creator["id"], Jsonb(context), req.message, intent, clock.now()),
        ).fetchone()
        memories = memory.load(conn, creator["id"])
        history = _history(conn, creator["id"], req, user_row["id"])
        project_line, sim_line = _context_line(conn, req.project_id, req.simulation_id)

    handoff = router.handoff(intent, req.screen)
    yield (
        "meta",
        {
            "message_id": str(user_row["id"]),
            "intent": intent,
            "handoff": "studio" if handoff else None,
        },
    )
    if handoff:
        return
    if intent in ("unclear", "hidden"):
        text = router.UNCLEAR_REPLY if intent == "unclear" else router.HIDDEN_REPLY
        yield "delta", {"text": text}
        yield "done", _finish(creator, context, intent, text, [], [], "template", [])
        return

    tool_ctx_args = {
        "creator": creator,
        "screen": req.screen,
        "project_id": req.project_id,
        "simulation_id": req.simulation_id,
        "frame_id": req.frame_id,
    }
    with creator_session(user_id) as conn:
        specs = T.allowed(intent, T.ToolContext(conn=conn, **tool_ctx_args))  # type: ignore[arg-type]
    state = _State(
        request=req,
        creator=creator,
        intent=intent,
        context=ChatContext(
            screen=req.screen,
            intent=intent,  # type: ignore[arg-type]
            memory=[m.value for m in memories],
            project=project_line,
            simulation=sim_line,
        ),
        messages=[*history, ChatTurn(role="user", content=req.message)],
        tools=specs,
        permitted={s.name for s in specs},
        allowed_text=[req.message, *(m.value for m in memories)],
    )

    checked = "model"
    for attempt, note in enumerate((None, "retry")):
        retry_note = None
        if note:
            retry_note = (
                f"Your last reply was not sent because {state.failure}. Write it again using "
                "only numbers that appear in the tool results, and nothing about saves, reach, "
                "impressions or watch time."
            )
        state.failure = None
        state.said = []
        yield from _attempt(state, user_id, tool_ctx_args, retry_note)
        if state.failure is None:
            checked = "model" if attempt == 0 else "model_retry"
            break
        _caught(creator["id"], state.failure, attempt)
        yield "reset", {"reason": "checking the numbers"}
    else:
        checked = "template"
        state.said = [_template(state)]
        yield "delta", {"text": state.said[0]}

    text = " ".join(state.said).strip()
    yield (
        "done",
        _finish(creator, context, intent, text, state.sources, state.calls, checked, state.jobs),
    )


def _attempt(
    state: _State, user_id: UUID, tool_ctx_args: dict, retry_note: str | None
) -> Iterator[tuple[str, dict]]:
    llm = providers.get_llm()
    for _round in range(MAX_TOOL_ROUNDS + 1):
        buffer, calls = "", []
        for chunk in llm.chat(
            T14Input(
                context=state.context,
                messages=state.messages,
                tools=state.tools,
                retry_note=retry_note,
            )
        ):
            if chunk.type == "tool_call" and chunk.call is not None:
                calls.append(chunk.call)
                continue
            done, buffer = _sentences(buffer + chunk.text, final=False)
            for sentence in done:
                if not (yield from _send(state, sentence)):
                    return
        done, _ = _sentences(buffer, final=True)
        for sentence in done:
            if not (yield from _send(state, sentence)):
                return
        if not calls:
            return
        if _round == MAX_TOOL_ROUNDS:
            break
        yield from _run_tools(state, user_id, tool_ctx_args, calls)
    state.failure = state.failure or "it kept calling tools without answering"


def _send(state: _State, sentence: str) -> Iterator[tuple[str, dict]]:
    reason = state.check(sentence)
    if reason:
        state.failure = reason
        return False
    state.said.append(sentence)
    yield "delta", {"text": sentence + " "}
    return True


def _run_tools(
    state: _State, user_id: UUID, tool_ctx_args: dict, calls: list[ToolCall]
) -> Iterator[tuple[str, dict]]:
    state.messages.append(
        ChatTurn(role="assistant", content=" ".join(state.said), tool_calls=calls)
    )
    for call in calls:
        yield "tool", {"name": call.name, "status": "running"}
        try:
            with creator_session(user_id) as conn:
                ctx = T.ToolContext(conn=conn, **tool_ctx_args)
                result = T.execute(ctx, call.name, call.args, state.permitted)
        except T.ToolError as exc:
            content = json.dumps({"error": str(exc), "facts": [str(exc)]})
            state.facts.append(str(exc))
            status = "failed"
        else:
            content = result.for_model()
            state.facts.extend(result.facts)
            state.sources.extend(result.sources)
            if result.job_id:
                job = {"job_id": result.job_id, "step": result.data.get("step")}
                state.jobs.append(job)
                yield "job", job
            status = "done"
        state.calls.append({"name": call.name, "args": call.args, "status": status})
        state.messages.append(
            ChatTurn(role="tool", content=content, tool_call_id=call.id, name=call.name)
        )
        yield "tool", {"name": call.name, "status": status}


def _template(state: _State) -> str:
    """The fallback: the tools' own facts, which carry only checked numbers."""
    facts = [f for f in state.facts if not state.check(f)]
    if not facts:
        return "Curo couldn’t answer that from your records. Try asking about a reel, a pattern or this draft."
    return "Here’s what your records show. " + " ".join(facts[:3])


def _cited(sources: list[dict]) -> list[dict]:
    seen, out = set(), []
    for s in sources:
        key = (s["kind"], s["id"], s["title"])
        if key not in seen:
            seen.add(key)
            out.append(s)
    return out[:MAX_SOURCES]


def _caught(creator_id: UUID, reason: str, attempt: int) -> None:
    from curo.db import service_connection

    log.warning("Ask Curo reply held back (attempt %s): %s", attempt + 1, reason)
    with service_connection() as conn:
        events.record(
            conn, creator_id, "chat_check_failed", {"reason": reason, "attempt": attempt + 1}
        )


def _finish(
    creator: dict,
    context: dict,
    intent: str,
    text: str,
    sources: list[dict],
    calls: list[dict],
    checked: str,
    jobs: list[dict],
) -> dict:
    cited = _cited(sources)
    with creator_session(creator["user_id"]) as conn:
        row = conn.execute(
            """
            insert into public.chat_messages
              (creator_id, context, role, content, tool_calls, intent, sources, checked, created_at)
            values (%s, %s, 'assistant', %s, %s, %s, %s, %s, %s) returning id
            """,
            (
                creator["id"],
                Jsonb(context),
                text,
                Jsonb(calls),
                intent,
                Jsonb(cited),
                checked,
                clock.now(),
            ),
        ).fetchone()
    return {
        "message_id": str(row["id"]),
        "text": text,
        "sources": cited,
        "checked": checked,
        "jobs": jobs,
    }
