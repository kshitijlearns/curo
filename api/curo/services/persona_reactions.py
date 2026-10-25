"""Persona reactions (v2.2 §6.3–§6.4): each Follower Persona's own take on an idea, a draft or a
Simulator result, cached per (persona, target, version).

One T27 call covers all four personas. Each persona's score is checked by code: the shown score
is ``PERSONA_MODEL_WEIGHT`` × the model's score + the rest × the code fit
(services/personas.code_fit), and both are stored. The reaction shown comes from that blended
score, so the avatars, the reaction words and A in the idea score always agree. Every opinion
passes the no-new-numbers check and the sensitive-attribute check; a failure is regenerated once,
then replaced by the template.

Re-opening a popover reads the cache; only a new target version calls the model.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from curo import providers, usage
from curo.config import get_settings
from curo.db import service_connection
from curo.schemas.tasks import T27, EvidenceRef, PersonaBrief, PersonaReaction, T27Input
from curo.services import persona_safety, persona_text
from curo.services import personas as P

log = logging.getLogger("curo.personas")


@dataclass
class Target:
    type: str  # idea | script | storyboard | caption | simulation
    id: UUID
    version: int
    idea: str
    draft: str | None = None
    format: str | None = None
    vector: list[float] | None = None
    project_id: UUID | None = None


# ------------------------------------------------------------------ persona views


def _vec(v) -> list[float] | None:
    if v is None:
        return None
    return json.loads(v) if isinstance(v, str) else list(v)


def evidence_refs(row: dict) -> list[EvidenceRef]:
    """Evidence chips a reaction may cite, from the persona's code facts."""
    ev = (row["profile"] or {}).get("evidence") or {}
    out = []
    for i, x in enumerate(ev.get("loves") or []):
        out.append(EvidenceRef(id=f"love:{i}", text=x["evidence"]))
    for i, x in enumerate(ev.get("turn_offs") or []):
        out.append(EvidenceRef(id=f"off:{i}", text=x["evidence"]))
    for f in ev.get("facts") or []:
        if f.startswith("Reels they comment on also get"):
            out.append(EvidenceRef(id=f"lift:{len(out)}", text=f))
    if not out:
        for i, f in enumerate((ev.get("facts") or [])[:2]):
            out.append(EvidenceRef(id=f"fact:{i}", text=f))
    return out[:8]


def brief(row: dict) -> PersonaBrief:
    prof = row["profile"] or {}
    return PersonaBrief(
        key=str(row["id"]),
        name=row["name"],
        voice=prof.get("voice", ""),
        facts=((prof.get("evidence") or {}).get("facts") or [])[:14],
        comes_for=prof.get("comes_for", []),
        loves=prof.get("loves", []),
        wants_more=prof.get("wants_more", []),
        turn_offs=prof.get("turn_offs", []),
        typical_comment=prof.get("typical_comment", ""),
        evidence=evidence_refs(row),
    )


def fit(row: dict) -> P.PersonaFit:
    prof = row["profile"] or {}
    ev = prof.get("evidence") or {}
    asks = " ".join([*prof.get("wants_more", []), *(t["label"] for t in ev.get("themes") or [])])
    return P.PersonaFit(
        id=str(row["id"]),
        name=row["name"],
        short_name=row["short_name"],
        share=float(row["share"]),
        vector=_vec(row.get("centroid")),
        topic_vector=_vec(row.get("topic_vector")),
        ask_words=P.words_of(asks),
        love_formats={x["value"] for x in ev.get("loves") or [] if x["kind"] == "format"},
        off_formats={x["value"] for x in ev.get("turn_offs") or [] if x["kind"] == "format"},
        loves=prof.get("loves", []),
        wants_more=prof.get("wants_more", []),
        turn_offs=prof.get("turn_offs", []),
        is_starter=row["is_starter"],
    )


def active_rows(conn, creator_id: UUID) -> list[dict]:
    return conn.execute(
        """
        select id, slot, name, short_name, share, color, avatar_seed, is_starter, confidence,
               profile, centroid::text as centroid, topic_vector::text as topic_vector
          from public.follower_personas
         where creator_id = %s and retired_at is null order by slot
        """,
        (creator_id,),
    ).fetchall()


# ------------------------------------------------------------------ running T27


def _facts(b: PersonaBrief, target: Target) -> list[str]:
    return [*b.facts, *(e.text for e in b.evidence), target.idea, target.draft or ""]


def _model_reactions(target: Target, briefs: list[PersonaBrief]) -> dict[str, PersonaReaction]:
    """T27 for these personas, one retry; only reactions that pass both checks are kept."""
    llm = providers.get_llm()
    done: dict[str, PersonaReaction] = {}
    by_key = {b.key: b for b in briefs}
    for _attempt in range(2):
        todo = [b for b in briefs if b.key not in done]
        if not todo:
            break
        try:
            out = llm.run(
                T27,
                T27Input(
                    target_type=target.type,  # type: ignore[arg-type]
                    idea=target.idea,
                    draft=(target.draft or None) and target.draft[:4000],
                    format=target.format,
                    personas=todo,
                ),
            ).reactions
        except Exception:
            log.warning("T27 failed", exc_info=True)
            continue
        for r in out:
            b = by_key.get(r.key)
            if b is None or r.key in done:
                continue
            if persona_safety.safe([r.opinion, r.win_them_over], numbers_from=_facts(b, target)):
                valid = {e.id for e in b.evidence}
                done[r.key] = r.model_copy(
                    update={"evidence_ids": [e for e in r.evidence_ids if e in valid]}
                )
    return done


