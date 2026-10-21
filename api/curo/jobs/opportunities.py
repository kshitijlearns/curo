"""build_opportunities (MVP doc §9; logic doc §8): nightly per creator — find, merge, filter,
score and explain the opportunity areas, keeping what the creator saved or dismissed.

v2 (PLAN_V2 §4.1): no peers. Candidates come from festivals, CURO's hashtag index, the shared
trend feed, the creator's audience and their own content."""

from __future__ import annotations

import json
import statistics
from collections import Counter
from typing import Any
from uuid import UUID

import numpy as np
from psycopg.types.json import Jsonb

from curo import clock, providers
from curo.db import service_connection
from curo.jobs import JobContext, JobFailed, job
from curo.jobs.hashtags import creator_niche, tags_for_creator, upcoming_festivals
from curo.schemas.tasks import T5, T5Input
from curo.services import opportunities as opp
from curo.services import phases, topics, validator
from curo.services.arrows import baseline_n
from curo.services.metrics import compute_baselines, reel_lifts
from curo.services.records import load_series
from curo.services.text import reel_title

FESTIVAL_MIN_DAYS, FESTIVAL_MAX_DAYS = 7, 30
THEME_MIN_SHARE = 0.03
FOLLOWUP_LIFT = 1.5
SUBCLUSTER_LIFT = 1.3
COMMON_DF = 0.10  # a word or tag on more than this share of reels doesn't define a topic


# --------------------------------------------------------------------------- loading


def subclusters_with_captions(conn, account_id) -> list[dict]:
    """The creator's sub-clusters, each with a caption-level vector (topics are compared on
    captions) and how close its own reels' captions typically sit to it."""
    embedder = providers.get_embedding()
    groups = conn.execute(
        "select id, label, centroid::text as c, reel_ids, lifts from public.subclusters where account_id = %s order by label",
        (account_id,),
    ).fetchall()
    captions = {
        str(r["id"]): f"{reel_title(r['caption'])} {' '.join(r['hashtags'])}"
        for r in conn.execute(
            "select id, caption, hashtags from public.reels where account_id = %s", (account_id,)
        ).fetchall()
    }
    out = []
    for g in groups:
        members = [captions[str(r)] for r in g["reel_ids"] if str(r) in captions]
        if not members:
            continue
        vectors = np.asarray(embedder.embed(members), dtype=float)
        center = vectors.mean(axis=0)
        center /= max(float(np.linalg.norm(center)), 1e-12)
        sims = [float(v @ center) for v in vectors]
        out.append(
            {
                "id": str(g["id"]),
                "label": g["label"],
                "centroid": json.loads(g["c"]),
                "caption_vector": center.tolist(),
                "lifts": g["lifts"] or {},
                "reel_ids": [str(r) for r in g["reel_ids"]],
                "typical_sim": statistics.median(sims),
            }
        )
    return out


def _doc_freq(texts: list[tuple[str, list[str]]]) -> Counter[str]:
    df: Counter[str] = Counter()
    for caption, tags in texts:
        df.update(set(topics.words(caption)) | {t.lower() for t in tags})
    return df


def _phrase(label: str) -> str:
    verb, _, rest = label.partition(" ")
    return (
        {"asks": "ask", "wants": "want"}.get(verb.lower(), verb.lower())
        + (f" {rest}" if rest else "")
    ).strip()


# --------------------------------------------------------------------------- candidates


def trend_candidates(cards: list[dict]) -> list[opp.Candidate]:
    """The niche's trend cards (rising hashtags and formats; festivals have their own source)."""
    out = []
    for c in cards:
        if (c["evidence"] or {}).get("kind") == "festival" or not c["hashtags"]:
            continue
        tags = {t.lower() for t in c["hashtags"]}
        out.append(
            opp.Candidate(
                key=f"trend:{c['key']}",
                source="trend",
                keywords=set(tags),
                anchors=set(tags),
                texts=[c["name"], c["summary"], *c["example_angles"]],
                hashtags=tags,
                trend=_trend_ref(c),
            )
        )
    return out


