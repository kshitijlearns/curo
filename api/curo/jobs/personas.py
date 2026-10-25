"""build_personas (v2.2 §3): the creator's 4 Follower Personas, rebuilt as comments arrive.

Steps (each safe to repeat: embeddings are cached per comment, the store is one transaction):
collect usable comments → embed (cached in ``comment_embeddings``) → cluster into exactly 4
(services/personas.py) → profile each group in code → T25 writes the personas → match last
build's personas (same id, name, colour and seed at cosine ≥ 0.8) → T26 writes what each thinks
of the creator → store ``follower_personas``, ``persona_history`` and ``persona_builds``.

Every persona text passes the no-new-numbers check and the sensitive-attribute check (keyword
list + T29); a failure is regenerated once, then replaced by a template from the facts.

When: inside the first recap (a fast build on what's read so far, refined once comments are
labelled), before each monthly recap, and mid-month after 150+ new comments (scheduler).
Thin data gives 4 "early guess" starter personas. Cost is recorded under feature "personas";
personas are free on every plan.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from psycopg.types.json import Jsonb

from curo import clock, providers, usage
from curo.config import get_settings
from curo.db import service_connection
from curo.jobs import JobContext, JobFailed, job
from curo.jobs.hashtags import creator_niche
from curo.jobs.understand import vector_literal
from curo.queue import enqueue
from curo.schemas.tasks import (
    T25,
    T26,
    PersonaGroupIn,
    PersonaThought,
    T25Input,
    T26Input,
    ThoughtIn,
    WrittenPersona,
)
from curo.services import persona_avatar, persona_safety, persona_text
from curo.services import personas as P
from curo.services.comments import language_of
from curo.services.text import reel_title

log = logging.getLogger("curo.personas")
EMBED_BATCH = 100
THOUGHT_MOODS = {"neutral", "love", "like", "unsure", "skip"}


# ------------------------------------------------------------------ loading


def _creator(conn, creator_id: UUID) -> dict:
    c = conn.execute(
        """
        select c.id, c.account_id, c.timezone, c.ig_username, a.username
          from public.creators c left join public.accounts a on a.id = c.account_id
         where c.id = %s
        """,
        (creator_id,),
    ).fetchone()
    if c is None or c["account_id"] is None:
        raise JobFailed("This creator has no Instagram account collected yet.")
    return c


def load_reels(conn, account_id: UUID) -> dict[str, P.PReel]:
    groups = {}
    for g in conn.execute(
        "select label, reel_ids from public.subclusters where account_id = %s order by label",
        (account_id,),
    ).fetchall():
        for rid in g["reel_ids"] or []:
            groups.setdefault(str(rid), g["label"])
    rows = conn.execute(
        """
        select r.id, r.caption, r.posted_at, d.content->>'context' as context,
               d.production->>'format' as format, s.views, s.likes, s.comments, s.shares
          from public.reels r
          left join public.reel_dna d on d.reel_id = r.id
          left join lateral (
            select views, likes, comments, shares from public.metric_snapshots m
             where m.reel_id = r.id and not m.flagged order by m.taken_at desc limit 1
          ) s on true
         where r.account_id = %s and not r.is_deleted
        """,
        (account_id,),
    ).fetchall()
    return {
        str(r["id"]): P.PReel(
            id=str(r["id"]),
            title=reel_title(r["caption"] or ""),
            posted=r["posted_at"],
            format=r["format"] if r["format"] not in (None, "unknown") else None,
            context=r["context"],
            group=groups.get(str(r["id"])),
            views=r["views"],
            likes=r["likes"],
            comments=r["comments"],
            shares=r["shares"],
        )
        for r in rows
    }


def load_comments(conn, account_id: UUID, limit: int | None = None) -> list[P.PComment]:
    """Usable comments: not the creator's own, not bots; newest reels first (a fast build
    reads only the newest ``limit``)."""
    rows = conn.execute(
        f"""
        select c.id, c.reel_id, c.text, c.intent, c.sentiment, c.language, c.tags_friend,
               c.posted_at, t.label as theme
          from public.comments c
          join public.reels r on r.id = c.reel_id
          left join public.comment_themes t on t.id = c.theme_id
         where r.account_id = %s and not r.is_deleted and not c.is_creator
           and not coalesce(c.is_bot, false) and length(trim(c.text)) > 0
         order by r.posted_at desc, c.ig_comment_id
         {"limit %s" if limit else ""}
        """,
        (account_id, limit) if limit else (account_id,),
    ).fetchall()
    return [
        P.PComment(
            id=str(r["id"]),
            reel_id=str(r["reel_id"]),
            text=r["text"],
            intent=r["intent"],
            sentiment=r["sentiment"],
            language=r["language"] or language_of(r["text"]),
            theme=r["theme"],
            tags_friend=bool(r["tags_friend"]),
            posted=r["posted_at"],
        )
        for r in rows
    ]


def comments_seen(conn, account_id: UUID) -> int:
    return conn.execute(
        """
        select count(*) as n from public.comments c join public.reels r on r.id = c.reel_id
         where r.account_id = %s and not c.is_creator
        """,
        (account_id,),
    ).fetchone()["n"]


def _embed_text(c: P.PComment) -> str:
    return " · ".join(x for x in (c.text, c.theme, c.intent, c.language) if x)


def embed(comments: list[P.PComment]) -> None:
    """Fill each comment's vector from the cache, embedding (and caching) the missing ones."""
    emb = providers.get_embedding()
    ids = [c.id for c in comments]
    with service_connection() as conn:
        cached = {
            str(r["comment_id"]): json.loads(r["v"])
            for r in conn.execute(
                """
                select comment_id, embedding::text as v from public.comment_embeddings
                 where comment_id = any(%s::uuid[]) and model = %s
                """,
                (ids, emb.model),
            ).fetchall()
        }
    missing = [c for c in comments if c.id not in cached]
    for i in range(0, len(missing), EMBED_BATCH):
        batch = missing[i : i + EMBED_BATCH]
        texts = [_embed_text(c) for c in batch]
        vectors = emb.embed(texts)
        usage.record(emb.name, emb.model, "embedding", sum(usage.tokens(t) for t in texts))
        with service_connection() as conn, conn.cursor() as cur:
            cur.executemany(
                """
                insert into public.comment_embeddings (comment_id, embedding, model)
                values (%s, %s::vector, %s)
                on conflict (comment_id) do update set embedding = excluded.embedding,
                  model = excluded.model, created_at = now()
                """,
                [(c.id, vector_literal(v), emb.model) for c, v in zip(batch, vectors, strict=True)],
            )
        for c, v in zip(batch, vectors, strict=True):
            cached[c.id] = v
    for c in comments:
        c.vector = cached[c.id]


