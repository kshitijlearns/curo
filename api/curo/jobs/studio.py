"""The Studio (logic doc §9–§12): one project carries idea → script → storyboard → caption.

Generation (ideas, scripts, storyboards, captions and their revisions) can take a model longer
than about 5 seconds, so it runs as the ``studio`` job on the worker's priority queue and the
API answers 202 with the job's id (MVP doc §7; DECISIONS D68). Quick steps — picking an idea,
the creator's own script, hashtags, the chosen caption, saving, validating an idea — run in the
request. Every version is kept; the newest is what the creator sees.
"""

from __future__ import annotations

import hashlib
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from curo import clock, events, providers
from curo.db import service_connection
from curo.jobs import JobContext, JobFailed, job
from curo.queue import enqueue
from curo.schemas.tasks import (
    T6,
    T7,
    T8,
    T11,
    T12,
    T13,
    BeatPlan,
    BeatText,
    CardRef,
    FrameBeat,
    FrameOut,
    T6Input,
    T7Input,
    T8Input,
    T11Input,
    T12Input,
    T13Input,
    TagOption,
)
from curo.services import captions as cap
from curo.services import ideas, revisions, script, storyboard, validator
from curo.services import studio_context as sc
from curo.services.assistant import memory
from curo.services.voice import word_budget

STEPS = ("ideas", "idea", "script", "storyboard", "caption", "final")
SHORTER = 0.85  # a creator who usually shortens scripts gets drafts planned 15% shorter


class StudioError(Exception):
    """A request that can't be done in the project's current state (shown to the creator)."""


# ====================================================================== reading and writing


def project_row(conn, project_id: UUID) -> dict:
    row = conn.execute("select * from public.projects where id = %s", (project_id,)).fetchone()
    if row is None:
        raise JobFailed("That project no longer exists.")
    return row


def latest(conn, table: str, project_id: UUID) -> dict | None:
    return conn.execute(
        f"select * from public.{table} where project_id = %s order by version desc limit 1",
        (project_id,),
    ).fetchone()


def selected_idea(conn, project_id: UUID) -> dict | None:
    return conn.execute(
        "select * from public.ideas where project_id = %s and selected order by created_at desc limit 1",
        (project_id,),
    ).fetchone()


def current(conn, project_id: UUID) -> tuple[dict | None, dict | None, dict | None, dict | None]:
    """The chosen idea and what belongs to it: its newest script, and the newest storyboard and
    captions made from one of its scripts. Picking another idea starts fresh; going back to an
    idea finds its work again."""
    idea = selected_idea(conn, project_id)
    if idea is None:
        return None, None, None, None
    scripts = conn.execute(
        "select * from public.script_versions where project_id = %s and idea_id = %s order by version desc",
        (project_id, idea["id"]),
    ).fetchall()
    if not scripts:
        return idea, None, None, None
    versions = [r["version"] for r in scripts]
    board = conn.execute(
        """
        select * from public.storyboard_versions where project_id = %s and script_version = any(%s)
         order by version desc limit 1
        """,
        (project_id, versions),
    ).fetchone()
    caps = conn.execute(
        """
        select * from public.captions where project_id = %s and script_version = any(%s)
         order by version desc limit 1
        """,
        (project_id, versions),
    ).fetchone()
    return idea, scripts[0], board, caps


def _touch(conn, project_id: UUID, step: str | None = None, title: str | None = None) -> None:
    conn.execute(
        """
        update public.projects set updated_at = %s, step = coalesce(%s, step),
               title = coalesce(%s, title)
         where id = %s
        """,
        (clock.now(), step, title, project_id),
    )


def _event(conn, creator_id, name: str, props: dict) -> None:
    events.record(conn, creator_id, name, props)


def _next_version(conn, table: str, project_id: UUID) -> int:
    # The project row is locked first, so two jobs on one project write versions in turn.
    conn.execute("select 1 from public.projects where id = %s for update", (project_id,))
    row = conn.execute(
        f"select coalesce(max(version), 0) + 1 as v from public.{table} where project_id = %s",
        (project_id,),
    ).fetchone()
    return row["v"]


def queue_step(project: dict, action: str, params: dict | None = None) -> UUID:
    """Start a generation step for a project; the same request twice reuses the first job."""
    params = params or {}
    digest = hashlib.sha1(repr(sorted(params.items())).encode()).hexdigest()[:10]
    with service_connection() as conn:
        counts = conn.execute(
            """
            select (select count(*) from public.ideas where project_id = %(p)s) as ideas,
                   (select count(*) from public.script_versions where project_id = %(p)s) as scripts,
                   (select count(*) from public.storyboard_versions where project_id = %(p)s) as boards,
                   (select count(*) from public.captions where project_id = %(p)s) as caps
            """,
            {"p": project["id"]},
        ).fetchone()
    state = f"{counts['ideas']}.{counts['scripts']}.{counts['boards']}.{counts['caps']}"
    return enqueue(
        "studio",
        {"project_id": str(project["id"]), "action": action, **params},
        creator_id=project["creator_id"],
        idempotency_key=f"studio:{project['id']}:{action}:{state}:{digest}",
    )


# ====================================================================== the job


