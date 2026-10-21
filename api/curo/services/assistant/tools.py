"""Ask Curo's tools (logic doc §14): CURO's own functions on the creator's records.

Each tool reads through the creator's RLS session (another creator's records read as
missing), and returns:
- ``facts``: plain sentences carrying every number the reply may state. The no-new-numbers
  check allows only numbers found here (and in the creator's own words).
- ``sources``: the records the facts came from, which the reply cites.
- ``data``: the same, structured, for the model.
- ``job_id``: for a change that runs as a job (the app follows it and reloads the draft).

Heavy reads that the Studio and Simulator jobs already do with the service connection (the
idea scorer, the estimate) are called the same way, for a creator and records this session
has already checked are theirs.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from curo import providers
from curo.db import service_connection
from curo.jobs import studio as studio_jobs
from curo.schemas.tasks import Intent, ToolSpec
from curo.schemas.taxonomy import ALL_FIELDS, DERIVED_FIELDS, UNKNOWN
from curo.services import insights, sim_context, simulator
from curo.services.arrows import baseline_n
from curo.services.assistant import memory
from curo.services.metrics import reel_lifts

AUDIENCE_NAMES = {"followers": "your followers", "new": "new audiences", "both": "both audiences"}
METRIC_ALIASES = {
    "views": "views",
    "likes": "like_rate",
    "comments": "comment_rate",
    "shares": "share_rate",
}


class ToolError(Exception):
    """A tool can't do what was asked here (the reply says so plainly)."""


@dataclass
class ToolContext:
    conn: Any  # the creator's RLS session
    creator: dict
    screen: str
    project_id: UUID | None = None
    simulation_id: UUID | None = None
    frame_id: str | None = None


@dataclass
class ToolResult:
    facts: list[str] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)
    data: dict = field(default_factory=dict)
    job_id: str | None = None

    def for_model(self) -> str:
        return json.dumps({"facts": self.facts, "data": self.data}, default=str)


@dataclass(frozen=True)
class Tool:
    spec: ToolSpec
    run: Callable[[ToolContext, dict], ToolResult]


# ------------------------------------------------------------------ formatting


def fmt_count(n: float | None) -> str:
    """504, 1.2K, 128K, 1.3M (as the app shows counts)."""
    if n is None:
        return "unknown"
    n = round(n)
    if n < 1000:
        return str(n)
    if n < 10_000:
        return f"{n / 1000:.1f}".rstrip("0").rstrip(".") + "K"
    if n < 1_000_000:
        return f"{round(n / 1000)}K"
    return f"{n / 1_000_000:.1f}".rstrip("0").rstrip(".") + "M"


def fmt_rate(x: float | None) -> str:
    if x is None:
        return "unknown"
    pct = x * 100
    return f"{pct:.1f}%" if pct >= 1 else f"{pct:.2f}%"


def _day(dt: datetime) -> str:
    return f"{dt.day} {dt.strftime('%b')}"


def _source(kind: str, id_: Any, title: str) -> dict:
    return {"kind": kind, "id": str(id_) if id_ is not None else None, "title": title}


# ------------------------------------------------------------------ reels


def _account(ctx: ToolContext) -> insights.AccountData:
    return insights.load_account(ctx.conn, ctx.creator["account_id"])


def _views_lift(data: insights.AccountData, reel_id: str) -> float | None:
    lift = reel_lifts(data.series[reel_id], data.baselines).get("views")
    if lift and baseline_n(data.baselines, "views", lift.age_h) >= 3:
        return lift.lift
    return None


def _reel_fact(data: insights.AccountData, reel_id: str) -> str:
    card = insights.reel_card(data, reel_id)
    m = card.metrics
    parts = [f"{fmt_count(m.views)} views"]
    parts.append("likes hidden" if m.likes is None else f"{fmt_count(m.likes)} likes")
    if m.comments is not None:
        parts.append(f"{fmt_count(m.comments)} comments")
    if m.shares is not None:
        parts.append(f"{fmt_count(m.shares)} shares")
    lift = _views_lift(data, reel_id)
    vs = f", {lift:.1f}× your usual views" if lift else ""
    return f"“{card.title}” (posted {_day(card.posted_at)}): {', '.join(parts)}{vs}."