def _trend_ref(c: dict) -> dict:
    return {
        "key": c["key"],
        "name": c["name"],
        "summary": c["summary"],
        "why_rising": c["why_rising"],
        "saturation": c["saturation"],
        "momentum": float(c["momentum"]) if c["momentum"] is not None else None,
    }


def festival_candidates(festivals: list[dict], today) -> list[opp.Candidate]:
    out = []
    for f in festivals:
        days = (f["starts_on"] - today).days
        if not FESTIVAL_MIN_DAYS <= days <= FESTIVAL_MAX_DAYS:
            continue
        kws = [k.lower() for k in f["keywords"]]
        out.append(
            opp.Candidate(
                key=f"festival:{f['id']}",
                source="trend",
                keywords=set(kws),
                anchors=set(kws) | topics.keyword_tags(kws),
                texts=[f["name"] + " " + " ".join(kws)],
                hashtags=topics.keyword_tags(kws),
                festival=dict(f),
            )
        )
    return out


def hashtag_candidates(growth: dict[str, float], watched: set[str]) -> list[opp.Candidate]:
    """A topic's posting grew 1.5× or more over the last 7 days (CURO's own index)."""
    return [
        opp.Candidate(
            key=f"tag:{t}", source="trend", keywords={t}, anchors={t}, texts=[f"#{t}"], hashtags={t}
        )
        for t, g in growth.items()
        if g >= 1.5 and t in watched
    ]


def theme_candidates(
    themes: list[dict], comments_by_theme: dict[str, list[dict]]
) -> list[opp.Candidate]:
    """A request or question theme in 3% or more of comments across the last 30 reels."""
    out = []
    for t in themes:
        if t["share"] < THEME_MIN_SHARE:
            continue
        comments = comments_by_theme.get(t["key"], [])
        out.append(
            opp.Candidate(
                key=f"theme:{t['key']}",
                source="audience",
                keywords=topics.distinctive([c["text"] for c in comments], min_count=3),
                texts=[t["label"]] + [c["text"] for c in comments[:20]],
                themes=[{**t, "phrase": _phrase(t["label"])}],
            )
        )
    return out


def content_candidates(
    series, rows: dict, baselines, subclusters: list[dict], comments: list[dict], followers, now
) -> list[opp.Candidate]:
    """A sub-cluster with a lift of 1.3+ not posted in 30 days, or an outlier reel that
    invites a follow-up (still growing, or asked for a part 2)."""
    out = []
    part_two = Counter(c["reel_id"] for c in comments if c["theme_key"] == "wants a part 2")
    for s in series:
        r = rows.get(s.reel_id)
        if r is None or s.paid or s.age_now_h > 14 * 24:
            continue
        lift = reel_lifts(s, baselines).get("views")
        if not lift or lift.lift < FOLLOWUP_LIFT or baseline_n(baselines, "views", lift.age_h) < 3:
            continue
        tl = phases.timeline(s.snaps, followers, from_posting=True)
        growing = bool(tl) and tl[-1][2] == "growing"
        velocity_growth = (
            round(tl[-1][1] / tl[-2][1], 2) if growing and len(tl) >= 2 and tl[-2][1] > 0 else None
        )
        asks = part_two.get(s.reel_id, 0)
        if not (growing or asks >= 3):
            continue
        title = reel_title(r["caption"])
        out.append(
            opp.Candidate(
                key=f"followup:{r['shortcode']}",
                source="your_content",
                keywords=set(),
                texts=[r["caption"]],
                followup={
                    "reel_id": s.reel_id,
                    "title": title,
                    "lift": round(lift.lift, 2),
                    "part_two": asks,
                    "growing": growing,
                    "velocity_growth": velocity_growth,
                },
            )
        )
    last_posted = {s.reel_id: s.posted_at for s in series}
    for g in subclusters:
        views = (g["lifts"].get("views") or {}).get("lift")
        newest = max((last_posted[r] for r in g["reel_ids"] if r in last_posted), default=None)
        if views and views >= SUBCLUSTER_LIFT and newest and (now - newest).days > 30:
            out.append(
                opp.Candidate(
                    key=f"subcluster:{g['id']}",
                    source="your_content",
                    keywords=set(),
                    texts=[g["label"]],
                    subcluster={"id": g["id"], "label": g["label"], "lift": views},
                )
            )
    return out