@job("studio")
def studio(ctx: JobContext) -> dict[str, Any]:
    p = ctx.payload
    project_id = UUID(str(p["project_id"]))
    with service_connection() as conn:
        project = project_row(conn, project_id)
        data = sc.load(conn, project["creator_id"], project["opportunity_id"])
    action = p["action"]
    try:
        if action == "ideas":
            return generate_round(project, data, p.get("prompt"))
        if action == "script":
            return write_script(project, data, p.get("direction"), bool(p.get("regenerate")))
        if action == "script_revise":
            return revise_script(project, data, str(p["instruction"]))
        if action == "storyboard":
            return build_storyboard(project, data)
        if action == "storyboard_revise":
            return revise_storyboard(project, data, str(p["instruction"]), p.get("frame"))
        if action == "captions":
            return write_captions(project, data)
        if action == "captions_revise":
            return revise_captions(project, data, p.get("instruction"), p.get("own_caption"))
    except StudioError as exc:
        raise JobFailed(str(exc)) from exc
    raise JobFailed(f"Unknown Studio step {action!r}.")


# ====================================================================== step 1 · ideas


def _candidates(data: sc.StudioData, out, valid: set[str], source: str) -> list[ideas.Candidate]:
    kept = [c for c in out.candidates if set(c.evidence_ids) & valid or source == "creator"]
    if not kept:
        return []
    vectors = providers.get_embedding().embed([f"{c.text} {c.angle}" for c in kept])
    return [
        ideas.Candidate(
            text=c.text,
            format=c.format,
            hook_type=c.hook_type,
            target=c.target_behaviour,
            vector=v,
            description=c.description,
            angle=c.angle,
            evidence_ids=[e for e in c.evidence_ids if e in valid],
            source=source,
        )
        for c, v in zip(kept, vectors, strict=True)
    ]


def rescorer(data: sc.StudioData):
    embedder = providers.get_embedding()

    def rescore(c: ideas.Candidate) -> ideas.Scored:
        vector = embedder.embed([f"{c.text} {c.angle}"])[0]
        return ideas.score(ideas.Candidate(**{**c.__dict__, "vector": vector}), data.ctx)

    return rescore


def generate_round(project: dict, data: sc.StudioData, prompt: str | None) -> dict[str, Any]:
    pack = sc.evidence_pack(data)
    if not pack:
        raise StudioError("Curo needs a few of your processed reels before it can suggest ideas.")
    valid = {e.id for e in pack}
    with service_connection() as conn:
        avoid = memory.avoided_words(memory.load(conn, project["creator_id"]))
    out = providers.get_llm().run(
        T6,
        T6Input(
            topic=data.topic,
            festival=data.festival["name"] if data.festival else None,
            keywords=data.keywords,
            evidence=pack,
            creator_formats=data.creator_formats,
            creator_input=prompt,
            avoid=sorted(avoid),
            count=15,
        ),
    )
    cands = _candidates(data, out, valid, "generated")
    if not cands:
        raise StudioError("None of the ideas Curo wrote could be backed by your data. Try again.")
    # Creator memory: what they asked never to be suggested is left out, whatever T6 wrote.
    kept = [c for c in cands if not memory.mentions(f"{c.text} {c.angle} {c.description}", avoid)]
    avoided = len(cands) - len(kept)
    if not kept:
        raise StudioError(
            "Every idea Curo wrote touched something you asked it to avoid "
            f"({', '.join(sorted(avoid))}). Add a note to steer it."
        )
    cands = kept
    scored = [ideas.score(c, data.ctx) for c in cands]
    chosen = ideas.pick_three(scored, data.ctx)
    texts = {e.id: e.text for e in pack}
    with service_connection() as conn:
        conn.execute("select 1 from public.projects where id = %s for update", (project["id"],))
        rnd = conn.execute(
            "select coalesce(max(round), -1) + 1 as r from public.ideas where project_id = %s",
            (project["id"],),
        ).fetchone()["r"]
        ids = [
            _insert_idea(conn, project["id"], s, rnd, prompt, "generated", texts) for s in chosen
        ]
        _touch(conn, project["id"], step="ideas")
        _event(
            conn,
            project["creator_id"],
            "ideas_generated",
            {
                "project_id": str(project["id"]),
                "round": rnd,
                "candidates": len(out.candidates),
                "without_evidence": len(out.candidates) - len(cands) - avoided,
                "avoided": avoided,
            },
        )
    react_to_ideas(project, data, chosen, ids)
    return {"round": rnd, "ideas": ids, "candidates": len(out.candidates), "kept": len(cands)}


def _idea_target(c: ideas.Candidate, target_id: UUID, project_id: UUID | None):
    from curo.services.persona_reactions import Target

    return Target(
        "idea",
        target_id,
        1,
        " ".join(x for x in (c.text, c.description, c.angle) if x),
        None,
        c.format,
        vector=c.vector,
        project_id=project_id,
    )


def react_to_ideas(project: dict, data: sc.StudioData, chosen: list, ids: list[str]) -> None:
    """v2.2: each shown idea gets the 4 personas' reactions (T27); A and the idea's score are
    recomputed from their blended scores, so the verdict and the avatars agree."""
    from curo.services import persona_reactions

    if not data.ctx.personas:
        return
    with service_connection() as conn:
        rows = persona_reactions.active_rows(conn, project["creator_id"])
    for s, idea_id in zip(chosen, ids, strict=True):
        target = _idea_target(s.candidate, UUID(idea_id), project["id"])
        try:
            opinions = persona_reactions.react(
                project["creator_id"], rows, target, "studio_personas"
            )
        except Exception:
            import logging

            logging.getLogger("curo.personas").exception("persona reactions for an idea failed")
            continue
        s2 = ideas.score(s.candidate, data.ctx, persona_reactions.blended_scores(opinions))
        s2.slot = s.slot
        with service_connection() as conn:
            conn.execute(
                "update public.ideas set score = %s, parts = %s, why = %s where id = %s",
                (
                    s2.score,
                    Jsonb({k: {"value": p.value, "facts": p.facts} for k, p in s2.parts.items()}),
                    ideas.why_line(s2),
                    idea_id,
                ),
            )