def search_reels(ctx: ToolContext, args: dict) -> ToolResult:
    data = _account(ctx)
    live = [rid for rid, r in data.rows.items() if not r["is_deleted"] and rid in data.series]
    fmt = args.get("format")
    if fmt:
        formats = {
            str(r["reel_id"]): r["format"]
            for r in ctx.conn.execute(
                """
                select d.reel_id, d.production->>'format' as format from public.reel_dna d
                  join public.reels r on r.id = d.reel_id where r.account_id = %s
                """,
                (ctx.creator["account_id"],),
            ).fetchall()
        }
        live = [rid for rid in live if formats.get(rid) == fmt]
    query = (args.get("query") or "").strip()
    if query:
        vec = providers.get_embedding().embed([query])[0]
        rows = ctx.conn.execute(
            """
            select e.reel_id, e.embedding::text as v from public.reel_embeddings e
              join public.reels r on r.id = e.reel_id where r.account_id = %s
            """,
            (ctx.creator["account_id"],),
        ).fetchall()
        sims = {str(r["reel_id"]): simulator.cosine(vec, json.loads(r["v"])) for r in rows}
        live = sorted((rid for rid in live if rid in sims), key=lambda rid: -sims[rid])[:8]
    order = args.get("order") or "best"
    if order == "recent":
        live.sort(key=lambda rid: data.rows[rid]["posted_at"], reverse=True)
    else:
        lifts = {rid: _views_lift(data, rid) for rid in live}
        known = [rid for rid in live if lifts[rid] is not None]
        known.sort(key=lambda rid: lifts[rid], reverse=order != "lowest")  # type: ignore[arg-type]
        live = known
    limit = max(1, min(int(args.get("limit") or 3), 5))
    picked = live[:limit]
    if not picked:
        return ToolResult(facts=["Curo found none of your reels for that."])
    titles = {rid: insights.reel_card(data, rid).title for rid in picked}
    return ToolResult(
        facts=[_reel_fact(data, rid) for rid in picked],
        sources=[_source("reel", rid, titles[rid]) for rid in picked],
        data={"reels": [{"id": rid, "title": titles[rid]} for rid in picked], "order": order},
    )


def get_reel(ctx: ToolContext, args: dict) -> ToolResult:
    reel_id = str(args.get("reel_id") or "")
    data = _account(ctx)
    if reel_id not in data.rows:
        raise ToolError("That isn’t one of your reels.")
    card = insights.reel_card(data, reel_id)
    facts = [_reel_fact(data, reel_id)]
    lifts = reel_lifts(data.series[reel_id], data.baselines)
    for metric in ("like_rate", "comment_rate", "share_rate"):
        lift = lifts.get(metric)
        if lift and baseline_n(data.baselines, metric, lift.age_h) >= 3:
            facts.append(f"Its {simulator.METRIC_WORDS[metric]} were {lift.lift:.1f}× your usual.")
    dna = ctx.conn.execute(
        "select content, production from public.reel_dna where reel_id = %s", (reel_id,)
    ).fetchone()
    described = {}
    if dna:
        prod = dna["production"] or {}
        described = {
            k: simulator.display(prod.get(k))
            for k in ("format", "hook_type", "opening_style", "ending", "cta_type")
        }
        facts.append(
            f"Format: {described['format']}; hook: {described['hook_type']}; ending: "
            f"{described['ending']}; call to action: {described['cta_type']}."
        )
    themes = ctx.conn.execute(
        """
        select t.label, count(*) as n from public.comments c
          join public.comment_themes t on t.key = c.theme_key and t.account_id = %s
         where c.reel_id = %s and not coalesce(c.is_bot, false)
         group by t.label order by n desc, t.label limit 2
        """,
        (ctx.creator["account_id"], reel_id),
    ).fetchall()
    for t in themes:
        facts.append(f"{t['n']} of its comments: {t['label'].lower()}.")
    return ToolResult(
        facts=facts,
        sources=[_source("reel", reel_id, card.title)],
        data={"title": card.title, "dna": described},
    )


