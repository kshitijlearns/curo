"""Studio projects (MVP doc §7; logic doc §9–§12). One project id carries the opportunity, the
chosen idea, every script, storyboard and caption version, and later the simulation.

Generation answers 202 with a job id (the app follows it on GET /v1/jobs/{id}, then reloads
the project); quick steps answer with the project.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status

from curo import clock
from curo.db import service_connection
from curo.jobs import studio
from curo.routes.deps import require_creator, rls_conn
from curo.schemas.api import (
    CaptionsReviseIn,
    ChosenCaptionIn,
    HashtagsIn,
    IdeasIn,
    InstructionIn,
    OwnScriptIn,
    Project,
    ProjectIn,
    ProjectStarted,
    SaveIn,
    ScriptIn,
    StudioJob,
    ValidateIn,
    Validation,
)
from curo.services import billing
from curo.services import ideas as idea_svc
from curo.services.captions import HashtagLimit
from curo.services.opportunities import TAG_LABELS

router = APIRouter(prefix="/v1", tags=["studio"])


def _own(conn: psycopg.Connection, project_id: UUID) -> dict:
    row = conn.execute("select * from public.projects where id = %s", (project_id,)).fetchone()
    if row is None:  # RLS: someone else's project reads as missing
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return row


def _conflict(exc: Exception) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, str(exc))


# ------------------------------------------------------------------ reading a project


def _idea(row: dict) -> dict[str, Any]:
    parts = row["parts"] or {}
    values = {k: float(v["value"]) for k, v in parts.items()} if parts else None
    return {
        "id": row["id"],
        "text": row["text"],
        "description": row["description"] or "",
        "why": row["why"] or "",
        "slot": row["slot"],
        "score": float(row["score"]) if row["score"] is not None else None,
        "parts": values,
        "shares": idea_svc.shares(values) if values else None,
        "evidence": row["evidence"] or [],
        "format": row["format"],
        "target_behaviour": row["target_behaviour"],
        "source": row["source"],
        "selected": row["selected"],
    }


def project_state(conn: psycopg.Connection, project_id: UUID) -> Project:
    p = _own(conn, project_id)
    out: dict[str, Any] = {
        "id": p["id"],
        "title": p["title"],
        "step": p["step"],
        "status": p["status"],
        "saved_at": p["saved_at"],
    }
    if p["opportunity_id"]:
        o = conn.execute(
            "select id, name, tag from public.opportunities where id = %s", (p["opportunity_id"],)
        ).fetchone()
        if o:
            out["opportunity"] = {"id": o["id"], "name": o["name"], "tag": TAG_LABELS[o["tag"]]}
    rows = conn.execute(
        # The three cards keep their jobs' order (proven, adapted, explore) whatever their
        # scores: the personas' reactions (v2.2) can move a score after the slots are picked.
        """
        select * from public.ideas where project_id = %s
         order by round, array_position(array['proven', 'adapted', 'explore'], slot) nulls last,
                  score desc nulls last, created_at
        """,
        (project_id,),
    ).fetchall()
    rounds: dict[int, dict] = {}
    for r in rows:
        rnd = rounds.setdefault(
            r["round"], {"round": r["round"], "prompt": r["prompt"], "ideas": []}
        )
        rnd["ideas"].append(_idea(r))
        if r["selected"]:
            out["idea"] = _idea(r)
    out["rounds"] = [
        r for r in rounds.values() if any(i["source"] == "generated" for i in r["ideas"])
    ]
    _idea_row, s, b, c = studio.current(conn, project_id)  # what belongs to the chosen idea
    if s:
        plan = s["plan"] or {}
        band = plan.get("band")
        out["script"] = {
            "version": s["version"],
            "beats": s["beats"],
            "seconds": s["beats"][-1]["end_s"] if s["beats"] else 0,
            "words": sum(len(b["text"].split()) for b in s["beats"]),
            "band": f"{band['low']}–{band['high']} seconds, from {band['basis']}" if band else None,
            "instruction": s["instruction"],
            "reply": s["reply"],
            "changed_beat_ids": s["changed_beat_ids"],
            "source": s["source"],
        }
    if b:
        stale = set(b["stale_frame_ids"] or [])
        out["storyboard"] = {
            "version": b["version"],
            "script_version": b["script_version"],
            "frames": [{**f, "stale": f["id"] in stale} for f in b["frames"]],
            "feasibility": b["feasibility"],
            "instruction": b["instruction"],
            "reply": b["reply"],
            "up_to_date": not stale,
        }
    if c:
        out["captions"] = {
            "version": c["version"],
            "options": c["options"],
            "chosen": c["chosen"],
            "hashtags": c["hashtags"],
            "candidates": [
                {"tag": t["tag"], "kind": t["kind"], "score": t["score"]}
                for t in c["candidates"] or []
            ],
            "instruction": c["instruction"],
            "reply": c["reply"],
        }
    return Project.model_validate(out)


# ------------------------------------------------------------------ projects


@router.post("/projects", response_model=ProjectStarted, status_code=status.HTTP_201_CREATED)
def create(body: ProjectIn, conn: psycopg.Connection = Depends(rls_conn)) -> ProjectStarted:
    """A new project, from an opportunity (its first three ideas start straight away) or from
    an idea the creator validated."""
    creator = require_creator(conn)
    if body.opportunity_id:
        own = conn.execute(
            "select 1 from public.opportunities where id = %s", (body.opportunity_id,)
        ).fetchone()
        if own is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Opportunity not found")
    with service_connection() as sc:  # a project credit (PLAN_V2 §4.6), checked first
        billing.require(sc, creator["id"], "project", clock.now())
    try:
        project_id, job_id = studio.create_project(
            creator["id"], body.opportunity_id, body.idea_text
        )
    except studio.StudioError as exc:
        raise _conflict(exc) from exc
    with service_connection() as sc:
        billing.spend(sc, creator["id"], "project", f"project:{project_id}", clock.now())
    return ProjectStarted(project_id=project_id, job_id=job_id)


@router.get("/projects/{project_id}", response_model=Project)
def get_project(project_id: UUID, conn: psycopg.Connection = Depends(rls_conn)) -> Project:
    require_creator(conn)
    return project_state(conn, project_id)


REVISIONS = {"ideas", "script_revise", "storyboard_revise", "captions_revise"}


def _start(conn, project_id: UUID, action: str, params: dict | None = None) -> StudioJob:
    require_creator(conn)
    project = _own(conn, project_id)
    if action in REVISIONS:  # up to PROJECT_REVISIONS per project credit
        with service_connection() as sc:
            billing.revise(sc, project_id)
    job_id = studio.queue_step(
        project, action, {k: v for k, v in (params or {}).items() if v is not None}
    )
    return StudioJob(project_id=project_id, job_id=job_id)


# ------------------------------------------------------------------ step 1 · ideas


@router.post(
    "/projects/{project_id}/ideas", response_model=StudioJob, status_code=status.HTTP_202_ACCEPTED
)
def new_ideas(
    project_id: UUID, body: IdeasIn, conn: psycopg.Connection = Depends(rls_conn)
) -> StudioJob:
    """Three ideas (a new round each time; with the creator's note, three that keep its core)."""
    return _start(conn, project_id, "ideas", {"prompt": body.prompt})


@router.post("/ideas/validate", response_model=Validation)
def validate(body: ValidateIn, conn: psycopg.Connection = Depends(rls_conn)) -> Validation:
    """Score a free-typed idea: verdict band, two reasons with evidence, tweaks with gains."""
    creator = require_creator(conn)
    return Validation.model_validate(studio.validate(creator["id"], body.text))


@router.post("/projects/{project_id}/ideas/{idea_id}/select", response_model=Project)
def select(
    project_id: UUID, idea_id: UUID, conn: psycopg.Connection = Depends(rls_conn)
) -> Project:
    require_creator(conn)
    _own(conn, project_id)
    try:
        studio.select_idea(project_id, idea_id)
    except studio.StudioError as exc:
        raise _conflict(exc) from exc
    return project_state(conn, project_id)


# ------------------------------------------------------------------ step 2 · script


@router.post(
    "/projects/{project_id}/script", response_model=StudioJob, status_code=status.HTTP_202_ACCEPTED
)
def script(
    project_id: UUID, body: ScriptIn, conn: psycopg.Connection = Depends(rls_conn)
) -> StudioJob:
    """Write the script (or regenerate it: a different structure and hook)."""
    return _start(
        conn,
        project_id,
        "script",
        {"direction": body.direction, "regenerate": body.regenerate or None},
    )


@router.post(
    "/projects/{project_id}/script/revise",
    response_model=StudioJob,
    status_code=status.HTTP_202_ACCEPTED,
)
def revise_script(
    project_id: UUID, body: InstructionIn, conn: psycopg.Connection = Depends(rls_conn)
) -> StudioJob:
    """A chat or voice change: only the beats it touches are rewritten."""
    return _start(conn, project_id, "script_revise", {"instruction": body.instruction})


@router.put("/projects/{project_id}/script", response_model=Project)
def own_script(
    project_id: UUID, body: OwnScriptIn, conn: psycopg.Connection = Depends(rls_conn)
) -> Project:
    """The creator's own script: kept as written, split into beats, notes added."""
    require_creator(conn)
    _own(conn, project_id)
    try:
        studio.put_own_script(project_id, body.text)
    except studio.StudioError as exc:
        raise _conflict(exc) from exc
    return project_state(conn, project_id)


# ------------------------------------------------------------------ step 3 · storyboard


@router.post(
    "/projects/{project_id}/storyboard",
    response_model=StudioJob,
    status_code=status.HTTP_202_ACCEPTED,
)
def storyboard(project_id: UUID, conn: psycopg.Connection = Depends(rls_conn)) -> StudioJob:
    """Build the frames (or redraw only those whose script lines changed)."""
    return _start(conn, project_id, "storyboard")


@router.post(
    "/projects/{project_id}/storyboard/revise",
    response_model=StudioJob,
    status_code=status.HTTP_202_ACCEPTED,
)
def revise_storyboard(
    project_id: UUID, body: InstructionIn, conn: psycopg.Connection = Depends(rls_conn)
) -> StudioJob:
    return _start(
        conn,
        project_id,
        "storyboard_revise",
        {
            "instruction": body.instruction,
            "frame": body.frame_id.removeprefix("f-") if body.frame_id else None,
        },
    )


# ------------------------------------------------------------------ step 4 · caption and hashtags


@router.post(
    "/projects/{project_id}/captions",
    response_model=StudioJob,
    status_code=status.HTTP_202_ACCEPTED,
)
def captions(project_id: UUID, conn: psycopg.Connection = Depends(rls_conn)) -> StudioJob:
    """Three captions with different jobs, and five suggested hashtags."""
    return _start(conn, project_id, "captions")


@router.post(
    "/projects/{project_id}/captions/revise",
    response_model=StudioJob,
    status_code=status.HTTP_202_ACCEPTED,
)
def revise_captions(
    project_id: UUID, body: CaptionsReviseIn, conn: psycopg.Connection = Depends(rls_conn)
) -> StudioJob:
    if not body.instruction and not body.own_caption:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Say what to change, or paste your caption."
        )
    return _start(
        conn,
        project_id,
        "captions_revise",
        {"instruction": body.instruction, "own_caption": body.own_caption},
    )