def _insert_idea(
    conn, project_id, s: ideas.Scored, rnd: int, prompt, source: str, texts: dict
) -> str:
    c = s.candidate
    chips = [texts[e] for e in c.evidence_ids if e in texts][:3]
    row = conn.execute(
        """
        insert into public.ideas
          (project_id, round, prompt, text, description, angle, format, hook_type,
           target_behaviour, slot, score, parts, evidence_ids, evidence, why, source, selected)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        returning id
        """,
        (
            project_id,
            rnd,
            prompt,
            c.text,
            c.description,
            c.angle,
            c.format,
            c.hook_type,
            c.target,
            s.slot,
            s.score,
            Jsonb({k: {"value": p.value, "facts": p.facts} for k, p in s.parts.items()}),
            c.evidence_ids,
            Jsonb(chips),
            ideas.why_line(s),
            source,
            source == "creator",
        ),
    ).fetchone()
    return str(row["id"])


def score_own(data: sc.StudioData, text: str) -> ideas.Scored:
    """The creator's own idea, read (T6, read mode) and scored with the same formula."""
    pack = sc.evidence_pack(data) or [
        sc.EvidenceItem(id="voice", kind="format", text="Your own idea.")
    ]
    out = providers.get_llm().run(
        T6,
        T6Input(
            topic=data.topic,
            festival=data.festival["name"] if data.festival else None,
            keywords=data.keywords,
            evidence=pack,
            creator_formats=data.creator_formats,
            creator_input=text,
            mode="read",
            count=1,
        ),
    )
    c = _candidates(data, out, {e.id for e in pack}, "creator")[0]
    c.text = text.strip()  # the creator's words, as written
    s = ideas.score(c, data.ctx)
    s.slot = next((slot for slot in ideas.SLOTS if ideas.qualifies(s, slot, data.ctx)), "explore")
    return s


def validate(creator_id: UUID, text: str) -> dict[str, Any]:
    """The Studio tab's validate chat: verdict band, two reasons, tweaks with their gains."""
    import uuid

    from curo.services import persona_reactions

    with service_connection() as conn:
        data = sc.load(conn, creator_id)
    s = score_own(data, text)
    # Tweaks are compared on the code-side score, the same scale they're re-scored on.
    shown = ideas.tweaks(s, data.ctx, rescorer(data))
    personas = None
    if data.ctx.personas:
        # Cached per text and persona build: validating the same idea again never calls the
        # model, and a rebuilt persona gives a fresh take.
        with service_connection() as conn:
            rows = persona_reactions.active_rows(conn, creator_id)
            build = conn.execute(
                "select max(version) as v from public.persona_builds where creator_id = %s",
                (creator_id,),
            ).fetchone()["v"]
        key = uuid.uuid5(
            uuid.NAMESPACE_URL, f"curo:validate:{creator_id}:{build}:{text.strip().lower()}"
        )
        opinions = persona_reactions.react(
            creator_id, rows, _idea_target(s.candidate, key, None), "studio_personas"
        )
        slot = s.slot
        s = ideas.score(s.candidate, data.ctx, persona_reactions.blended_scores(opinions))
        s.slot = slot
        out = persona_reactions.out(opinions, rows)
        personas = {
            "status": "ready",
            "target_type": "idea",
            "target_id": key,
            "target_version": 1,
            **out,
        }
    with service_connection() as conn:
        _event(
            conn,
            creator_id,
            "idea_validated",
            {"score": s.score, "verdict": ideas.verdict(s.score)},
        )
    return {
        "text": text.strip(),
        "score": round(s.score, 2),
        "verdict": ideas.verdict(s.score),
        "parts": s.values,
        "shares": ideas.shares(s.values),
        "reasons": ideas.reasons(s),
        "tweaks": [{"text": t.text, "gain": t.gain} for t in shown],
        "personas": personas,
    }


def create_project(
    creator_id: UUID, opportunity_id: UUID | None, idea_text: str | None
) -> tuple[UUID, UUID | None]:
    """A new project, from an opportunity (its first ideas start straight away) or from an
    idea the creator validated (it becomes the chosen idea)."""
    with service_connection() as conn:
        if opportunity_id:
            opp = conn.execute(
                "select name from public.opportunities where id = %s and creator_id = %s",
                (opportunity_id, creator_id),
            ).fetchone()
            if opp is None:
                raise StudioError("That opportunity isn't yours.")
        project = conn.execute(
            """
            insert into public.projects (creator_id, opportunity_id, title, step, created_at, updated_at)
            values (%s, %s, %s, %s, %s, %s) returning *
            """,
            (
                creator_id,
                opportunity_id,
                None,
                "idea" if idea_text else "ideas",
                clock.now(),
                clock.now(),
            ),
        ).fetchone()
        _event(
            conn,
            creator_id,
            "project_created",
            {
                "project_id": str(project["id"]),
                "opportunity_id": str(opportunity_id) if opportunity_id else None,
            },
        )
    if idea_text:
        with service_connection() as conn:
            data = sc.load(conn, creator_id, opportunity_id)
        s = score_own(data, idea_text)
        texts = {e.id: e.text for e in sc.evidence_pack(data)}
        with service_connection() as conn:
            idea_id = _insert_idea(conn, project["id"], s, 0, None, "creator", texts)
            _touch(conn, project["id"], step="idea", title=s.candidate.text)
        react_to_ideas(project, data, [s], [idea_id])  # v2.2: its score agrees with the personas
        return project["id"], None
    job_id = queue_step(project, "ideas") if opportunity_id else None
    return project["id"], job_id