# ------------------------------------------------------------------ patterns and opportunities


def get_pattern_cards(ctx: ToolContext, args: dict) -> ToolResult:
    metric = METRIC_ALIASES.get(str(args.get("metric") or ""))
    direction = args.get("direction")  # "works" (linked with more), "hurts" (with less), or both
    up = {"works": True, "hurts": False}.get(str(direction))
    rows = ctx.conn.execute(
        """
        select id::text, feature, value, metric, effect, n, scope from public.pattern_cards
         where account_id = %s and (%s::text is null or metric = %s)
           and (%s::boolean is null or (effect > 1) = %s)
         order by abs(ln(effect)) desc, feature, value, metric limit %s
        """,
        (
            ctx.creator["account_id"],
            metric,
            metric,
            up,
            up,
            max(1, min(int(args.get("limit") or 4), 6)),
        ),
    ).fetchall()
    if not rows:
        return ToolResult(facts=["Curo hasn’t found a clear pattern in your reels for that yet."])
    facts, sources = [], []
    for r in rows:
        card = simulator.Card(
            r["id"], r["feature"], r["value"], r["metric"], float(r["effect"]), r["n"], r["scope"]
        )
        reels, usual, n = simulator._whose(card)
        what = simulator.phrase(card.feature, card.value)
        facts.append(
            f"{reels.capitalize()} with {what} got {card.effect:.2f}× {usual} "
            f"{simulator.METRIC_WORDS[card.metric]}{n}."
        )
        sources.append(_source("pattern", card.id, what[0].upper() + what[1:]))
    return ToolResult(facts=facts, sources=sources)


def get_opportunity(ctx: ToolContext, args: dict) -> ToolResult:
    o = None
    if args.get("opportunity_id"):
        o = ctx.conn.execute(
            "select * from public.opportunities where id = %s", (str(args["opportunity_id"]),)
        ).fetchone()
    elif args.get("name"):
        o = ctx.conn.execute(
            """
            select * from public.opportunities where name ilike %s and status <> 'dismissed'
             order by rank nulls last limit 1
            """,
            (f"%{args['name']}%",),
        ).fetchone()
    elif ctx.project_id:
        o = ctx.conn.execute(
            """
            select o.* from public.opportunities o join public.projects p
              on p.opportunity_id = o.id where p.id = %s
            """,
            (ctx.project_id,),
        ).fetchone()
    if o is None:
        o = ctx.conn.execute(
            """
            select * from public.opportunities where status in ('active', 'saved')
             order by rank nulls last, score desc limit 1
            """
        ).fetchone()
    if o is None:
        return ToolResult(facts=["There are no opportunities for you yet."])
    facts = [f"{o['name']} scores {float(o['score']):.1f} out of 10."]
    for p in (o["parts"] or {}).values():
        facts.extend(p.get("facts") or [])
    return ToolResult(
        facts=facts[:6],
        sources=[_source("opportunity", o["id"], o["name"])],
        data={"name": o["name"], "description": o["description"]},
    )


def score_idea(ctx: ToolContext, args: dict) -> ToolResult:
    text = str(args.get("text") or "").strip()
    if len(text) < 3:
        raise ToolError("Which idea should Curo score?")
    v = studio_jobs.validate(ctx.creator["id"], text)
    facts = [f"“{v['text']}”: {v['verdict']}, idea score {v['score']:.2f}."]
    facts += [f"{r['text']} {r['evidence']}".strip() for r in v["reasons"]]
    facts += [f"Tweak: {t['text']} (+{t['gain']:.2f} to the idea score)." for t in v["tweaks"]]
    return ToolResult(
        facts=facts,
        sources=[_source("idea", None, v["text"])],
        data={"verdict": v["verdict"], "score": v["score"]},
    )


# ------------------------------------------------------------------ the Studio draft


