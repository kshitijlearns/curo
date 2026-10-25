"""Everything a Studio step reads about the creator, loaded once per step.

The creator's reels with their DNA and lifts, sub-clusters, pattern cards, audience themes,
the niche's trend cards, trend facts, voice profile, caption habits and hashtag results;
plus the evidence pack T6 writes ideas from (logic doc §9), each fact with an id the ideas
cite. All of it is read from what CURO has collected — nothing here is invented.
"""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

from curo import clock, providers
from curo.jobs.hashtags import creator_niche, upcoming_festivals
from curo.jobs.learning import mining_rows
from curo.jobs.opportunities import subclusters_with_captions
from curo.schemas.tasks import EvidenceItem, Toolkit, VoiceProfile
from curo.schemas.taxonomy import UNKNOWN, label_for
from curo.services import ideas, script, topics, voice
from curo.services.captions import TagEvidence, caption_style, series_tags
from curo.services.metrics import compute_baselines
from curo.services.records import load_dna, load_series
from curo.services.text import reel_title

MIX_METRICS = ("views", "like_rate", "share_rate", "comment_rate")
METRIC_BEHAVIOUR = {
    "views": "views",
    "like_rate": "likes",
    "comment_rate": "comments",
    "share_rate": "shares",
}
FESTIVAL_HORIZON = 30
OTHER_FESTIVALS_DAYS = 120  # an idea about a festival further off still counts as about it


def persona_fits(conn, creator_id: UUID) -> list:
    """The creator's 4 Follower Personas as the idea scorer reads them (none while building)."""
    from curo.services import persona_reactions

    rows = persona_reactions.active_rows(conn, creator_id)
    return [persona_reactions.fit(r) for r in rows] if len(rows) == 4 else []


@dataclass
class StudioData:
    creator_id: UUID
    account_id: UUID
    username: str
    followers: int | None
    now: datetime
    opportunity: dict | None
    festival: dict | None
    keywords: list[str]
    ctx: ideas.Context  # what the idea scorer reads
    voice: VoiceProfile
    lengths: list[script.ReelLength]
    examples: dict[str, list[script.Example]]  # format → the creator's strongest 3
    toolkit: Toolkit
    cards: list[dict]  # pattern cards as rows
    theme_samples: dict[str, list[str]]
    language_mix: dict[str, float]
    trend_cards: list[dict]  # the niche's trend feed (v2: replaces tracked peers)
    caption_style: Any
    tag_evidence: dict[str, TagEvidence]
    series: dict[str, set[str]]  # format → the creator's series or signature tags for it
    region_words: set[str]
    creator_formats: list[str]
    dna: dict[str, dict] = field(default_factory=dict)

    @property
    def topic(self) -> str | None:
        return self.opportunity["name"] if self.opportunity else None


def _lift(group_lifts: dict, metric: str) -> float | None:
    value = group_lifts.get(metric)
    if isinstance(value, dict):
        return value.get("lift")
    return value