# --------------------------------------------------------------------------- naming


def explain(s: opp.Scored, kws: list[str]) -> tuple[str, str, str]:
    c = s.candidate
    lead = [f for k in opp.top_parts(s) for f in s.parts[k].facts[:1]] or [
        "It came up in your data."
    ]
    data = T5Input(
        sources=sorted(c.sources),
        keywords=kws[:12],
        hashtags=sorted(c.hashtags)[:8],
        festival=c.festival["name"] if c.festival else None,
        themes=[t["label"].lower() for t in c.themes],
        follow_up_of=c.followup["title"] if c.followup else None,
        subcluster=c.subcluster["label"] if c.subcluster else None,
        example_titles=[],
        lead_facts=lead,
        fit_facts=s.parts["F"].facts,
    )
    llm = providers.get_llm()
    # Numbers may come from the facts or from the input itself ("wants a part 2").
    facts = [
        *lead,
        *s.parts["F"].facts,
        *data.themes,
        *data.example_titles,
        *data.keywords,
        *data.hashtags,
        data.festival or "",
        data.follow_up_of or "",
    ]
    out = None

    def write() -> str:
        nonlocal out
        out = llm.run(T5, data)
        return f"{out.name} {out.description} {out.why_it_fits}"

    _text, source = validator.checked(write, facts, lambda: "")
    if source == "template" or out is None:
        name = (
            data.festival or (data.themes[0] if data.themes else " ".join(kws[:2]))
        ).capitalize()
        return name, " ".join(lead[:2]), (s.parts["F"].facts or lead)[0]
    return out.name, out.description, out.why_it_fits


def trending(cards: list[dict], n: int = 3) -> list[dict]:
    """ "What's trending in your niche" on the detail page: the niche's strongest trend cards."""
    ranked = sorted(cards, key=lambda c: (-(float(c["momentum"] or 0)), c["name"]))
    return [
        {
            "name": c["name"],
            "why_rising": c["why_rising"],
            "saturation": c["saturation"],
        }
        for c in ranked[:n]
    ]


# --------------------------------------------------------------------------- the job