def _project(ctx: ToolContext) -> dict:
    if ctx.project_id is None:
        raise ToolError("There’s no Studio draft open.")
    p = ctx.conn.execute(
        "select * from public.projects where id = %s", (ctx.project_id,)
    ).fetchone()
    if p is None:
        raise ToolError("That draft isn’t yours.")
    return p


def _line_facts(beats: list[dict], n: int) -> list[str]:
    """One script line: what it's for (the plan's purpose for that beat) and its note."""
    b = beats[n - 1]
    when = f" ({b['t']})" if b.get("t") else ""
    end = "" if b["text"].rstrip().endswith((".", "!", "?", "…")) else "."
    facts = [f"Line {n} of {len(beats)} is the {b['role']}{when}: “{b['text']}”{end}"]
    if b.get("purpose") and b["purpose"] != b["role"]:
        facts.append(f"Its job in the plan: {b['purpose']}.")
    note = b.get("note")
    if note:
        facts.append(f"{note['desc']} {note['evidence']}")
    else:
        facts.append("Curo has no pattern note on this line.")
    return facts


def get_draft(ctx: ToolContext, args: dict) -> ToolResult:
    p = _project(ctx)
    idea, script_row, board, caps = studio_jobs.current(ctx.conn, p["id"])
    title = p["title"] or (idea["text"] if idea else "Your draft")
    facts = []
    line = args.get("line")
    if script_row and line:
        beats = script_row["beats"]
        n = len(beats) if str(line) == "last" else int(line)
        if 1 <= n <= len(beats):
            return ToolResult(
                facts=_line_facts(beats, n),
                sources=[_source("project", p["id"], title)],
                data={"line": n},
            )
    if idea:
        facts.append(f"The idea: “{idea['text']}”.")
    if script_row:
        beats = script_row["beats"]
        facts.append(f"The script runs {round(beats[-1]['end_s'])} seconds in {len(beats)} lines.")
        for b in beats:
            note = b.get("note")
            if note:
                facts.append(f"“{b['text']}” — {note['desc']} {note['evidence']}")
    if board:
        feas = board["feasibility"] or {}
        if feas.get("label"):
            facts.append(
                f"The storyboard has {len(board['frames'])} frames: {feas['label']} to film."
            )
    if caps and caps["chosen"] is not None:
        chosen = caps["options"][min(caps["chosen"], len(caps["options"]) - 1)]["text"]
        facts.append(f"The chosen caption: “{chosen}”.")
        if caps["hashtags"]:
            facts.append("Hashtags: " + " ".join(f"#{t}" for t in caps["hashtags"]) + ".")
    return ToolResult(
        facts=facts or ["The draft has no idea picked yet."],
        sources=[_source("project", p["id"], title)],
        data={"step": p["step"]},
    )


def _queue(ctx: ToolContext, action: str, params: dict) -> ToolResult:
    p = _project(ctx)
    if studio_jobs.current(ctx.conn, p["id"])[1] is None:
        raise ToolError("The draft has no script yet. Write one in the Studio first.")
    job_id = studio_jobs.queue_step(p, action, params)
    return ToolResult(
        sources=[_source("project", p["id"], p["title"] or "Your draft")],
        data={"queued": action, "step": "script" if action == "script_revise" else "storyboard"},
        job_id=str(job_id),
    )


def rewrite_script(ctx: ToolContext, args: dict) -> ToolResult:
    instruction = str(args.get("instruction") or "").strip()
    if not instruction:
        raise ToolError("What should change in the script?")
    return _queue(ctx, "script_revise", {"instruction": instruction})


def update_frame(ctx: ToolContext, args: dict) -> ToolResult:
    instruction = str(args.get("instruction") or "").strip()
    if not instruction:
        raise ToolError("What should change in the frame?")
    params: dict[str, Any] = {"instruction": instruction}
    if args.get("frame_id") or ctx.frame_id:
        params["frame"] = str(args.get("frame_id") or ctx.frame_id)
    return _queue(ctx, "storyboard_revise", params)


# ------------------------------------------------------------------ the Simulator


