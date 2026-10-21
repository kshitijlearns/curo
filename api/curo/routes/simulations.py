"""The Simulator (MVP doc §7 and §10; logic doc §13).

``POST /v1/simulations`` checks the upload (MP4 or MOV, up to 90 seconds) and answers 202 with
the job that runs it; ``GET /v1/simulations/{id}`` gives its status, then the full result.
Applying an edit writes it back to the linked Studio draft; a re-run takes a new upload (the
re-recorded take) and is shown against the run before it.

v2: ``GET /v1/simulations/{id}/agents/{n}`` shows one AI agent (persona, reaction, chat) and
``POST …/agents/{n}/chat`` talks to it, in character, up to AGENT_CHAT_MESSAGES messages per
simulation. Everything an agent says is labelled simulated in the app.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status

from curo import clock, providers
from curo.config import get_settings
from curo.db import service_connection
from curo.jobs import audience as audience_jobs
from curo.jobs import simulation as sim_jobs
from curo.providers.storage.base import StorageError
from curo.routes.deps import require_creator, rls_conn
from curo.routes.uploads import upload_prefix
from curo.schemas.api import (
    AgentChatIn,
    AgentChatOut,
    AgentOut,
    EditApplied,
    RerunIn,
    SimEdit,
    Simulation,
    SimulationIn,
    SimulationStarted,
)
from curo.schemas.tasks import T22, AgentChatTurn, Reaction, T22Input, Timeline
from curo.services import billing, mp4, validator

router = APIRouter(prefix="/v1/simulations", tags=["simulator"])


def _upload(creator: dict, path: str) -> mp4.VideoMeta:
    """The creator's own upload, checked: an MP4 or MOV of at most 90 seconds."""
    if not path.startswith(upload_prefix(creator["id"])) or ".." in path:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "That upload isn’t yours.")
    try:
        data = providers.get_storage().get(get_settings().storage_bucket_videos, path)
    except StorageError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Curo couldn’t find that upload. Upload the video again.",
        ) from exc
    try:
        return mp4.check(data)
    except mp4.NotAVideo as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


def _own_sim(conn: psycopg.Connection, simulation_id: UUID) -> dict:
    row = conn.execute(
        "select * from public.simulations where id = %s", (simulation_id,)
    ).fetchone()
    if row is None:  # RLS: someone else's simulation reads as missing
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Simulation not found")
    return row


def _edit(row: dict) -> SimEdit:
    return SimEdit(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        feature_change=row["feature_change"],
        effort=row["effort"],
        gains=row["gains"] or {},
        frame_index=row["frame_index"],
        frame_label=row["frame_label"],
        applied=row["applied"],
        applied_at=row["applied_at"],
        applied_job_id=row["applied_job_id"],
    )


def simulation_state(conn: psycopg.Connection, simulation_id: UUID) -> Simulation:
    s = _own_sim(conn, simulation_id)
    edits = conn.execute(
        """
        select * from public.simulation_edits where simulation_id = %s
         order by delta desc nulls last, title
        """,
        (simulation_id,),
    ).fetchall()
    title = None
    if s["project_id"]:
        p = conn.execute(
            "select title from public.projects where id = %s", (s["project_id"],)
        ).fetchone()
        title = p["title"] if p else None
    meta: dict[str, Any] = s["video_meta"] or {}
    return Simulation(
        id=s["id"],
        status=s["status"],
        error=s["error"],
        audience=s["audience"],
        project_id=s["project_id"],
        project_title=title,
        parent_simulation_id=s["parent_simulation_id"],
        video={k: meta.get(k) for k in ("duration_s", "width", "height")} if meta else None,
        score=s["score"],
        scores=s["scores"],
        engagement_score=s["engagement_score"],
        result=s["result"],
        edits=[_edit(e) for e in edits],
        job_id=s["job_id"],
        created_at=s["created_at"],
        finished_at=s["finished_at"],
    )


@router.post("", response_model=SimulationStarted, status_code=status.HTTP_202_ACCEPTED)
def start(body: SimulationIn, conn: psycopg.Connection = Depends(rls_conn)) -> SimulationStarted:
    creator = require_creator(conn)
    meta = _upload(creator, body.upload_path)
    if body.project_id is not None:
        own = conn.execute(
            "select id from public.projects where id = %s", (body.project_id,)
        ).fetchone()
        if own is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    with service_connection() as sc:  # a simulation credit (PLAN_V2 §4.6), checked first
        billing.require(sc, creator["id"], "simulation", clock.now())
    simulation_id, job_id = sim_jobs.create(
        creator["id"], body.upload_path, meta, body.audience, body.project_id, body.caption
    )
    with service_connection() as sc:
        billing.spend(sc, creator["id"], "simulation", f"simulation:{simulation_id}", clock.now())
    return SimulationStarted(simulation_id=simulation_id, job_id=job_id)


@router.get("/{simulation_id}", response_model=Simulation)
def get_simulation(simulation_id: UUID, conn: psycopg.Connection = Depends(rls_conn)) -> Simulation:
    require_creator(conn)
    return simulation_state(conn, simulation_id)