def niche_priors(conn, niche: str | None) -> dict[str, float] | None:
    """The intent mix of comments across CURO creators in the niche (starter personas)."""
    if not niche:
        return None
    rows = conn.execute(
        """
        select c.intent, count(*) as n
          from public.comments c
          join public.reels r on r.id = c.reel_id
          join public.reel_dna d on d.reel_id = r.id
         where c.intent is not null and not c.is_creator and not coalesce(c.is_bot, false)
           and d.content->>'cluster' = any(%s)
         group by c.intent
        """,
        ([k for k, v in P_NICHES.items() if v == niche],),
    ).fetchall()
    total = sum(r["n"] for r in rows)
    if total < 100:
        return None
    return {r["intent"]: r["n"] / total for r in rows}


def _niche_map() -> dict[str, str]:
    from curo.services.topics import NICHE_OF_CLUSTER

    return NICHE_OF_CLUSTER


P_NICHES = _niche_map()


def active(conn, creator_id: UUID) -> list[dict]:
    """The creator's current 4 personas, by slot."""
    return conn.execute(
        """
        select * from public.follower_personas
         where creator_id = %s and retired_at is null order by slot
        """,
        (creator_id,),
    ).fetchall()


def latest_build(conn, creator_id: UUID) -> dict | None:
    return conn.execute(
        """
        select * from public.persona_builds where creator_id = %s
         order by version desc limit 1
        """,
        (creator_id,),
    ).fetchone()


# ------------------------------------------------------------------ writing (T25, T26)


def _persona_texts(w: WrittenPersona) -> list[str]:
    return [
        w.name,
        w.short_name,
        w.tagline,
        *w.comes_for,
        *w.loves,
        *w.wants_more,
        *w.turn_offs,
        w.engagement_style,
        w.voice,
        w.typical_comment,
    ]