def _simulation(ctx: ToolContext) -> dict:
    if ctx.simulation_id is None:
        raise ToolError("There’s no simulation open.")
    s = ctx.conn.execute(
        "select * from public.simulations where id = %s", (ctx.simulation_id,)
    ).fetchone()
    if s is None:
        raise ToolError("That simulation isn’t yours.")
    if s["status"] != "done" or not s["result"]:
        raise ToolError("This simulation hasn’t finished yet.")
    return s


def _sim_title(ctx: ToolContext, s: dict) -> str:
    if s["project_id"]:
        p = ctx.conn.execute(
            "select title from public.projects where id = %s", (s["project_id"],)
        ).fetchone()
        if p and p["title"]:
            return p["title"]
    return "Your upload"


def get_simulation(ctx: ToolContext, args: dict) -> ToolResult:
    s = _simulation(ctx)
    r = s["result"]
    section = str(args.get("section") or "summary")
    audience = args.get("audience") or s["audience"]
    a = r["audiences"].get(audience) or r["audiences"]["both"]
    score_line = (
        f"For {AUDIENCE_NAMES.get(audience, audience)} it scores {a['score']} out of 100: "
        f"likely to do better than {a['score']}% of your recent reels."
    )
    rows = {x["metric"]: x for x in r["report"]}

    def row_fact(metric: str) -> str:
        row = rows[metric]
        if not row.get("known"):
            return f"There isn’t enough of your history to estimate {row['label']}."
        if metric == "views":
            return (
                f"Views: {fmt_count(row['low'])}–{fmt_count(row['high'])} estimated, "
                f"{row['change_pct']:+d}% against your usual {fmt_count(row['baseline'])}."
            )
        return (
            f"{row['label'].capitalize()} per view: {fmt_rate(row['mid'])} estimated, "
            f"{row['change_pct']:+d}% against your usual {fmt_rate(row['baseline'])}."
        )

    def edit_facts() -> list[str]:
        edits = ctx.conn.execute(
            "select id, title, gains from public.simulation_edits where simulation_id = %s",
            (s["id"],),
        ).fetchall()
        by_id = {str(e["id"]): e for e in edits}
        out = [
            f"Edit: {by_id[eid]['title']} (+{(by_id[eid]['gains'] or {}).get(audience, 0)} est.)."
            for eid in a["edit_ids"]
            if eid in by_id
        ]
        return out or ["None of the changes Curo tested would raise this estimate."]

    wanted = METRIC_ALIASES.get(section)
    if wanted:  # one count: the estimate, and what's linked with it
        items = [i for i in a["holding"] + a["working"] if i["metric"] == wanted]
        facts = [row_fact(wanted), *(i["text"] for i in items[:2])]
    elif section == "time":
        bt = r.get("best_time")
        facts = (
            [f"Best time to post: {bt['label']}. {bt['fact']}"]
            if bt
            else [
                "Curo needs at least two of your reels posted at the same day and time to suggest a slot."
            ]
        )
    elif section == "edits":
        facts = edit_facts()
    elif section == "audiences":
        facts = [
            f"{AUDIENCE_NAMES[key].capitalize()}: {other['score']} out of 100. {other['summary']}"
            for key, other in r["audiences"].items()
        ]
    else:
        facts = [
            score_line,
            a["summary"],
            *(i["text"] for i in a["holding"][:1]),
            *edit_facts()[:2],
        ]
    return ToolResult(
        facts=facts,
        sources=[_source("simulation", s["id"], _sim_title(ctx, s))],
        data={"audience": audience, "section": section},
    )


def compare_to_draft(ctx: ToolContext, args: dict) -> ToolResult:
    s = _simulation(ctx)
    title = _sim_title(ctx, s)
    if not s["project_id"]:
        return ToolResult(facts=["This simulation isn’t linked to a Studio draft."])
    script_row = studio_jobs.current(ctx.conn, s["project_id"])[1]
    inputs = s["inputs"] or {}
    if script_row and inputs.get("transcript") is not None:
        items = simulator.compare(
            inputs["transcript"], inputs.get("duration_s"), script_row["beats"]
        )
    else:
        items = s["result"].get("compare") or []
    facts = [i["text"] for i in items] or ["The video follows the draft’s script."]
    return ToolResult(
        facts=facts,
        sources=[
            _source("simulation", s["id"], title),
            _source("project", s["project_id"], title),
        ],
    )


