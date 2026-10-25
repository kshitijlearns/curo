"""The Creator Recap (v2.1 §3): every number in it, computed here — never by the AI.

``build(data)`` turns what CURO has collected for a period into facts per slide, applies each
slide's minimum-data rule (a slide without its data is dropped, never shown with a zero),
picks and orders the slides for the story arc (5–12), and works out the creator's level,
modifier and archetype. T23 later writes the playful lines around these facts; every line is
checked against the slide's ``display`` facts by the no-new-numbers validator.

Public data only: CURO can't see saves, reach, watch time, demographics or who follows whom.
Where a slide talks about people beyond the creator's followers it uses the public proxy
views ÷ follower count, and says so.
"""

from __future__ import annotations

import itertools
import math
import re
import statistics
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from curo.schemas.taxonomy import label_for
from curo.services import recap_config as C

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
METRIC_WORDS = {
    "views": "views",
    "like_rate": "likes per view",
    "comment_rate": "comments per view",
    "share_rate": "shares per view",
}

# ------------------------------------------------------------------ inputs


@dataclass
class Reel:
    id: str
    title: str
    posted: datetime  # the creator's local time
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    caption: str = ""
    hashtags: list[str] = field(default_factory=list)
    audio_name: str | None = None
    paid: bool = False
    dna: dict[str, Any] | None = None  # content + production features, when processed

    def rate(self, part: str) -> float | None:
        v = getattr(self, part)
        if v is None or not self.views:
            return None
        return v / self.views


@dataclass
class Comment:
    text: str
    likes: int = 0
    language: str | None = None


@dataclass
class Theme:
    label: str
    share: float
    n: int


@dataclass
class Group:
    label: str
    views_lift: float | None
    n: int


@dataclass
class Card:
    feature: str
    value: str
    metric: str
    effect: float
    n: int


@dataclass
class RecapInput:
    kind: str  # "first" | "monthly"
    period_start: date
    period_end: date  # inclusive
    handle: str
    followers: int | None
    total_posts: int | None
    reels: list[Reel]  # posted in the period
    history: list[Reel]  # every reel CURO knows (for "your usual")
    comments: list[Comment] = field(default_factory=list)  # on the period's reels
    themes: list[Theme] = field(default_factory=list)
    groups: list[Group] = field(default_factory=list)
    cards: list[Card] = field(default_factory=list)
    follower_start: int | None = None  # monthly: first snapshot of the month
    follower_end: int | None = None  # monthly: last snapshot of the month
    views_older_gained: int | None = None  # monthly: views older reels gained in the month
    previous: dict | None = None  # the previous monthly recap's facts
    opportunities: int = 0
    trend_tags: set[str] = field(default_factory=set)
    today: date | None = None
    # v2.2: the 4 Follower Personas (share order) and, for a monthly recap, last month's
    # share of each persona that existed then (persona id → share).
    personas: list[dict] = field(default_factory=list)
    persona_previous: dict[str, float] | None = None


# ------------------------------------------------------------------ numbers


def fmt_in(n: float | int) -> str:
    """Indian digit grouping: 248300 → 2,48,300; 1234567 → 12,34,567."""
    neg = n < 0
    n = abs(n)
    whole = round(n)
    s = str(whole)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups) + "," + tail
    return ("-" if neg else "") + s


def fmt_short(n: float | int) -> str:
    """Headline form: 2.4Cr, 2.4L, 24.8K, 248 (Indian lakh / crore)."""
    n = float(n)
    for size, unit in ((1e7, "Cr"), (1e5, "L"), (1e3, "K")):
        if abs(n) >= size:
            v = n / size
            return f"{v:.1f}".rstrip("0").rstrip(".") + unit
    return fmt_in(n)


def fmt_x(x: float) -> str:
    return f"{x:.1f}".rstrip("0").rstrip(".") + "×"


def pct(x: float) -> str:
    return f"{round(x * 100)}%"


# ------------------------------------------------------------------ level, modifier, archetype


def level_for(followers: int | None) -> tuple[str, str] | None:
    if followers is None:
        return None
    for upper, name, line in C.LEVELS:
        if upper is None or followers <= upper:
            return name, line
    return None  # pragma: no cover


