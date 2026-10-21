"""Mock stand-in for T15 (propose edits): one concrete change per factor holding a draft back,
written only from the factor itself. The backend re-scores each one before showing it."""

from __future__ import annotations

from curo.schemas.tasks import EditProposal, T15Input, T15Output

BAND_WORDS = {
    "under_20s": "under 20 seconds",
    "20_to_40s": "20–40 seconds",
    "over_40s": "over 40 seconds",
}


def _edit(f, data: T15Input) -> EditProposal | None:
    change = {f.feature: f.better}
    if f.feature == "payoff_band" and f.better == "under_2s":
        return EditProposal(
            title="Show the final look first",
            description="Open on the finished look for a second, then go back to the start. "
            "The payoff then lands in the first 2 seconds.",
            feature_change={**change, "opening_style": "final_look_first"},
            effort="edit_only",
        )
    if f.feature == "opening_style" and f.better == "final_look_first":
        return EditProposal(
            title="Open on the finished look",
            description="Start with the final look, then rewind to the plain outfit.",
            feature_change={**change, "payoff_band": "under_2s"},
            effort="edit_only",
        )
    if f.feature == "cta_type" and f.better == "share_prompt":
        return EditProposal(
            title="End with a send prompt",
            description="Ask viewers to send it to the friend they’re getting ready with, not only "
            "to comment.",
            feature_change=change,
            effort="reshoot",
        )
    if f.feature == "cta_type" and f.better == "comment_prompt":
        return EditProposal(
            title="Ask for a comment at the end",
            description="Close by asking viewers to tell you their pick in the comments.",
            feature_change=change,
            effort="reshoot",
        )
    if f.feature == "ending" and f.better == "choice_question":
        return EditProposal(
            title="End on a choice question",
            description="Ask viewers which look they’d pick before you close.",
            feature_change=change,
            effort="reshoot",
        )
    if f.feature == "ending" and f.better == "final_look":
        return EditProposal(
            title="End on the final look",
            description="Close on the finished look and hold it for a beat.",
            feature_change=change,
            effort="edit_only",
        )
    if f.feature == "duration_band" and f.better in BAND_WORDS:
        return EditProposal(
            title=f"Trim it to {BAND_WORDS[f.better]}",
            description="Cut the pauses between looks so it lands sooner.",
            feature_change=change,
            effort="edit_only",
        )
    if f.feature == "onscreen_text" and f.better == "yes":
        return EditProposal(
            title="Add a label to each look",
            description="Put a few words on screen for each look, for people watching without "
            "sound.",
            feature_change=change,
            effort="edit_only",
        )
    if f.feature == "pace" and f.better == "fast":
        return EditProposal(
            title="Cut on the beat",
            description="Tighten the cuts between looks so the reel moves faster.",
            feature_change=change,
            effort="edit_only",
        )
    if f.feature == "hook_type":
        return EditProposal(
            title="Open with a stronger promise",
            description="Re-record the first line so it promises what the reel shows.",
            feature_change=change,
            effort="reshoot",
        )
    return None  # nothing a creator can change after recording (e.g. the topic's tension)


def t15(data: T15Input) -> T15Output:
    out, seen = [], set()
    for f in data.factors:
        edit = _edit(f, data)
        if edit and edit.title not in seen:
            seen.add(edit.title)
            out.append(edit)
    return T15Output(edits=out[:8])