def select_idea(project_id: UUID, idea_id: UUID) -> None:
    with service_connection() as conn:
        project = project_row(conn, project_id)
        idea = conn.execute(
            "select * from public.ideas where id = %s and project_id = %s", (idea_id, project_id)
        ).fetchone()
        if idea is None:
            raise StudioError("That idea isn't part of this project.")
        conn.execute(
            "update public.ideas set selected = (id = %s) where project_id = %s",
            (idea_id, project_id),
        )
        _touch(conn, project_id, step="idea", title=idea["text"])
        skipped = conn.execute(
            "select id::text from public.ideas where project_id = %s and round = %s and id <> %s",
            (project_id, idea["round"], idea_id),
        ).fetchall()
        _event(
            conn,
            project["creator_id"],
            "idea_picked",
            {
                "project_id": str(project_id),
                "idea_id": str(idea_id),
                "slot": idea["slot"],
                "score": float(idea["score"]) if idea["score"] is not None else None,
                "skipped": [r["id"] for r in skipped],
            },
        )


# ====================================================================== step 2 · script


def _need_idea(project: dict) -> dict:
    with service_connection() as conn:
        idea = selected_idea(conn, project["id"])
    if idea is None:
        raise StudioError("Pick an idea first.")
    return idea


def _fmt(idea: dict, data: sc.StudioData) -> str:
    f = idea["format"]
    if f and f != "unknown":
        return f
    return data.creator_formats[0] if data.creator_formats else "talking_head"


def _examples(data: sc.StudioData, fmt: str) -> list[script.Example]:
    if data.examples.get(fmt):
        return data.examples[fmt]
    pool = [e for exs in data.examples.values() for e in exs]
    return pool[:3]


def _cards(data: sc.StudioData) -> dict[str, script.NoteCard]:
    return {
        c["id"]: script.NoteCard(
            c["id"], c["feature"], c["value"], c["metric"], float(c["effect"]), c["n"], c["scope"]
        )
        for c in data.cards
    }


def _notes(beats: list[dict], data: sc.StudioData) -> dict[str, dict]:
    cards = _cards(data)
    usable = script.candidate_cards(list(cards.values()))
    out = providers.get_llm().run(
        T8,
        T8Input(
            beats=[BeatText(id=b["id"], role=b["role"], text=b["text"]) for b in beats],
            cards=[
                CardRef(id=c.id, feature=c.feature, value=c.value, metric=c.metric, effect=c.effect)
                for c in usable
            ],
        ),
    )
    return script.keep_supported(
        [(n.beat_id, n.note_type, n.pattern_card_id) for n in out.notes], cards
    )


def _timed(beats: list[dict], data: sc.StudioData) -> list[dict]:
    times = script.timings([b["text"] for b in beats], data.voice)
    out = []
    for b, (start, end) in zip(beats, times, strict=True):
        out.append(
            {
                **b,
                "start_s": start,
                "end_s": end,
                "t": f"{script.fmt_time(start)} – {script.fmt_time(end)}",
            }
        )
    return out


def _with_notes(beats: list[dict], data: sc.StudioData) -> list[dict]:
    notes = _notes(beats, data)
    return [{**b, "note": notes.get(b["id"])} for b in beats]