def cached(conn, persona_ids: list[str], target: Target) -> dict[str, dict]:
    rows = conn.execute(
        """
        select * from public.persona_opinions
         where persona_id = any(%s::uuid[]) and target_type = %s and target_id = %s
           and target_version = %s
        """,
        (persona_ids, target.type, target.id, target.version),
    ).fetchall()
    return {str(r["persona_id"]): r for r in rows}


def react(creator_id: UUID, rows: list[dict], target: Target, feature: str) -> list[dict]:
    """Each persona's opinion of the target (cached, else T27 + checks + the code blend)."""
    ids = [str(r["id"]) for r in rows]
    with service_connection() as conn:
        have = cached(conn, ids, target)
    missing = [r for r in rows if str(r["id"]) not in have]
    if missing:
        with usage.feature(feature):
            _run(creator_id, missing, target)
        with service_connection() as conn:
            have = cached(conn, ids, target)
    return [have[i] for i in ids if i in have]


def _run(creator_id: UUID, rows: list[dict], target: Target) -> None:
    llm = providers.get_llm()
    weight = get_settings().persona_model_weight
    briefs = [brief(r) for r in rows]
    model = _model_reactions(target, briefs)
    if target.vector is None:
        text = f"{target.idea} {target.draft or ''}".strip()
        target.vector = providers.get_embedding().embed([text[:2000] or "reel"])[0]
    with service_connection() as conn:
        for r, b in zip(rows, briefs, strict=True):
            m = model.get(b.key)
            source = "model"
            if m is None:
                m = persona_text.reaction_template(b, target.idea, target.draft, target.type)
                source = "template"
            code, parts = P.code_fit(target.vector, f"{target.idea} {target.draft or ''}",
                                     target.format, fit(r))  # fmt: skip
            score = P.blend(float(m.score), 100 * code, weight)
            reaction = P.reaction_for(score)
            log.info(
                "persona score %s %s: model=%s code=%.1f blend=%.1f (%s)",
                r["short_name"], target.type, m.score, 100 * code, score, parts,
            )  # fmt: skip
            conn.execute(
                """
                insert into public.persona_opinions
                  (creator_id, persona_id, project_id, target_type, target_id, target_version,
                   reaction, score_model, score_code, score, would, opinion, win_them_over,
                   evidence_ids, model_version)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (persona_id, target_type, target_id, target_version) do nothing
                """,
                (
                    creator_id,
                    r["id"],
                    target.project_id,
                    target.type,
                    target.id,
                    target.version,
                    reaction,
                    float(m.score) if source == "model" else None,
                    round(100 * code, 2),
                    score,
                    Jsonb(m.would.model_dump()),
                    m.opinion,
                    m.win_them_over or None,
                    m.evidence_ids,
                    llm.version(T27) if source == "model" else f"template:{llm.version(T27)}",
                ),
            )


# ------------------------------------------------------------------ what the app reads


def out(opinions: list[dict], rows: list[dict]) -> dict[str, Any]:
    """The reactions in share order, the summary line and A (0–1) for the target."""
    by_id = {str(o["persona_id"]): o for o in opinions}
    items = []
    for r in rows:
        o = by_id.get(str(r["id"]))
        if o is None:
            continue
        refs = {e.id: e.text for e in evidence_refs(r)}
        mood = P.REACTION_MOOD[o["reaction"]]
        items.append(
            {
                "persona_id": str(r["id"]),
                "name": r["name"],
                "short_name": r["short_name"],
                "color": r["color"],
                "avatar_seed": r["avatar_seed"],
                "share": float(r["share"]),
                "is_starter": r["is_starter"],
                "reaction": o["reaction"],
                "reaction_label": P.REACTION_WORDS[o["reaction"]],
                "mood": mood,
                "badge": P.BADGE[mood],
                "score": round(float(o["score"])),
                "score_model": None if o["score_model"] is None else float(o["score_model"]),
                "score_code": float(o["score_code"]),
                "would": o["would"],
                "opinion": o["opinion"],
                "win_them_over": o["win_them_over"],
                "evidence": [refs[e] for e in o["evidence_ids"] if e in refs],
            }
        )
    # A from the exact blended scores (the items show them rounded).
    scores = {i["persona_id"]: float(by_id[i["persona_id"]]["score"]) / 100 for i in items}
    fits = [fit(r) for r in rows]
    return {
        "reactions": items,
        "summary": P.summary([(i["name"], i["reaction"], i["share"]) for i in items]),
        "audience": round(P.audience_part(scores, fits), 4) if items else None,
        "label": P.LABEL,
    }


def blended_scores(opinions: list[dict]) -> dict[str, float]:
    """persona id → its blended score on 0–1 (A's inputs)."""
    return {str(o["persona_id"]): float(o["score"]) / 100 for o in opinions}