def modifier_for(total_posts: int | None, history: list[Reel], today: date) -> str | None:
    """One tag: just getting started, consistency champ, or seasoned creator."""
    if total_posts is not None and total_posts < C.JUST_STARTED_POSTS:
        return C.MODIFIERS["just_started"]
    weeks = []
    for w in range(C.CONSISTENCY_WEEKS):
        end = today - timedelta(days=7 * w)
        start = end - timedelta(days=7)
        weeks.append(sum(1 for r in history if start < r.posted.date() <= end))
    if weeks and all(n >= C.CONSISTENCY_PER_WEEK for n in weeks):
        return C.MODIFIERS["consistency"]
    if total_posts is not None and total_posts >= C.SEASONED_POSTS:
        return C.MODIFIERS["seasoned"]
    return None


def _has(text: str, cues: tuple[str, ...]) -> bool:
    t = text.lower()
    return any(c in t for c in cues)


def _median(xs: list[float]) -> float | None:
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def _lift(period: list[Reel], history: list[Reel], part: str) -> float | None:
    now = _median([r.rate(part) for r in period])
    usual = _median([r.rate(part) for r in history])
    if now is None or not usual:
        return None
    return now / usual


def weeks_in(start: date, end: date) -> int:
    return max(1, ((end - start).days // 7) + 1)


def weeks_with_post(reels: list[Reel]) -> int:
    return len({r.posted.isocalendar()[:2] for r in reels})


def archetype_scores(d: RecapInput) -> tuple[dict[str, float], dict[str, dict]]:
    """Each archetype's 0–1 score and the evidence behind it (deterministic)."""
    reels = d.reels
    n = len(reels)
    scores: dict[str, float] = dict.fromkeys(C.ARCHETYPES, 0.0)
    evidence: dict[str, dict] = {}
    if n == 0:
        return scores, evidence
    with_dna = [r for r in reels if r.dna]
    source = "video analysis" if len(with_dna) * 2 >= n else "captions and hashtags"

    def share(match) -> tuple[float, int]:
        k = sum(1 for r in reels if match(r))
        return k / n, k

    def dna(r: Reel, key: str) -> str | None:
        return (r.dna or {}).get(key)

    rules = {
        "storyteller": lambda r: dna(r, "narrative") in ("story_arc", "day_in_the_life", "before_after")
        or (not r.dna and _has(r.caption, C.CUES["storyteller"])),
        "teacher": lambda r: dna(r, "format") in ("tutorial", "listicle")
        or dna(r, "narrative") in ("list", "step_by_step", "problem_solution")
        or (not r.dna and _has(r.caption, C.CUES["teacher"])),
        "entertainer": lambda r: dna(r, "format") == "skit"
        or dna(r, "cluster") == "comedy"
        or dna(r, "ending") == "punchline"
        or (not r.dna and _has(r.caption, C.CUES["entertainer"])),
        "trend_rider": lambda r: dna(r, "audio") == "trending_audio"
        or bool({t.lower() for t in r.hashtags} & d.trend_tags)
        or (bool(r.audio_name) and "original" not in (r.audio_name or "").lower()),
    }  # fmt: skip
    for key, rule in rules.items():
        s, k = share(rule)
        scores[key] = round(s, 3)
        evidence[key] = {"reels": n, "matching": k, "source": source}

    # The Conversation Starter: comments per view is the strongest lift, and above usual.
    lifts = {p: _lift(reels, d.history, p) for p in ("likes", "comments", "shares")}
    known = {p: v for p, v in lifts.items() if v is not None}
    if known and max(known, key=lambda p: known[p]) == "comments" and known["comments"] > 1:
        scores["conversation_starter"] = round(min(1.0, 0.6 + 0.4 * (known["comments"] - 1)), 3)
        evidence["conversation_starter"] = {"comment_lift": round(known["comments"], 2)}

    # The Aesthetic Curator: one visual style in most reels, and likes per view above usual.
    styles = Counter(dna(r, "visual_style") for r in with_dna if dna(r, "visual_style"))
    if styles and with_dna:
        style, k = styles.most_common(1)[0]
        top = k / len(with_dna)
        like_lift = lifts.get("likes")
        if top >= 0.6 and like_lift is not None and like_lift >= 1:
            scores["aesthetic_curator"] = round(top, 3)
            evidence["aesthetic_curator"] = {"style": style, "share": round(top, 2)}

    # The Consistent One: a reel in nearly every week of the period.
    weeks = weeks_in(d.period_start, d.period_end)
    if weeks >= 4:
        ratio = weeks_with_post(reels) / weeks
        scores["consistent_one"] = round(ratio if ratio >= 0.85 else ratio * 0.5, 3)
        evidence["consistent_one"] = {"weeks": weeks, "weeks_with_post": weeks_with_post(reels)}

    # The Night Owl: most reels posted after 9 pm (or before 4 am).
    late = sum(1 for r in reels if r.posted.hour >= C.NIGHT_HOUR or r.posted.hour < 4)
    s = late / n
    scores["night_owl"] = round(s if s > 0.5 else s * 0.5, 3)
    evidence["night_owl"] = {"reels": n, "late": late}
    return scores, evidence


def archetype_for(d: RecapInput) -> tuple[str, str | None, dict]:
    scores, evidence = archetype_scores(d)
    order = list(C.ARCHETYPES)
    ranked = sorted(order, key=lambda k: (-scores[k], order.index(k)))
    best = ranked[0]
    runner = ranked[1] if scores[ranked[1]] >= C.RUNNER_UP_MIN else None
    if scores[best] <= 0:  # nothing stands out yet: posting rhythm is the honest default
        best, runner = "consistent_one", None
    return best, runner, {"scores": scores, "evidence": evidence.get(best, {})}


# ------------------------------------------------------------------ comparisons and milestones


def comparison_for(views: int) -> dict | None:
    """The "that's like…" comparison whose multiple lands between 2 and 50 (closest to 10)."""
    best = None
    for label, size, note in C.COMPARISONS:
        times = views / size
        if C.COMPARISON_MIN <= times <= C.COMPARISON_MAX:
            score = abs(math.log10(times) - 1)
            if best is None or score < best[0]:
                best = (score, {"label": label, "times": round(times), "note": note})
    return best[1] if best else None


def next_milestone(followers: int) -> int | None:
    return next((m for m in C.MILESTONES if m > followers), None)


# ------------------------------------------------------------------ comments


_PHONE = re.compile(r"(?:\+?\d[\d\s-]{8,}\d)")
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_URL = re.compile(r"https?://|www\.", re.IGNORECASE)
_EMOJI = re.compile("[\U0001f300-\U0001faff☀-➿❤]")


def clean_comments(comments: list[Comment]) -> list[Comment]:
    """No spam, no personal data, no handles."""
    out = []
    for c in comments:
        t = (c.text or "").strip()
        if not t or _PHONE.search(t) or _EMAIL.search(t) or _URL.search(t):
            continue
        t = re.sub(r"@[\w.]+", "@…", t)
        out.append(Comment(t, c.likes, c.language))
    return out


# ------------------------------------------------------------------ slides


def _period_label(d: RecapInput) -> str:
    if d.kind == "first":
        return "your story so far"
    return d.period_start.strftime("%B %Y")


def _part_of_day(hour: int) -> str:
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 21:
        return "evening"
    return "night"


def _window(hour: int) -> str:
    start = (hour // 2) * 2
    end = start + 2

    def h(x: int) -> str:
        x %= 24
        suffix = "am" if x < 12 else "pm"
        return f"{(x % 12) or 12} {suffix}"

    return f"{h(start)}–{h(end)}"


def slide_facts(d: RecapInput) -> dict[str, dict | None]:
    """Facts for every slide type; None where the minimum-data rule fails."""
    reels = [r for r in d.reels]
    with_views = [r for r in reels if r.views is not None]
    hist_views = [r.views for r in d.history if r.views is not None and not r.paid]
    usual_views = statistics.median(hist_views) if hist_views else None
    comments = clean_comments(d.comments)
    label = _period_label(d)
    f: dict[str, dict | None] = {}

    f["intro"] = {
        "period": label,
        "handle": d.handle,
        "display": [f"This is @{d.handle}: {label}."],
        "how": "The period this recap covers.",
    }

    # posting
    if reels:
        days = Counter(r.posted.weekday() for r in reels)
        parts = Counter(_part_of_day(r.posted.hour) for r in reels)
        day = WEEKDAYS[max(days, key=lambda k: (days[k], -k))]
        part = max(parts, key=lambda k: (parts[k], k))
        f["posting"] = {
            "reels": len(reels),
            "top_day": day,
            "top_part": part,
            "weeks_with_post": weeks_with_post(reels),
            "chart": [days.get(i, 0) for i in range(7)],
            "display": [
                f"You posted {len(reels)} reels.",
                f"Your most common posting time: {day} {part}.",
            ],
            "how": "Counted from your public reels in this period, by the day and time you "
            "posted (your time zone).",
        }
    else:
        f["posting"] = None

    # streak: the longest run of consecutive weeks with a post
    if len(reels) >= 3:
        weeks = sorted({r.posted.date() - timedelta(days=r.posted.weekday()) for r in reels})
        best = run = 1
        for a, b in itertools.pairwise(weeks):
            run = run + 1 if (b - a).days == 7 else 1
            best = max(best, run)
        f["streak"] = (
            {
                "weeks": best,
                "display": [f"{best} weeks in a row with at least one reel."],
                "how": "The longest run of calendar weeks with at least one reel.",
            }
            if best >= 2
            else None
        )
    else:
        f["streak"] = None

    # views_total
    if with_views:
        total = sum(r.views for r in with_views)
        older = d.views_older_gained if d.kind == "monthly" else None
        if older:
            total += older
        comp = comparison_for(total)
        display = [f"Your reels were watched {fmt_in(total)} times ({fmt_short(total)})."]
        if comp:
            display.append(f"That's {comp['label']}, {comp['times']} times over.")
        f["views_total"] = {
            "views": total,
            "views_in": fmt_in(total),
            "views_short": fmt_short(total),
            "comparison": comp,
            "display": display,
            "how": (
                "Views on your reels this month (public counts): reels posted this month at "
                "their latest count, plus what older reels gained during the month."
                if d.kind == "monthly"
                else "The latest public view count of each reel in this period, added up."
            ),
        }
    else:
        f["views_total"] = None

    # beyond_followers (public proxy)
    if d.followers and with_views:
        ratios = sorted(r.views / d.followers for r in with_views)
        best_ratio = ratios[-1]
        med = statistics.median(ratios)
        f["beyond_followers"] = {
            "median_ratio": round(med, 1),
            "best_ratio": round(best_ratio, 1),
            "display": [
                f"Your best reel reached {fmt_x(best_ratio)} your follower count in views.",
                f"A typical reel reached {fmt_x(med)} your follower count.",
            ],
            "note": "Based on public views vs. your follower count.",
            "how": "Views ÷ your follower count, per reel. CURO can't see who follows whom, so "
            "this is a public stand-in for reach beyond your followers.",
        }
    else:
        f["beyond_followers"] = None

    # top_reel
    if len(with_views) >= 3:
        top = max(with_views, key=lambda r: (r.views, r.id))
        lift = (top.views / usual_views) if usual_views else None
        display = [f"“{top.title}” got {fmt_in(top.views)} views."]
        if lift:
            display.append(f"That's {fmt_x(lift)} your usual views.")
        f["top_reel"] = {
            "reel_id": top.id,
            "title": top.title,
            "views": top.views,
            "lift": round(lift, 1) if lift else None,
            "display": display,
            "how": "Your reel with the most public views in this period, against the median "
            "views of all your reels.",
        }
    else:
        f["top_reel"] = None

    # most_talked
    talk = [r for r in with_views if r.comments is not None and r.views]
    if len(talk) >= 3:
        r = max(talk, key=lambda x: (x.comments / x.views, x.id))
        f["most_talked"] = {
            "reel_id": r.id,
            "title": r.title,
            "comments": r.comments,
            "display": [f"“{r.title}” got your audience talking: {fmt_in(r.comments)} comments."],
            "how": "The reel with the most comments per view in this period.",
        }
    else:
        f["most_talked"] = None

    # most_shared
    shared = [r for r in reels if r.shares is not None]
    if len(shared) >= 2:
        r = max(shared, key=lambda x: (x.shares, x.id))
        f["most_shared"] = (
            {
                "reel_id": r.id,
                "title": r.title,
                "shares": r.shares,
                "display": [f"“{r.title}” was shared {fmt_in(r.shares)} times."],
                "how": "The public share count, where Instagram shows it.",
            }
            if r.shares > 0
            else None
        )
    else:
        f["most_shared"] = None

    # growth
    if d.kind == "monthly":
        if d.follower_start is not None and d.follower_end is not None:
            delta = d.follower_end - d.follower_start
            f["growth"] = {
                "delta": delta,
                "followers": d.follower_end,
                "display": [
                    f"{'+' if delta >= 0 else ''}{fmt_in(delta)} followers this month."
                    if delta
                    else "Your follower count held steady this month.",
                    f"You're at {fmt_in(d.follower_end)} followers.",
                ],
                "how": "Your public follower count on the first and last day CURO checked this "
                "month.",
            }
        else:
            f["growth"] = None
    elif d.followers is not None:
        m = next_milestone(d.followers)
        if m:
            gap = m - d.followers
            f["growth"] = {
                "followers": d.followers,
                "milestone": m,
                "gap": gap,
                "display": [
                    f"You have {fmt_in(d.followers)} followers.",
                    f"{fmt_in(gap)} to go until {fmt_short(m)}.",
                ],
                "how": "Your public follower count today and the next round number.",
            }
        else:
            f["growth"] = None
    else:
        f["growth"] = None

    # vs_last_month
    prev = d.previous or {}
    pv, pr = prev.get("views"), prev.get("reels")
    if d.kind == "monthly" and pv and f["views_total"]:
        change = (f["views_total"]["views"] - pv) / pv
        display = [
            f"{'Up' if change >= 0 else 'Down'} {pct(abs(change))} in views from last month."
        ]
        if pr is not None:
            display.append(f"{len(reels)} reels this month, {pr} the month before.")
        f["vs_last_month"] = {
            "views_change": round(change, 3),
            "reels": len(reels),
            "previous_reels": pr,
            "display": display,
            "how": "This month's views against last month's recap.",
        }
    else:
        f["vs_last_month"] = None

    # audience_voice
    if len(comments) >= 30:
        top_c = max(comments, key=lambda c: (c.likes, c.text))
        emojis = Counter(e for c in comments for e in _EMOJI.findall(c.text))
        themes = [t.label for t in sorted(d.themes, key=lambda t: (-t.share, t.label))[:3]]
        display = [f"Your most-liked comment ({fmt_in(top_c.likes)} likes): “{top_c.text[:90]}”"]
        if themes:
            display.append("What your audience asks for most: " + ", ".join(themes) + ".")
        if emojis:
            display.append(f"Most-used emoji: {emojis.most_common(1)[0][0]}")
        f["audience_voice"] = {
            "comments": len(comments),
            "top_comment": top_c.text[:140],
            "top_comment_likes": top_c.likes,
            "themes": themes,
            "emoji": emojis.most_common(1)[0][0] if emojis else None,
            "display": display,
            "how": f"From {fmt_in(len(comments))} public comments on this period's reels. CURO "
            "never shows who wrote them.",
        }
    else:
        f["audience_voice"] = None

    # language_mix
    langs = Counter(c.language for c in comments if c.language)
    total_l = sum(langs.values())
    if len(comments) >= 30 and len([k for k in langs if k != "mixed"]) >= 2 and total_l:
        mix = [
            (C.LANGUAGE_NAMES.get(k, k.capitalize()), v / total_l) for k, v in langs.most_common(3)
        ]
        f["language_mix"] = {
            "mix": [{"language": name, "share": round(s, 2)} for name, s in mix],
            "display": [
                "Your comment section speaks "
                + ", ".join(f"{name} ({pct(s)})" for name, s in mix)
                + "."
            ],
            "how": "The language of each public comment, labelled by CURO.",
        }
    else:
        f["language_mix"] = None

    # best_time: the creator's own history, by views against their usual
    hist = [r for r in d.history if r.views is not None and not r.paid]
    if len(hist) >= 8 and usual_views:
        slots: dict[tuple[int, int], list[float]] = {}
        for r in hist:
            slots.setdefault((r.posted.weekday(), (r.posted.hour // 2) * 2), []).append(
                r.views / usual_views
            )
        good = {k: statistics.median(v) for k, v in slots.items() if len(v) >= 2}
        if good:
            (wd, hr), lift = max(good.items(), key=lambda kv: (kv[1], -kv[0][0], -kv[0][1]))
            f["best_time"] = (
                {
                    "day": WEEKDAYS[wd],
                    "window": _window(hr),
                    "lift": round(lift, 1),
                    "reels": len(slots[(wd, hr)]),
                    "display": [
                        f"Your golden hour: {WEEKDAYS[wd]}, {_window(hr)}.",
                        f"Reels posted then got {fmt_x(lift)} your usual views.",
                    ],
                    "how": "Your reels grouped by day and two-hour window, at least 2 reels per "
                    "group, against your usual views.",
                }
                if lift > 1
                else None
            )
        else:
            f["best_time"] = None
    else:
        f["best_time"] = None

    # superpower: the strongest positive pattern card with n ≥ 5
    good_cards = [c for c in d.cards if c.n >= 5 and c.effect > 1]
    if good_cards:
        c = max(good_cards, key=lambda c: (c.effect, c.n, c.feature, c.value))
        what = label_for(c.value)
        f["superpower"] = {
            "feature": c.feature,
            "value": c.value,
            "label": what,
            "metric": c.metric,
            "effect": round(c.effect, 1),
            "n": c.n,
            "display": [
                f"Your superpower: {what.lower()} — {fmt_x(c.effect)} your usual "
                f"{METRIC_WORDS.get(c.metric, c.metric)} ({c.n} reels)."
            ],
            "how": "The pattern in your own reels with the biggest lift, found in at least 5 "
            "reels and compared with similar reels of yours without it.",
        }
    else:
        f["superpower"] = None

    # top_topic
    groups = [g for g in d.groups if g.views_lift is not None]
    if len(d.groups) >= 2 and groups:
        g = max(groups, key=lambda g: (g.views_lift, g.n, g.label))
        f["top_topic"] = (
            {
                "label": g.label,
                "lift": round(g.views_lift, 1),
                "n": g.n,
                "display": [
                    f"You're the go-to for {g.label.lower()}: those reels get "
                    f"{fmt_x(g.views_lift)} your usual views ({g.n} reels)."
                ],
                "how": "Your reels grouped by topic; the group with the best views against "
                "your usual.",
            }
            if g.views_lift > 1
            else None
        )
    else:
        f["top_topic"] = None

    # creator_type (always)
    lvl = level_for(d.followers)
    mod = modifier_for(d.total_posts, d.history, d.today or d.period_end)
    arche, runner, ev = archetype_for(d)
    name, line = C.ARCHETYPES[arche]
    f["creator_type"] = {
        "level": lvl[0] if lvl else None,
        "level_line": lvl[1] if lvl else None,
        "modifier": mod,
        "archetype": name,
        "archetype_key": arche,
        "archetype_line": line,
        "runner_up": C.ARCHETYPES[runner][0] if runner else None,
        "evidence": ev,
        "display": [
            f"You're {lvl[0] if lvl else 'a creator'} · {name}.",
            line,
        ],
        "how": "Level from your public follower count; type from how you create in this "
        "period (scores in the evidence).",
    }
    f["share_card"] = {"display": ["Your recap, ready to share."], "how": "A summary card."}
    f["next_up"] = {
        "opportunities": d.opportunities,
        "display": [
            f"{d.opportunities} opportunities are waiting for you."
            if d.opportunities
            else "Your opportunities are on the way."
        ],
        "how": "Opportunity areas ready on your Home.",
    }
    f.update(persona_facts(d))
    if f.get("followers_summary"):  # the share card's avatar row (names only)
        f["share_card"]["personas"] = f["followers_summary"]["personas"]
    return f


# ------------------------------------------------------------------ Meet your followers (v2.2 §4)

PERSONA_SLIDES = ("persona_1", "persona_2", "persona_3", "persona_4")


def _plural(short: str) -> str:
    return short if short.endswith(("s", "Crowd")) else f"{short}s"


def persona_facts(d: RecapInput) -> dict[str, dict | None]:
    """followers_intro, persona_1…4, followers_summary and (monthly) followers_shift. Shares
    are the personas' own (code); their lines come from T26, already checked."""
    out: dict[str, dict | None] = {s: None for s in C.PERSONA_SEQUENCE}
    ps = d.personas
    if len(ps) != 4:
        return out
    early = bool(ps[0].get("is_starter"))
    small = [
        {k: p[k] for k in ("id", "name", "short_name", "share_pct", "color", "avatar_seed")}
        for p in ps
    ]
    out["followers_intro"] = {
        "personas": small,
        "early_guess": early,
        "display": ["Now meet the people who watch you."],
        "how": "Four groups found in your public comments. Personas are summaries, not real "
        "people.",
    }
    for slide, p in zip(PERSONA_SLIDES, ps, strict=True):
        out[slide] = {
            **{k: p[k] for k in ("id", "name", "short_name", "share_pct", "color", "avatar_seed")},
            "tagline": p["tagline"],
            "comes_for": p["comes_for"][:3],
            "thought": p["thought"],
            "early_guess": early,
            "display": [f"{p['share_pct']}% of your comments", p["tagline"]],
            "how": "A group of your public comments, written as a character. "
            + ("An early guess: it gets sharper as people comment." if early else ""),
        }
    out["followers_summary"] = {
        "personas": small,
        "early_guess": early,
        "display": [", ".join(f"{p['short_name']} {p['share_pct']}%" for p in ps)],
        "how": "Shares of your comments, by group.",
    }
    if d.kind == "monthly" and d.persona_previous is not None and not early:
        moves = []
        for p in ps:
            before = d.persona_previous.get(str(p["id"]))
            if before is None:
                moves.append((1.0, f"A new group is showing up: {p['name']}.", p))
            elif abs(p["share"] - before) >= C.PERSONA_SHIFT_POINTS:
                verb = "grew" if p["share"] > before else "went"
                line = (
                    f"{_plural(p['short_name'])} {verb} from {round(100 * before)}% to "
                    f"{p['share_pct']}% of your comments this month."
                )
                moves.append((abs(p["share"] - before), line, p))
        if moves:
            moves.sort(key=lambda m: -m[0])
            out["followers_shift"] = {
                "persona_id": str(moves[0][2]["id"]),
                "color": moves[0][2]["color"],
                "avatar_seed": moves[0][2]["avatar_seed"],
                "display": [m[1] for m in moves[:3]],
                "how": "Each group's share of your comments against last month.",
            }
    return out


def choose(facts: dict[str, dict | None]) -> list[str]:
    """The slides whose rule passed, in story order, capped at 12 — or 18 with the persona
    sequence, which is never dropped."""
    chosen = [s for s in C.ORDER if facts.get(s) is not None]
    cap = C.MAX_SLIDES_WITH_PERSONAS if facts.get("followers_intro") else C.MAX_SLIDES
    for s in C.DROP_FIRST:
        if len(chosen) <= cap:
            break
        if s in chosen:
            chosen.remove(s)
    return chosen


def visuals(slides: list[str], facts: dict[str, dict | None]) -> dict[str, dict]:
    """Background and text colour per slide (rotating), plus motion hints."""
    out = {}
    for i, s in enumerate(slides):
        bg, fg = C.BACKGROUNDS[i % len(C.BACKGROUNDS)]
        if s == "creator_type":
            bg, fg = "ink", "white"
        elif s in C.PERSONA_SEQUENCE:
            colour = (facts.get(s) or {}).get("color")
            bg, fg = C.PERSONA_BACKGROUNDS.get(colour or "", ("white", "ink"))
        out[s] = {
            "bg": bg,
            "fg": fg,
            "accent": "blue" if bg != "ink" else "lavender",
            "milestone": s in C.MILESTONE_SLIDES,
            "seconds": 8 if s in C.LONG_SLIDES else 6,
        }
    return out


def share_stats(facts: dict[str, dict | None]) -> list[dict]:
    """The 3–4 headline stats for the share card and Home's highlight cards."""
    out = []
    if facts.get("views_total"):
        out.append(
            {"slide": "views_total", "label": "views", "value": facts["views_total"]["views_short"]}
        )
    if facts.get("posting"):
        out.append({"slide": "posting", "label": "reels", "value": str(facts["posting"]["reels"])})
    if facts.get("top_reel") and facts["top_reel"].get("lift"):
        out.append(
            {
                "slide": "top_reel",
                "label": "best reel vs usual",
                "value": fmt_x(facts["top_reel"]["lift"]),
            }
        )
    if facts.get("growth") and facts["growth"].get("delta") is not None:
        d = facts["growth"]["delta"]
        out.append(
            {
                "slide": "growth",
                "label": "new followers",
                "value": f"{'+' if d >= 0 else ''}{fmt_short(d)}",
            }
        )
    elif facts.get("growth"):
        out.append(
            {
                "slide": "growth",
                "label": "followers",
                "value": fmt_short(facts["growth"]["followers"]),
            }
        )
    if len(out) < 4 and facts.get("streak"):
        out.append(
            {"slide": "streak", "label": "week streak", "value": str(facts["streak"]["weeks"])}
        )
    if len(out) < 4 and facts.get("most_talked"):
        out.append(
            {
                "slide": "most_talked",
                "label": "comments on one reel",
                "value": fmt_short(facts["most_talked"]["comments"]),
            }
        )
    return out[:4]  # fmt: skip


@dataclass
class Recap:
    slides: list[str]
    facts: dict[str, dict | None]
    visuals: dict[str, dict]
    stats: list[dict]
    level: str | None
    modifier: str | None
    archetype: str
    runner_up: str | None
    evidence: dict


def build(d: RecapInput) -> Recap:
    facts = slide_facts(d)
    slides = choose(facts)
    ct = facts["creator_type"]
    return Recap(
        slides=slides,
        facts=facts,
        visuals=visuals(slides, facts),
        stats=share_stats(facts),
        level=ct["level"],
        modifier=ct["modifier"],
        archetype=ct["archetype"],
        runner_up=ct["runner_up"],
        evidence=ct["evidence"],
    )


# ------------------------------------------------------------------ template copy (fallback)


def template_copy(slide: str, facts: dict) -> tuple[str, str]:
    """A plain headline and subline from the facts alone (T23's fallback and the mock)."""
    shown = facts.get("display") or [""]
    g = facts.get
    if slide == "intro":
        head = "Your story so far" if g("period") == "your story so far" else f"Your {g('period')}"
        return head[:60], f"@{g('handle')}, let's unpack it."[:90]
    # Slides with a big count-up number: the headline names it rather than repeating it.
    if slide == "posting":
        return "reels, posted by you", f"{g('top_day')} {g('top_part')}s were your thing."
    if slide == "streak":
        return "in a row with a new reel", "You kept showing up, week after week."
    if slide == "views_total":
        comp = g("comparison")
        sub = (
            f"That's {comp['label']}, {comp['times']} times over."
            if comp
            else "Every one of those was someone watching you."
        )
        return "times your reels were watched", sub[:90]
    if slide == "beyond_followers":
        return "your follower count, in views", "Lots of new people found your best reel."
    if slide == "top_reel":
        if g("lift"):
            return "Your biggest hit", f"{fmt_x(g('lift'))} your usual views."
        return "Your biggest hit", f"{fmt_in(g('views'))} views."
    if slide == "most_talked":
        return "This one got everyone talking", f"{fmt_in(g('comments'))} comments."
    if slide == "most_shared":
        return "People couldn't stop sending this", f"{fmt_in(g('shares'))} shares."
    if slide == "growth":
        if g("delta") is not None:
            d = g("delta")
            if d > 0:
                return "new followers this month", "Your community grew."
            return "A steady month", f"You're at {fmt_in(g('followers'))} followers."
        return (
            f"followers to go until {fmt_short(g('milestone'))}",
            f"You're at {fmt_in(g('followers'))} now.",
        )
    if slide == "vs_last_month":
        ch = g("views_change")
        return (f"{'Up' if ch >= 0 else 'Down'} {pct(abs(ch))} in views",
                "Against last month." if ch >= 0 else "A quieter month, and you kept going.")  # fmt: skip
    if slide == "audience_voice":
        themes = g("themes") or []
        return "What your audience said", (
            ", ".join(themes) if themes else f"“{g('top_comment')[:70]}”"
        )[:90]
    if slide == "language_mix":
        mix = g("mix") or []
        return f"Your comments speak {mix[0]['language']}", shown[0][:90]
    if slide == "best_time":
        return "Your golden hour", f"{g('day')}, {g('window')}."
    if slide == "superpower":
        return "Your superpower", f"{g('label')}: {fmt_x(g('effect'))} your usual."[:90]
    if slide == "top_topic":
        return f"The go-to for {g('label').lower()}"[
            :60
        ], f"{fmt_x(g('lift'))} your usual views there."
    if slide == "creator_type":
        lvl = g("level") or "A creator"
        return f"{lvl} · {g('archetype')}"[:60], (g("archetype_line") or "")[:90]
    if slide == "share_card":
        return "Your recap card", "Share it or save it."
    if slide == "followers_intro":
        return "Meet your followers", "Now meet the people who watch you."
    if slide in PERSONA_SLIDES:
        return (g("name") or "")[:60], f"{g('share_pct')}% of your comments"
    if slide == "followers_summary":
        return "Your follower groups", "Tap any of them on Home to get to know them."
    if slide == "followers_shift":
        return "Your followers are shifting", shown[0][:90]
    if slide == "next_up":
        n = g("opportunities")
        return "Your next month starts here", (
            f"{n} opportunities are waiting." if n else "Trends and ideas are waiting on your Home."
        )
    return shown[0][:60], ""  # pragma: no cover
