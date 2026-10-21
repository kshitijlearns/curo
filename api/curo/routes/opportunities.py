"""Opportunity areas (logic doc §8) and Saved (§14): GET /v1/opportunities,
GET /v1/opportunities/{id}, POST · DELETE /v1/opportunities/{id}/save,
POST /v1/opportunities/{id}/dismiss, GET /v1/saved."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status

from curo import clock, events
from curo.routes.deps import require_creator, rls_conn
from curo.schemas.api import (
    OpportunityCard,
    OpportunityDetail,
    OpportunityPart,
    SavedDraft,
    SavedOpportunity,
    SavedOut,
    TrendCard,
    TrendNote,
)
from curo.services.opportunities import TAG_LABELS, TOP

router = APIRouter(prefix="/v1", tags=["opportunities"])


def _card(o: dict[str, Any]) -> OpportunityCard:
    return OpportunityCard(
        id=o["id"],
        name=o["name"],
        tag=TAG_LABELS[o["tag"]],
        score=float(o["score"]),
        score_shown=round(float(o["score"])),
        card=o["card"] or o["name"],
        saved=o["status"] == "saved",
        topic_key=o["topic_key"],
    )


def _detail(o: dict[str, Any]) -> OpportunityDetail:
    parts = o["parts"] or {}
    total = sum(p["weight"] * p["value"] for p in parts.values()) or 1.0
    ev = o["evidence"] or {}
    return OpportunityDetail(
        **_card(o).model_dump(),
        description=o["description"] or "",
        signals=list(o["signals"] or []),
        parts=[
            OpportunityPart(
                key=k,
                name=p["name"],
                weight=p["weight"],
                value=p["value"],
                share=round(p["weight"] * p["value"] / total, 3),
                facts=p["facts"],
            )
            for k, p in parts.items()
        ],
        trending=[TrendNote(**t) for t in ev.get("trending", [])],
        fit=o["why_it_fits"] or [],
        window_ends_on=o["window_ends_on"],
        saved_score=float(o["saved_score"]) if o["saved_score"] is not None else None,
    )


def _get(conn: psycopg.Connection, opportunity_id: UUID) -> dict[str, Any]:
    row = conn.execute(
        "select * from public.opportunities where id = %s", (opportunity_id,)
    ).fetchone()  # RLS: only the creator's own
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Opportunity not found")
    return row


def _event(conn: psycopg.Connection, creator_id, name: str, props: dict) -> None:
    events.record(conn, creator_id, name, props)


@router.get("/opportunities", response_model=list[OpportunityCard])
def list_opportunities(conn: psycopg.Connection = Depends(rls_conn)) -> list[OpportunityCard]:
    """The top 5 by score (the "5 for you" pill)."""
    require_creator(conn)
    rows = conn.execute(
        """
        select * from public.opportunities
         where status in ('active', 'saved') and rank is not null
         order by rank limit %s
        """,
        (TOP,),
    ).fetchall()
    return [_card(o) for o in rows]


@router.get("/opportunities/{opportunity_id}", response_model=OpportunityDetail)
def get_opportunity(
    opportunity_id: UUID, conn: psycopg.Connection = Depends(rls_conn)
) -> OpportunityDetail:
    require_creator(conn)
    return _detail(_get(conn, opportunity_id))


@router.post("/opportunities/{opportunity_id}/save", response_model=OpportunityCard)
def save(opportunity_id: UUID, conn: psycopg.Connection = Depends(rls_conn)) -> OpportunityCard:
    """Bookmark it: keeps today's score beside the score it had when saved (logic doc §14)."""
    creator = require_creator(conn)
    o = _get(conn, opportunity_id)
    if o["status"] != "saved":
        o = conn.execute(
            """
            update public.opportunities set status = 'saved', saved_score = score, saved_at = %s
             where id = %s returning *
            """,
            (clock.now(), opportunity_id),
        ).fetchone()
        _event(conn, creator["id"], "opportunity_saved", {"opportunity_id": str(opportunity_id)})
    return _card(o)


