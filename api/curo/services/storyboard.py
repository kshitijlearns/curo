"""Studio step 3: the storyboard (logic doc §11).

Each frame is one script beat turned into a shot the creator can film with the setups they
already use; frames link to beats by id, so script and storyboard never drift apart.

* Timing: each beat's words at the creator's speaking speed ("0:00 – 0:04").
* Shots: from the creator's own toolkit (cameras, places and light in their Production DNA).
* Devices: proven visual devices — from peer outliers of the same format and from the
  creator's own pattern cards (showing the result in the first 2 seconds, say).
* Feasibility: four costs — locations, a second person, outfit or prop changes, lighting
  changes. "Make this easier" merges locations, swaps helper shots for tripod shots and keeps
  one light, leaving the hook frame as it is; that is enforced here, not left to the model.
* Pacing changes frame durations but keeps the total inside the creator's best length band.
"""

from __future__ import annotations

from dataclasses import dataclass

from curo.services.script import fmt_time

HARD_COST, MODERATE_COST = 3.5, 1.5


# ------------------------------------------------------------------ devices


@dataclass
class DeviceSource:
    """A proven visual device and where it comes from."""

    line: str
    source: str  # "yours" | "creators like you"


def devices(creator_cards: list[dict]) -> list[DeviceSource]:
    """Devices from the pattern cards that lift results: the creator's own, or the cold-start
    priors "based on creators like you" (v2: no peers)."""
    out: list[DeviceSource] = []
    for c in creator_cards:
        if c["effect"] <= 1.0:
            continue
        if (c["feature"], c["value"]) == ("payoff_band", "under_2s"):
            out.append(
                DeviceSource("Show the finished result within the first 2 seconds.", "yours")
            )
        elif (c["feature"], c["value"]) == ("ending", "final_look"):
            out.append(DeviceSource("Hold the final look for a beat at the end.", "yours"))
        elif (c["feature"], c["value"]) == ("opening_style", "final_look_first"):
            out.append(DeviceSource("Open on the final look, then rewind to the start.", "yours"))
        elif (c["feature"], c["value"]) == ("pace", "fast"):
            out.append(DeviceSource("Snap cut on the beat between looks.", "yours"))
    seen, unique = set(), []
    for d in out:
        if d.line not in seen:
            seen.add(d.line)
            unique.append(d)
    return unique


# ------------------------------------------------------------------ frames


def assemble(beats: list[dict], drawn: list[dict]) -> list[dict]:
    """T11's frames joined to the script beats they show (by beat id), with the beat's line and
    timing. A beat T11 left out gets no frame rather than an invented one."""
    by_beat = {f["beat_id"]: f for f in drawn}
    out = []
    for b in beats:
        f = by_beat.get(b["id"])
        if f is None:
            continue
        out.append(
            {
                **f,
                "id": f"f-{b['id']}",
                "beat_id": b["id"],
                "line": b["text"],
                "start_s": b["start_s"],
                "end_s": b["end_s"],
                "t": f"{fmt_time(b['start_s'])} – {fmt_time(b['end_s'])}",
            }
        )
    return out


def stale(frames: list[dict], beats: list[dict]) -> list[str]:
    """Frames whose beat changed (text or timing) or disappeared since they were drawn."""
    current = {b["id"]: b for b in beats}
    out = []
    for f in frames:
        b = current.get(f["beat_id"])
        if b is None or b["text"] != f.get("line"):
            out.append(f["id"])
    return out


# ------------------------------------------------------------------ feasibility


def _known(values: list[str | None]) -> set[str]:
    return {v for v in values if v and v != "unknown"}


def feasibility(frames: list[dict]) -> dict:
    """Four costs → a score (100 = nothing to arrange) and a plain label."""
    locations = max(0, len(_known([f.get("setting") for f in frames])) - 1)
    helper = 1 if any(f.get("needs_helper") for f in frames) else 0
    changes = sum(1 for f in frames if f.get("outfit_change"))
    lighting = max(0, len(_known([f.get("lighting") for f in frames])) - 1)
    cost = locations + 2 * helper + 0.5 * changes + lighting
    label = "Easy" if cost <= MODERATE_COST else "Moderate" if cost <= HARD_COST else "Hard"
    detail = [
        "one location" if not locations else f"{locations + 1} locations",
        "no helper needed" if not helper else "needs a second person",
    ]
    if changes:
        detail.append(f"{changes} outfit or prop change{'s' if changes > 1 else ''}")
    detail.append("one light setup" if not lighting else f"{lighting + 1} light setups")
    return {
        "label": label,
        "score": round(100 * max(0.0, 1 - cost / 6)),
        "detail": " · ".join(detail),
        "costs": {
            "locations": locations,
            "helper": helper,
            "changes": changes,
            "lighting": lighting,
        },
    }


def make_easier(frames: list[dict], toolkit_camera: str | None) -> tuple[list[dict], list[str]]:
    """One location, no helper, one light — the hook frame kept as it is. Returns the frames
    and the beat ids whose shot changed (T11 rewrites their instructions)."""
    if not frames:
        return frames, []
    rest = frames[1:]
    settings = [f.get("setting") for f in frames if f.get("setting") not in (None, "unknown")]
    lights = [f.get("lighting") for f in frames if f.get("lighting") not in (None, "unknown")]
    place = max(set(settings), key=settings.count) if settings else None
    light = max(set(lights), key=lights.count) if lights else None
    camera = (
        "tripod" if toolkit_camera in (None, "unknown", "handheld", "mixed") else toolkit_camera
    )
    out, changed = [frames[0]], []
    for f in rest:
        g = dict(f)
        if place:
            g["setting"] = place
        if light:
            g["lighting"] = light
        if g.get("needs_helper"):
            g["needs_helper"] = False
            g["camera"] = camera
        if g != f:
            changed.append(f["beat_id"])
        out.append(g)
    return out, changed


def repace(frames: list[dict], faster: bool, band: tuple[float, float]) -> list[dict]:
    """Shorten or lengthen every frame by 15%, keeping the total inside the length band."""
    if not frames:
        return frames
    total = frames[-1]["end_s"] - frames[0]["start_s"]
    target = total * (0.85 if faster else 1.15)
    target = min(max(target, band[0]), band[1])
    k = target / total if total else 1.0
    out, t = [], 0.0
    for f in frames:
        d = (f["end_s"] - f["start_s"]) * k
        out.append(
            {
                **f,
                "start_s": round(t, 1),
                "end_s": round(t + d, 1),
                "t": f"{fmt_time(t)} – {fmt_time(t + d)}",
            }
        )
        t += d
    return out


def label_frames(frames: list[dict], max_words: int = 4) -> tuple[list[dict], list[str]]:
    """On-screen text for every frame that has none: the first words of its line, for people
    watching without sound. Returns the frames and the beat ids that changed."""
    out, changed = [], []
    for f in frames:
        if f.get("onscreen_text"):
            out.append(f)
            continue
        line = f.get("line") or ""
        head = line.split(":", 1)[0]  # "Look number 1: belted…" is labelled "Look number 1"
        if ":" in line and len(head.split()) <= max_words:
            line = head
        words = [w.strip('.,!?:;“”"') for w in line.split()][:max_words]
        label = " ".join(w for w in words if w)[:60]
        if label:
            changed.append(f["beat_id"])
            out.append({**f, "onscreen_text": label})
        else:
            out.append(f)
    return out, changed