def load(conn, creator_id: UUID, opportunity_id: UUID | None = None) -> StudioData:
    now = clock.now()
    today = now.date()
    embedder = providers.get_embedding()
    creator = conn.execute(
        """
        select c.id, c.account_id, c.voice_profile, a.username, a.followers
          from public.creators c join public.accounts a on a.id = c.account_id where c.id = %s
        """,
        (creator_id,),
    ).fetchone()
    account_id = creator["account_id"]
    series = load_series(conn, [account_id])[account_id]
    baselines = compute_baselines(series)
    dna = load_dna(conn, [account_id])
    _rows, lifts_by_reel = mining_rows(series, baselines, dna)
    reels = {
        str(r["id"]): r
        for r in conn.execute(
            """
            select id, caption, hashtags, posted_at, duration_s, is_paid_partnership
              from public.reels where account_id = %s and not is_deleted
             order by posted_at, shortcode
            """,
            (account_id,),
        ).fetchall()
    }

    # ---------------------------------------------------------------- sub-clusters and formats
    raw_groups = subclusters_with_captions(conn, account_id)
    fmt_of = {rid: (d["production"] or {}).get("format") for rid, d in dna.items()}
    groups = []
    for g in raw_groups:
        formats = Counter(
            fmt_of.get(r) for r in g["reel_ids"] if fmt_of.get(r) not in (None, UNKNOWN)
        )
        groups.append(
            ideas.Group(
                id=g["id"],
                label=g["label"],
                vector=g["caption_vector"],
                typical_sim=g["typical_sim"],
                lifts={m: lift for m in MIX_METRICS if (lift := _lift(g["lifts"], m))},
                n=len(g["reel_ids"]),
                format=formats.most_common(1)[0][0] if formats else None,
            )
        )
    by_format: dict[str, list[dict[str, float]]] = defaultdict(list)
    for rid, lifts in lifts_by_reel.items():
        f = fmt_of.get(rid)
        if f and f != UNKNOWN:
            by_format[f].append({m: v.lift for m, v in lifts.items()})
    format_stats = {
        f: ideas.FormatStat(
            f,
            len(rows),
            {
                m: statistics.median(vals)
                for m in MIX_METRICS
                if (vals := [r[m] for r in rows if m in r])
            },
        )
        for f, rows in by_format.items()
    }
    creator_formats = [
        f for f, _ in Counter(f for f in fmt_of.values() if f and f != UNKNOWN).most_common()
    ]

    # ---------------------------------------------------------------- pattern cards
    cards = [
        dict(r)
        for r in conn.execute(
            """
            select id::text, feature, value, metric, effect, n, scope from public.pattern_cards
             where account_id = %s order by abs(ln(effect)) desc, feature, value, metric
            """,
            (account_id,),
        ).fetchall()
    ]
    card_facts = [
        ideas.CardFact(
            c["id"], c["feature"], c["value"], c["metric"], float(c["effect"]), c["n"], c["scope"]
        )
        for c in cards
    ]

    # ---------------------------------------------------------------- audience
    themes = conn.execute(
        """
        select key, label, share, n from public.comment_themes
         where account_id = %s and key is not null order by share desc, key
        """,
        (account_id,),
    ).fetchall()
    samples: dict[str, list[str]] = {}
    for t in themes:
        samples[t["key"]] = [
            r["text"]
            for r in conn.execute(
                """
                select c.text from public.comments c join public.reels r on r.id = c.reel_id
                 where r.account_id = %s and c.theme_key = %s and not coalesce(c.is_bot, false)
                 order by c.like_count desc, c.ig_comment_id limit 3
                """,
                (account_id, t["key"]),
            ).fetchall()
        ]
    theme_texts = [f"{t['label']} {' '.join(samples[t['key']])}" for t in themes]
    theme_vectors = embedder.embed(theme_texts) if theme_texts else []
    theme_facts = [
        ideas.ThemeFact(
            key=t["key"],
            label=t["label"],
            share=float(t["share"]),
            n=t["n"],
            vector=v,
            words=theme_words(t["label"]),
        )
        for t, v in zip(themes, theme_vectors, strict=True)
    ]
    comments = conn.execute(
        """
        select c.text, c.language from public.comments c join public.reels r on r.id = c.reel_id
         where r.account_id = %s and not coalesce(c.is_bot, false) and not c.is_creator
         order by c.posted_at desc nulls last, c.ig_comment_id limit 500
        """,
        (account_id,),
    ).fetchall()
    langs = Counter(c["language"] for c in comments if c["language"])
    total = sum(langs.values()) or 1
    language_mix = {k: round(v / total, 2) for k, v in langs.most_common()}
    region_words = {w for c in comments for w in topics.words(c["text"]) if w in topics.PLACES}

    # ---------------------------------------------------------------- the niche's trend feed
    niche = creator_niche(conn, account_id)
    trend_cards = [
        dict(c)
        for c in conn.execute(
            """
            select key, name, summary, why_rising, example_angles, momentum, saturation, hashtags
              from public.trend_cards where niche = %s
             order by momentum desc nulls last, key
            """,
            (niche,),
        ).fetchall()
    ]
    t_vectors = (
        embedder.embed([f"{c['name']} {' '.join(c['example_angles'] or [])}" for c in trend_cards])
        if trend_cards
        else []
    )
    trend_angles = [
        ideas.TrendAngle(
            c["key"],
            c["name"],
            (c["example_angles"] or [c["summary"]])[0],
            float(c["momentum"]) if c["momentum"] is not None else None,
            v,
        )
        for c, v in zip(trend_cards, t_vectors, strict=True)
    ]

    # ---------------------------------------------------------------- opportunity and trend
    opportunity = None
    if opportunity_id:
        opportunity = conn.execute(
            "select * from public.opportunities where id = %s and creator_id = %s",
            (opportunity_id, creator_id),
        ).fetchone()
    festival, keywords = _festival_for(conn, opportunity, account_id, today)
    pages = conn.execute(
        "select tag, daily_counts, post_count from public.hashtag_pages"
    ).fetchall()
    rising = {
        p["tag"]: g
        for p in pages
        if (g := topics.growth(p["daily_counts"] or {}, today)) is not None and g >= 1.5
    }
    others = conn.execute(
        """
        select name, starts_on, ends_on, keywords from public.festival_calendar
         where ends_on >= %s and starts_on <= %s order by starts_on, name
        """,
        (today, today + timedelta(days=OTHER_FESTIVALS_DAYS)),
    ).fetchall()
    trend = ideas.TrendFact(
        festival=festival["name"] if festival else None,
        starts_on=festival["starts_on"] if festival else None,
        ends_on=festival["ends_on"] if festival else None,
        keywords={k.lower() for k in (festival["keywords"] if festival else [])},
        rising=rising,
        others=[
            ideas.Festival(
                o["name"], o["starts_on"], o["ends_on"], {k.lower() for k in o["keywords"]}
            )
            for o in others
            if not festival or o["name"] != festival["name"]
        ],
    )

    # ---------------------------------------------------------------- the creator's recent reels
    ordered = sorted(reels.values(), key=lambda r: (r["posted_at"], str(r["id"])), reverse=True)
    recent_text = [f"{reel_title(r['caption'])} {' '.join(r['hashtags'])}" for r in ordered[:10]]
    recent = embedder.embed(recent_text) if recent_text else []

    ctx = ideas.Context(
        today=today,
        groups=groups,
        formats=format_stats,
        cards=card_facts,
        themes=theme_facts,
        trend=trend,
        trend_angles=trend_angles,
        recent=recent,
        # v2.2: A is the share-weighted persona score once the 4 personas exist.
        personas=persona_fits(conn, creator_id),
    )

    # ---------------------------------------------------------------- voice, length, examples
    vp = (
        VoiceProfile.model_validate(creator["voice_profile"])
        if creator["voice_profile"]
        else voice.profile(d["transcript"] for d in dna.values())
    )
    followers = creator["followers"]
    lengths = []
    for s in series:
        d = dna.get(s.reel_id)
        lift = lifts_by_reel.get(s.reel_id, {}).get("views")
        lengths.append(
            script.ReelLength(
                format=fmt_of.get(s.reel_id),
                duration_s=float(d["duration_s"]) if d and d["duration_s"] else None,
                views_lift=lift.lift if lift and not s.paid else None,
            )
        )
    examples: dict[str, list[script.Example]] = {}
    ranked = sorted(
        (rid for rid in dna if rid in lifts_by_reel and "views" in lifts_by_reel[rid]),
        key=lambda rid: -lifts_by_reel[rid]["views"].lift,
    )
    for rid in ranked:
        d = dna[rid]
        f = fmt_of.get(rid)
        t1 = d["transcript"] or {}
        if not f or f == UNKNOWN or len(examples.setdefault(f, [])) >= 3:
            continue
        examples[f].append(
            script.Example(
                text=" ".join(w["word"] for w in t1.get("transcript", [])),
                onscreen=[o["text"] for o in t1.get("onscreen_text", [])],
                ending=(d["production"] or {}).get("ending"),
            )
        )

    # ---------------------------------------------------------------- toolkit and captions
    prods = [d["production"] or {} for d in dna.values()]

    def most(field_name: str) -> list[str]:
        c = Counter(p.get(field_name) for p in prods if p.get(field_name) not in (None, UNKNOWN))
        return [v for v, _ in c.most_common()]

    toolkit = Toolkit(
        cameras=most("camera"), settings=most("setting"), lighting=most("visual_style")
    )
    creator_captions = [(r["caption"], list(r["hashtags"])) for r in ordered]
    style = caption_style([c for c, _ in creator_captions[:30]])

    # ---------------------------------------------------------------- hashtag evidence
    evidence: dict[str, TagEvidence] = {}

    def ev(tag: str) -> TagEvidence:
        tag = tag.lower()
        return evidence.setdefault(tag, TagEvidence(tag))

    for rid, r in reels.items():
        lift = lifts_by_reel.get(rid, {}).get("views")
        for t in {t.lower() for t in r["hashtags"]}:
            e = ev(t)
            if lift:
                e.creator_lifts.append(lift.lift)
    # Tags from the niche's trend feed: what's rising now (v2: replaces peers' tags).
    users: Counter[str] = Counter()
    for c in trend_cards:
        for t in {t.lower() for t in c["hashtags"]}:
            users[t] += 2  # shared by the niche, so never the creator's own series tag
            ev(t).trend_momentum = float(c["momentum"]) if c["momentum"] is not None else None
            ev(t).in_trend_feed = True
    docs = [{t.lower() for t in r["hashtags"]} for r in reels.values()]
    n_docs = max(len(docs), 1)
    for p in pages:
        e = ev(p["tag"])
        e.page_posts = p["post_count"]
    for k in keywords:
        ev(k.replace(" ", "").lower())
    for tag, e in evidence.items():
        e.doc_share = sum(1 for d in docs if tag in d) / n_docs
    series_by_format: dict[str, set[str]] = {}
    for f_ in {f for f in fmt_of.values() if f and f != UNKNOWN}:
        same = [
            (r["caption"], list(r["hashtags"])) for rid, r in reels.items() if fmt_of.get(rid) == f_
        ]
        series_by_format[f_] = series_tags(same, dict(users))

    return StudioData(
        creator_id=creator_id,
        account_id=account_id,
        username=creator["username"],
        followers=followers,
        now=now,
        opportunity=dict(opportunity) if opportunity else None,
        festival=festival,
        keywords=keywords,
        ctx=ctx,
        voice=vp,
        lengths=lengths,
        examples=examples,
        toolkit=toolkit,
        cards=cards,
        theme_samples=samples,
        language_mix=language_mix,
        trend_cards=trend_cards,
        caption_style=style,
        tag_evidence=evidence,
        series=series_by_format,
        region_words=region_words,
        creator_formats=creator_formats,
        dna=dna,
    )