def _store_script(
    project: dict,
    beats: list[dict],
    plan: dict,
    instruction,
    reply: str,
    source: str,
    changed: list[str],
) -> int:
    with service_connection() as conn:
        version = _next_version(conn, "script_versions", project["id"])
        idea, _script, board, _caps = current(conn, project["id"])
        conn.execute(
            """
            insert into public.script_versions
              (project_id, version, idea_id, beats, instruction, source, changed_beat_ids, reply,
               plan, created_at)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                project["id"],
                version,
                idea["id"] if idea else None,
                Jsonb(beats),
                instruction,
                source,
                changed,
                reply,
                Jsonb(plan),
                clock.now(),
            ),
        )
        if board is not None:
            conn.execute(
                "update public.storyboard_versions set stale_frame_ids = %s where id = %s",
                (storyboard.stale(board["frames"], beats), board["id"]),
            )
        _touch(conn, project["id"], step="script")
    return version


def write_script(
    project: dict, data: sc.StudioData, direction: str | None, regenerate: bool
) -> dict[str, Any]:
    idea = _need_idea(project)
    fmt = _fmt(idea, data)
    band = script.length_band(data.lengths, fmt)
    with service_connection() as conn:
        shorter = memory.prefers_shorter(memory.load(conn, project["creator_id"]))
    # Creator memory: a creator who usually shortens scripts starts at the short end.
    seconds = max(float(band.low), round(band.seconds * SHORTER)) if shorter else band.seconds
    budget = word_budget(seconds, data.voice)
    examples = _examples(data, fmt)
    with service_connection() as conn:
        before = current(conn, project["id"])[1]
    variant = (before["version"] if before else 0) if regenerate else 0
    target = idea["target_behaviour"] or "views"
    structure = script.structure(fmt, idea["text"], target, examples)
    if regenerate and variant % 2 == 1:  # a different structure: with or without the setup beat
        has_setup = any(r == "setup" for r, _ in structure)
        structure = (
            [s for s in structure if s[0] != "setup"]
            if has_setup
            else [*structure[:1], ("setup", "a quick setup before the first item"), *structure[1:]]
        )
    plan = script.plan(structure, budget)
    out = providers.get_llm().run(
        T7,
        T7Input(
            idea=idea["text"],
            angle=idea["angle"] or "",
            format=fmt,
            topic=data.topic,
            voice=data.voice,
            beats=plan,
            examples=[e.text for e in examples],
            action="regenerate" if regenerate else "write",
            direction=direction,
            variant=variant,
        ),
    )
    written = {b.id: b.text for b in out.beats}
    if any(p.id not in written for p in plan):
        raise StudioError("The script came back incomplete. Try again.")
    beats = [
        {"id": p.id, "role": p.role, "purpose": p.purpose, "text": written[p.id]} for p in plan
    ]
    beats = _with_notes(_timed(beats, data), data)
    total = beats[-1]["end_s"]
    plan_info = {
        "band": {
            "low": band.low,
            "high": band.high,
            "seconds": band.seconds,
            "n": band.n,
            "basis": band.basis,
        },
        "word_budget": budget,
        "target_seconds": seconds,
        "shorter": shorter,
        "words_per_second": data.voice.words_per_second,
        "voice_reels": data.voice.reels,
        "format": fmt,
        "structure": [
            {"id": p.id, "role": p.role, "purpose": p.purpose, "words": p.words} for p in plan
        ],
    }
    if regenerate:
        reply = "Regenerated the full script. Same idea, a different way in."
    else:
        reply = script_reply(total, band)
        if shorter:
            reply = "Started at the short end, as you usually shorten scripts. " + reply
        if direction:
            reply = "Generated with your direction in mind. " + reply
    version = _store_script(
        project,
        beats,
        plan_info,
        direction,
        reply,
        "generated",
        [b["id"] for b in beats],
    )
    return {"version": version, "seconds": total, "words": budget}


def script_reply(total: float, band: script.Band) -> str:
    """What was written, measured — never the plan restated as if it were the result."""
    secs = round(total)
    if band.n == 0:
        return f"This draft runs about {secs} seconds at your speaking speed."
    if band.low <= total <= band.high:
        return (
            f"This draft runs about {secs} seconds at your speaking speed — inside the "
            f"{band.low}–{band.high} seconds {band.basis} do best at."
        )
    side = "shorter" if total < band.low else "longer"
    ask = "expand" if side == "shorter" else "shorten"
    return (
        f"This draft runs about {secs} seconds at your speaking speed, {side} than the "
        f"{band.low}–{band.high} seconds {band.basis} do best at. Ask Curo to {ask} it if you like."
    )


def revise_script(
    project: dict,
    data: sc.StudioData,
    instruction: str,
    route: revisions.Route | None = None,
    source: str = "revision",
) -> dict[str, Any]:
    """A change to the script: T13 sorts the creator's words into an action, unless the action
    is already decided (a Simulator edit, ``source="simulator_edit"``)."""
    with service_connection() as conn:
        latest_script = current(conn, project["id"])[1]
    if latest_script is None:
        return write_script(project, data, instruction, regenerate=False)
    beats = latest_script["beats"]
    if route is None:
        routed = providers.get_llm().run(
            T13,
            T13Input(
                step="script",
                instruction=instruction,
                items=[f"{b['id']}: {b['text']}" for b in beats],
            ),
        )
        route = revisions.Route(routed.action, routed.targets, routed.params)
    route = revisions.resolve("script", route.action, route.targets, route.params, beats, None)
    if route.action == "regenerate":
        return write_script(project, data, instruction, regenerate=True)
    plan = latest_script["plan"] or {}
    band = plan.get("band") or {"low": 15, "high": 60, "seconds": 30}
    seconds_now = beats[-1]["end_s"]
    scale = 1.0
    if route.action == "shorten":
        wanted = float(route.params.get("seconds") or seconds_now * 0.65)
        scale = max(0.3, min(1.0, wanted / max(seconds_now, 1)))
    elif route.action == "expand":
        wanted = float(route.params.get("seconds") or min(band["high"], seconds_now * 1.3))
        scale = max(1.0, wanted / max(seconds_now, 1))
    words = {s["id"]: s["words"] for s in plan.get("structure", [])}
    out = providers.get_llm().run(
        T7,
        T7Input(
            idea=_need_idea(project)["text"],
            format=plan.get("format") or "talking_head",
            topic=data.topic,
            voice=data.voice,
            beats=[
                BeatPlan(
                    id=b["id"],
                    role=b["role"],
                    purpose=b.get("purpose") or b["role"],
                    words=max(1, round(words.get(b["id"], len(b["text"].split())) * scale)),
                    text=b["text"],
                )
                for b in beats
            ],
            examples=[e.text for e in _examples(data, plan.get("format") or "")],
            action=route.action,  # type: ignore[arg-type]
            rewrite=route.targets,
            direction=instruction,
            tone="conversational" if route.action == "change_tone" else "default",
            variant=latest_script["version"],
        ),
    )
    written = {b.id: b.text for b in out.beats}
    merged, changed = script.merge_revision(
        [{k: b[k] for k in ("id", "role", "purpose", "text") if k in b} for b in beats],
        written,
        set(route.targets),
    )
    new_beats = _with_notes(_timed(merged, data), data)
    reply = revisions.script_reply(route, new_beats, new_beats[-1]["end_s"], changed)
    version = _store_script(project, new_beats, plan, instruction, reply, source, changed)
    return {"version": version, "action": route.action, "changed": changed}


def put_own_script(project_id: UUID, text: str) -> None:
    """ "Dump your script idea here": the creator's words become the beats, as written."""
    parts = script.split_own(text)
    if not parts:
        raise StudioError("Write a few lines first.")
    with service_connection() as conn:
        project = project_row(conn, project_id)
        data = sc.load(conn, project["creator_id"], project["opportunity_id"])
    beats = [
        {"id": f"b{i}", "role": role, "purpose": "your line", "text": line}
        for i, (role, line) in enumerate(parts, start=1)
    ]
    beats = _with_notes(_timed(beats, data), data)
    plan = {
        "band": None,
        "word_budget": None,
        "words_per_second": data.voice.words_per_second,
        "format": None,
        "structure": [
            {
                "id": b["id"],
                "role": b["role"],
                "purpose": b["purpose"],
                "words": len(b["text"].split()),
            }
            for b in beats
        ],
    }
    _store_script(
        project,
        beats,
        plan,
        None,
        "Kept your script exactly as you wrote it and added the notes Curo can back.",
        "creator",
        [b["id"] for b in beats],
    )


# ====================================================================== step 3 · storyboard


def _devices(data: sc.StudioData, fmt: str | None) -> list[str]:
    return [d.line for d in storyboard.devices(data.cards)]


def _need_script(project: dict) -> dict:
    with service_connection() as conn:
        script_row = current(conn, project["id"])[1]
    if script_row is None:
        raise StudioError("Write or generate the script first.")
    return script_row


def _store_board(
    project: dict, script_version: int, frames: list[dict], instruction, reply: str
) -> dict:
    feas = storyboard.feasibility(frames)
    with service_connection() as conn:
        version = _next_version(conn, "storyboard_versions", project["id"])
        conn.execute(
            """
            insert into public.storyboard_versions
              (project_id, version, script_version, frames, feasibility, instruction, reply, created_at)
            values (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                project["id"],
                version,
                script_version,
                Jsonb(frames),
                Jsonb(feas),
                instruction,
                reply,
                clock.now(),
            ),
        )
        _touch(conn, project["id"], step="storyboard")
    return {"version": version, "feasibility": feas}


def _frame_beats(beats: list[dict]) -> list[FrameBeat]:
    return [
        FrameBeat(
            id=b["id"], role=b["role"], text=b["text"], seconds=round(b["end_s"] - b["start_s"], 1)
        )
        for b in beats
    ]


def _frame_outs(frames: list[dict]) -> list[FrameOut]:
    fields = FrameOut.model_fields
    return [FrameOut.model_validate({k: f[k] for k in fields if k in f}) for f in frames]


def build_storyboard(project: dict, data: sc.StudioData) -> dict[str, Any]:
    script_row = _need_script(project)
    beats = script_row["beats"]
    with service_connection() as conn:
        board = current(conn, project["id"])[2]
    stale_ids = set(storyboard.stale(board["frames"], beats)) if board else set()
    if board and board["script_version"] == script_row["version"] and not stale_ids:
        return {"version": board["version"], "unchanged": True}
    have = {f["beat_id"] for f in board["frames"]} if board else set()
    targets = (
        [b["id"] for b in beats if f"f-{b['id']}" in stale_ids or b["id"] not in have]
        if board
        else [b["id"] for b in beats]
    )
    kept = [f for f in (board["frames"] if board else []) if f["id"] not in stale_ids]
    out = providers.get_llm().run(
        T11,
        T11Input(
            format=(script_row["plan"] or {}).get("format") or "talking_head",
            beats=_frame_beats(beats),
            toolkit=data.toolkit,
            devices=_devices(data, (script_row["plan"] or {}).get("format")),
            action="build",
            frames=_frame_outs(kept),
            targets=targets,
        ),
    )
    frames = storyboard.assemble(beats, [f.model_dump() for f in out.frames])
    feas = storyboard.feasibility(frames)
    if board:
        reply = (
            f"Redrew {len(targets)} frame{'s' if len(targets) != 1 else ''} whose lines changed. "
            "The rest are as they were."
        )
    else:
        reply = (
            f"Each script line is now a shot you can film with your usual setup: {feas['detail']}."
        )
    return _store_board(project, script_row["version"], frames, None, reply)


def revise_storyboard(
    project: dict,
    data: sc.StudioData,
    instruction: str,
    frame: str | None,
    route: revisions.Route | None = None,
) -> dict[str, Any]:
    """A change to the storyboard: T13 sorts the request into an action, unless it is already
    decided (a Simulator edit)."""
    script_row = _need_script(project)
    with service_connection() as conn:
        board = current(conn, project["id"])[2]
    if board is None:
        return build_storyboard(project, data)
    frames = board["frames"]
    if route is None:
        routed = providers.get_llm().run(
            T13,
            T13Input(
                step="storyboard",
                instruction=instruction,
                items=[f"{f['beat_id']}: {f['shot_type']}" for f in frames],
                current=frame,
            ),
        )
        route = revisions.Route(routed.action, routed.targets, routed.params)
    route = revisions.resolve(
        "storyboard", route.action, route.targets, route.params, frames, frame
    )
    changed: list[str] = []
    beats = script_row["beats"]
    if route.action == "pacing":
        band = ((script_row["plan"] or {}).get("band")) or {"low": 15, "high": 60}
        faster = str(route.params.get("direction", "faster")) != "slower"
        new_frames = storyboard.repace(frames, faster, (band["low"], band["high"]))
        changed = [f["beat_id"] for f in frames]
    else:
        base = frames
        targets = route.targets
        if route.action == "easier":
            cam = data.toolkit.cameras[0] if data.toolkit.cameras else None
            base, targets = storyboard.make_easier(frames, cam)
        out = providers.get_llm().run(
            T11,
            T11Input(
                format=(script_row["plan"] or {}).get("format") or "talking_head",
                beats=_frame_beats(beats),
                toolkit=data.toolkit,
                devices=_devices(data, (script_row["plan"] or {}).get("format")),
                action=route.action,  # type: ignore[arg-type]
                frames=_frame_outs(base),
                targets=targets,
                direction=instruction,
                variant=board["version"],
            ),
        )
        drawn = {f.beat_id: f.model_dump() for f in out.frames}
        new_frames = []
        for f in base:
            if f["beat_id"] in targets and f["beat_id"] in drawn:
                g = {**f, **drawn[f["beat_id"]]}
                if route.action == "easier":  # what makes it easier is enforced, not suggested
                    g.update({k: f[k] for k in ("setting", "lighting", "camera", "needs_helper")})
                new_frames.append(g)
            else:
                new_frames.append(f)
        changed = [f["beat_id"] for f, old in zip(new_frames, frames, strict=True) if f != old]
    feas = storyboard.feasibility(new_frames)
    reply = revisions.storyboard_reply(route, new_frames, feas, changed)
    result = _store_board(project, script_row["version"], new_frames, instruction, reply)
    return {**result, "action": route.action, "changed": changed}


# ====================================================================== step 4 · captions and hashtags


def _scored_tags(
    data: sc.StudioData, beats: list[dict], idea: dict, extra: list[str] = ()
) -> list[cap.ScoredTag]:
    # Relevance is to this draft: its idea, topic, script and the phrases people search.
    phrases = cap.search_phrases(
        data.topic, data.keywords, data.festival["name"] if data.festival else None
    )
    vocabulary = {
        w
        for text in [idea["text"], data.topic or "", *(b["text"] for b in beats), *phrases]
        for w in sc.topics.words(text)
        if w not in sc.topics.GENERIC
    }
    evidence = dict(data.tag_evidence)
    for t in extra:
        t = t.lower().lstrip("#")
        if t and t not in evidence:
            evidence[t] = cap.TagEvidence(t, suggested=True)
    festival_tags = {
        k.replace(" ", "").lower() for k in (data.festival["keywords"] if data.festival else [])
    }
    series = data.series.get(_fmt(idea, data), set())  # their series for this kind of reel
    scored = cap.score_tags(
        list(evidence.values()), vocabulary, festival_tags, series, data.region_words
    )
    return [s for s in scored if s.relevance >= 0.3 or s.kind == "series"][:12]


def _caption_facts(
    beats: list[dict], idea: dict, data: sc.StudioData, phrases: list[str]
) -> list[str]:
    return [idea["text"], data.topic or "", *(b["text"] for b in beats), *phrases]


def _caption_input(
    beats: list[dict], idea: dict, data: sc.StudioData, tags: list[cap.ScoredTag], **kw
) -> T12Input:
    phrases = cap.search_phrases(
        data.topic, data.keywords, data.festival["name"] if data.festival else None
    )
    return T12Input(
        idea=idea["text"],
        topic=data.topic,
        hook=beats[0]["text"],
        beats=[b["text"] for b in beats],
        ending=beats[-1]["text"],
        search_phrases=phrases,
        style=data.caption_style,
        hashtags=[TagOption(tag=t.tag, kind=t.kind, score=t.score) for t in tags],  # type: ignore[arg-type]
        **kw,
    )


def _written_captions(data_in: T12Input, facts: list[str]):
    llm = providers.get_llm()
    out = None

    def write() -> str:
        nonlocal out
        out = llm.run(T12, data_in)
        return " ".join(c.text for c in out.captions)

    _text, source = validator.checked(write, facts, lambda: "")
    if source == "template" or out is None:
        hook = data_in.hook.split(".")[0]
        return (
            [
                {"text": f"{hook}. {data_in.ending}", "job": "comments"},
                {"text": f"{hook}.", "job": "likes"},
                {"text": f"{hook}. Send this to a friend.", "job": "shares"},
            ],
            [],
            source,
        )
    return [c.model_dump() for c in out.captions], list(out.hashtags), source


def write_captions(project: dict, data: sc.StudioData) -> dict[str, Any]:
    script_row = _need_script(project)
    idea = _need_idea(project)
    beats = script_row["beats"]
    tags = _scored_tags(data, beats, idea)
    data_in = _caption_input(beats, idea, data, tags)
    options, picked, source = _written_captions(
        data_in, _caption_facts(beats, idea, data, data_in.search_phrases)
    )
    tags = _scored_tags(data, beats, idea, extra=picked)
    suggested = cap.suggest(tags)
    options = [{**o, "why": cap.JOB_WHY[o["job"]]} for o in options]
    target = idea["target_behaviour"]
    chosen = next((i for i, o in enumerate(options) if o["job"] == target), 0)
    with service_connection() as conn:
        version = _next_version(conn, "captions", project["id"])
        conn.execute(
            """
            insert into public.captions
              (project_id, version, script_version, options, chosen, hashtags, candidates, reply,
               created_at)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                project["id"],
                version,
                script_row["version"],
                Jsonb(options),
                chosen,
                suggested,
                Jsonb([t.__dict__ for t in tags]),
                "Three captions, each doing a different job, and five hashtags picked for relevance.",
                clock.now(),
            ),
        )
        _touch(conn, project["id"], step="caption")
    return {"version": version, "source": source, "hashtags": suggested}