def _valid_change(change: dict) -> dict[str, str]:
    out = {}
    for k, v in (change or {}).items():
        allowed = ALL_FIELDS.get(k) or DERIVED_FIELDS.get(k) or ()
        if k in simulator.ADJUSTABLE and v in allowed and v != UNKNOWN:
            out[k] = v
    return out


def run_simulation(ctx: ToolContext, args: dict) -> ToolResult:
    """What if: re-score the recording with changed features (T9 steps 3–5 again)."""
    s = _simulation(ctx)
    inputs = s["inputs"] or {}
    if not inputs.get("vector"):
        raise ToolError("This simulation is from before what-ifs were kept. Run it again first.")
    change = _valid_change(args.get("feature_change") or {})
    if not change:
        raise ToolError(
            "Curo can test changes to the hook, opening, ending, call to action, "
            "length, pace or on-screen text."
        )
    features = inputs["features"]
    with service_connection() as conn:
        data = sim_context.load(conn, ctx.creator["id"])
    near = simulator.neighbours(inputs["vector"], features.get("format"), data.pool)
    before = simulator.scores(simulator.estimate(features, near, data.cards), data.history)
    after_est = simulator.estimate({**features, **change}, near, data.cards)
    after = simulator.scores(after_est, data.history)
    what = " and ".join(simulator.phrase(k, v) for k, v in change.items())
    facts = [
        f"With {what}, the estimate for {AUDIENCE_NAMES[a]} moves from {before[a]} to "
        f"{after[a]} out of 100."
        if after[a] != before[a]
        else f"With {what}, the estimate for {AUDIENCE_NAMES[a]} stays at {before[a]} out of 100."
        for a in simulator.AUDIENCES
    ]
    if after == before:
        facts.append(f"Your patterns don’t link {what} with a difference yet.")
    return ToolResult(
        facts=facts,
        sources=[_source("simulation", s["id"], _sim_title(ctx, s))],
        data={"change": change, "before": before, "after": after},
    )


# ------------------------------------------------------------------ memory


def remember(ctx: ToolContext, args: dict) -> ToolResult:
    m = memory.save_stated(ctx.conn, ctx.creator["id"], str(args.get("note") or ""))
    if m is None:
        raise ToolError("What should Curo remember?")
    return ToolResult(
        sources=[_source("memory", m.id, m.value)],
        data={"remembered": m.value, "avoids": memory.avoided(m.value)},
    )


def forget(ctx: ToolContext, args: dict) -> ToolResult:
    gone = memory.forget(ctx.conn, ctx.creator["id"], str(args.get("query") or ""))
    return ToolResult(data={"forgotten": [m.value for m in gone]})


# ------------------------------------------------------------------ the registry


def _spec(name: str, description: str, props: dict, required: list[str] | None = None) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=description,
        input_schema={"type": "object", "properties": props, "required": required or []},
    )


