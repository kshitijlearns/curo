"""The Simulator's jobs (MVP doc §9–10, T9 and T15; logic doc §13).

``run_simulation`` treats an upload exactly like a posted reel — understanding (T1), DNA (T2)
and embedding, through the same code as ``process_reel`` — then estimates it against the
creator's own history (T9). T15 proposes edits for what holds it back, and each one is
re-scored by T9 before it is shown, so the score, its reasons and its edits come from one run.

v2 (PLAN_V2 §4.5) adds the AI audience (``jobs/audience.py``): SIM_AGENTS personas built from
the creator's own comments watch the video, react, comment and reply; their calibrated rates
give the predicted ranges, the skip curve and the 0–100 engagement score the app leads with.
T9's estimate stays underneath for Ask Curo's "what if" and the edits.

``apply_sim_edit`` writes an accepted edit back to the linked Studio draft ("Edit & re-run"):
the script and storyboard change as a ``simulator_edit`` version. The creator then records
again and uploads the new take, and the Simulator runs on it as a re-run.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from psycopg.types.json import Jsonb

from curo import clock, events, providers
from curo.config import get_settings
from curo.db import service_connection
from curo.jobs import JobContext, JobFailed, job
from curo.jobs import audience as audience_jobs
from curo.jobs import studio as studio_jobs
from curo.jobs.understand import understand_video
from curo.providers.storage.base import StorageError
from curo.queue import enqueue
from curo.schemas.tasks import T15, EditProposal, Factor, T15Input
from curo.schemas.taxonomy import ALL_FIELDS, DERIVED_FIELDS, UNKNOWN
from curo.services import dna, ideas, mp4, sim_context, simulator, validator
from curo.services import storyboard as sb
from curo.services import studio_context as sc
from curo.services.revisions import Route
from curo.services.text import hashtags_in, reel_title

METHOD_VERSION = "t9-v0"
RECENT_DAYS = 60  # originality: against the creator's own recent reels
ROLE_NAMES = {"hook": "Hook", "setup": "Setup", "ending": "Ending"}
ACCURACY_RUNS = 10
UNDERSTOOD = ("hook_type", "opening_style", "narrative", "ending", "cta_type")


def create(
    creator_id: UUID,
    video_path: str,
    meta: mp4.VideoMeta,
    audience: str,
    project_id: UUID | None = None,
    caption: str | None = None,
    parent_id: UUID | None = None,
) -> tuple[UUID, UUID]:
    """Record the simulation and start its job; returns (simulation id, job id)."""
    with service_connection() as conn:
        row = conn.execute(
            """
            insert into public.simulations
              (creator_id, project_id, parent_simulation_id, video_path, video_meta, audience,
               caption, created_at)
            values (%s, %s, %s, %s, %s, %s, %s, %s) returning id
            """,
            (
                creator_id,
                project_id,
                parent_id,
                video_path,
                Jsonb({"duration_s": meta.duration_s, "width": meta.width, "height": meta.height}),
                audience,
                caption,
                clock.now(),
            ),
        ).fetchone()
    job_id = enqueue(
        "run_simulation",
        {"simulation_id": str(row["id"])},
        creator_id=creator_id,
        idempotency_key=f"simulation:{row['id']}",
    )
    _set(row["id"], job_id=job_id)
    return row["id"], job_id


def queue_apply(edit_id: UUID, creator_id: UUID) -> UUID:
    return enqueue(
        "apply_sim_edit",
        {"edit_id": str(edit_id)},
        creator_id=creator_id,
        idempotency_key=f"simulation_edit:{edit_id}",
    )


def _set(simulation_id: UUID, **fields: Any) -> None:
    cols = ", ".join(f"{k} = %s" for k in fields)
    with service_connection() as conn:
        conn.execute(
            f"update public.simulations set {cols} where id = %s",
            (*fields.values(), simulation_id),
        )


# ====================================================================== run_simulation


@job("run_simulation")
def run_simulation(ctx: JobContext) -> dict[str, Any]:
    simulation_id = UUID(str(ctx.payload["simulation_id"]))
    with service_connection() as conn:
        sim = conn.execute(
            "select * from public.simulations where id = %s", (simulation_id,)
        ).fetchone()
    if sim is None:
        return {"skipped": "missing"}
    if sim["status"] == "done":
        return {"simulation_id": str(simulation_id), "skipped": "already done"}
    _set(simulation_id, status="running", error=None)
    try:
        scores = simulate(ctx, sim)
    except JobFailed as exc:
        _set(simulation_id, status="failed", error=str(exc), finished_at=clock.now())
        raise
    except Exception:
        _set(
            simulation_id,
            status="failed",
            error="Curo couldn’t finish this simulation. Try running it again.",
            finished_at=clock.now(),
        )
        raise
    return {"simulation_id": str(simulation_id), "scores": scores}


def _draft(conn, project_id: UUID | None) -> dict | None:
    if project_id is None:
        return None
    project = conn.execute("select * from public.projects where id = %s", (project_id,)).fetchone()
    if project is None:
        return None
    idea, script_row, board, captions = studio_jobs.current(conn, project_id)
    return {
        "project": project,
        "idea": idea,
        "script": script_row,
        "board": board,
        "captions": captions,
    }


def _caption(given: str | None, draft: dict | None) -> tuple[str, list[str]]:
    """The caption the reel will be posted with: the one given with the upload, else the linked
    draft's chosen caption and hashtags, else none."""
    if given is not None:
        return given, hashtags_in(given)
    caps = draft["captions"] if draft else None
    if caps and caps["chosen"] is not None and caps["options"]:
        text = caps["options"][min(caps["chosen"], len(caps["options"]) - 1)]["text"]
        tags = list(dict.fromkeys([*hashtags_in(text), *caps["hashtags"]]))
        return text, tags
    return "", []