def revise_captions(
    project: dict, data: sc.StudioData, instruction: str | None, own: str | None
) -> dict[str, Any]:
    script_row = _need_script(project)
    idea = _need_idea(project)
    with service_connection() as conn:
        before = current(conn, project["id"])[3]
    if before is None:
        return write_captions(project, data)
    beats = script_row["beats"]
    action = "polish" if own and instruction else "rewrite"
    if instruction and not own:
        routed = providers.get_llm().run(T13, T13Input(step="caption", instruction=instruction))
        action = revisions.resolve("caption", routed.action, [], {}, [], None).action
        if action == "own":  # not a request: the creator's own caption, kept as written
            own, instruction, action = instruction, None, "rewrite"
    tags = [cap.ScoredTag(**t) for t in before["candidates"] or []]
    variant = {"rewrite": "default"}.get(action, action)
    data_in = _caption_input(
        beats,
        idea,
        data,
        tags,
        variant=variant if not own or action == "polish" else "default",
        own_caption=own,
        direction=instruction,
    )
    facts = _caption_facts(beats, idea, data, data_in.search_phrases) + ([own] if own else [])
    options, _picked, _source = _written_captions(data_in, facts)
    options = [{**o, "why": cap.JOB_WHY[o["job"]] if not own else "Your caption"} for o in options]
    reply = (
        "Kept your caption as you wrote it."
        if own and action != "polish"
        else revisions.CAPTION_REPLIES[action]
    )
    with service_connection() as conn:
        version = _next_version(conn, "captions", project["id"])
        conn.execute(
            """
            insert into public.captions
              (project_id, version, script_version, options, chosen, hashtags, candidates,
               instruction, reply, created_at)
            values (%s, %s, %s, %s, 0, %s, %s, %s, %s, %s)
            """,
            (
                project["id"],
                version,
                script_row["version"],
                Jsonb(options),
                before["hashtags"],
                Jsonb(before["candidates"]),
                instruction or own,
                reply,
                clock.now(),
            ),
        )
    return {"version": version, "action": action}


