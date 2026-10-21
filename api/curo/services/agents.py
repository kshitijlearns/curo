"""The Simulator's AI audience (v2, PLAN_V2 §4.5): pure arithmetic over agents' reactions.

* ``allocate`` splits N agents across the creator's audience segments by share.
* ``timeline`` turns T1's understanding into what every agent sees.
* ``rates`` counts what the agents did: views = agents who didn't skip; likes, comments,
  shares and saves as a share of the agents who watched.
* ``calibrate``: for each public metric m, k_m = exp(mean(ln(real_rate_r / agent_rate_r)))
  over the creator's past reels, with p10/p90 of those ratios as the range.
* ``predict``: calibrated rate = agent rate × k_m, range × (p10/k, p90/k); counts = the
  creator's 7-day usual views × rate. Saves have no public count to calibrate on, so they use
  the likes factor and are always labelled "simulated".
* ``engagement``: E = like_rate + 3·comment_rate + 4·share_rate (calibrated); the score is the
  share of the creator's past reels whose real E it beats (0–100).
* ``skip_curve``: the share of agents still watching at each second.

Missing stays missing: no calibration → no counts, only the agents' own rates.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from curo.schemas.tasks import (
    Reaction,
    Segment,
    T1Output,
    T21Output,
    TimedPoint,
    Timeline,
    TimelinePoint,
)

METRICS = ("views", "likes", "comments", "shares")
E_WEIGHTS = {"likes": 1.0, "comments": 3.0, "shares": 4.0}
MIN_PAST_FOR_SCORE = 5
SHARE_PROMPT = re.compile(
    r"\b(send (this|it)|share (this|it)|tag (a|your)|bhejo|send to)\b", re.IGNORECASE
)
SAVE_PROMPT = re.compile(r"\b(save (this|it)|save for later)\b", re.IGNORECASE)


def allocate(segments: list[Segment], n: int) -> dict[str, int]:
    """Agents per segment by share, largest remainder; every segment gets at least one."""
    total = sum(s.share for s in segments) or 1.0
    raw = {s.key: n * s.share / total for s in segments}
    out = {k: max(1, math.floor(v)) for k, v in raw.items()}
    left = n - sum(out.values())
    for k in sorted(raw, key=lambda k: (-(raw[k] - math.floor(raw[k])), k)):
        if left <= 0:
            break
        out[k] += 1
        left -= 1
    while left < 0:  # the "at least one" pushed it over: take from the largest
        k = max(out, key=lambda k: (out[k], k))
        out[k] -= 1
        left += 1
    return out


def timeline(t1: T1Output | dict, caption: str = "", duration_s: float | None = None) -> Timeline:
    t1 = t1 if isinstance(t1, T1Output) else T1Output.model_validate(t1 or {})
    points: list[TimelinePoint] = []
    for d in t1.seconds:
        points.append(TimelinePoint(t=d.t, what=d.description))
    for o in t1.onscreen_text:
        points.append(TimelinePoint(t=o.t, what=f"On screen: {o.text}"))
    spoken = [w for w in t1.transcript]
    if spoken:
        # Group the words into lines of about three seconds.
        start, words = spoken[0].t, []
        for w in spoken:
            if w.t - start > 3 and words:
                points.append(TimelinePoint(t=start, what=f"Says: {' '.join(words)}"))
                start, words = w.t, []
            words.append(w.word)
        if words:
            points.append(TimelinePoint(t=start, what=f"Says: {' '.join(words)}"))
    points.sort(key=lambda p: (p.t, p.what))
    firsts = [p.t for p in points if p.what.startswith(("Says:", "On screen:"))]
    text = " ".join([caption, t1.transcript_text(), *(o.text for o in t1.onscreen_text)])
    return Timeline(
        duration_s=duration_s or t1.duration_s,
        hook_s=min(firsts) if firsts else None,
        payoff_s=t1.first_payoff_s,
        points=points[:60],
        caption=caption,
        has_share_prompt=bool(SHARE_PROMPT.search(text)),
        has_question="?" in text,
        has_save_prompt=bool(SAVE_PROMPT.search(text)),
    )


# ------------------------------------------------------------------ rates


@dataclass
class Rates:
    n: int
    watched: int
    likes: int
    comments: int
    shares: int
    saves: int

    def rate(self, metric: str) -> float | None:
        if metric == "views":
            return self.watched / self.n if self.n else None
        count = {"likes": self.likes, "comments": self.comments, "shares": self.shares}.get(
            metric, self.saves if metric == "saves" else None
        )
        if count is None or not self.watched:
            return None
        return count / self.watched


def rates(reactions: list[Reaction]) -> Rates:
    watched = [r for r in reactions if not r.skipped]
    return Rates(
        n=len(reactions),
        watched=len(watched),
        likes=sum(r.liked for r in watched),
        comments=sum(r.commented for r in watched),
        shares=sum(r.shared for r in watched),
        saves=sum(r.saved for r in watched),
    )


def skip_curve(reactions: list[Reaction], duration_s: float | None) -> list[dict]:
    """Share of all agents still watching at each whole second (0 … duration)."""
    if not reactions:
        return []
    end = math.ceil(duration_s or max(r.watch_until_s for r in reactions))
    n = len(reactions)
    return [
        {"t": s, "watching": round(sum(1 for r in reactions if r.watch_until_s >= s) / n, 3)}
        for s in range(0, end + 1)
    ]


# ------------------------------------------------------------------ calibration


@dataclass
class Factor:
    metric: str
    k: float | None
    low: float | None
    high: float | None
    n: int


def _pct(values: list[float], q: float) -> float:
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    pos = q * (len(s) - 1)
    lo = math.floor(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def calibrate(pairs: dict[str, list[tuple[float | None, float | None]]]) -> dict[str, Factor]:
    """``pairs[metric]`` = [(real rate, agent rate)] per past reel; a missing side is skipped."""
    out = {}
    for m in METRICS:
        ratios = [real / agent for real, agent in pairs.get(m, []) if real and agent]
        if not ratios:
            out[m] = Factor(m, None, None, None, 0)
            continue
        k = math.exp(sum(math.log(x) for x in ratios) / len(ratios))
        low, high = (_pct(ratios, 0.1), _pct(ratios, 0.9)) if len(ratios) >= 3 else (k / 2, k * 2)
        out[m] = Factor(m, k, min(low, k), max(high, k), len(ratios))
    return out


# ------------------------------------------------------------------ prediction


@dataclass
class Prediction:
    metric: str
    rate: float | None  # calibrated
    low: float | None
    high: float | None
    count: int | None
    count_low: int | None
    count_high: int | None
    simulated: bool  # saves: no public count to calibrate on


def predict(r: Rates, factors: dict[str, Factor], usual_views: float | None) -> list[Prediction]:
    out = []
    for m in (*METRICS, "saves"):
        f = factors.get("likes" if m == "saves" else m)
        agent = r.rate(m)
        if agent is None or f is None or f.k is None:
            out.append(Prediction(m, None, None, None, None, None, None, m == "saves"))
            continue
        rate, low, high = agent * f.k, agent * (f.low or f.k), agent * (f.high or f.k)
        if m == "views":
            count = _count(usual_views, rate)
            c_low, c_high = _count(usual_views, low), _count(usual_views, high)
        else:
            views = next((p for p in out if p.metric == "views"), None)
            base = views.count if views else None
            count, c_low, c_high = _count(base, rate), _count(base, low), _count(base, high)
        out.append(Prediction(m, rate, low, high, count, c_low, c_high, m == "saves"))
    return out


def _count(base: float | None, rate: float | None) -> int | None:
    if base is None or rate is None:
        return None
    return round(base * rate)


def engagement(by_metric: dict[str, float | None]) -> float | None:
    """E = like_rate + 3·comment_rate + 4·share_rate; None if any part is unknown."""
    parts = [by_metric.get(m) for m in E_WEIGHTS]
    if any(p is None for p in parts):
        return None
    return sum(E_WEIGHTS[m] * by_metric[m] for m in E_WEIGHTS)  # type: ignore[operator]


def engagement_score(e: float | None, past: list[float]) -> int | None:
    """The share of past reels' real E that this beats, as 0–100 (needs 5 past reels)."""
    if e is None or len(past) < MIN_PAST_FOR_SCORE:
        return None
    beaten = sum(1 for p in past if e > p)
    return round(100 * beaten / len(past))