def _festival_for(
    conn, opportunity: dict | None, account_id: UUID, today: date
) -> tuple[dict | None, list[str]]:
    """The opportunity's festival if it has one; otherwise the next festival in the creator's
    niche within 30 days (ideas of the creator's own can still ride it)."""
    fest_id = None
    keywords: list[str] = []
    if opportunity:
        evidence = opportunity["evidence"] or {}
        keywords = list(evidence.get("keywords") or [])
        if evidence.get("festival"):
            fest_id = evidence["festival"]["id"]
    if fest_id:
        row = conn.execute(
            "select id::text, name, starts_on, ends_on, keywords from public.festival_calendar where id = %s",
            (fest_id,),
        ).fetchone()
        if row:
            return dict(row), _dedupe([*row["keywords"], *keywords])
        return None, keywords
    if opportunity:
        return None, keywords
    upcoming = upcoming_festivals(conn, creator_niche(conn, account_id), today, FESTIVAL_HORIZON)
    if upcoming:
        f = upcoming[0]
        return {k: f[k] for k in ("id", "name", "starts_on", "ends_on", "keywords")}, list(
            f["keywords"]
        )
    return None, []


# Words that say how a theme is asked, not what about.
THEME_STOP = frozenset(
    {"asks", "wants", "about", "looks", "look", "versions", "from", "more", "it's"}
)