@job("build_opportunities")
def build_opportunities(ctx: JobContext) -> dict[str, Any]:
    creator_id = UUID(str(ctx.payload["creator_id"]))
    now = clock.now()
    today = now.date()
    with service_connection() as conn:
        creator = conn.execute(
            """
            select c.id, c.account_id, a.followers from public.creators c
              join public.accounts a on a.id = c.account_id where c.id = %s
            """,
            (creator_id,),
        ).fetchone()
        if creator is None:
            raise JobFailed("No collected account for this creator yet.")
        account_id = creator["account_id"]
        series = load_series(conn, [account_id])[account_id]
        rows = {
            str(r["id"]): r
            for r in conn.execute(
                "select * from public.reels where account_id = %s order by posted_at, shortcode",
                (account_id,),
            ).fetchall()
        }
        subclusters = subclusters_with_captions(conn, account_id)
        formats = Counter(
            r["f"]
            for r in conn.execute(
                """
                select d.production->>'format' as f from public.reel_dna d join public.reels r on r.id = d.reel_id
                 where r.account_id = %s and d.production->>'format' <> 'unknown'
                """,
                (account_id,),
            ).fetchall()
        )
        comments = [
            {**c, "reel_id": str(c["reel_id"])}
            for c in conn.execute(
                """
                with recent as (select id from public.reels where account_id = %s and not is_deleted
                                 order by posted_at desc limit 30)
                select c.text, c.intent, c.theme_key, c.reel_id from public.comments c
                 where c.reel_id in (select id from recent) and c.labelled_at is not null
                   and not coalesce(c.is_bot, false) and not c.is_creator
                 order by c.posted_at, c.ig_comment_id
                """,
                (account_id,),
            ).fetchall()
        ]
        themes = [
            dict(t)
            for t in conn.execute(
                "select key, label, kind, share, n from public.comment_themes where account_id = %s order by key",
                (account_id,),
            ).fetchall()
        ]
        pages = conn.execute(
            "select tag, daily_counts, reel_count_7d from public.hashtag_pages"
        ).fetchall()
        niche = creator_niche(conn, account_id)
        cards = [
            dict(c)
            for c in conn.execute(
                "select * from public.trend_cards where niche = %s order by key", (niche,)
            ).fetchall()
        ]
        festivals = upcoming_festivals(conn, niche, today, FESTIVAL_MAX_DAYS)
        blocked = {
            str(r["value"]).lower()
            for r in conn.execute(
                "select value from public.creator_memory where creator_id = %s and key = 'blocked_topic'",
                (creator_id,),
            ).fetchall()
        }
        watched = tags_for_creator(conn, creator_id, account_id)

    comments_by_theme: dict[str, list[dict]] = {}
    for c in comments:
        if c["theme_key"]:
            comments_by_theme.setdefault(c["theme_key"], []).append(c)
    growth = {
        p["tag"]: g
        for p in pages
        if (g := topics.growth(p["daily_counts"] or {}, today)) is not None
    }
    baselines = compute_baselines(series)
    df = _doc_freq([(r["caption"], r["hashtags"]) for r in rows.values()])
    n_docs = len(rows)

    specific_growth = {t: g for t, g in growth.items() if df[t] / max(n_docs, 1) <= COMMON_DF}
    candidates = (
        trend_candidates(cards)
        + festival_candidates(festivals, today)
        + hashtag_candidates(specific_growth, watched)
        + theme_candidates(themes, comments_by_theme)
        + content_candidates(
            series, rows, baselines, subclusters, comments, creator["followers"], now
        )
    )
    merged = opp.merge(candidates, comments_by_theme)
    creator_recent = [
        r for r in rows.values() if not r["is_deleted"] and (now - r["posted_at"]).days < 14
    ]
    kept = [
        c
        for c in merged
        if not opp.posted_recently(c, creator_recent)
        and not opp.unsafe(c, blocked)
        and not (c.festival and c.festival["ends_on"] < today)
    ]
    context = opp.Context(
        today=today,
        subclusters=subclusters,
        creator_formats=dict(formats),
        comments=comments,
        comment_regions=dict(topics.regions_in(c["text"] for c in comments)),
        hashtag_growth=growth,
        hashtag_reels_7d={
            p["tag"]: p["reel_count_7d"] for p in pages if p["reel_count_7d"] is not None
        },
    )
    named = name_all(kept, context)
    saved = persist(creator_id, named, now, trending(cards))
    return {
        "candidates": len(candidates),
        "merged": len(merged),
        "kept": len(kept),
        "top": [(name, s.score) for name, s in saved[: opp.TOP]],
    }


def _kws(c: opp.Candidate) -> list[str]:
    festival = [k for k in c.festival.get("keywords", [])] if c.festival else []
    return festival + sorted((c.anchors or c.keywords) - set(festival))


