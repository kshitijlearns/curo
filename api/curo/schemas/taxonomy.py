"""The fixed DNA taxonomy (logic doc §4).

Production and Content DNA use closed lists so reels can be compared and counted; free text
(the hook's words, key entities) is kept beside the fixed values for the AI to read. Every
field also allows ``unknown``: a field whose confidence is below 0.6 is stored as unknown
rather than guessed (logic doc §5 step 3).
"""

from __future__ import annotations

UNKNOWN = "unknown"
MIN_CONFIDENCE = 0.6

# ------------------------------------------------------------------ Content DNA (what it's about)

CONTENT_FIELDS: dict[str, tuple[str, ...]] = {
    # The broad cluster; finer sub-clusters are learned from embeddings, never set by the AI.
    "cluster": (
        "fashion_styling",
        "beauty",
        "creator_tips",
        "food",
        "lifestyle",
        "fitness",
        "travel",
        "comedy",
        "education",
        "other",
    ),
    "context": ("everyday", "festive", "wedding", "work", "travel", "seasonal", "sale"),
    "characters": ("creator_solo", "creator_with_friend", "family", "group", "no_person"),
    "core_tension": (
        "doing_it_wrong",
        "choice_dilemma",
        "budget_limit",
        "transformation",
        "relatable_struggle",
        "insider_tip",
        "comparison",
        "celebration",
        "none",
    ),
}

# ------------------------------------------------------------------ Production DNA (how it was made)

PRODUCTION_FIELDS: dict[str, tuple[str, ...]] = {
    "format": (
        "talking_head",
        "voiceover_broll",
        "grwm",
        "tutorial",
        "listicle",
        "lookbook",
        "multi_look",
        "haul",
        "transition",
        "before_after",
        "vlog",
        "skit",
    ),
    # 14 hook types
    "hook_type": (
        "question",
        "mistake",
        "how_to",
        "number_list",
        "bold_claim",
        "relatable",
        "before_after",
        "transformation",
        "curiosity_gap",
        "story",
        "challenge",
        "reveal",
        "budget",
        "trend_audio",
    ),
    "opening_style": (
        "face_to_camera",
        "final_look_first",
        "product_closeup",
        "mirror_shot",
        "action_mid_shot",
        "text_over_broll",
    ),
    # 9 narrative shapes
    "narrative": (
        "list",
        "step_by_step",
        "story_arc",
        "before_after",
        "comparison",
        "problem_solution",
        "montage",
        "day_in_the_life",
        "reveal_then_explain",
    ),
    "ending": (
        "choice_question",
        "open_question",
        "recap",
        "final_look",
        "reveal",
        "loop",
        "cliffhanger",
        "punchline",
        "abrupt",
    ),
    "cta_type": (
        "none",
        "comment_prompt",
        "save_prompt",
        "share_prompt",
        "follow_prompt",
        "part_two_tease",
    ),
    "pov": ("first_person", "second_person", "observational"),
    "camera": ("tripod", "handheld", "mirror_selfie", "selfie_handheld", "mixed"),
    "audio": ("original_speech", "voiceover", "trending_audio", "music_only", "mixed"),
    "visual_style": ("natural_light", "warm_light", "bright_even", "moody", "colourful"),
    "setting": (
        "bedroom",
        "living_room",
        "outdoors",
        "market",
        "studio",
        "event_venue",
        "office",
    ),
}

ALL_FIELDS: dict[str, tuple[str, ...]] = {**CONTENT_FIELDS, **PRODUCTION_FIELDS}

# Features computed in code from T1 and the reel record (not asked of the AI), binned so they
# can be mined like the closed fields.
DERIVED_FIELDS: dict[str, tuple[str, ...]] = {
    "duration_band": ("under_20s", "20_to_40s", "over_40s"),
    "payoff_band": ("under_2s", "2_to_4s", "over_4s"),
    "pace": ("slow", "medium", "fast"),
    "onscreen_text": ("yes", "no"),
}

# Plain-language names for values, used when a feature is shown to the creator.
LABELS: dict[str, str] = {
    "choice_question": "Choice-question endings",
    "open_question": "Open-question endings",
    "recap": "Recap endings",
    "final_look": "Ending on the final look",
    "multi_look": "One item, many looks",
    "lookbook": "Lookbooks",
    "listicle": "Listicles",
    "grwm": "Get-ready-with-me",
    "haul": "Hauls",
    "mistake": "Mistake hooks",
    "number_list": "Number hooks",
    "reveal": "Reveal hooks",
    "final_look_first": "Opening on the final look",
    "save_prompt": "Save prompts",
    "share_prompt": "Send-to-a-friend prompts",
    "comment_prompt": "Comment prompts",
    "mirror_selfie": "Mirror selfie shots",
    "tripod": "Tripod shots",
    "under_2s": "Payoff in the first 2 seconds",
    "2_to_4s": "Payoff at 2–4 seconds",
    "over_4s": "Payoff after 4 seconds",
    "under_20s": "Reels under 20 seconds",
    "20_to_40s": "Reels of 20–40 seconds",
    "over_40s": "Reels over 40 seconds",
    "choice_dilemma": "Reels built on a choice",
    "relatable_struggle": "Relatable struggles",
    "doing_it_wrong": "“You’re doing it wrong” reels",
    "budget_limit": "Budget-limit reels",
    "how_to": "How-to hooks",
    "fast": "Fast cutting",
    "slow": "Slow cutting",
    "medium": "Medium-paced cutting",
}


def label_for(value: str) -> str:
    return LABELS.get(value, value.replace("_", " ").capitalize())