TOOLS: dict[str, Tool] = {
    t.spec.name: t
    for t in (
        Tool(
            _spec(
                "search_reels",
                "Find the creator's past reels by topic, format or result.",
                {
                    "query": {"type": "string"},
                    "format": {"type": "string", "enum": list(ALL_FIELDS["format"])},
                    "order": {"type": "string", "enum": ["best", "recent", "lowest"]},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 5},
                },
            ),
            search_reels,
        ),
        Tool(
            _spec(
                "get_reel",
                "One reel's public counts, lifts against the creator's usual, DNA and comment themes.",
                {"reel_id": {"type": "string"}},
                ["reel_id"],
            ),
            get_reel,
        ),
        Tool(
            _spec(
                "get_pattern_cards",
                "What tends to work for this creator (or hold them back), with the evidence.",
                {
                    "metric": {"type": "string", "enum": list(METRIC_ALIASES)},
                    "direction": {"type": "string", "enum": ["works", "hurts"]},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 6},
                },
            ),
            get_pattern_cards,
        ),
        Tool(
            _spec(
                "get_opportunity",
                "An opportunity's score parts and evidence (default: the open draft's).",
                {"opportunity_id": {"type": "string"}, "name": {"type": "string"}},
            ),
            get_opportunity,
        ),
        Tool(
            _spec(
                "score_idea",
                "Score an idea with the Studio's idea formula: verdict, reasons, tweaks.",
                {"text": {"type": "string"}},
                ["text"],
            ),
            score_idea,
        ),
        Tool(
            _spec(
                "get_draft",
                "The open Studio draft: idea, script lines with their notes, storyboard, caption; "
                'or one line (1 = the first, "last" = the last) and why it\'s there.',
                {"line": {"type": ["integer", "string"]}},
            ),
            get_draft,
        ),
        Tool(
            _spec(
                "rewrite_script",
                "Change the open draft's script; only the lines the instruction targets change.",
                {"instruction": {"type": "string"}},
                ["instruction"],
            ),
            rewrite_script,
        ),
        Tool(
            _spec(
                "update_frame",
                "Redraw one storyboard frame of the open draft.",
                {"instruction": {"type": "string"}, "frame_id": {"type": "string"}},
                ["instruction"],
            ),
            update_frame,
        ),
        Tool(
            _spec(
                "get_simulation",
                "The open simulation's estimate: score, report, reasons, edits, best time.",
                {
                    "section": {
                        "type": "string",
                        "enum": [
                            "summary",
                            "views",
                            "likes",
                            "comments",
                            "shares",
                            "time",
                            "edits",
                            "audiences",
                        ],
                    },
                    "audience": {"type": "string", "enum": ["followers", "new", "both"]},
                },
            ),
            get_simulation,
        ),
        Tool(
            _spec(
                "run_simulation",
                "What if: re-score the open simulation's recording with changed DNA features.",
                {"feature_change": {"type": "object", "additionalProperties": {"type": "string"}}},
                ["feature_change"],
            ),
            run_simulation,
        ),
        Tool(
            _spec(
                "compare_to_draft",
                "Line the recording up against its Studio draft, beat by beat.",
                {},
            ),
            compare_to_draft,
        ),
        Tool(
            _spec(
                "remember",
                "Keep a stated preference of the creator's (shown and deletable in Settings).",
                {"note": {"type": "string"}},
                ["note"],
            ),
            remember,
        ),
        Tool(
            _spec(
                "forget",
                "Delete the preferences the creator asks Curo to forget.",
                {"query": {"type": "string"}},
            ),
            forget,
        ),
    )
}

BY_INTENT: dict[Intent, tuple[str, ...]] = {
    "explain": (
        "search_reels",
        "get_reel",
        "get_pattern_cards",
        "get_opportunity",
        "score_idea",
        "get_draft",
        "get_simulation",
        "compare_to_draft",
    ),
    "what_if": ("run_simulation", "get_simulation", "score_idea"),
    "change": ("rewrite_script", "update_frame", "get_draft"),
    "remember": ("remember",),
    "forget": ("forget",),
    "unclear": (),
    "hidden": (),
}

NEEDS = {  # tools that only make sense with something open
    "get_draft": "project",
    "rewrite_script": "project",
    "update_frame": "project",
    "get_simulation": "simulation",
    "run_simulation": "simulation",
    "compare_to_draft": "simulation",
}


def allowed(intent: Intent, ctx: ToolContext) -> list[ToolSpec]:
    out = []
    for name in BY_INTENT[intent]:
        need = NEEDS.get(name)
        if need == "project" and ctx.project_id is None:
            continue
        if need == "simulation" and ctx.simulation_id is None:
            continue
        out.append(TOOLS[name].spec)
    return out


def execute(ctx: ToolContext, name: str, args: dict, permitted: set[str]) -> ToolResult:
    if name not in permitted or name not in TOOLS:
        raise ToolError(f"Curo can’t use {name} here.")
    return TOOLS[name].run(ctx, args or {})