@router.put("/projects/{project_id}/hashtags", response_model=Project)
def hashtags(
    project_id: UUID, body: HashtagsIn, conn: psycopg.Connection = Depends(rls_conn)
) -> Project:
    """Save the chosen hashtags. A sixth is refused: Instagram allows five."""
    require_creator(conn)
    _own(conn, project_id)
    try:
        studio.put_hashtags(project_id, body.hashtags)
    except HashtagLimit as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    except studio.StudioError as exc:
        raise _conflict(exc) from exc
    return project_state(conn, project_id)


@router.put("/projects/{project_id}/caption", response_model=Project)
def chosen_caption(
    project_id: UUID, body: ChosenCaptionIn, conn: psycopg.Connection = Depends(rls_conn)
) -> Project:
    require_creator(conn)
    _own(conn, project_id)
    try:
        studio.choose_caption(project_id, body.chosen)
    except studio.StudioError as exc:
        raise _conflict(exc) from exc
    return project_state(conn, project_id)


# ------------------------------------------------------------------ final draft


@router.post("/projects/{project_id}/save", response_model=Project)
def save(project_id: UUID, body: SaveIn, conn: psycopg.Connection = Depends(rls_conn)) -> Project:
    """Save the draft to Saved (no "Simulate" here: CURO only simulates a recorded video)."""
    require_creator(conn)
    _own(conn, project_id)
    try:
        studio.save_project(project_id, body.step)
    except studio.StudioError as exc:
        raise _conflict(exc) from exc
    return project_state(conn, project_id)