def simulate(ctx: JobContext, sim: dict) -> dict[str, int]:
    settings = get_settings()
    bucket = settings.storage_bucket_videos
    try:
        raw = providers.get_storage().get(bucket, sim["video_path"])
    except StorageError as exc:
        raise JobFailed("Curo couldn’t find the uploaded video. Upload it again.") from exc
    try:
        meta = mp4.check(raw)
    except mp4.NotAVideo as exc:
        raise JobFailed(str(exc)) from exc
    creator_id = sim["creator_id"]
    with service_connection() as conn:
        draft = _draft(conn, sim["project_id"])
    caption, hashtags = _caption(sim["caption"], draft)

    # Steps 2–5 of the pipeline, as for a posted reel.
    u = understand_video(
        bucket, sim["video_path"], meta.duration_s, caption, hashtags, ctx.progress
    )
    t1 = u.t1.model_dump()
    features = dna.features(u.content, u.production, t1, meta.duration_s)

    ctx.progress(step="trend")
    with service_connection() as conn:
        data = sim_context.load(conn, creator_id)
        project = draft["project"] if draft else None
        studio = sc.load(conn, creator_id, project["opportunity_id"] if project else None)
        accuracy = _accuracy(conn, creator_id)
        parent = (
            conn.execute(
                "select id, scores from public.simulations where id = %s",
                (sim["parent_simulation_id"],),
            ).fetchone()
            if sim["parent_simulation_id"]
            else None
        )
    trend, subcluster = _trend(studio, data, u, caption, hashtags, features, project)

    ctx.progress(step="compare")
    near = simulator.neighbours(u.vector, features.get("format"), data.pool)
    est = simulator.estimate(features, near, data.cards, data.widen)

    ctx.progress(step="estimate")
    scores = simulator.scores(est, data.history)
    rows = simulator.report(est, data.baselines_7d)
    edits = _edits(features, near, data, scores, meta, u.t1.first_payoff_s, draft)
    frames = _Frames(draft, meta.duration_s)
    for e in edits:
        ref = frames.ref(simulator.edit_moment(e["feature_change"]))
        e["frame_index"] = ref["frame"] if ref else None
        e["frame_label"] = ref["label"] if ref else None
        e["beat_id"] = ref.get("beat_id") if ref else None

    audiences = {}
    for audience in simulator.AUDIENCES:
        working, holding = simulator.reasons(features, data.cards, audience, u.t1.first_payoff_s)
        audiences[audience] = {
            "score": scores[audience],
            "label": simulator.score_label(scores[audience]),
            "summary": simulator.summary(rows, holding),
            "working": [_item(r, u.vector, data, frames) for r in working],
            "holding": [_item(r, u.vector, data, frames) for r in holding],
            "edit_ids": simulator.best_edits(
                [(str(e["id"]), e["gains"], e["effort"]) for e in edits], audience
            ),
        }

    crowd = audience_jobs.run_audience(
        sim["id"],
        creator_id,
        u.t1,
        caption,
        meta.duration_s,
        data.baselines_7d.get("views"),
        ctx.progress,
    )
    previous_engagement = None
    if sim["parent_simulation_id"]:
        with service_connection() as conn:
            row = conn.execute(
                "select engagement_score from public.simulations where id = %s",
                (sim["parent_simulation_id"],),
            ).fetchone()
        previous_engagement = row["engagement_score"] if row else None
    crowd["previous_engagement_score"] = previous_engagement

    local_now = clock.now().astimezone(ZoneInfo(data.timezone))
    result = {
        "audience": crowd,
        "method": METHOD_VERSION,
        "video": {
            "duration_s": meta.duration_s,
            "width": meta.width,
            "height": meta.height,
        },
        "caption": caption,
        "linked": draft is not None and draft["script"] is not None,
        "audiences": audiences,
        "report": rows,
        "best_time": simulator.best_time(data.posts, local_now),
        "accuracy": accuracy,
        "dna": {
            "content": simulator.content_rows(u.content, subcluster),
            "production": simulator.production_rows(u.production, features, meta.duration_s, t1),
            "trend": trend,
        },
        "compare": (
            simulator.compare(u.t1.transcript_text(), meta.duration_s, draft["script"]["beats"])
            if draft and draft["script"]
            else []
        ),
        "notes": _notes(features, u.t1.transcript, est, near)
        + (
            ["Your recent estimates missed more often than they should, so these ranges are wider."]
            if data.widen > 1
            else []
        ),
        "basis": {
            "neighbours": len(near),
            "own_neighbours": est.own_n,
            "own_reels": len(data.own),
            "history": len(data.history),
        },
        "previous": (
            {"simulation_id": str(parent["id"]), "scores": parent["scores"]}
            if parent and parent["scores"]
            else None
        ),
    }
    with service_connection() as conn:
        conn.execute("delete from public.simulation_edits where simulation_id = %s", (sim["id"],))
        for e in edits:
            conn.execute(
                """
                insert into public.simulation_edits
                  (id, simulation_id, title, description, feature_change, delta, effort,
                   frame_index, frame_label, beat_id, gains)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    e["id"],
                    sim["id"],
                    e["title"],
                    e["description"],
                    Jsonb(e["feature_change"]),
                    e["gains"][sim["audience"]],
                    e["effort"],
                    e["frame_index"],
                    e["frame_label"],
                    e["beat_id"],
                    Jsonb(e["gains"]),
                ),
            )
        conn.execute(
            """
            update public.simulations
               set status = 'done', score = %s, scores = %s, predicted = %s, result = %s,
                   method_version = %s, inputs = %s, video_meta = %s, finished_at = %s,
                   error = null, engagement_score = %s, timeline = %s, persona_version = %s
             where id = %s
            """,
            (
                scores[sim["audience"]],
                Jsonb(scores),
                Jsonb(simulator.predicted_counts(est, data.baselines_7d)),
                Jsonb(result),
                METHOD_VERSION,
                Jsonb(
                    {  # what Ask Curo re-scores "what if" changes and comparisons from
                        "features": features,
                        "vector": [round(x, 6) for x in u.vector],
                        "payoff_s": u.t1.first_payoff_s,
                        "duration_s": meta.duration_s,
                        "transcript": u.t1.transcript_text(),
                    }
                ),
                Jsonb(
                    {
                        "duration_s": meta.duration_s,
                        "width": meta.width,
                        "height": meta.height,
                        "brand": meta.brand,
                    }
                ),
                clock.now(),
                crowd["engagement_score"],
                Jsonb(crowd["timeline"]),
                crowd["persona_version"],
                sim["id"],
            ),
        )
        events.record(
            conn,
            creator_id,
            "simulation_done",
            {"simulation_id": str(sim["id"]), "score": scores[sim["audience"]]},
        )
    return scores


# ---------------------------------------------------------------------- pieces of the result


class _Frames:
    """Links a moment of the recording ("hook", "ending") to the linked draft's storyboard
    frame, or names the moment when there's no storyboard."""

    def __init__(self, draft: dict | None, duration_s: float | None):
        board = draft["board"] if draft else None
        script_row = draft["script"] if draft else None
        self.frames = board["frames"] if board else []
        self.roles = {b["id"]: b["role"] for b in (script_row["beats"] if script_row else [])}
        self.duration = duration_s

    def _name(self, index: int) -> str:
        role = self.roles.get(self.frames[index]["beat_id"], "")
        if role == "item":
            k = sum(1 for f in self.frames[: index + 1] if self.roles.get(f["beat_id"]) == "item")
            return f"Part {k}"
        return ROLE_NAMES.get(role, "Frame")

    def ref(self, moment: str | None) -> dict | None:
        if moment is None:
            return None
        if self.frames:
            index = 0 if moment == "hook" else len(self.frames) - 1
            return {
                "frame": index,
                "label": f"Frame {index + 1} · {self._name(index)}",
                "beat_id": self.frames[index]["beat_id"],
            }
        if moment == "hook":
            return {"frame": None, "label": "Opening · 0:00"}
        end = f" · {simulator._mmss(self.duration)}" if self.duration else ""
        return {"frame": None, "label": f"Ending{end}"}


def _item(r: simulator.Reason, vector: list[float], data, frames: _Frames) -> dict:
    ref = frames.ref(r.moment)
    return {
        "key": r.key,
        "feature": r.feature,
        "value": r.value,
        "better": r.better,
        "metric": r.card.metric,
        "text": r.text,
        "short": r.short,
        "evidence": simulator.evidence(r, vector, data.pool),
        "frame": ref["frame"] if ref else None,
        "frame_label": ref["label"] if ref else None,
    }


def _valid(feature: str, value: str) -> bool:
    allowed = ALL_FIELDS.get(feature) or DERIVED_FIELDS.get(feature) or ()
    return feature in simulator.ADJUSTABLE and value in allowed and value != UNKNOWN


def _edits(
    features: dict[str, str],
    near: list[simulator.Neighbour],
    data: sim_context.SimData,
    scores: dict[str, int],
    meta: mp4.VideoMeta,
    payoff_s: float | None,
    draft: dict | None,
) -> list[dict]:
    """T15's proposals, each re-scored by T9 (step 7); only those that help some audience."""
    found = simulator.factors(features, data.cards)[:8]
    if not found:
        return []
    facts = [simulator.fact(r) for r in found]
    out = providers.get_llm().run(
        T15,
        T15Input(
            format=features.get("format", UNKNOWN),
            duration_s=meta.duration_s,
            payoff_s=payoff_s,
            script=[b["text"] for b in draft["script"]["beats"]]
            if draft and draft["script"]
            else [],
            factors=[
                Factor(
                    feature=r.feature,
                    current=r.value,
                    better=r.better or "",
                    metric=r.card.metric,
                    fact=f,
                )
                for r, f in zip(found, facts, strict=True)
            ],
        ),
    )
    edits, seen = [], set()
    for p in out.edits:
        change = {
            k: v for k, v in p.feature_change.items() if _valid(k, v) and features.get(k) != v
        }
        key = tuple(sorted(change.items()))
        if not change or key in seen:
            continue
        seen.add(key)
        gains = simulator.rescore_edit(features, change, near, data.cards, data.history, scores)
        if max(gains.values()) <= 0:
            continue  # re-scored, it doesn't help: not shown
        title, description = _honest(p, found, facts)
        edits.append(
            {
                "id": uuid.uuid4(),
                "title": title,
                "description": description,
                "feature_change": change,
                "effort": p.effort,
                "gains": gains,
            }
        )
    return edits


def _honest(p: EditProposal, found: list[simulator.Reason], facts: list[str]) -> tuple[str, str]:
    """The edit's words may only carry numbers from the facts it was given; otherwise the
    template words for its first factor are used."""
    if not validator.new_numbers(f"{p.title} {p.description}", facts):
        return p.title, p.description
    feature = next(iter(p.feature_change))
    r = next((x for x in found if x.feature == feature), found[0])
    better = simulator.phrase(r.feature, r.better or r.value)
    return f"Try {better}"[:60], facts[found.index(r)]


def _notes(features: dict, transcript: list, est: simulator.Estimate, near: list) -> list[str]:
    """What the estimate couldn't see, said plainly."""
    out = []
    missing = [f for f in UNDERSTOOD if f not in features]
    if len(missing) >= 3:
        names = {
            "hook_type": "hook",
            "opening_style": "opening",
            "narrative": "structure",
            "ending": "ending",
            "cta_type": "call to action",
        }
        listed = ", ".join(names[m] for m in missing)
        out.append(
            f"Curo couldn’t make out this video’s {listed}, so the estimate leans on your "
            "similar reels and leaves those out."
        )
    if not transcript:
        out.append("No speech was found in this video, so nothing it says was compared.")
    if near and est.own_n < simulator.MIN_OWN:
        out.append(
            f"{est.own_n} of the {len(near)} reels it’s compared with are yours; the rest are "
            "from creators you track. With fewer of your own, the ranges are wider."
        )
    if not near:
        out.append("Curo found no similar reels to compare with, so there’s no estimate yet.")
    return out


def _accuracy(conn, creator_id: UUID) -> str:
    rows = conn.execute(
        """
        select in_range from public.simulations
         where creator_id = %s and in_range is not null order by created_at desc limit %s
        """,
        (creator_id, ACCURACY_RUNS),
    ).fetchall()
    return simulator.accuracy_note(sum(1 for r in rows if r["in_range"]), len(rows))


def _trend(
    studio: sc.StudioData,
    data: sim_context.SimData,
    u,
    caption: str,
    hashtags: list[str],
    features: dict[str, str],
    project: dict | None,
) -> tuple[list[list[str]], str | None]:
    """The Trend DNA panel (logic doc §13; v2 no peers): topic momentum, the trend in the
    creator's niche it rides, audience and creator fit, and originality against their own recent
    reels. Fits come from the same parts the idea scorer uses (logic doc §9)."""
    spoken = u.t1.transcript_text()
    title = reel_title(caption) if caption else ""
    text = f"{title or spoken[:120]} {' '.join(hashtags)}".strip()
    vector = providers.get_embedding().embed([text or "reel"])[0]
    ctx = studio.ctx
    group, rel = ideas.nearest_group(vector, ctx)
    subcluster = group.label if group and rel >= 0.5 else None
    candidate = ideas.Candidate(
        text=f"{caption} {spoken}".strip(),
        format=features.get("format", UNKNOWN),
        hook_type=features.get("hook_type", UNKNOWN),
        target="views",
        vector=vector,
    )
    h = ideas.part_h(candidate, ctx)
    a = ideas.part_a(candidate, ctx)
    t = ideas.part_t(candidate, ctx)
    adapted = ideas.adapted_from(candidate, ctx)
    since = data.now - timedelta(days=RECENT_DAYS)
    recent = [x for x in data.own if x.posted_at and x.posted_at >= since]
    value, closest = simulator.originality(u.vector, recent)
    topic = (studio.opportunity or {}).get("name") if project else None

    def fit(part) -> str:
        band = simulator.fit_band(part.value)
        return f"{band} · {part.facts[0]}" if part.facts else band

    rows = [
        ["Topic", topic or subcluster or "Unknown"],
        ["Momentum", " ".join(t.facts) or "No rising hashtag or coming event matches it"],
        [
            "Trending in your niche",
            adapted.name if adapted else "No trend in your niche's feed matches it",
        ],
        ["Audience fit", fit(a)],
        ["Creator fit", fit(h)],
        ["Originality", simulator.originality_text(value, closest)],
    ]
    return rows, subcluster


# ====================================================================== apply_sim_edit


@job("apply_sim_edit")
def apply_sim_edit(ctx: JobContext) -> dict[str, Any]:
    """Write an accepted edit back to the linked Studio draft: script changes first (as a
    ``simulator_edit`` version), then the frames whose lines changed are redrawn, then any
    storyboard-only change."""
    edit_id = UUID(str(ctx.payload["edit_id"]))
    with service_connection() as conn:
        edit = conn.execute(
            """
            select e.*, s.project_id from public.simulation_edits e
              join public.simulations s on s.id = e.simulation_id where e.id = %s
            """,
            (edit_id,),
        ).fetchone()
        if edit is None or edit["project_id"] is None:
            return {"skipped": "no draft"}
        project = studio_jobs.project_row(conn, edit["project_id"])
        script_row = studio_jobs.current(conn, project["id"])[1]
        data = sc.load(conn, project["creator_id"], project["opportunity_id"])
    if script_row is None:
        return {"skipped": "no script"}
    instruction = f"{edit['title']}. {edit['description']}"
    changes = simulator.studio_changes(edit["feature_change"])
    done: list[str] = []
    try:
        for ch in [c for c in changes if c.step == "script"]:
            studio_jobs.revise_script(
                project,
                data,
                instruction,
                route=Route(ch.action, [], dict(ch.params)),
                source="simulator_edit",
            )
            done.append(ch.action)
        with service_connection() as conn:
            board = studio_jobs.current(conn, project["id"])[2]
        if board is not None and done:
            studio_jobs.build_storyboard(project, data)  # frames whose lines changed
        for ch in [c for c in changes if c.step == "storyboard"]:
            if board is None:
                break
            if ch.action == "label_frames":
                _label_frames(project, instruction)
            else:
                studio_jobs.revise_storyboard(
                    project, data, instruction, None, route=Route(ch.action, [], dict(ch.params))
                )
            done.append(ch.action)
    except studio_jobs.StudioError as exc:
        raise JobFailed(str(exc)) from exc
    return {"edit_id": str(edit_id), "changes": done}


def _label_frames(project: dict, instruction: str) -> None:
    with service_connection() as conn:
        _idea, script_row, board, _caps = studio_jobs.current(conn, project["id"])
    if board is None or script_row is None:
        return
    frames, changed = sb.label_frames(board["frames"])
    if not changed:
        return
    n = len(changed)
    reply = f"Added on-screen text to {n} frame{'s' if n != 1 else ''} that had none."
    studio_jobs._store_board(project, script_row["version"], frames, instruction, reply)