def theme_words(label: str) -> set[str]:
    """A theme's key words: "Asks where it's from" → {"where"}, "Wants budget versions" →
    {"budget"}."""
    return {w for w in topics.words(label) if len(w) >= 4 and w not in THEME_STOP} | (
        {"part"} if "part" in label.lower() else set()
    )


def _dedupe(words: list[str]) -> list[str]:
    seen: set[str] = set()
    return [w for w in words if not (w.lower() in seen or seen.add(w.lower()))]


# ------------------------------------------------------------------ the evidence pack (T6)


def evidence_pack(data: StudioData) -> list[EvidenceItem]:
    """Opportunity, creator history, audience and trend (logic doc §9; v2 no peers), as cited
    facts."""
    out: list[EvidenceItem] = []
    opp = data.opportunity
    if opp:
        facts = [f for p in (opp["parts"] or {}).values() for f in p.get("facts", [])[:1]]
        out.append(
            EvidenceItem(
                id=f"opp:{opp['id']}",
                kind="opportunity",
                text=f"Opportunity “{opp['name']}”, {round(float(opp['score']))}/10. "
                + " ".join(facts[:3]),
            )
        )
    groups = sorted(data.ctx.groups, key=lambda g: -(g.lifts.get("views") or 0))[:5]
    for g in groups:
        parts = ", ".join(
            f"{g.lifts[m]:.2f}× {ideas.METRIC_WORDS[m]}" for m in MIX_METRICS if m in g.lifts
        )
        out.append(
            EvidenceItem(
                id=f"sub:{g.id}",
                kind="subcluster",
                text=f"Your “{g.label}” reels ({g.n}): {parts}.",
                format=g.format,
            )
        )
    for c in data.cards[:10]:
        who = f"{c['n']} of your reels" if c["scope"] == "yours" else "based on creators like you"
        out.append(
            EvidenceItem(
                id=f"card:{c['id']}",
                kind="pattern",
                text=f"{label_for(c['value'])} → {float(c['effect']):.2f}× {ideas.METRIC_WORDS[c['metric']]} ({who}).",
            )
        )
    for f, stat in sorted(data.ctx.formats.items(), key=lambda kv: -kv[1].n)[:5]:
        band = script.length_band(data.lengths, f)
        out.append(
            EvidenceItem(
                id=f"format:{f}",
                kind="format",
                text=f"Your {ideas.format_name(f)} reels ({stat.n}) do best at {band.low}–{band.high} seconds.",
                format=f,
            )
        )
    for t in data.ctx.themes[:5]:
        out.append(
            EvidenceItem(
                id=f"theme:{t.key}",
                kind="theme",
                text=f"{t.label}: {round(t.share * 100, 1)}% of your recent comments.",
                samples=data.theme_samples.get(t.key, [])[:3],
            )
        )
    for c in data.trend_cards[:4]:
        angles = "; ".join(c["example_angles"] or [])
        out.append(
            EvidenceItem(
                id=f"trend:card:{c['key']}",
                kind="trend",
                text=f"Trending in your niche: {c['name']}. {c['why_rising']}"
                + (f" Angles: {angles}." if angles else ""),
            )
        )
    if data.festival:
        f = data.festival
        days = (f["starts_on"] - data.now.date()).days
        when = f"starts in {days} days" if days > 0 else "is on now"
        out.append(
            EvidenceItem(id=f"trend:festival:{f['id']}", kind="trend", text=f"{f['name']} {when}.")
        )
    for tag, g in sorted(data.ctx.trend.rising.items(), key=lambda kv: -kv[1])[:3]:
        out.append(
            EvidenceItem(
                id=f"trend:tag:{tag}",
                kind="trend",
                text=f"Daily posts on #{tag} are {g:.1f}× the 4 weeks before.",
            )
        )
    if opp and (opp["parts"] or {}).get("O"):
        facts = opp["parts"]["O"].get("facts") or []
        if facts:
            out.append(EvidenceItem(id="trend:saturation", kind="trend", text=facts[0]))
    return out