def put_hashtags(project_id: UUID, tags: list[str]) -> list[str]:
    clean = cap.normalise_tags(tags)  # raises HashtagLimit past five
    with service_connection() as conn:
        caps = current(conn, project_id)[3]
        if caps is None:
            raise StudioError("Generate captions first.")
        conn.execute("update public.captions set hashtags = %s where id = %s", (clean, caps["id"]))
        _touch(conn, project_id)
    return clean


def choose_caption(project_id: UUID, index: int) -> None:
    with service_connection() as conn:
        caps = current(conn, project_id)[3]
        if caps is None:
            raise StudioError("Generate captions first.")
        if not 0 <= index < len(caps["options"]):
            raise StudioError("That caption doesn't exist.")
        conn.execute("update public.captions set chosen = %s where id = %s", (index, caps["id"]))
        _touch(conn, project_id)


def save_project(project_id: UUID, step: str | None) -> None:
    if step is not None and step not in STEPS:
        raise StudioError("Unknown step.")
    with service_connection() as conn:
        project = project_row(conn, project_id)
        if selected_idea(conn, project_id) is None:
            raise StudioError("Pick an idea first, then save your draft.")
        conn.execute(
            """
            update public.projects set status = 'saved', saved_at = %s, updated_at = %s,
                   step = coalesce(%s, step)
             where id = %s
            """,
            (clock.now(), clock.now(), step, project_id),
        )
        _event(
            conn,
            project["creator_id"],
            "draft_saved",
            {"project_id": str(project_id), "step": step},
        )