def _ok(texts: list[str], facts: list[str]) -> bool:
    return persona_safety.safe(texts, numbers_from=facts)


def write_personas(
    groups: list[PersonaGroupIn], niche: str | None, language: str | None
) -> tuple[list[WrittenPersona], list[str]]:
    """T25 for all four (one call, one retry); a persona that fails the checks twice gets the
    template. Names are made distinct and kept names are kept."""
    llm = providers.get_llm()
    payload = T25Input(niche=niche or "lifestyle", main_language=language, groups=groups)
    done: dict[str, WrittenPersona] = {}
    source: dict[str, str] = {}
    for attempt in ("model", "model_retry"):
        if len(done) == len(groups):
            break
        try:
            out = {p.key: p for p in llm.run(T25, payload).personas}
        except Exception:
            log.warning("T25 failed", exc_info=True)
            out = {}
        for g in groups:
            w = out.get(g.key)
            if g.key in done or w is None:
                continue
            if _ok(_persona_texts(w), g.facts):
                done[g.key], source[g.key] = w, attempt
    names = persona_text.pick_names([g.data for g in groups])
    hinglish = language == "hinglish"
    for g, n in zip(groups, names, strict=True):
        if g.key not in done:
            done[g.key], source[g.key] = (
                persona_text.write_template(g, n, niche, hinglish),
                "template",
            )
    result = []
    used: set[str] = set()
    pool = [*persona_text.SPARE, *(n for v in persona_text.INTENT_NAMES.values() for n in v)]
    for g in groups:
        w = done[g.key]
        if g.keep_name and g.keep_short_name:
            w = w.model_copy(update={"name": g.keep_name, "short_name": g.keep_short_name})
        if w.name.lower() in used:  # names must be distinct
            alt = next(n for n in pool if n[0].lower() not in used)
            w = w.model_copy(update={"name": alt[0], "short_name": alt[1]})
        used.add(w.name.lower())
        result.append(w)
    return result, [source[g.key] for g in groups]


def write_thoughts(handle: str, items: list[ThoughtIn]) -> tuple[list[PersonaThought], list[str]]:
    llm = providers.get_llm()
    done: dict[str, PersonaThought] = {}
    source: dict[str, str] = {}
    by_key = {t.key: t for t in items}
    for attempt in ("model", "model_retry"):
        if len(done) == len(items):
            break
        try:
            out = llm.run(T26, T26Input(handle=handle, personas=items)).thoughts
        except Exception:
            log.warning("T26 failed", exc_info=True)
            out = []
        for t in out:
            if t.key not in by_key or t.key in done:
                continue
            if _ok([t.thought, *t.loves, *t.wants_more], by_key[t.key].facts):
                if t.mood not in THOUGHT_MOODS:
                    t = t.model_copy(update={"mood": by_key[t.key].mood_hint})
                done[t.key], source[t.key] = t, attempt
    for t in items:
        if t.key not in done:
            done[t.key], source[t.key] = persona_text.thought_template(t), "template"
    return [done[t.key] for t in items], [source[t.key] for t in items]


# ------------------------------------------------------------------ the build


def _group_in(p: P.Profile, keep: dict | None) -> PersonaGroupIn:
    data = p.evidence()
    data["comes_for_hint"] = p.comes_for_hint
    data.pop("favourite_reels", None)
    data["favourite_reels"] = [r["title"] for r in p.favourite_reels]
    return PersonaGroupIn(
        key=f"g{p.slot}",
        facts=p.facts or [f"{p.share_pct}% of your comments come from this group."],
        data=data,
        samples=p.samples,
        keep_name=keep["name"] if keep else None,
        keep_short_name=keep["short_name"] if keep else None,
    )


def _main_language(comments: list[P.PComment]) -> str | None:
    langs = [c.language for c in comments if c.language]
    return max(sorted(set(langs)), key=langs.count) if langs else None


def build_now(creator_id: UUID, reason: str, fast: bool = False) -> dict[str, Any]:
    """Build (or rebuild) the creator's personas now. Returns a summary."""
    with usage.feature("personas"):
        return _build(creator_id, reason, fast)


