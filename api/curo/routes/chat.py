"""Ask Curo (MVP doc §7: ``POST /v1/chat``; logic doc §14) and creator memory.

``POST /v1/chat`` takes the message and the screen it was sent from (with the draft or
simulation on screen) and streams the reply as server-sent events:

- ``meta``   {message_id, intent, handoff}: handoff "studio" means the app should apply the
  message as that Studio step's revision; nothing more follows.
- ``tool``   {name, status}: a tool running on the creator's records.
- ``job``    {job_id, step}: a change running as a job (the app follows it, then reloads).
- ``delta``  {text}: the next checked sentence of the reply.
- ``reset``  {reason}: a sentence failed the number check; clear what was shown, a corrected
  reply follows.
- ``done``   {message_id, text, sources, checked, jobs}: the whole reply, the records it
  cites, and how its numbers were checked.
- ``error``  {message}

Memory is visible and deletable in Settings: ``GET /v1/memory``, ``DELETE /v1/memory/{id}``.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from curo.auth import User, current_user
from curo.routes.deps import require_creator, rls_conn
from curo.schemas.api import ChatIn, ChatMessageOut, MemoryOut
from curo.services.assistant import loop, memory

log = logging.getLogger("curo.chat")
router = APIRouter(prefix="/v1", tags=["ask curo"])


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str, ensure_ascii=False)}\n\n"


@router.post(
    "/chat",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": "The reply, streamed"}},
)
def chat(body: ChatIn, user: User = Depends(current_user)) -> StreamingResponse:
    req = loop.ChatRequest(
        message=body.message.strip(),
        screen=body.screen,
        project_id=body.project_id,
        simulation_id=body.simulation_id,
        frame_id=body.frame_id,
    )

    spent = _spend_message(user.id)

    def events() -> Iterator[str]:
        if spent is not None:  # out of Ask Curo messages: said in the stream (PLAN_V2 §4.7)
            yield _sse("error", spent)
            return
        try:
            for event, data in loop.turn(user.id, req):
                yield _sse(event, data)
        except Exception:  # the stream has started: say so in the stream
            log.exception("Ask Curo failed")
            yield _sse("error", {"message": "Curo couldn’t answer just now. Try again."})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/chat", response_model=list[ChatMessageOut])
def history(
    project_id: UUID | None = None,
    simulation_id: UUID | None = None,
    limit: int = Query(20, ge=1, le=100),
    conn: psycopg.Connection = Depends(rls_conn),
) -> list[ChatMessageOut]:
    """The conversation about one simulation or draft (project memory), oldest first."""
    creator = require_creator(conn)
    if simulation_id:
        where, arg = "context->>'simulation_id' = %s", str(simulation_id)
    elif project_id:
        where, arg = (
            "context->>'project_id' = %s and context->>'simulation_id' is null",
            str(project_id),
        )
    else:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Name a draft or simulation.")
    rows = conn.execute(
        f"""
        select id, role, content, sources, intent, created_at from public.chat_messages
         where creator_id = %s and {where} and role in ('user', 'assistant')
         order by created_at desc limit %s
        """,
        (creator["id"], arg, limit),
    ).fetchall()
    return [
        ChatMessageOut(
            id=r["id"],
            role=r["role"],
            content=r["content"],
            sources=r["sources"] or [],
            intent=r["intent"],
            created_at=r["created_at"],
        )
        for r in reversed(rows)
    ]


@router.get("/memory", response_model=list[MemoryOut])
def list_memory(conn: psycopg.Connection = Depends(rls_conn)) -> list[MemoryOut]:
    creator = require_creator(conn)
    return [
        MemoryOut(id=m.id, key=m.key, value=m.value, source=m.source)  # type: ignore[arg-type]
        for m in memory.load(conn, creator["id"])
    ]


@router.delete("/memory/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(memory_id: UUID, conn: psycopg.Connection = Depends(rls_conn)) -> None:
    creator = require_creator(conn)
    if memory.delete(conn, creator["id"], memory_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Memory not found")


def _spend_message(user_id) -> dict | None:
    """One Ask Curo message from this month's allowance; the out-of-credits reply if none."""
    import uuid

    from curo import clock
    from curo.db import service_connection
    from curo.services import billing

    with service_connection() as conn:
        creator = conn.execute(
            "select id from public.creators where user_id = %s", (user_id,)
        ).fetchone()
        if creator is None:
            return None  # the turn answers "start onboarding" itself
        try:
            billing.spend(conn, creator["id"], "chat", f"chat:{uuid.uuid4()}", clock.now())
        except billing.OutOfCredits as exc:
            return {
                "code": "out_of_credits",
                "resource": "chat",
                "plan": exc.plan,
                "message": exc.message,
            }
    return None