# ====================================================================== persona reactions (v2.2)


def _idea_text(idea: dict) -> str:
    return " ".join(x for x in (idea["text"], idea["description"], idea["angle"]) if x)


VERSIONED = {
    "script": "script_versions",
    "storyboard": "storyboard_versions",
    "caption": "captions",
}


def persona_target(
    conn,
    project: dict,
    target_type: str | None = None,
    target_id: UUID | None = None,
    version: int | None = None,
):
    """What the personas react to: a named idea, else the project's current draft (the chosen
    caption, else the storyboard, else the script, else the chosen idea). None before an idea.
    ``version``: an earlier version of that draft (only its id is needed to read the cache)."""
    from curo.services.persona_reactions import Target

    pid = project["id"]
    if version is not None and target_type in VERSIONED:
        row = conn.execute(
            f"select id from public.{VERSIONED[target_type]} where project_id = %s and version = %s",
            (pid, version),
        ).fetchone()
        if row is None:
            return None
        return Target(target_type, row["id"], version, "", project_id=pid)
    if target_type == "idea" and target_id:
        idea = conn.execute(
            "select * from public.ideas where id = %s and project_id = %s", (target_id, pid)
        ).fetchone()
        if idea is None:
            return None
        return Target("idea", idea["id"], 1, _idea_text(idea), None, idea["format"], project_id=pid)
    idea, s, b, c = current(conn, pid)
    if idea is None:
        return None
    base = _idea_text(idea)
    fmt = idea["format"]
    if c and (target_type in (None, "caption")):
        opts = c["options"] or []
        chosen = opts[c["chosen"]] if c["chosen"] is not None and c["chosen"] < len(opts) else None
        text = (chosen or (opts[0] if opts else {})).get("text", "")
        tags = " ".join(f"#{t}" for t in c["hashtags"] or [])
        return Target(
            "caption", c["id"], c["version"], base, f"{text} {tags}".strip(), fmt, project_id=pid
        )
    if b and (target_type in (None, "storyboard")):
        frames = " / ".join(
            " ".join(
                x for x in (f.get("shot_type"), f.get("instruction"), f.get("onscreen_text")) if x
            )
            for f in b["frames"] or []
        )
        return Target("storyboard", b["id"], b["version"], base, frames, fmt, project_id=pid)
    if s and (target_type in (None, "script")):
        script_text = " ".join(beat["text"] for beat in s["beats"] or [])
        return Target("script", s["id"], s["version"], base, script_text, fmt, project_id=pid)
    return Target("idea", idea["id"], 1, base, None, fmt, project_id=pid)