def name_all(
    cands: list[opp.Candidate], context: opp.Context
) -> list[tuple[opp.Scored, tuple[str, str, str]]]:
    """Score and name every topic. Two topics given the same name mean the same thing to a
    creator (say, price questions and budget requests): they're merged and scored again."""
    embedder = providers.get_embedding()
    for _ in range(3):
        vectors = (
            embedder.embed([" ".join([*c.texts[:20], *sorted(c.keywords)]) for c in cands])
            if cands
            else []
        )
        scored = [opp.score(c, v, context) for c, v in zip(cands, vectors, strict=True)]
        named = [(s, explain(s, _kws(s.candidate))) for s in scored]
        by_name: dict[str, opp.Candidate] = {}
        merged = False
        for s, (name, _d, _w) in sorted(named, key=lambda x: -x[0].score):
            key = name.strip().lower()
            if key in by_name:
                by_name[key].absorb(s.candidate)
                merged = True
            else:
                by_name[key] = s.candidate
        if not merged:
            return sorted(named, key=lambda x: -x[0].score)
        cands = list(by_name.values())
    return sorted(named, key=lambda x: -x[0].score)


def persist(
    creator_id: UUID,
    named: list[tuple[opp.Scored, tuple[str, str, str]]],
    now,
    niche_trends: list[dict],
) -> list[tuple[str, opp.Scored]]:
    with service_connection() as conn:
        existing = {
            r["topic_key"]: r
            for r in conn.execute(
                "select id, topic_key, status from public.opportunities where creator_id = %s",
                (creator_id,),
            ).fetchall()
        }
    out = []
    rank = 0
    keep_keys = set()
    for s, (name, description, why) in named:
        c = s.candidate
        status = existing.get(c.key, {}).get("status", "active")
        if status != "dismissed":
            rank += 1
        evidence = {
            "sources": sorted(c.sources),
            "keywords": sorted(c.anchors or c.keywords)[:20],
            "hashtags": sorted(c.hashtags)[:10],
            "trending": niche_trends,
            "trend": c.trend,
            "festival": (
                {
                    "id": c.festival["id"],
                    "name": c.festival["name"],
                    "starts_on": c.festival["starts_on"].isoformat(),
                }
                if c.festival
                else None
            ),
            "themes": [
                {"key": t["key"], "label": t["label"], "share": t["share"]} for t in c.themes
            ],
            "followup": c.followup,
            "subcluster": c.subcluster,
        }
        parts = {
            k: {
                "value": p.value,
                "weight": opp.WEIGHTS[k],
                "name": opp.PART_NAMES[k],
                "facts": p.facts,
            }
            for k, p in s.parts.items()
        }
        with service_connection() as conn:
            conn.execute(
                """
                insert into public.opportunities
                  (creator_id, topic_key, name, tag, score, parts, evidence, description, why_it_fits,
                   card, signals, status, window_ends_on, rank, built_at)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'active', %s, %s, %s)
                on conflict (creator_id, topic_key) do update set
                  name = excluded.name, tag = excluded.tag, score = excluded.score,
                  parts = excluded.parts, evidence = excluded.evidence,
                  description = excluded.description, why_it_fits = excluded.why_it_fits,
                  card = excluded.card, signals = excluded.signals,
                  window_ends_on = excluded.window_ends_on, rank = excluded.rank,
                  built_at = excluded.built_at,
                  status = case when public.opportunities.status = 'expired' then 'active'
                                else public.opportunities.status end
                """,
                (
                    creator_id,
                    c.key,
                    name,
                    c.tag,
                    min(10.0, s.score),
                    Jsonb(parts),
                    Jsonb(evidence),
                    description,
                    Jsonb(opp.fit_rows(s, why)),
                    opp.card_text(s, name),
                    opp.signals(s),
                    c.festival["ends_on"] if c.festival else None,
                    rank if status != "dismissed" else None,
                    now,
                ),
            )
        keep_keys.add(c.key)
        out.append((name, s))
    with service_connection() as conn:
        # Topics that no longer qualify: active ones go; saved ones stay (with their window).
        conn.execute(
            """
            delete from public.opportunities
             where creator_id = %s and status = 'active' and not (topic_key = any(%s))
            """,
            (creator_id, list(keep_keys)),
        )
        conn.execute(
            """
            update public.opportunities set status = 'expired'
             where creator_id = %s and status = 'active' and window_ends_on < %s
            """,
            (creator_id, now.date()),
        )
    return out