@router.post("/{simulation_id}/edits/{edit_id}/apply", response_model=EditApplied)
def apply_edit(
    simulation_id: UUID, edit_id: UUID, conn: psycopg.Connection = Depends(rls_conn)
) -> EditApplied:
    """Accept an edit. With a linked Studio draft, it is written back to the draft's script and
    storyboard (a job); without one it is only marked, for the creator to make by hand."""
    creator = require_creator(conn)
    sim = _own_sim(conn, simulation_id)
    edit = conn.execute(
        "select * from public.simulation_edits where id = %s and simulation_id = %s",
        (edit_id, simulation_id),
    ).fetchone()
    if edit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edit not found")
    job_id = edit["applied_job_id"]
    if not edit["applied"]:
        has_script = (
            sim["project_id"] is not None
            and conn.execute(
                "select 1 from public.script_versions where project_id = %s limit 1",
                (sim["project_id"],),
            ).fetchone()
        )
        if has_script:
            job_id = sim_jobs.queue_apply(edit_id, creator["id"])
        conn.execute(
            """
            update public.simulation_edits set applied = true, applied_at = %s, applied_job_id = %s
             where id = %s
            """,
            (clock.now(), job_id, edit_id),
        )
        edit = conn.execute(
            "select * from public.simulation_edits where id = %s", (edit_id,)
        ).fetchone()
    return EditApplied(edit=_edit(edit), job_id=job_id)


@router.post(
    "/{simulation_id}/rerun",
    response_model=SimulationStarted,
    status_code=status.HTTP_202_ACCEPTED,
)
def rerun(
    simulation_id: UUID, body: RerunIn, conn: psycopg.Connection = Depends(rls_conn)
) -> SimulationStarted:
    """Simulate the re-recorded take, linked to the run before it (the score change is shown
    against that run). The same draft and audience carry over."""
    creator = require_creator(conn)
    before = _own_sim(conn, simulation_id)
    if body.upload_path == before["video_path"]:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Upload the re-recorded video to re-run. The same video gives the same estimate.",
        )
    meta = _upload(creator, body.upload_path)
    with service_connection() as sc:
        billing.require(sc, creator["id"], "simulation", clock.now())
    new_id, job_id = sim_jobs.create(
        creator["id"],
        body.upload_path,
        meta,
        before["audience"],
        before["project_id"],
        body.caption if body.caption is not None else before["caption"],
        parent_id=simulation_id,
    )
    with service_connection() as sc:
        billing.spend(sc, creator["id"], "simulation", f"simulation:{new_id}", clock.now())
    return SimulationStarted(simulation_id=new_id, job_id=job_id)


# ---------------------------------------------------------------------- talk to an agent


def _agent(conn: psycopg.Connection, sim: dict, agent_no: int):
    row = conn.execute(
        "select * from public.simulation_agents where simulation_id = %s and agent_no = %s",
        (sim["id"], agent_no),
    ).fetchone()
    if row is None or not sim["persona_version"]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    agents, _labels = audience_jobs.load_agents(conn, sim["creator_id"], sim["persona_version"])
    brief = next((a for a in agents if a.agent_no == agent_no), None)
    if brief is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    return row, brief


def _chat(conn: psycopg.Connection, simulation_id: UUID, agent_no: int) -> list[dict]:
    return [
        {"role": r["role"], "content": r["content"]}
        for r in conn.execute(
            """
            select role, content from public.agent_chats
             where simulation_id = %s and agent_no = %s order by created_at, id
            """,
            (simulation_id, agent_no),
        ).fetchall()
    ]


def _left(conn: psycopg.Connection, simulation_id: UUID) -> int:
    used = conn.execute(
        "select count(*) as n from public.agent_chats where simulation_id = %s and role = 'user'",
        (simulation_id,),
    ).fetchone()["n"]
    return max(0, get_settings().agent_chat_messages - used)


@router.get("/{simulation_id}/agents/{agent_no}", response_model=AgentOut)
def get_agent(
    simulation_id: UUID, agent_no: int, conn: psycopg.Connection = Depends(rls_conn)
) -> AgentOut:
    require_creator(conn)
    sim = _own_sim(conn, simulation_id)
    row, brief = _agent(conn, sim, agent_no)
    return AgentOut(
        agent_no=agent_no,
        segment=brief.segment,
        segment_label=brief.segment_label,
        persona_text=brief.persona_text,
        reaction=row["reaction"],
        chat=_chat(conn, simulation_id, agent_no),
        messages_left=_left(conn, simulation_id),
    )


@router.post("/{simulation_id}/agents/{agent_no}/chat", response_model=AgentChatOut)
def chat_with_agent(
    simulation_id: UUID,
    agent_no: int,
    body: AgentChatIn,
    conn: psycopg.Connection = Depends(rls_conn),
) -> AgentChatOut:
    """One question to one agent, answered in character about this video and its own reaction.
    The answer may only carry numbers from the agent's reaction and the video (validator)."""
    require_creator(conn)
    sim = _own_sim(conn, simulation_id)
    row, brief = _agent(conn, sim, agent_no)
    if _left(conn, simulation_id) <= 0:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            {
                "code": "agent_chat_limit",
                "message": "This simulation has used its "
                f"{get_settings().agent_chat_messages} agent messages.",
            },
        )
    reaction = Reaction.model_validate(row["reaction"])
    timeline = Timeline.model_validate(sim["timeline"] or {})
    history = [AgentChatTurn.model_validate(t) for t in _chat(conn, simulation_id, agent_no)]
    facts = [
        body.message,
        reaction.model_dump_json(),
        timeline.model_dump_json(),
        *(t.content for t in history),
    ]

    def write() -> str:
        return (
            providers.get_llm()
            .run(
                T22,
                T22Input(
                    persona=brief,
                    reaction=reaction,
                    timeline=timeline,
                    history=history,
                    question=body.message,
                ),
            )
            .answer
        )

    answer, _src = validator.checked(write, facts, lambda: f"{reaction.reason}.")
    now = clock.now()
    with conn.cursor() as cur:
        cur.executemany(
            """
            insert into public.agent_chats (simulation_id, agent_no, role, content, created_at)
            values (%s, %s, %s, %s, %s)
            """,
            [
                (simulation_id, agent_no, "user", body.message, now),
                (simulation_id, agent_no, "agent", answer, now),
            ],
        )
    return AgentChatOut(answer=answer, messages_left=_left(conn, simulation_id))
