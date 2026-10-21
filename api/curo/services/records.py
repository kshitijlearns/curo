"""Reading Reel Records from the database for the learning jobs and the screens. The same
queries work for the worker (service role) and inside a creator's RLS session."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from curo import clock
from curo.services.metrics import ReelSeries, Snap


def load_series(conn, account_ids: list[UUID]) -> dict[UUID, list[ReelSeries]]:
    """Every reel of the accounts with its snapshots (hidden counts stay None)."""
    now = clock.now()
    reels = conn.execute(
        """
        select id, account_id, posted_at, is_paid_partnership, is_deleted
          from public.reels where account_id = any(%s)
         order by posted_at, shortcode
        """,
        (account_ids,),
    ).fetchall()
    snaps = conn.execute(
        """
        select m.reel_id, m.age_hours, m.views, m.likes, m.comments, m.shares
          from public.metric_snapshots m join public.reels r on r.id = m.reel_id
         where r.account_id = any(%s)
        """,
        (account_ids,),
    ).fetchall()
    by_reel: dict[UUID, list[Snap]] = {}
    for s in snaps:
        by_reel.setdefault(s["reel_id"], []).append(
            Snap(float(s["age_hours"]), s["views"], s["likes"], s["comments"], s["shares"])
        )
    out: dict[UUID, list[ReelSeries]] = {a: [] for a in account_ids}
    for r in reels:
        out[r["account_id"]].append(
            ReelSeries(
                reel_id=str(r["id"]),
                posted_at=r["posted_at"],
                age_now_h=(now - r["posted_at"]).total_seconds() / 3600,
                snaps=sorted(by_reel.get(r["id"], []), key=lambda s: s.age_h),
                paid=r["is_paid_partnership"],
                deleted=r["is_deleted"],
            )
        )
    return out


def load_dna(conn, account_ids: list[UUID]) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        """
        select d.reel_id, d.content, d.production, d.transcript, r.duration_s, r.caption
          from public.reel_dna d join public.reels r on r.id = d.reel_id
         where r.account_id = any(%s)
        """,
        (account_ids,),
    ).fetchall()
    return {str(r["reel_id"]): r for r in rows}


def load_vectors(conn, account_id: UUID) -> dict[str, list[float]]:
    rows = conn.execute(
        """
        select e.reel_id, e.embedding::text as v
          from public.reel_embeddings e join public.reels r on r.id = e.reel_id
         where r.account_id = %s and not r.is_deleted
        """,
        (account_id,),
    ).fetchall()
    return {str(r["reel_id"]): json.loads(r["v"]) for r in rows}