@router.delete("/opportunities/{opportunity_id}/save", response_model=OpportunityCard)
def unsave(opportunity_id: UUID, conn: psycopg.Connection = Depends(rls_conn)) -> OpportunityCard:
    creator = require_creator(conn)
    _get(conn, opportunity_id)
    o = conn.execute(
        """
        update public.opportunities
           set status = case when window_ends_on < %s then 'expired' else 'active' end,
               saved_score = null, saved_at = null
         where id = %s and status = 'saved' returning *
        """,
        (clock.now().date(), opportunity_id),
    ).fetchone() or _get(conn, opportunity_id)
    _event(conn, creator["id"], "opportunity_unsaved", {"opportunity_id": str(opportunity_id)})
    return _card(o)


@router.post("/opportunities/{opportunity_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
def dismiss(opportunity_id: UUID, conn: psycopg.Connection = Depends(rls_conn)) -> None:
    """Hide it and record the signal (it stays hidden on later rebuilds)."""
    creator = require_creator(conn)
    o = _get(conn, opportunity_id)
    conn.execute(
        "update public.opportunities set status = 'dismissed', rank = null where id = %s",
        (opportunity_id,),
    )
    _event(
        conn,
        creator["id"],
        "opportunity_dismissed",
        {
            "opportunity_id": str(opportunity_id),
            "topic_key": o["topic_key"],
            "score": float(o["score"]),
        },
    )


@router.get("/saved", response_model=SavedOut)
def saved(conn: psycopg.Connection = Depends(rls_conn)) -> SavedOut:
    """Saved opportunities with the score when saved and today's, marked "window passed"
    once a dated event is over; and saved Studio drafts, newest first."""
    require_creator(conn)
    today = clock.now().date()
    rows = conn.execute(
        "select * from public.opportunities where status = 'saved' order by saved_at desc"
    ).fetchall()
    drafts = conn.execute(
        """
        select p.id, p.title, p.step, p.saved_at, o.name as opportunity,
               (select s.frames->0->>'icon_key' from public.storyboard_versions s
                 where s.project_id = p.id order by s.version desc limit 1) as icon_key
          from public.projects p left join public.opportunities o on o.id = p.opportunity_id
         where p.status = 'saved' order by p.saved_at desc
        """
    ).fetchall()
    return SavedOut(
        drafts=[
            SavedDraft(
                id=d["id"],
                title=d["title"] or "Untitled draft",
                opportunity=d["opportunity"],
                step=d["step"],
                saved_at=d["saved_at"],
                icon_key=d["icon_key"] or "closeup",
            )
            for d in drafts
        ],
        opportunities=[
            SavedOpportunity(
                id=o["id"],
                name=o["name"],
                tag=TAG_LABELS[o["tag"]],
                score_today=float(o["score"]),
                score_when_saved=float(o["saved_score"]) if o["saved_score"] is not None else None,
                window_passed=bool(o["window_ends_on"] and o["window_ends_on"] < today),
                saved_at=o["saved_at"],
            )
            for o in rows
        ],
    )


@router.get("/trends", response_model=list[TrendCard])
def trending_for_you(conn: psycopg.Connection = Depends(rls_conn)) -> list[TrendCard]:
    """Trending for you: the niche's shared trend cards, ranked by fit with the creator's own
    content and momentum (PLAN_V2 §4.4)."""
    from curo import providers
    from curo.jobs.hashtags import creator_niche
    from curo.jobs.opportunities import subclusters_with_captions
    from curo.services import trends

    creator = require_creator(conn)
    if not creator["account_id"]:
        return []
    niche = creator_niche(conn, creator["account_id"])
    cards = [
        dict(c)
        for c in conn.execute(
            "select * from public.trend_cards where niche = %s order by key", (niche,)
        ).fetchall()
    ]
    if not cards:
        return []
    vectors = providers.get_embedding().embed(
        [f"{c['name']} {c['summary']} {' '.join(c['hashtags'])}" for c in cards]
    )
    groups = subclusters_with_captions(conn, creator["account_id"])
    return [
        TrendCard(
            id=r.card["id"],
            name=r.card["name"],
            summary=r.card["summary"],
            why_rising=r.card["why_rising"],
            why_it_fits=r.why,
            example_angles=r.card["example_angles"],
            window_start=r.card["window_start"],
            window_end=r.card["window_end"],
            momentum=float(r.card["momentum"]) if r.card["momentum"] is not None else None,
            saturation=r.card["saturation"],
            hashtags=r.card["hashtags"],
            fit=r.fit,
        )
        for r in trends.rank_for_creator(cards, vectors, groups)
    ]