def _build(creator_id: UUID, reason: str, fast: bool) -> dict[str, Any]:
    with service_connection() as conn:
        c = _creator(conn, creator_id)
        tz = ZoneInfo(c["timezone"] or "Asia/Kolkata")
        account_id = c["account_id"]
        seen = comments_seen(conn, account_id)
        reels = load_reels(conn, account_id)
        comments = load_comments(conn, account_id, P.FAST_MAX_COMMENTS if fast else None)
        niche = creator_niche(conn, account_id)
        previous = active(conn, creator_id)
    now = clock.now()
    today = now.astimezone(tz).date()
    handle = c["username"] or c["ig_username"] or "you"
    truncated = fast and seen > len(comments)
    with_comments = len({x.reel_id for x in comments})
    language = _main_language(comments)
    if P.is_thin(len(comments), with_comments):
        result = _store_starter(
            creator_id, c, comments, reels, niche, today, previous, reason, seen
        )
    else:
        embed(comments)
        prior = [
            json.loads(_vec_text(p["centroid"]))
            for p in previous
            if not p["is_starter"] and p["centroid"] is not None
        ]
        built = P.build(
            comments, reels, now, seeds=P.FAST_SEEDS if fast else P.SEEDS, previous=prior or None
        )
        result = _store_built(
            creator_id, handle, built, comments, reels, niche, language, today, previous,
            reason, fast, seen,
        )  # fmt: skip
    if truncated:
        enqueue(
            "build_personas",
            {"creator_id": str(creator_id), "reason": "refine"},
            creator_id=creator_id,
            idempotency_key=f"personas:{creator_id}:refine:{result['version']}",
        )
    return result


def _next_version(conn, creator_id: UUID) -> int:
    # One build per creator at a time: the lock is held until this transaction ends.
    conn.execute("select pg_advisory_xact_lock(hashtext(%s))", (f"personas:{creator_id}",))
    row = conn.execute(
        "select coalesce(max(version), 0) + 1 as v from public.persona_builds where creator_id = %s",
        (creator_id,),
    ).fetchone()
    return row["v"]


def _period(comments: list[P.PComment], today: date) -> tuple[date, date]:
    days = [x.posted.date() for x in comments if x.posted]
    return (min(days) if days else today - timedelta(days=P.RECENT_DAYS - 1)), today


def _topic_vectors(texts: list[str]) -> list[list[float]]:
    return providers.get_embedding().embed(texts)


def _store_built(
    creator_id: UUID,
    handle: str,
    built: P.Built,
    comments: list[P.PComment],
    reels: dict[str, P.PReel],
    niche: str | None,
    language: str | None,
    today: date,
    previous: list[dict],
    reason: str,
    fast: bool,
    seen: int,
) -> dict[str, Any]:
    prev_real = [p for p in previous if not p["is_starter"] and p["centroid"] is not None]
    prev_vectors = [json.loads(_vec_text(p["centroid"])) for p in prev_real]
    matched = P.match(prev_vectors, built.centroids)  # new index → previous index
    keeps = {i: prev_real[j] for i, j in matched.items()}
    # A matched persona keeps its name only once its name was given on labelled comments: the
    # first (fast) build often runs before labelling, so its names are provisional. Id, colour
    # and seed are always kept.
    with service_connection() as conn:
        last = latest_build(conn, creator_id)
    settled = bool(last) and last["n_labelled"] >= 0.5 * max(1, last["n_comments"])
    groups = [_group_in(p, keeps.get(i) if settled else None) for i, p in enumerate(built.profiles)]
    written, w_sources = write_personas(groups, niche, language)
    thoughts_in = [
        ThoughtIn(
            key=g.key,
            name=w.name,
            voice=w.voice,
            language=language,
            facts=g.facts,
            mood_hint=p.mood,  # type: ignore[arg-type]
            loves=w.loves[:4],
            wants_more=w.wants_more[:3],
            top_reels=[r["title"] for r in p.favourite_reels][:4],
        )
        for g, w, p in zip(groups, written, built.profiles, strict=True)
    ]
    thoughts, t_sources = write_thoughts(handle, thoughts_in)
    colours = P.colours({i: keeps[i]["color"] for i in keeps})
    topic = _topic_vectors(
        [
            " ".join([*(r["title"] for r in p.favourite_reels), *w.comes_for, *w.loves])
            for p, w in zip(built.profiles, written, strict=True)
        ]
    )
    period = _period(comments, today)
    rows = []
    for i, (p, w, t) in enumerate(zip(built.profiles, written, thoughts, strict=True)):
        rows.append(
            {
                "keep": keeps.get(i),
                "slot": p.slot,
                "name": w.name,
                "short_name": w.short_name,
                "tagline": w.tagline,
                "share": max(0.0001, round(p.share, 4)),
                "color": colours[i],
                "confidence": p.confidence,
                "profile": _profile_json(w, p, w_sources[i]),
                "thought": {**t.model_dump(), "source": t_sources[i]},
                "centroid": built.centroids[i],
                "topic_vector": topic[i],
                "is_starter": False,
                "n_comments": p.n_comments,
                "n_reels": p.n_reels,
                "mood": t.mood,
                "sentiment": p.sentiment,
            }
        )
    return _store(
        creator_id, rows, previous, period, reason, fast, False, comments, seen, built.stability
    )


