"""Everything about the Creator Recap that is copy or a threshold, in one place (v2.1 §3.5–3.6).

Change a level boundary, a modifier, an archetype's one-liner or a "that's like…" comparison
here; ``services/recap.py`` reads only these constants.
"""

from __future__ import annotations

# ------------------------------------------------------------------ creator level (followers)

# (upper bound inclusive, name, one-liner); the last has no upper bound.
LEVELS: list[tuple[int | None, str, str]] = [
    (100, "The Spark", "Curious and brave: you took the first step and started creating."),
    (1_000, "The Explorer", "You're finding your voice and your people."),
    (10_000, "The Community Builder", "A real community is forming around your content."),
    (50_000, "The Rising Voice", "People are paying attention, and your reach is growing."),
    (100_000, "The Trendsetter", "What you post starts conversations in your niche."),
    (500_000, "The Influencer", "You shape what your audience watches and buys."),
    (1_000_000, "The Star", "A big, loyal audience shows up for you."),
    (None, "The Icon", "You're a household name in your space."),
]

# Post-count modifiers (a small tag next to the level).
JUST_STARTED_POSTS = 10  # fewer than this in total
CONSISTENCY_WEEKS = 4  # each of the last 4 weeks …
CONSISTENCY_PER_WEEK = 4  # … with at least 4 reels
SEASONED_POSTS = 100  # this many or more in total
MODIFIERS = {
    "just_started": "Just getting started",
    "consistency": "Consistency champ",
    "seasoned": "Seasoned creator",
}

# ------------------------------------------------------------------ archetypes

# Fixed order breaks ties (earlier wins).
ARCHETYPES: dict[str, tuple[str, str]] = {
    "storyteller": ("The Storyteller", "Your reels have a beginning, a middle and an end."),
    "teacher": ("The Teacher", "People come to you to learn something useful."),
    "entertainer": ("The Entertainer", "You make people laugh, and they come back for more."),
    "conversation_starter": (
        "The Conversation Starter",
        "Your reels get people talking in the comments.",
    ),
    "trend_rider": ("The Trend Rider", "You catch what's rising and make it yours."),
    "aesthetic_curator": ("The Aesthetic Curator", "Your look is consistent and people love it."),
    "consistent_one": ("The Consistent One", "You show up week after week."),
    "night_owl": ("The Night Owl", "Your best work goes up after dark."),
}
RUNNER_UP_MIN = 0.3  # a runner-up is shown only above this score

# Caption cues when a reel's video DNA isn't ready yet (the first recap).
CUES = {
    "storyteller": ("story", "storytime", "day in my life", "ditl", "vlog", "before and after",
                    "before/after", "my journey"),
    "teacher": ("tip", "tips", "how to", "how i", "steps", "mistake", "guide", "hack", "learn",
                "explained", "tutorial", "ways to"),
    "entertainer": ("funny", "comedy", "skit", "relatable", "lol", "meme", "😂", "🤣", "pov"),
}  # fmt: skip
NIGHT_HOUR = 21  # "after 9 pm"

# ------------------------------------------------------------------ "that's like…"

# (label, size, source note). Generic, verifiable sizes; no named venues.
COMPARISONS: list[tuple[str, int, str]] = [
    ("a 40-seat classroom", 40, "a typical school classroom"),
    ("a 300-seat cinema hall", 300, "a typical single multiplex screen"),
    ("a 1,000-seat auditorium", 1_000, "a large college auditorium"),
    ("a 5,000-seat indoor arena", 5_000, "a mid-size indoor arena"),
    ("a 30,000-seat cricket stadium", 30_000, "a mid-size cricket stadium"),
    ("a 1,00,000-seat stadium", 100_000, "the largest stadiums in the world"),
]
COMPARISON_MIN, COMPARISON_MAX = 2, 50

# ------------------------------------------------------------------ follower milestones

MILESTONES = [100, 500, 1_000, 5_000, 10_000, 25_000, 50_000, 100_000, 250_000, 500_000,
              1_000_000, 2_000_000, 5_000_000, 10_000_000]  # fmt: skip

# ------------------------------------------------------------------ the story

MIN_SLIDES, MAX_SLIDES = 5, 12
FIRST_RECAP_DAYS = 90
# The arc: a hook, then wins, then audience, then style, then the reveal.
ORDER = [
    "intro", "posting", "streak", "views_total", "beyond_followers", "top_reel", "most_talked",
    "most_shared", "growth", "vs_last_month", "audience_voice", "language_mix", "best_time",
    "superpower", "top_topic", "creator_type", "share_card", "next_up",
]  # fmt: skip
ALWAYS = ("intro", "creator_type", "share_card", "next_up")
# When there are too many, these middle slides go first (least essential first).
DROP_FIRST = ["language_mix", "streak", "most_shared", "best_time", "top_topic",
              "vs_last_month", "most_talked", "audience_voice", "superpower",
              "beyond_followers", "growth", "top_reel", "views_total", "posting"]  # fmt: skip
LONG_SLIDES = {"audience_voice", "creator_type", "share_card", "superpower"}  # 8 s, not 6 s
MILESTONE_SLIDES = {"views_total", "top_reel", "growth", "creator_type"}  # confetti

# Full-bleed backgrounds rotate through the palette. Body text must pass WCAG AA (4.5:1), so
# blue (#5B73F2) is an accent, never a background behind body text (D216).
BACKGROUNDS = [
    ("lavender", "ink"),
    ("pink", "ink"),
    ("ink", "white"),
    ("gray", "ink"),
    ("white", "ink"),
]
COLOURS = {
    "blue": "#5B73F2",
    "lavender": "#C3BFF2",
    "pink": "#F2D4E2",
    "white": "#FFFFFF",
    "gray": "#E4E4EC",
    "ink": "#242424",
}
LANGUAGE_NAMES = {
    "en": "English", "hi": "Hindi", "hinglish": "Hinglish", "mr": "Marathi", "ta": "Tamil",
    "te": "Telugu", "bn": "Bengali", "gu": "Gujarati", "kn": "Kannada", "ml": "Malayalam",
    "pa": "Punjabi", "ur": "Urdu", "mixed": "a mix",
}  # fmt: skip