# ------------------------------------------------------------------ what the explanation reads


def _mmss(s: float) -> str:
    s = max(0, round(s))
    return f"{s // 60}:{s % 60:02d}"


def facts(
    r: Rates,
    curve: list[dict],
    reactions: list[Reaction],
    tl: Timeline,
    labels: dict[str, str],
    segment_of: dict[int, str],
) -> list[str]:
    """Tagged facts for T21: "[working|holding|edit at_s] sentence". Numbers only from here."""
    out: list[str] = []
    n = r.n or 1
    if curve:
        drops = [
            (curve[i - 1]["watching"] - curve[i]["watching"], curve[i]["t"])
            for i in range(1, len(curve))
        ]
        drop, at = max(drops, key=lambda d: (d[0], -d[1])) if drops else (0.0, 0)
        gone = 1 - curve[min(at, len(curve) - 1)]["watching"]
        if drop > 0:
            out.append(
                f"[holding {at}] {round(100 * gone)}% of agents had stopped watching by "
                f"{_mmss(at)}."
            )
        end = curve[-1]["watching"]
        tag = "working" if end >= 0.35 else "holding"
        out.append(f"[{tag} {curve[-1]['t']}] {round(100 * end)}% of agents watched to the end.")
    if tl.payoff_s is not None:
        if tl.payoff_s <= 2:
            out.append(f"[working {tl.payoff_s:g}] The result shows by {_mmss(tl.payoff_s)}.")
        else:
            out.append(
                f"[holding {tl.payoff_s:g}] The result only shows at {_mmss(tl.payoff_s)}; "
                "many agents had scrolled on by then."
            )
            out.append(
                "[edit 0] Open on the finished result, then show how you got there "
                f"(it now shows at {_mmss(tl.payoff_s)})."
            )
    if r.watched:
        out.append(
            f"[working] {round(100 * r.likes / r.watched)}% of the agents who watched liked it."
        )
    end_s = tl.duration_s or (curve[-1]["t"] if curve else 0)
    if not tl.has_share_prompt:
        out.append(
            f"[edit {end_s:g}] Add a send prompt at the end: say who to send it to "
            f"({r.shares} of {r.watched} watching agents shared it)."
        )
    else:
        out.append(f"[working {end_s:g}] The send prompt got {r.shares} agents to share it.")
    if not tl.has_question:
        out.append(f"[edit {end_s:g}] End on a question so the audience has something to answer.")
    else:
        out.append(f"[working {end_s:g}] The question brought {r.comments} agent comments.")
    # Which segment stayed least.
    by_seg: dict[str, list[Reaction]] = {}
    for x in reactions:
        by_seg.setdefault(segment_of.get(x.agent_no, ""), []).append(x)
    stay = {k: sum(1 for x in v if not x.skipped) / len(v) for k, v in by_seg.items() if k and v}
    if stay:
        worst = min(stay, key=lambda k: (stay[k], k))
        best = max(stay, key=lambda k: (stay[k], k))
        out.append(
            f"[holding] Only {round(100 * stay[worst])}% of {labels.get(worst, worst)} agents "
            "kept watching."
        )
        out.append(
            f"[working] {round(100 * stay[best])}% of {labels.get(best, best)} agents kept "
            "watching."
        )
    out.append(f"[context] {n} agents saw it; {r.watched} watched past the first seconds.")
    return out


TAGGED = re.compile(r"^\[(working|holding|edit)(?: (\d+(?:\.\d+)?))?\] (.+)$")


def template_explanation(fact_lines: list[str]) -> T21Output:
    """The first three tagged facts of each kind, word for word."""
    out: dict[str, list[TimedPoint]] = {"working": [], "holding": [], "edit": []}
    for f in fact_lines:
        m = TAGGED.match(f)
        if not m:
            continue
        kind, at, text = m.groups()
        if len(out[kind]) < 3:
            out[kind].append(TimedPoint(text=text, at_s=float(at) if at else None))
    return T21Output(working=out["working"], holding=out["holding"], edits=out["edit"])