def _vec_text(v) -> str:
    return v if isinstance(v, str) else str(v)


def _profile_json(w: WrittenPersona, p: P.Profile, source: str) -> dict:
    ev = p.evidence()
    loves_ev = [i["evidence"] for i in ev["loves"]]
    offs_ev = [i["evidence"] for i in ev["turn_offs"]]
    return {
        "comes_for": w.comes_for,
        "loves": w.loves,
        "loves_evidence": [loves_ev[i] if i < len(loves_ev) else None for i in range(len(w.loves))],
        "wants_more": w.wants_more,
        "turn_offs": w.turn_offs,
        "turn_offs_evidence": [
            offs_ev[i] if i < len(offs_ev) else None for i in range(len(w.turn_offs))
        ],
        "engagement_style": w.engagement_style,
        "language": ev["languages"],
        "voice": w.voice,
        "typical_comment": w.typical_comment,
        "evidence": ev,
        "source": source,
    }


def _store_starter(
    creator_id: UUID,
    c: dict,
    comments: list[P.PComment],
    reels: dict[str, P.PReel],
    niche: str | None,
    today: date,
    previous: list[dict],
    reason: str,
    seen: int,
) -> dict[str, Any]:
    from collections import Counter

    langs = Counter(x.language for x in comments if x.language)
    total = sum(langs.values())
    mix = [(k, n / total) for k, n in langs.most_common(3)] if total else [("en", 1.0)]
    topics = [g for g, _ in Counter(r.group for r in reels.values() if r.group).most_common(2)]
    with service_connection() as conn:
        priors = niche_priors(conn, niche)
    starters = P.starter(niche, topics, mix, priors)
    language = mix[0][0] if mix else None
    facts_of = {
        s["slot"]: [
            f"{s['share_pct']}% of your comments, by an early guess from creators in your niche.",
            P.EARLY_GUESS + ".",
        ]
        for s in starters
    }
    thoughts, sources = write_thoughts(
        c["username"] or c["ig_username"] or "you",
        [
            ThoughtIn(
                key=f"g{s['slot']}",
                name=s["name"],
                voice=s["voice"],
                language=language,
                facts=facts_of[s["slot"]],
                mood_hint="neutral",
                loves=s["loves"],
                wants_more=s["wants_more"],
            )
            for s in starters
        ],
    )
    # A starter persona keeps its identity across starter rebuilds by name.
    by_name = {p["name"]: p for p in previous if p["is_starter"]}
    rows = []
    for s, t, src in zip(starters, thoughts, sources, strict=True):
        ev = {
            "share": round(s["share"], 4),
            "share_pct": s["share_pct"],
            "n_comments": 0,
            "n_reels": 0,
            "intents": [{"intent": s["intent"], "share": None}],
            "languages": [
                {"language": lang, "name": P.language_name(lang), "share": round(v, 3)}
                for lang, v in mix
            ],
            "meter": 3,
            "meter_word": P.MOOD_WORDS[3],
            "mood": "neutral",
            "starter": True,
            "facts": facts_of[s["slot"]],
            "loves": [],
            "turn_offs": [],
            "favourite_reels": [],
            "lifts": {},
        }
        rows.append(
            {
                "keep": by_name.get(s["name"]),
                "slot": s["slot"],
                "name": s["name"],
                "short_name": s["short_name"],
                "tagline": s["tagline"],
                "share": round(s["share"], 4),
                "color": None,
                "confidence": "low",
                "profile": {
                    "comes_for": s["comes_for"],
                    "loves": s["loves"],
                    "loves_evidence": [None] * len(s["loves"]),
                    "wants_more": s["wants_more"],
                    "turn_offs": s["turn_offs"],
                    "turn_offs_evidence": [None] * len(s["turn_offs"]),
                    "engagement_style": s["engagement_style"],
                    "language": ev["languages"],
                    "voice": s["voice"],
                    "typical_comment": s["typical_comment"],
                    "evidence": ev,
                    "source": "starter",
                },
                "thought": {**t.model_dump(), "source": src},
                "centroid": None,
                "topic_vector": None,
                "is_starter": True,
                "n_comments": 0,
                "n_reels": 0,
                "mood": t.mood,
                "sentiment": None,
            }
        )
    kept = {i: r["keep"]["color"] for i, r in enumerate(rows) if r["keep"]}
    for r, colour in zip(rows, P.colours(kept), strict=True):
        r["color"] = colour
    period = _period(comments, today)
    return _store(creator_id, rows, previous, period, reason, False, True, comments, seen, None)


