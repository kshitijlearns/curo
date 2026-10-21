"""Chat and voice requests in Studio, sorted into actions (logic doc §10–§12, T13).

T13 reads the instruction and returns an action, its targets and parameters; this module
holds each step's actions, fills in targets the action implies (a new hook targets the hook
beat), falls back sensibly when the model names something else, and writes Curo's reply from
what was actually done.
"""

from __future__ import annotations

from dataclasses import dataclass, field

ACTIONS: dict[str, tuple[str, ...]] = {
    "script": (
        "rewrite_hook",
        "change_tone",
        "shorten",
        "expand",
        "change_ending",
        "edit_line",
        "regenerate",
    ),
    "storyboard": (
        "change_shot",
        "another_opening",
        "easier",
        "change_transition",
        "pacing",
        "visual_treatment",
    ),
    # "own": the text isn't a request but the creator's own caption, kept as written.
    "caption": ("shorter", "playful", "question", "polish", "rewrite", "own"),
}
FALLBACK = {"script": "regenerate", "storyboard": "change_shot", "caption": "rewrite"}


@dataclass
class Route:
    action: str
    targets: list[str] = field(default_factory=list)
    params: dict[str, str | float] = field(default_factory=dict)


def resolve(
    step: str, action: str, targets: list[str], params: dict, items: list[dict], current: str | None
) -> Route:
    """A valid action with the targets it implies. ``items`` are beats ({id, role}) or frames
    ({beat_id}); ``current`` is the frame on screen."""
    if action not in ACTIONS[step]:
        action = FALLBACK[step]
    ids = [i["id"] if "id" in i else i["beat_id"] for i in items]
    targets = [t for t in targets if t in ids]
    if step == "script":
        by_role = {i["role"]: i["id"] for i in items}
        if action == "rewrite_hook":
            targets = [i["id"] for i in items if i["role"] == "hook"][:1]
        elif action == "change_ending":
            targets = [i["id"] for i in items if i["role"] == "ending"][-1:] or [ids[-1]]
        elif action in ("change_tone", "shorten", "expand", "regenerate"):
            targets = ids
        elif action == "edit_line" and not targets:
            targets = [by_role.get("hook", ids[0])]
    elif step == "storyboard":
        if action == "another_opening":
            targets = ids[:1]
        elif action in ("easier", "pacing"):
            targets = ids
        elif not targets:
            targets = [current] if current in ids else ids[:1]
    return Route(action, targets, dict(params))


def script_reply(route: Route, beats: list[dict], seconds: float, changed: list[str]) -> str:
    a = route.action
    if not changed and a not in ("regenerate",):
        return "That didn’t change anything in the script — try asking for a new hook, a different ending, or a shorter cut."
    if a == "rewrite_hook":
        return "Rewrote the hook. The rest of the script is unchanged."
    if a == "change_tone":
        return "Rewrote it to sound more like you talking to a friend. Same beats, same order."
    if a == "shorten":
        return f"Cut it down to about {round(seconds)} seconds — same structure, fewer words."
    if a == "expand":
        return f"Expanded it to about {round(seconds)} seconds so each beat has room."
    if a == "change_ending":
        ending = next((b for b in beats if b["id"] in changed), None)
        if ending and "save" in ending["text"].lower():
            return (
                "Changed the ending to a save prompt. Saves aren’t public, so Curo can’t measure "
                "them; it will track likes and shares instead."
            )
        return "Changed the ending — its note now matches the new line."
    if a == "edit_line":
        index = next((i for i, b in enumerate(beats, start=1) if b["id"] in changed), None)
        return (
            f"Rewrote line {index}. The other lines are unchanged."
            if index
            else "Rewrote that line."
        )
    return "Regenerated the full script. Same idea, a different way in."


def storyboard_reply(
    route: Route, frames: list[dict], feasibility: dict, changed: list[str]
) -> str:
    a = route.action
    index = next(
        (i for i, f in enumerate(frames, start=1) if f["beat_id"] in (changed or route.targets)),
        None,
    )
    if a == "easier":
        if not changed:
            return f"It’s already as simple as it gets: {feasibility['detail']}."
        return f"Made it easier to record: {feasibility['detail']}. The opening shot is unchanged."
    if a == "pacing":
        total = frames[-1]["end_s"] if frames else 0
        return f"Changed the pacing — it now runs about {round(total)} seconds."
    if a == "another_opening":
        return "Swapped the opening shot."
    if a == "change_transition":
        return f"Changed the transition into frame {index}." if index else "Changed the transition."
    if a == "visual_treatment":
        return f"Changed the look of frame {index}." if index else "Changed the look of that frame."
    return f"Here’s a different shot for frame {index}." if index else "Here’s a different shot."


CAPTION_REPLIES = {
    "shorter": "Shorter options — each fits before Instagram’s “more” cut-off.",
    "playful": "More playful options, in your usual caption style.",
    "question": "Each option now ends on a question, to invite comments.",
    "polish": "Polished your caption. The meaning is unchanged.",
    "rewrite": "Here are three new captions based on that.",
}