def _store(
    creator_id: UUID,
    rows: list[dict],
    previous: list[dict],
    period: tuple[date, date],
    reason: str,
    fast: bool,
    starter: bool,
    comments: list[P.PComment],
    seen: int,
    stability: float | None,
) -> dict[str, Any]:
    now = clock.now()
    n_comments, n_reels = len(comments), len({x.reel_id for x in comments})
    n_labelled = sum(1 for x in comments if x.intent)
    month = period[1].replace(day=1)
    kept_ids = {str(r["keep"]["id"]) for r in rows if r["keep"]}
    with service_connection() as conn:
        version = _next_version(conn, creator_id)
        retired = [p for p in previous if str(p["id"]) not in kept_ids]
        for p in retired:
            conn.execute(
                "update public.follower_personas set retired_at = %s where id = %s", (now, p["id"])
            )
        ids = []
        for r in rows:
            vec = vector_literal(r["centroid"]) if r["centroid"] else None
            topic = vector_literal(r["topic_vector"]) if r["topic_vector"] else None
            values = (
                r["slot"],
                r["name"],
                r["short_name"],
                r["tagline"],
                r["share"],
                r["color"],
                r["confidence"],
                Jsonb(r["profile"]),
                Jsonb(r["thought"]),
                vec,
                topic,
                version,
                period[0],
                period[1],
                r["is_starter"],
                r["n_comments"],
                r["n_reels"],
                now,
            )
            if r["keep"]:
                conn.execute(
                    """
                    update public.follower_personas set slot = %s, name = %s, short_name = %s,
                           tagline = %s, share = %s, color = %s, confidence = %s, profile = %s,
                           thought = %s, centroid = %s::vector, topic_vector = %s::vector,
                           version = %s, period_start = %s, period_end = %s, is_starter = %s,
                           n_comments = %s, n_reels = %s, updated_at = %s
                     where id = %s
                    """,
                    (*values, r["keep"]["id"]),
                )
                pid = r["keep"]["id"]
                seed = r["keep"]["avatar_seed"]
            else:
                seed = persona_avatar.seed_for(creator_id, r["slot"], f"v{version}:{r['name']}")
                pid = conn.execute(
                    """
                    insert into public.follower_personas
                      (slot, name, short_name, tagline, share, color, confidence, profile,
                       thought, centroid, topic_vector, version, period_start, period_end,
                       is_starter, n_comments, n_reels, updated_at, creator_id, avatar_seed)
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector, %s::vector, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s)
                    returning id
                    """,
                    (*values, creator_id, seed),
                ).fetchone()["id"]
            ids.append(str(pid))
            conn.execute(
                """
                insert into public.persona_history
                  (persona_id, creator_id, period, share, mood, sentiment, n_comments, version)
                values (%s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (persona_id, period) do update set share = excluded.share,
                  mood = excluded.mood, sentiment = excluded.sentiment,
                  n_comments = excluded.n_comments, version = excluded.version
                """,
                (
                    pid,
                    creator_id,
                    month,
                    r["share"],
                    r["mood"],
                    r["sentiment"],
                    r["n_comments"],
                    version,
                ),
            )
        conn.execute(
            """
            insert into public.persona_builds
              (creator_id, version, reason, fast, is_starter, n_comments, n_reels, n_labelled,
               comments_seen, stability)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                creator_id,
                version,
                reason,
                fast,
                starter,
                n_comments,
                n_reels,
                n_labelled,
                seen,
                stability,
            ),
        )
    return {
        "version": version,
        "personas": ids,
        "names": [r["name"] for r in rows],
        "shares": [r["share"] for r in rows],
        "kept": len(kept_ids),
        "retired": len(retired),
        "starter": starter,
        "fast": fast,
        "comments": n_comments,
    }


# ------------------------------------------------------------------ when to build


def needs_build(conn, creator_id: UUID) -> str | None:
    """Why the creator's personas should be rebuilt now, or None."""
    c = conn.execute(
        "select account_id from public.creators where id = %s", (creator_id,)
    ).fetchone()
    if not c or not c["account_id"]:
        return None
    last = latest_build(conn, creator_id)
    if last is None:
        return "initial"
    seen = comments_seen(conn, c["account_id"])
    usable = conn.execute(
        """
        select count(*) as n, count(distinct c.reel_id) as reels,
               count(*) filter (where c.intent is not null) as labelled
          from public.comments c join public.reels r on r.id = c.reel_id
         where r.account_id = %s and not c.is_creator and not coalesce(c.is_bot, false)
        """,
        (c["account_id"],),
    ).fetchone()
    if last["fast"] and usable["n"] > last["n_comments"]:
        return "refine"
    # Built before the comments were labelled (the onboarding build), and now they are.
    if last["n_labelled"] < 0.5 * last["n_comments"] and usable["labelled"] >= 0.8 * usable["n"]:
        return "refine"
    if last["is_starter"] and not P.is_thin(usable["n"], usable["reels"]):
        return "refine"
    if seen - last["comments_seen"] >= get_settings().persona_refresh_comments:
        return "midmonth"
    return None


def queue_if_needed(creator_id: UUID, key: str) -> str | None:
    with service_connection() as conn:
        reason = needs_build(conn, creator_id)
    if reason:
        enqueue(
            "build_personas",
            {"creator_id": str(creator_id), "reason": reason},
            creator_id=creator_id,
            idempotency_key=f"personas:{creator_id}:{reason}:{key}",
        )
    return reason


def queue_for_account(account_id: UUID, key: str) -> None:
    """After labels or learning change for an account: rebuild its creator's personas if due."""
    with service_connection() as conn:
        creators = conn.execute(
            "select id from public.creators where account_id = %s", (account_id,)
        ).fetchall()
    for c in creators:
        queue_if_needed(c["id"], key)


def ensure_for_recap(creator_id: UUID, kind: str) -> None:
    """Before a recap: the first recap gets a fast build; a monthly one, this month's build."""
    try:
        if kind == "first":
            build_now(creator_id, "onboarding", fast=True)
            return
        with service_connection() as conn:
            last = latest_build(conn, creator_id)
            tz = conn.execute(
                "select timezone from public.creators where id = %s", (creator_id,)
            ).fetchone()
        zone = ZoneInfo((tz or {}).get("timezone") or "Asia/Kolkata")
        month_start = datetime.combine(clock.now().astimezone(zone).date().replace(day=1),
                                       datetime.min.time(), zone)  # fmt: skip
        if last is None or last["created_at"] < month_start:
            build_now(creator_id, "monthly")
    except JobFailed:
        raise
    except Exception:  # a recap never fails because personas couldn't be built
        log.exception("persona build before the recap failed")


def tick(now: datetime) -> list[str]:
    """Daily: rebuild for active creators whose personas are due (mid-month 150+ comments, a
    fast or starter build that can now be refined)."""
    out: list[str] = []
    with service_connection() as conn:
        rows = conn.execute(
            """
            select c.id from public.creators c
             where c.account_id is not null and c.paused_at is null
            """
        ).fetchall()
    for r in rows:
        reason = queue_if_needed(r["id"], f"{now:%Y%m%d}")
        if reason:
            out.append(f"build_personas:{r['id']}")
    return out


@job("build_personas")
def build_personas(ctx: JobContext) -> dict[str, Any]:
    creator_id = UUID(str(ctx.payload["creator_id"]))
    ctx.progress(step="personas", message="Meeting your followers")
    return build_now(creator_id, ctx.payload.get("reason", "manual"), bool(ctx.payload.get("fast")))
