"""Generate CURO's deterministic demo dataset into fixtures/data/.

    python fixtures/generate.py

Everything is synthetic (no real Instagram data). The mock PublicDataProvider serves it as
if it were live at the current clock time. Times are offsets in hours from the anchor,
12 days before Ganesh Chaturthi 2027 (Saturday 4 September 2027).

What's in it
- @curo.demo: a Mumbai fashion/styling creator (~48K followers), 50 past reels across five
  sub-clusters (festive styling, reel-making tips, GRWM, hauls, one-item-many-looks) plus two
  reels posted after the anchor (appear when you time-travel forward).
- The prototype's reels and their stories: "3 mistakes…" peaking and travelling beyond
  followers; the Navratri GRWM slowing with "where is it from?" comments; "One kurta, five
  dupattas" picking up again with part-2 requests; the thrift haul in its long tail with
  price questions.
- Data-quality cases: hidden likes, missing share counts, comments turned off, a deleted
  reel, a vendor glitch that reports fewer views, paid partnerships, reels seen late.
- 10 peers (prototype handles + four invented) × 30 reels; recent Ganpati outfit reels with
  an Outlier Index of 2 or more on several of them.
- Comments in English, Hinglish and Hindi: "that's me", questions, requests (part 2, where
  is it from, budget version), friend tags, praise, negatives, spam and bots.
- Hashtag pages and a two-year festival calendar.

Outcomes such as the Ganpati opportunity score are NOT written here: the real logic has to
produce them from this data.
"""

from __future__ import annotations

import json
import math
import random
import re
import shutil
import string
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "api"))

from curo.providers.public_data.mock import curve_fraction, views_at  # noqa: E402

OUT = REPO / "fixtures" / "data"
SEED = 2027
ANCHOR = "2027-08-23T10:00:00+05:30"  # 12 days before Ganesh Chaturthi (2027-09-04)
DEMO = "curo.demo"
D = 24.0  # hours per day

rng = random.Random(SEED)

# ---------------------------------------------------------------------------- helpers

_SC = string.ascii_letters + string.digits + "_-"
_used_codes: set[str] = set()


def shortcode() -> str:
    while True:
        code = rng.choice("CD") + "".join(rng.choice(_SC) for _ in range(10))
        if code not in _used_codes:
            _used_codes.add(code)
            return code


def media_id() -> str:
    return str(rng.randrange(3_000_000_000_000_000_000, 3_999_999_999_999_999_999))


def tags_in(caption: str) -> list[str]:
    return [
        w[1:].lower().strip(".,!?") for w in caption.split() if w.startswith("#") and len(w) > 1
    ]


def mentions_in(caption: str) -> list[str]:
    return [
        w[1:].lower().strip(".,!?:") for w in caption.split() if w.startswith("@") and len(w) > 1
    ]


def lognormal(sigma: float) -> float:
    return math.exp(rng.gauss(0, sigma))


# Typical creator curve: ~72% of 7-day views by day 3 (logic doc §6 worked example).
TYPICAL = {"tau_h": 62.0, "beta": 1.6}


def total_for_views(target_views: float, age_h: float, tau_h: float, beta: float) -> int:
    """v_total so that a reel of this shape has ``target_views`` at ``age_h``."""
    return round(target_views / curve_fraction(age_h, tau_h, beta))


# ---------------------------------------------------------------------------- the creator

CLUSTERS = {
    # views multiplier vs the creator's median, and public rates (likes/comments/shares per view)
    "festive": {
        "label": "Festive styling",
        "mult": 1.5,
        "like": 0.049,
        "comment": 0.0024,
        "share": 0.0075,
    },
    "tips": {
        "label": "Reel-making tips",
        "mult": 1.05,
        "like": 0.038,
        "comment": 0.0030,
        "share": 0.0045,
    },
    "grwm": {"label": "GRWM", "mult": 0.85, "like": 0.030, "comment": 0.0032, "share": 0.0025},
    "haul": {"label": "Hauls", "mult": 0.6, "like": 0.028, "comment": 0.0028, "share": 0.0018},
    "multilook": {
        "label": "One item, many looks",
        "mult": 1.3,
        "like": 0.054,
        "comment": 0.0020,
        "share": 0.0090,
    },
}

# How each cluster is usually made (generator truth, in the taxonomy of
# api/curo/schemas/taxonomy.py). add_understanding() turns it into each reel's DNA and the
# T1 video-understanding output a video model would report.
CLUSTER_DNA = {
    "festive": {
        "niche": "fashion_styling",
        "format": "lookbook",
        "opening_style": "face_to_camera",
        "narrative": "list",
        "ending": "choice_question",
        "cta_type": "comment_prompt",
        "pov": "first_person",
        "camera": "tripod",
        "audio": "original_speech",
        "visual_style": "warm_light",
        "setting": "bedroom",
        "core_tension": "choice_dilemma",
        "cuts": 3.0,
        "onscreen": 0.8,
    },
    "tips": {
        "niche": "creator_tips",
        "format": "listicle",
        "opening_style": "face_to_camera",
        "narrative": "list",
        "ending": "recap",
        "cta_type": "save_prompt",
        "pov": "second_person",
        "camera": "tripod",
        "audio": "voiceover",
        "visual_style": "natural_light",
        "setting": "bedroom",
        "core_tension": "doing_it_wrong",
        "cuts": 4.2,
        "onscreen": 0.9,
    },
    "grwm": {
        "niche": "fashion_styling",
        "format": "grwm",
        "opening_style": "mirror_shot",
        "narrative": "step_by_step",
        "ending": "final_look",
        "cta_type": "comment_prompt",
        "pov": "first_person",
        "camera": "mirror_selfie",
        "audio": "original_speech",
        "visual_style": "natural_light",
        "setting": "bedroom",
        "core_tension": "relatable_struggle",
        "cuts": 2.2,
        "onscreen": 0.4,
    },
    "haul": {
        "niche": "fashion_styling",
        "format": "haul",
        "opening_style": "product_closeup",
        "narrative": "list",
        "ending": "abrupt",
        "cta_type": "none",
        "pov": "first_person",
        "camera": "handheld",
        "audio": "original_speech",
        "visual_style": "bright_even",
        "setting": "living_room",
        "core_tension": "budget_limit",
        "cuts": 3.4,
        "onscreen": 0.6,
    },
    "multilook": {
        "niche": "fashion_styling",
        "format": "multi_look",
        "opening_style": "face_to_camera",
        "narrative": "list",
        "ending": "final_look",
        "cta_type": "comment_prompt",
        "pov": "first_person",
        "camera": "tripod",
        "audio": "mixed",
        "visual_style": "warm_light",
        "setting": "bedroom",
        "core_tension": "choice_dilemma",
        "cuts": 3.6,
        "onscreen": 0.9,
    },
}

BASE_TOTAL = 50_000  # the creator's typical 30-day views

# The synthetic world's production patterns, sized like the prototype's own notes ("pick-one
# prompts brought 2.1× your usual comments", "reels that end on the finished look get 1.7×
# your median likes", "'send to a friend' endings: 1.6× shares"). The real pattern mining
# has to find them (Phase 3); nothing downstream reads these numbers.
CHOICE_QUESTION_COMMENTS = 1.7
FINAL_LOOK_LIKES = 1.25
EARLY_PAYOFF_LIKES = 1.25  # first payoff within 2 seconds
SHARE_PROMPT_SHARES = 1.6
ENDING_ODDS = {  # cluster: (usual ending, its probability, the alternative)
    "festive": ("choice_question", 0.6, "final_look"),
    "multilook": ("final_look", 0.55, "choice_question"),
    "grwm": ("final_look", 0.6, "choice_question"),
    "tips": ("recap", 0.65, "choice_question"),
    "haul": ("abrupt", 0.6, "choice_question"),
}
dna_rng = random.Random(SEED + 202)


def draw_choices(cluster: str) -> dict:
    usual, p, other = ENDING_ODDS[cluster]
    ending = usual if dna_rng.random() < p else other
    early = dna_rng.random() < 0.45
    payoff = round(dna_rng.uniform(0.8, 1.8) if early else dna_rng.uniform(2.3, 5.5), 1)
    share_prompt = dna_rng.random() < (0.2 if cluster == "tips" else 0.3)
    return {"ending": ending, "payoff_s": payoff, "share_prompt": share_prompt}


def apply_choice_effects(rates: dict, ending: str, payoff_s: float, cta: str) -> None:
    """The same patterns hold for the creator and for similar creators (the peers)."""
    if ending == "choice_question":
        rates["comment"] *= CHOICE_QUESTION_COMMENTS
    if ending == "final_look":
        rates["like"] *= FINAL_LOOK_LIKES
    if payoff_s < 2:
        rates["like"] *= EARLY_PAYOFF_LIKES
    if cta == "share_prompt":
        rates["share"] *= SHARE_PROMPT_SHARES


def demo_reels() -> list[dict]:
    """The creator's reels. The first four are the prototype's."""
    specs: list[dict] = [
        # --- after the anchor: appear when you time-travel forward
        {
            "h": 30,
            "cluster": "festive",
            "title": "One outfit, three Ganpati moods",
            "caption": "One outfit, three Ganpati moods — traditional, modern, festive. Which one is you? 🌸 "
            "#ganpatioutfit #ganeshchaturthi #festivelook #ethnicstyling #mumbaistyle",
            "views_total": 74_000,
        },
        {
            "h": 100,
            "cluster": "grwm",
            "title": "GRWM: pandal hopping in the rain",
            "caption": "GRWM: pandal hopping in the rain 🌧️ what's your monsoon festive essential? "
            "#grwm #ganeshotsav #mumbai",
        },
        # --- the prototype's four (newest first)
        {
            "h": -74,
            "cluster": "tips",
            "title": "3 mistakes ruining your aesthetic reel",
            "caption": "3 mistakes ruining your aesthetic reel 🎥 Number 2 is the one everyone makes. "
            "Save this before your next shoot! #reeltips #contentcreator #aestheticreels",
            # a late bloomer: still at its peak at 3 days, 2× the follower count
            "views_now": 104_000,
            "tau_h": 80,
            "beta": 1.6,
            "rates": {"like": 0.036, "comment": 0.0029, "share": 0.0027},
            "duration_s": 32,
            # the logic doc's §4 example record
            "dna": {
                "format": "listicle",
                "hook_type": "mistake",
                "opening_style": "face_to_camera",
                "narrative": "list",
                "ending": "recap",
                "cta_type": "save_prompt",
                "pov": "first_person",
                "camera": "tripod",
                "audio": "voiceover",
                "visual_style": "warm_light",
                "setting": "bedroom",
                "cuts": 4.2,
                "payoff_s": 1.8,
                "onscreen": 1.0,
            },
            "story": "thats_me",
        },
        {
            "h": -150,
            "cluster": "grwm",
            "title": "Get ready with me: Navratri edition",
            "caption": "Get ready with me: Navratri edition ✨ lehenga, jhumkas and way too much glitter. "
            "#grwm #navratri #navratrilook #festivelook",
            "views_now": 41_000,
            "tau_h": 110,
            "beta": 1.4,
            "rates": {"like": 0.029, "comment": 0.0035, "share": 0.0023},
            "duration_s": 45,
            "story": "where_from",
            # the prototype: "pick-one prompts brought 2.1× your usual comments" on this reel
            "dna": {"ending": "choice_question", "cta_type": "comment_prompt", "payoff_s": 2.9},
        },
        {
            "h": -195,
            "cluster": "multilook",
            "title": "One kurta, five dupattas",
            "caption": "One kurta, five dupattas 💛 which one would you wear? #dupattastyling "
            "#oneoutfitmanyways #ethnicstyling #kurtalove",
            "base_total": 75_000,
            "tau_h": 55,
            "beta": 1.6,
            # picks up again on day 6 and is still climbing at the anchor
            "wave2": {"start_h": 144, "v": 190_000, "tau_h": 90, "beta": 2.0},
            "rates": {"like": 0.053, "comment": 0.0016, "share": 0.0073},
            "duration_s": 28,
            "story": "part2",
            # the prototype: ends on the finished look; people send it to recreate the looks
            "dna": {"ending": "final_look", "cta_type": "share_prompt", "payoff_s": 1.2},
        },
        {
            "h": -270,
            "cluster": "haul",
            "title": "Thrift haul under ₹2,000",
            "caption": "Thrift haul under ₹2,000 🛍️ everything I found at the market this weekend "
            "#thrifthaul #budgetfashion #mumbaishopping",
            "views_now": 22_000,
            "tau_h": 50,
            "beta": 1.2,
            "rates": {"like": 0.028, "comment": 0.0028, "share": 0.0018},
            "duration_s": 52,
            "story": "price",
            "dna": {"ending": "abrupt", "cta_type": "none", "payoff_s": 3.6},
        },
        # --- the rest of the latest ten
        {
            "h": -294,
            "cluster": "grwm",
            "title": "GRWM: monsoon office look",
            "likes_hidden": True,
            "caption": "GRWM: monsoon office look ☔ waterproof everything. #grwm #officewear #monsoonstyle",
            "glitch": {"from_h": -120, "to_h": -94, "factor": 0.97},
        },
        {
            "h": -310,
            "cluster": "festive",
            "title": "Raksha Bandhan looks: 3 outfits for the sibling photos",
            "caption": "Raksha Bandhan looks: 3 outfits for the sibling photos 🎀 tag your sibling! "
            "#rakshabandhan #festivelook #ethnicstyling",
        },
        {
            "h": -360,
            "cluster": "tips",
            "title": "How I light my reels with one window",
            "shares_hidden": True,
            "caption": "How I light my reels with one window ☀️ no ring light needed. #reeltips #lighting",
        },
        {
            "h": -410,
            "cluster": "festive",
            "title": "Independence Day styling without the costume vibe",
            "caption": "Independence Day styling without the costume vibe 🇮🇳 #independenceday #ethnicstyling",
        },
        {
            "h": -470,
            "cluster": "grwm",
            "title": "My monsoon skincare routine (paid partnership)",
            "paid": True,
            "comments_disabled": True,
            "caption": "My monsoon skincare routine ✨ in partnership with @glowlab.example #ad #skincare",
        },
        {
            "h": -520,
            "cluster": "multilook",
            "title": "One saree, three drapes",
            "caption": "One saree, three drapes 🌸 which drape is your favourite? #sareedraping "
            "#oneoutfitmanyways #sareelove",
        },
    ]

    older = [
        ("tips", "My 10-minute reel editing routine", {"deleted_h": -40}),
        ("multilook", "One white shirt, five ways", {}),
        ("haul", "Colaba Causeway haul: what's worth it", {}),
        ("festive", "Haldi outfit ideas that aren't all yellow", {}),
        ("grwm", "GRWM for a college reunion", {"shares_hidden": True}),
        ("tips", "Phone settings I use for every reel", {}),
        ("multilook", "One lehenga skirt, four looks", {}),
        ("festive", "Wedding guest looks under ₹3,000", {}),
        ("haul", "Linking Road earrings haul", {"shares_hidden": True}),
        ("grwm", "Get ready with me: first day at the new studio", {"likes_hidden": True}),
        ("multilook", "Three ways to wear a denim jacket with ethnic wear", {}),
        ("tips", "Why your transitions look jumpy (and the fix)", {}),
        ("festive", "Eid outfit ideas in pastels", {}),
        ("grwm", "GRWM: date night in Bandra", {}),
        ("multilook", "One dupatta, five draping styles", {}),
        ("haul", "Myntra sale haul: hits and misses", {"shares_hidden": True}),
        ("tips", "5 angles that make any outfit look better on camera", {}),
        ("festive", "Holi whites that survive the colours", {}),
        ("grwm", "Get ready with me for a sangeet", {}),
        ("multilook", "One black kurta, office to party", {}),
        ("haul", "Festive jewellery haul under ₹1,500", {}),
        ("tips", "Stop filming like this: framing mistakes", {}),
        ("grwm", "GRWM: 15-minute festive makeup", {"paid": True}),
        ("multilook", "Two blouses, six sarees", {}),
        ("festive", "Wedding season: three looks, one budget", {}),
        ("tips", "B-roll ideas when you have no time", {"shares_hidden": True}),
        ("haul", "Sarojini-style haul, Mumbai edition", {}),
        ("grwm", "GRWM: Christmas brunch", {}),
        ("multilook", "One co-ord set, four outfits", {}),
        ("festive", "Diwali party looks from my own wardrobe", {"at_day": -288}),
        ("tips", "How I plan a week of reels in one hour", {"likes_hidden": True}),
        ("festive", "Karva Chauth red, but make it modern", {"at_day": -298}),
        ("grwm", "GRWM: Navratri day one", {"at_day": -321}),
        ("festive", "Navratri colours: nine days, nine looks", {"at_day": -323}),
        ("multilook", "One bandhani dupatta, three looks", {}),
        ("haul", "Pre-festive haul: what I bought for the season", {"at_day": -335}),
        (
            "festive",
            "What I wore for Ganpati last year",
            {"at_day": -345, "story": "ganpati_last_year"},
        ),
        ("tips", "The one setting that fixed my blurry reels", {}),
        ("multilook", "One silk saree, three occasions", {}),
        ("grwm", "GRWM: Ganpati visarjan day", {"at_day": -332}),
    ]
    h = -560.0
    for cluster, title, extra in older:
        if "at_day" in extra:
            h_i = extra["at_day"] * D + rng.uniform(-6, 6)
        else:
            h -= rng.uniform(4.5, 8.5) * D
            h_i = h
        tag_pool = {
            "festive": "#festivelook #ethnicstyling #festivestyling",
            "tips": "#reeltips #contentcreator",
            "grwm": "#grwm #getreadywithme",
            "haul": "#haul #budgetfashion",
            "multilook": "#oneoutfitmanyways #styletips",
        }[cluster]
        spec = {"h": h_i, "cluster": cluster, "title": title, "caption": f"{title} {tag_pool}"}
        spec.update({k: v for k, v in extra.items() if k != "at_day"})
        if extra.get("paid"):
            spec["caption"] += " #ad"
        specs.append(spec)

    reels = []
    for spec in specs:
        c = CLUSTERS[spec["cluster"]]
        tau = spec.get("tau_h", TYPICAL["tau_h"] * lognormal(0.12))
        beta = spec.get("beta", TYPICAL["beta"])
        if "views_now" in spec:
            v_total = total_for_views(spec["views_now"], -spec["h"], tau, beta)
        elif "base_total" in spec:
            v_total = spec["base_total"]
        elif "views_total" in spec:
            v_total = spec["views_total"]
        else:
            mult = c["mult"] * (1.5 if spec.get("story") == "ganpati_last_year" else 1.0)
            v_total = round(BASE_TOTAL * mult * lognormal(0.22))
        rates = spec.get("rates") or {
            "like": c["like"] * lognormal(0.12),
            "comment": c["comment"]
            * lognormal(0.15)
            * (1.5 if spec.get("story") == "ganpati_last_year" else 1),
            "share": c["share"] * lognormal(0.15),
        }
        curve = {"v_total": v_total, "tau_h": round(tau, 2), "beta": beta}
        if "wave2" in spec:
            curve["wave2"] = spec["wave2"]
        dna = dict(CLUSTER_DNA[spec["cluster"]], **spec.get("dna", {}))
        # Production choices shape this reel's rates (drawn from their own stream, so views
        # and everything above stay as they were). Reels with scripted rates keep them.
        choices = draw_choices(spec["cluster"])
        explicit = spec.get("dna", {})
        if "ending" not in explicit:
            dna["ending"] = choices["ending"]
        if "payoff_s" not in explicit:
            dna["payoff_s"] = choices["payoff_s"]
        if "cta_type" not in explicit:
            if choices["share_prompt"]:
                dna["cta_type"] = "share_prompt"
            elif dna["ending"] == "choice_question" and dna["cta_type"] == "none":
                dna["cta_type"] = "comment_prompt"
        if not spec.get("rates"):
            apply_choice_effects(rates, dna["ending"], dna["payoff_s"], dna["cta_type"])
        reels.append(
            {
                "ig_media_id": media_id(),
                "shortcode": shortcode(),
                "posted_h": round(spec["h"], 2),
                "duration_s": spec.get("duration_s", round(rng.uniform(22, 58))),
                "caption": spec["caption"],
                "hashtags": tags_in(spec["caption"]),
                "mentions": mentions_in(spec["caption"]),
                "audio_name": "Original audio"
                if rng.random() < 0.6
                else rng.choice(TRENDING_AUDIO),
                "is_paid_partnership": bool(spec.get("paid")),
                "likes_hidden": bool(spec.get("likes_hidden")),
                "shares_hidden": bool(spec.get("shares_hidden")),
                "comments_disabled": bool(spec.get("comments_disabled")),
                "deleted_h": spec.get("deleted_h"),
                "glitch": spec.get("glitch"),
                "curve": curve,
                "rates": {k: round(v, 5) for k, v in rates.items()},
                "meta": {
                    "title": spec["title"],
                    "cluster": spec["cluster"],
                    "story": spec.get("story"),
                    "explicit": sorted(spec.get("dna", {})),
                    **dna,
                },
            }
        )
    return reels


TRENDING_AUDIO = [
    "Kesariya (lofi) · Arijit Singh",
    "Trending festive beat · DJ Remix",
    "Aesthetic piano loop",
    "Dhol tasha intro",
    "Soft acoustic vlog",
]

# ---------------------------------------------------------------------------- peers

PEERS = [
    # username, full name, followers, reach ratio (median views ÷ followers)
    ("theoutfitdiaries", "The Outfit Diaries", 92_000, 0.75),
    ("stylewithrhea", "Style with Rhea", 135_000, 0.7),
    ("mumbaiwardrobe", "Mumbai Wardrobe", 61_000, 0.85),
    ("thedrapestory", "The Drape Story", 38_000, 1.0),
    ("kavyawears", "Kavya Wears", 27_000, 1.1),
    ("styledbysana", "Styled by Sana", 74_000, 0.8),
    ("everydayethnic", "Everyday Ethnic", 19_000, 1.2),
    ("sareeandsneakers", "Saree & Sneakers", 44_000, 0.9),
    ("dupatta.diaries", "Dupatta Diaries", 23_000, 1.05),
    ("festive.fits.daily", "Festive Fits Daily", 52_000, 0.8),
]

# Recent peer reels that matter for opportunities. oi = Outlier Index target (views lift).
PEER_SPECIALS = {
    "theoutfitdiaries": [
        (-60, "Ganpati outfit ideas: 5 looks from traditional to modern", "ganpati", 3.4),
        (-290, "3 styling mistakes that make ethnic wear look cheap", "mistakes", 1.8),
    ],
    "stylewithrhea": [
        (-100, "Ganpati look: final look first, then the chaos behind it", "ganpati_reveal", 2.5),
        (-430, "1 saree, 4 drapes", "multilook", 1.8),
        (-520, "The final-look-first reveal: festive edition", "reveal", 1.9),
    ],
    "mumbaiwardrobe": [
        (-140, "What to wear for Ganpati pandal hopping in Mumbai", "ganpati", 2.9),
        (-330, "Dupatta mistakes everyone makes", "mistakes", 1.7),
    ],
    "thedrapestory": [
        (-200, "Ganpati saree drapes in 60 seconds", "ganpati", 2.2),
        (-380, "Reveal first: the drape, then how I did it", "reveal", 2.0),
    ],
    "kavyawears": [(-250, "Ganpati outfit haul under ₹1,500", "ganpati", 1.3)],
    "styledbysana": [
        (-40, "Modak-pink Ganpati look, start to finish", "ganpati", 1.6),
        (-300, "Stop doing this with festive jewellery", "mistakes", 1.9),
    ],
    "sareeandsneakers": [(-460, "Final look first: saree with sneakers", "reveal", 1.8)],
}

PEER_TOPICS = [
    ("Festive look under ₹2,000", "festive"),
    ("GRWM for a family function", "grwm"),
    ("One kurta, three ways", "multilook"),
    ("Monsoon outfit ideas", "everyday"),
    ("Office to evening in one outfit", "multilook"),
    ("Mehendi outfit ideas", "festive"),
    ("Jewellery haul from the local market", "haul"),
    ("How to style a plain saree", "tips"),
    ("Colour combinations for ethnic wear", "tips"),
    ("Wedding guest looks", "festive"),
    ("Thrift flip: old dupatta, new look", "multilook"),
    ("College fit check", "everyday"),
]


def peer_reels(username: str, followers: int, reach: float) -> list[dict]:
    median_total = followers * reach / curve_fraction(7 * D, *TYPICAL.values())
    reels = []
    specials = PEER_SPECIALS.get(username, [])
    used_h = {round(h) for h, *_ in specials}
    hours = []
    h = -10.0
    while len(hours) < 30 - len(specials):
        h -= rng.uniform(1.5, 5.0) * D
        if all(abs(h - u) > 30 for u in used_h):
            hours.append(h)
    items = [(hh, *rng.choice(PEER_TOPICS), lognormal(0.25)) for hh in hours]
    items += [(hh, title, topic, oi) for hh, title, topic, oi in specials]
    for hh, title, topic, mult in sorted(items, key=lambda x: -x[0]):
        tags = {
            "ganpati": "#ganpatioutfit #ganeshchaturthi #festivelook",
            "ganpati_reveal": "#ganpatioutfit #ganeshchaturthi #revealfirst",
            "mistakes": "#stylingmistakes #styletips",
            "reveal": "#revealfirst #festivelook",
            "multilook": "#oneoutfitmanyways #styletips",
            "festive": "#festivelook #ethnicstyling",
            "grwm": "#grwm",
            "haul": "#haul",
            "tips": "#styletips",
            "everyday": "#ootd",
        }[topic]
        caption = f"{title} {tags}"
        reels.append(
            {
                "ig_media_id": media_id(),
                "shortcode": shortcode(),
                "posted_h": round(hh, 2),
                "duration_s": round(rng.uniform(15, 55)),
                "caption": caption,
                "hashtags": tags_in(caption),
                "mentions": [],
                "audio_name": "Original audio"
                if rng.random() < 0.5
                else rng.choice(TRENDING_AUDIO),
                "is_paid_partnership": rng.random() < 0.04,
                "likes_hidden": rng.random() < 0.05,
                "shares_hidden": rng.random() < 0.25,
                "comments_disabled": False,
                "deleted_h": None,
                "glitch": None,
                "curve": {
                    "v_total": round(median_total * mult),
                    "tau_h": round(TYPICAL["tau_h"] * lognormal(0.12), 2),
                    "beta": TYPICAL["beta"],
                },
                "rates": {
                    "like": round(0.04 * lognormal(0.2), 5),
                    "comment": round(0.0022 * lognormal(0.25), 5),
                    "share": round(0.006 * lognormal(0.3), 5),
                },
                "meta": {"title": title, "topic": topic, "oi_target": round(mult, 2)},
            }
        )
        # Production choices shape the peer's rates too (views are unaffected).
        r = reels[-1]
        usual = PEER_ENDINGS[topic]
        other = "final_look" if usual == "choice_question" else "choice_question"
        ending = usual if dna_rng.random() < 0.6 else other
        early = dna_rng.random() < 0.45
        payoff = round(dna_rng.uniform(0.8, 1.8) if early else dna_rng.uniform(2.3, 5.0), 1)
        share_prompt = dna_rng.random() < 0.25
        cta = "share_prompt" if share_prompt else PEER_TOPIC_DNA[topic].get("cta_type", "comment_prompt")
        if ending == "choice_question" and cta == "none":
            cta = "comment_prompt"
        r["meta"].update({"ending": ending, "payoff_s": payoff, "cta_type": cta})
        apply_choice_effects(r["rates"], ending, payoff, cta)
        r["rates"] = {k: round(v, 5) for k, v in r["rates"].items()}
    return reels


PEER_ENDINGS = {
    "ganpati": "choice_question",
    "ganpati_reveal": "final_look",
    "reveal": "final_look",
    "mistakes": "recap",
    "multilook": "choice_question",
    "festive": "final_look",
    "grwm": "final_look",
    "haul": "abrupt",
    "tips": "recap",
    "everyday": "final_look",
}


# ---------------------------------------------------------------------------- comments

FAN_HANDLES = [
    "aesthetic.anya",
    "meera.styles",
    "twirlwithtara",
    "budgetbae.in",
    "riya.k",
    "nisha_dreams",
    "palak.wears",
    "ishaan.films",
    "zoya.creates",
    "tanvi_t",
    "sakshi.s",
    "mehul.makes",
    "pooja_pune",
    "ritika.r",
    "kabir.shoots",
    "diya.loves.dupattas",
    "aarti.m",
    "neha.nair",
    "simran.styles",
    "devika.d",
    "ankita_ootd",
    "rahul.reels",
    "fatima.f",
    "shreya.sings",
    "jhanvi.j",
]
BOT_HANDLES = ["promo.boost.247", "get.followers.now", "crypto_king_offer", "dm.for.collab.xyz"]

COMMENTS = {
    "thats_me": [
        "Mistake #2 is literally me every single time. Saving this.",
        "this is so me 😭",
        "bilkul mera haal hai 😂",
        "same yaar, every single time",
        "why is this literally me",
        "mujhe laga sirf main aisa karti hoon 🙈",
        "called out in 30 seconds 💀",
        "ये तो बिल्कुल मैं हूँ 😂",
    ],
    "question_where": [
        "Please drop the link for the lehenga, I need it before Dussehra.",
        "where is this kurta from?",
        "ye dupatta kahan se liya?",
        "lehenga link please 🙏",
        "jhumkas kahan se hai?",
        "which store is this from?",
        "यह लहंगा कहाँ से लिया?",
        "is this from Linking Road?",
    ],
    "question_price": [
        "Which market is this? Need a budget festive one next!",
        "price kitna hai?",
        "how much was the kurta?",
        "kitne ka mila?",
        "is this under 1000?",
        "कितने का है?",
    ],
    "question_how": [
        "which camera do you use?",
        "what app do you edit on?",
        "how do you get this lighting?",
        "transition kaise kiya?",
        "what lens is this?",
    ],
    "request_part2": [
        "part 2 please!!",
        "part 2 with the yellow kurta 🙏",
        "need a part 2 asap",
        "please make part 2",
        "part 2 pleaseee",
        "dusra part kab aayega?",
    ],
    "request_budget": [
        "budget version please 🙏",
        "please do a budget festive look",
        "under 1500 version please",
        "sasta version bhi dikhao 😅",
        "budget wala video banao na",
    ],
    "request_festive": [
        "please do one for Ganpati 🙏",
        "Ganpati outfit ideas next please",
        "Navratri looks next pls",
        "festive outfit ideas for Ganpati please",
        "ganpati ke liye kya pehnu? video banao",
    ],
    "friend_tag": [
        "@riya.k this is so you",
        "@meera_s we need this for mehendi",
        "@palak.wears look!!",
        "@sakshi.s twinning this Ganpati?",
        "@zoya.creates send this to your mom",
    ],
    "praise": [
        "So pretty 😍",
        "Love the mustard one",
        "kya baat hai 🔥",
        "obsessed with this",
        "The mustard one!! Doing this for my cousin's mehendi.",
        "bahut sundar ❤️",
        "बहुत सुंदर",
        "you always nail it",
        "saving this for the wedding season",
    ],
    "pick": [
        "the third one!",
        "look 2 for sure",
        "dupatta 4 💛",
        "number 1 all the way",
        "3rd one is my fav",
    ],
    "negative": [
        "Too much filter honestly",
        "This is not new, seen it 100 times",
        "Hauls are boring now",
        "audio is too loud",
        "not your best one",
    ],
    "places": [
        "doing this look in Pune this weekend!",
        "Mumbai rains + this outfit = perfect",
        "wearing this to the Lalbaug pandal",
        "Pune mein ye kahan milega?",
    ],
    "emoji": ["😍😍", "🔥🔥", "❤️", "👏👏", "💛"],
    "bot": [
        "Promote your page DM us 🔥🔥",
        "Earn $500 daily click link in bio",
        "Nice pic! Check my profile",
        "💯💯💯 follow back",
        "Want more followers? DM now",
    ],
    "creator_reply": [
        "Thank you so much! 💖",
        "Part 2 coming soon 😉",
        "Linked in my stories!",
        "haha same 😂",
    ],
}

# Mix of comment kinds per story (weights).
MIXES = {
    "thats_me": {
        "thats_me": 41,
        "question_how": 12,
        "question_where": 6,
        "friend_tag": 12,
        "praise": 12,
        "emoji": 5,
        "bot": 5,
        "negative": 2,
        "creator_reply": 5,
    },
    "where_from": {
        "question_where": 45,
        "question_price": 8,
        "praise": 18,
        "request_festive": 6,
        "emoji": 6,
        "bot": 6,
        "friend_tag": 5,
        "creator_reply": 6,
    },
    "part2": {
        "request_part2": 22,
        "pick": 22,
        "friend_tag": 14,
        "praise": 16,
        "question_where": 10,
        "emoji": 5,
        "bot": 5,
        "creator_reply": 6,
    },
    "price": {
        "question_price": 32,
        "request_budget": 14,
        "negative": 10,
        "praise": 12,
        "question_where": 10,
        "emoji": 6,
        "bot": 8,
        "creator_reply": 8,
    },
    "ganpati_last_year": {
        "request_festive": 14,
        "praise": 26,
        "friend_tag": 12,
        "pick": 10,
        "question_where": 14,
        "places": 10,
        "emoji": 6,
        "bot": 4,
        "creator_reply": 4,
    },
    "default": {
        "praise": 26,
        "thats_me": 6,
        "question_where": 12,
        "question_price": 5,
        "question_how": 5,
        "request_part2": 3,
        "request_budget": 4,
        "request_festive": 4,
        "friend_tag": 10,
        "pick": 5,
        "places": 4,
        "negative": 3,
        "emoji": 6,
        "bot": 4,
        "creator_reply": 3,
    },
}

TOP_COMMENTS = {
    "thats_me": ("Mistake #2 is literally me every single time. Saving this.", 214, 18),
    "where_from": ("Please drop the link for the lehenga, I need it before Dussehra.", 96, 11),
    "part2": ("The mustard one!! Doing this for my cousin's mehendi.", 388, 24),
    "price": ("Which market is this? Need a budget festive one next!", 57, 9),
}


def comments_for(reel: dict, owner: str, n: int, story: str | None, peer: bool) -> list[dict]:
    if reel.get("comments_disabled") or n <= 0:
        return []
    mix = MIXES.get(story or "default", MIXES["default"])
    kinds, weights = zip(*mix.items(), strict=True)
    out = []
    top = TOP_COMMENTS.get(story or "")
    for i in range(n):
        kind = rng.choices(kinds, weights)[0]
        if kind == "creator_reply":
            author, text = owner, rng.choice(COMMENTS[kind])
        elif kind == "bot":
            author, text = rng.choice(BOT_HANDLES), rng.choice(COMMENTS[kind])
        else:
            author, text = rng.choice(FAN_HANDLES), rng.choice(COMMENTS[kind])
        likes = int(rng.expovariate(1 / (6 if not peer else 3)))
        replies = int(rng.expovariate(1 / 1.2)) if likes > 3 else 0
        if kind in ("bot", "emoji"):
            likes, replies = rng.randint(0, 2), 0
        if i == 0 and top:
            text, likes, replies = top
            author, kind = rng.choice(FAN_HANDLES), story
        age = min(rng.expovariate(1 / 30), 24 * 20)
        out.append(
            {
                "id": f"{reel['shortcode']}_c{i:03d}",
                "text": text,
                "author": author,
                "posted_h": round(reel["posted_h"] + 0.3 + age, 2),
                "likes": likes,
                "replies": replies,
                "kind": kind,  # generator truth for tests; the provider never returns it
            }
        )
    return out


# ---------------------------------------------------------------------------- hashtags

HASHTAG_PAGES = {
    # tag: (posts on the page, weekly growth of new reels, base new reels/day 4 weeks ago)
    "ganpatioutfit": (182_000, 3.4, 9),
    "ganeshchaturthi": (4_800_000, 2.1, 40),
    "ganeshotsav": (1_900_000, 2.0, 18),
    "festivelook": (2_300_000, 1.3, 30),
    "festivestyling": (210_000, 1.4, 6),
    "ethnicstyling": (640_000, 1.05, 10),
    "mumbaistyle": (390_000, 1.05, 7),
    "mumbaifashion": (1_200_000, 1.0, 12),
    "oneoutfitthreeways": (58_000, 1.2, 2),
    "oneoutfitmanyways": (96_000, 1.15, 3),
    "outfitideas": (8_900_000, 1.0, 60),
    "indianwear": (3_100_000, 1.0, 25),
    "navratri": (5_200_000, 1.2, 20),
    "dupattastyling": (44_000, 1.1, 2),
    "revealfirst": (31_000, 1.6, 2),
    "stylingmistakes": (27_000, 1.5, 2),
    "reeltips": (510_000, 1.0, 8),
    "grwm": (19_000_000, 1.0, 120),
    "budgetfashion": (870_000, 1.1, 9),
}


def hashtag_pages(all_reels: dict[str, list[dict]]) -> dict[str, dict]:
    pages = {}
    for tag, (post_count, growth, base_per_day) in HASHTAG_PAGES.items():
        reels = []
        # The account reels that carry the tag (creator + peers)
        for owner, rs in all_reels.items():
            for r in rs:
                if tag in r["hashtags"] and -35 * D <= r["posted_h"] <= 0:
                    reels.append(
                        {
                            "ig_media_id": r["ig_media_id"],
                            "shortcode": r["shortcode"],
                            "owner": owner,
                            "posted_h": r["posted_h"],
                            "caption": r["caption"],
                            "hashtags": r["hashtags"],
                            "duration_s": r["duration_s"],
                            "views": round(views_at(-r["posted_h"], r["curve"])),
                            "likes": None,
                            "comments": None,
                        }
                    )
        # Plus other public accounts: new reels per day grow by `growth` each week.
        for day in range(28, 0, -1):
            rate = base_per_day * growth ** ((28 - day) / 7) / 4  # sample a quarter of them
            for _ in range(int(rate) + (1 if rng.random() < rate % 1 else 0)):
                posted = -day * D + rng.uniform(0, D)
                views = round(8_000 * lognormal(0.9))
                reels.append(
                    {
                        "ig_media_id": media_id(),
                        "shortcode": shortcode(),
                        "owner": f"creator_{rng.randrange(10_000, 99_999)}",
                        "posted_h": round(posted, 2),
                        "caption": f"#{tag}",
                        "hashtags": [tag],
                        "duration_s": round(rng.uniform(10, 60)),
                        "views": views,
                        "likes": round(views * 0.04),
                        "comments": round(views * 0.002),
                    }
                )
        pages[tag] = {
            "tag": tag,
            "post_count": post_count,
            "reels": sorted(reels, key=lambda r: r["posted_h"]),
        }
    return pages


# ---------------------------------------------------------------------------- festival calendar

FESTIVALS = [
    # id, name, start, end, verified (checked against panchang sources), keywords
    (
        "diwali-2026",
        "Diwali",
        "2026-11-08",
        "2026-11-08",
        False,
        ["diwali", "deepavali", "festive"],
    ),
    ("christmas-2026", "Christmas", "2026-12-25", "2026-12-25", True, ["christmas", "party"]),
    (
        "wedding-2026",
        "Wedding season",
        "2026-11-15",
        "2027-02-28",
        False,
        ["wedding", "sangeet", "mehendi", "haldi"],
    ),
    ("eid-al-fitr-2027", "Eid al-Fitr", "2027-03-10", "2027-03-10", False, ["eid", "eid outfit"]),
    ("holi-2027", "Holi", "2027-03-22", "2027-03-22", False, ["holi", "whites"]),
    (
        "raksha-bandhan-2027",
        "Raksha Bandhan",
        "2027-08-17",
        "2027-08-17",
        False,
        ["rakhi", "raksha bandhan"],
    ),
    (
        "ganesh-chaturthi-2027",
        "Ganesh Chaturthi",
        "2027-09-04",
        "2027-09-14",
        True,
        [
            "ganpati",
            "ganesh chaturthi",
            "ganeshotsav",
            "ganpati outfit",
            "pandal",
            "visarjan",
            "modak",
        ],
    ),
    (
        "navratri-2027",
        "Navratri",
        "2027-09-30",
        "2027-10-08",
        False,
        ["navratri", "garba", "dandiya", "chaniya choli"],
    ),
    ("dussehra-2027", "Dussehra", "2027-10-09", "2027-10-09", False, ["dussehra"]),
    (
        "karva-chauth-2027",
        "Karva Chauth",
        "2027-10-18",
        "2027-10-18",
        True,
        ["karva chauth", "red"],
    ),
    ("diwali-2027", "Diwali", "2027-10-29", "2027-10-29", True, ["diwali", "deepavali", "festive"]),
    (
        "wedding-2027",
        "Wedding season",
        "2027-11-15",
        "2028-02-28",
        False,
        ["wedding", "sangeet", "mehendi", "haldi"],
    ),
    ("christmas-2027", "Christmas", "2027-12-25", "2027-12-25", True, ["christmas", "party"]),
    ("eid-al-fitr-2028", "Eid al-Fitr", "2028-02-27", "2028-02-27", False, ["eid", "eid outfit"]),
    ("holi-2028", "Holi", "2028-03-11", "2028-03-11", True, ["holi", "whites"]),
    (
        "ganesh-chaturthi-2028",
        "Ganesh Chaturthi",
        "2028-08-23",
        "2028-09-02",
        True,
        [
            "ganpati",
            "ganesh chaturthi",
            "ganeshotsav",
            "ganpati outfit",
            "pandal",
            "visarjan",
            "modak",
        ],
    ),
    (
        "navratri-2028",
        "Navratri",
        "2028-09-19",
        "2028-09-27",
        False,
        ["navratri", "garba", "dandiya"],
    ),
    ("diwali-2028", "Diwali", "2028-10-17", "2028-10-17", True, ["diwali", "deepavali", "festive"]),
]


def festivals() -> list[dict]:
    return [
        {
            "id": fid,
            "name": name,
            "starts_on": start,
            "ends_on": end,
            "regions": ["IN", "IN-MH"] if "ganesh" in fid else ["IN"],
            "niches": ["fashion", "beauty", "lifestyle"]
            + (["food"] if "ganesh" in fid or "diwali" in fid else []),
            "keywords": kw,
            "verified": verified,
        }
        for fid, name, start, end, verified, kw in FESTIVALS
    ]


# ---------------------------------------------------------------------------- video understanding (T1)
#
# What a video model would report for each reel (transcript with timings, shots, on-screen
# text, a description per second, audio type, first payoff), written from the reel's DNA.
# The mock video provider serves these; the mock DNA extractor must then recover the DNA
# from them, so the real pipeline (T1 → T2 → embeddings → learning) runs end to end.
# A separate random stream keeps every count above unchanged.

t1rng = random.Random(SEED + 101)

NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "nine": 9}
COLORS = ["mustard", "maroon", "emerald", "ivory", "pastel pink", "royal blue", "rust", "teal"]
GARMENTS = ["lehenga", "anarkali", "saree", "sharara set", "kurta set", "chaniya choli"]
ACCESSORIES = ["jhumkas", "a potli bag", "kolhapuri chappals", "a statement choker", "bangles"]
HAUL_ITEMS = ["earrings", "kurta", "tote bag", "juttis", "co-ord set", "dupatta", "bangles"]
MARKETS = ["Colaba Causeway", "Linking Road", "the local market", "Hill Road"]
STYLINGS = [
    "belted with a potli bag",
    "with a long jacket on top",
    "draped over one shoulder",
    "tucked in with sneakers",
    "with statement jhumkas",
    "layered with a cape",
]
TIPS = [
    ("I used to film with the window behind me, so my face went dark",
     "you film with the window behind you, so your face goes dark"),
    ("I skipped the grid, so my eyes landed too low in the frame",
     "you skip the grid, so your eyes land too low in the frame"),
    ("I let the phone change exposure halfway through",
     "you let the phone change exposure halfway through"),
    ("I cut in the middle of a movement, so the transition jumped",
     "you cut in the middle of a movement, so the transition jumps"),
    ("I used the wide lens for close-ups", "you use the wide lens for close-ups"),
    ("I recorded in a room with an echo", "you record in a room with an echo"),
    ("I shot everything at eye level", "you shoot everything at eye level"),
]
STEPS = [
    "set the phone at chest height",
    "face the window",
    "lock the focus",
    "record three seconds of b-roll",
    "cut on the movement",
    "add captions last",
]
STYLE_TIPS = [
    ("I paired heavy jhumkas with a heavy neckline", "you pair heavy jhumkas with a heavy neckline"),
    ("I picked a dupatta that fought with the print", "you pick a dupatta that fights with the print"),
    ("I got the blouse length wrong", "you get the blouse length wrong"),
    ("I skipped pressing the pleats", "you skip pressing the pleats"),
    ("I matched everything to the exact same colour", "you match everything to the exact same colour"),
    ("I wore flat juttis with a long lehenga", "you wear flat juttis with a long lehenga"),
]
STYLE_STEPS = [
    "choose a single statement piece",
    "match the dupatta to the border",
    "pin the pleats",
    "add a contrast blouse",
    "finish with juttis",
]
# Hooks a viewer can read from the on-screen title alone; anything else, with no voice over a
# trending sound, is a trend-audio hook.
STRONG_HOOKS = ("mistake", "reveal", "how_to", "story", "curiosity_gap", "budget")
FESTIVE_WORDS = [
    "ganpati", "ganesh", "diwali", "navratri", "eid", "holi", "karva", "raksha", "independence",
    "christmas", "visarjan", "pandal", "dussehra", "festive",
]
WEDDING_WORDS = ["wedding", "sangeet", "haldi", "mehendi"]

CAMERA_PHRASES = {
    "tripod": ["steady tripod shot", "static shot from a tripod"],
    "handheld": ["handheld, slightly shaky", "handheld shot"],
    "mirror_selfie": ["mirror selfie, phone visible", "filmed in the mirror"],
    "selfie_handheld": ["selfie-style, arm's length"],
}
SETTING_PHRASES = {
    "bedroom": ["in a bedroom", "bedroom with a wardrobe behind"],
    "living_room": ["in a living room", "on the sofa in the living room"],
    "outdoors": ["outdoors on the street", "on a balcony"],
    "market": ["at a busy market stall"],
    "studio": ["against a studio backdrop"],
    "event_venue": ["at a decorated pandal", "at a decorated venue"],
    "office": ["at an office desk"],
}
LIGHT_PHRASES = {
    "warm_light": ["warm light", "warm golden glow"],
    "natural_light": ["soft daylight from a window", "natural window light"],
    "bright_even": ["bright, even light", "evenly lit"],
    "moody": ["dim, moody light"],
    "colourful": ["colourful, saturated frame"],
}
OPENING_DESC = {
    "face_to_camera": "The creator talks straight to the camera",
    "final_look_first": "The finished look is shown first, full length",
    "product_closeup": "Close-up of the {item} in hand",
    "mirror_shot": "Mirror shot of the creator in the outfit",
    "action_mid_shot": "The creator is already mid-way through getting ready",
    "text_over_broll": "Bold text over b-roll of the room",
}


def _explicit_count(title: str) -> int | None:
    for w in title.lower().replace(",", " ").replace(":", " ").split():
        if w.isdigit() and 1 < int(w) < 10:
            return int(w)
        if w in NUM_WORDS and NUM_WORDS[w] > 1:
            return NUM_WORDS[w]
    return None


def _count_in(title: str) -> int:
    return _explicit_count(title) or 3


def _hook_for(title: str, cluster: str) -> str:
    t = title.lower()
    if "mistake" in t or t.startswith("stop ") or "why your" in t:
        return "mistake"
    if "final look first" in t or "reveal" in t:
        return "reveal"
    if t.startswith("how i") or t.startswith("how to"):
        return "how_to"
    if "what i wore" in t:
        return "story"
    if "worth it" in t or "hits and misses" in t:
        return "curiosity_gap"
    if "₹" in t or "budget" in t:
        return "budget"
    if t.startswith(("grwm", "get ready with me")):
        return "relatable"
    if (cluster in ("multilook", "festive") and _explicit_count(title)) or t.startswith(
        ("one ", "two ", "1 ")
    ):
        return "number_list"
    return {"festive": "bold_claim", "tips": "how_to", "grwm": "relatable", "haul": "budget",
            "multilook": "number_list"}[cluster]


def _tension_for(dna: dict, title: str, caption: str = "") -> str:
    """The reel's core tension, from what drives it (in this order)."""
    t = title.lower()
    if dna["hook_type"] == "mistake":
        return "doing_it_wrong"
    if "₹" in t or "budget" in t or dna["format"] == "haul":
        return "budget_limit"
    asks = re.search(r"which (?:look|one|step) (?:would|were|do) you|pick one", caption.lower())
    if dna["ending"] == "choice_question" or asks:
        return "choice_dilemma"
    if dna.get("narrative") == "comparison":
        return "comparison"
    if dna["hook_type"] == "reveal":
        return "transformation"
    if dna["format"] in ("listicle", "tutorial"):
        return "insider_tip"
    if dna["format"] == "grwm":
        return "relatable_struggle"
    return "none"


def _strong_hook(title: str) -> str | None:
    """A hook the title alone makes clear (used when nobody speaks)."""
    t = title.lower()
    if "mistake" in t or t.startswith("stop ") or "why your" in t:
        return "mistake"
    if "final look first" in t or "reveal" in t:
        return "reveal"
    if t.startswith(("how i", "how to")):
        return "how_to"
    if "what i wore" in t:
        return "story"
    if "worth it" in t or "hits and misses" in t:
        return "curiosity_gap"
    if "₹" in t or "budget" in t:
        return "budget"
    if t.startswith(("grwm", "get ready with me")):
        return "relatable"
    return None


def _context_for(title: str, default: str = "everyday") -> str:
    t = title.lower()
    if any(w in t for w in WEDDING_WORDS):
        return "wedding"
    if any(w in t for w in FESTIVE_WORDS):
        return "festive"
    if "office" in t or "studio" in t:
        return "work"
    if "monsoon" in t or "rain" in t:
        return "seasonal"
    if " sale" in t:
        return "sale"
    return default


PEER_TOPIC_DNA = {
    "ganpati": {"format": "lookbook", "ending": "choice_question", "cta_type": "comment_prompt",
                "core_tension": "choice_dilemma"},
    "ganpati_reveal": {"format": "lookbook", "hook_type": "reveal", "opening_style": "final_look_first",
                       "narrative": "reveal_then_explain", "ending": "final_look",
                       "core_tension": "transformation"},
    "reveal": {"format": "lookbook", "hook_type": "reveal", "opening_style": "final_look_first",
               "narrative": "reveal_then_explain", "ending": "final_look",
               "core_tension": "transformation"},
    "mistakes": {"format": "listicle", "hook_type": "mistake", "ending": "recap",
                 "cta_type": "save_prompt", "pov": "second_person", "core_tension": "doing_it_wrong"},
    "multilook": {"format": "multi_look", "hook_type": "number_list", "ending": "choice_question",
                  "cta_type": "comment_prompt", "core_tension": "choice_dilemma"},
    "festive": {"format": "lookbook", "hook_type": "bold_claim", "ending": "final_look"},
    "grwm": {"format": "grwm", "hook_type": "relatable", "opening_style": "mirror_shot",
             "narrative": "step_by_step", "camera": "mirror_selfie", "ending": "final_look",
             "core_tension": "relatable_struggle"},
    "haul": {"format": "haul", "hook_type": "budget", "opening_style": "product_closeup",
             "camera": "handheld", "ending": "abrupt", "cta_type": "none",
             "setting": "living_room", "core_tension": "budget_limit"},
    "tips": {"format": "tutorial", "hook_type": "how_to", "narrative": "step_by_step",
             "ending": "recap", "cta_type": "save_prompt", "pov": "second_person",
             "core_tension": "insider_tip"},
    "everyday": {"format": "lookbook", "hook_type": "bold_claim", "ending": "final_look"},
}
PEER_BASE = {
    "niche": "fashion_styling", "format": "lookbook", "opening_style": "face_to_camera",
    "narrative": "list", "ending": "final_look", "cta_type": "comment_prompt",
    "pov": "first_person", "camera": "tripod", "audio": "original_speech",
    "visual_style": "natural_light", "setting": "bedroom", "core_tension": "choice_dilemma",
    "cuts": 3.2, "onscreen": 0.6,
}


def creator_truth(reels: list[dict]) -> None:
    """Finish each creator reel's DNA: the cluster's usual production plus the choices drawn
    in demo_reels() (ending, call to action, payoff time — the ones that shaped its rates),
    the hook its title implies, its occasion and its core tension."""
    for r in reels:
        meta = r["meta"]
        dna = {k: v for k, v in meta.items() if k in CLUSTER_DNA["festive"] or k in (
            "hook_type", "payoff_s")}
        title = meta["title"]
        dna.setdefault("hook_type", _hook_for(title, meta["cluster"]))
        dna["context"] = _context_for(r["caption"])
        dna["characters"] = "creator_solo"
        if dna["hook_type"] == "reveal":
            dna["opening_style"] = "final_look_first"
        if dna["hook_type"] == "story":
            dna["narrative"] = "comparison"
        dna["core_tension"] = _tension_for(dna, title, r["caption"])
        meta["dna"] = dna


def peer_truth(reels: list[dict]) -> None:
    for r in reels:
        meta = r["meta"]
        topic = meta["topic"]
        dna = dict(PEER_BASE, **PEER_TOPIC_DNA[topic])
        dna.setdefault("hook_type", "number_list")
        festive_topic = topic.startswith("ganpati") or topic == "festive"
        dna["context"] = _context_for(r["caption"], "festive" if festive_topic else "everyday")
        dna["camera"] = dna["camera"] if "camera" in PEER_TOPIC_DNA[topic] else t1rng.choice(
            ["tripod", "tripod", "handheld"])
        dna["visual_style"] = t1rng.choice(["natural_light", "warm_light", "bright_even"])
        dna["setting"] = dna["setting"] if "setting" in PEER_TOPIC_DNA[topic] else t1rng.choice(
            ["bedroom", "bedroom", "outdoors", "living_room"])
        dna["audio"] = "trending_audio" if r["audio_name"] != "Original audio" and t1rng.random() < 0.5 else "original_speech"
        dna["cuts"] = round(dna["cuts"] * math.exp(t1rng.gauss(0, 0.2)), 1)
        t1rng.uniform(0.8, 5.0)  # (keeps this stream's later draws where they were)
        dna["ending"], dna["payoff_s"], dna["cta_type"] = (
            meta["ending"],
            meta["payoff_s"],
            meta["cta_type"],
        )
        dna["characters"] = "creator_with_friend" if t1rng.random() < 0.1 else "creator_solo"
        dna["core_tension"] = _tension_for(dna, meta["title"], r["caption"])
        meta["dna"] = dna


def _say(words: list[dict], t: float, sentence: str, rate: float = 2.6) -> float:
    for w in sentence.split():
        words.append({"t": round(t, 2), "word": w})
        t += t1rng.uniform(0.85, 1.15) / rate
    return t + 0.35


def build_t1(r: dict) -> dict:
    """The T1 output a video model would report for this reel."""
    meta, dna = r["meta"], r["meta"]["dna"]
    title = meta["title"]
    dur = float(r["duration_s"])
    n = _count_in(title)
    fmt, hook, ending, cta, pov = (dna[k] for k in ("format", "hook_type", "ending", "cta_type", "pov"))
    color, garment, accessory = t1rng.choice(COLORS), t1rng.choice(GARMENTS), t1rng.choice(ACCESSORIES)
    item = t1rng.choice(HAUL_ITEMS)
    base = next((g for g in ("kurta", "dupatta", "saree", "shirt", "jacket", "co-ord", "blouse",
                             "skirt") if g in title.lower()), "outfit")
    occasion = next((w.capitalize() for w in FESTIVE_WORDS + WEDDING_WORDS if w in title.lower()), None)

    # --- what is said
    hook_line = {
        "mistake": f"{title}." if "mistake" in title.lower() else "You're making this mistake and it's ruining your reels.",
        "how_to": f"Here's {title[0].lower() + title[1:]}." if title.lower().startswith("how") else "Here's how I do it.",
        "number_list": f"{title}.",
        "bold_claim": f"{title}. Trust me, this is the only way to do it.",
        "relatable": "Get ready with me, because I'm already running late.",
        "curiosity_gap": f"{title}. Wait till you see the last one.",
        "story": f"So this happened. {title}.",
        "reveal": "Final look first, then I'll show you how I did it.",
        "budget": f"{title}, and everything is under budget.",
        "question": f"Do you also struggle with this? {title}.",
    }.get(hook, f"{title}.")
    body: list[str] = []
    filming = dna["niche"] == "creator_tips"
    if fmt == "listicle":
        bank = TIPS if filming else STYLE_TIPS
        for k in range(n):
            tip = bank[(k + len(title)) % len(bank)][0 if pov == "first_person" else 1]
            label = "Mistake" if hook == "mistake" else "Tip"
            body.append(f"{label} number {k + 1}: {tip}.")
    elif fmt == "tutorial":
        bank = STEPS if filming else STYLE_STEPS
        for k in range(min(n, len(bank))):
            body.append(f"Step {k + 1}: {bank[(k + len(title)) % len(bank)]}.")
    elif fmt == "lookbook":
        for k in range(n):
            body.append(f"Look number {k + 1}: I'm wearing a {COLORS[(k + len(title)) % len(COLORS)]} "
                        f"{GARMENTS[(k * 2 + len(title)) % len(GARMENTS)]} with {ACCESSORIES[k % len(ACCESSORIES)]}.")
        if occasion:
            body.append(f"Perfect for {occasion}.")
    elif fmt == "multi_look":
        for k in range(n):
            body.append(f"Same {base}, look number {k + 1}: I wore it {STYLINGS[(k + len(title)) % len(STYLINGS)]}.")
    elif fmt == "grwm":
        body += [
            "Starting with skincare because the humidity is unreal.",
            "Quick base, just concealer and sunscreen.",
            "Kohl and a little highlight.",
            f"Now the outfit, a {color} {garment}.",
            f"Adding {accessory} because why not.",
        ]
    elif fmt == "haul":
        for k in range(4):
            it = HAUL_ITEMS[(k + len(title)) % len(HAUL_ITEMS)]
            this = "these" if it.endswith("s") else "this"
            price = t1rng.choice([150, 250, 299, 450, 600, 899])
            body.append(("First up, I got " if k == 0 else "Next, I got ") + f"{this} {it} for ₹{price}.")
        body.append("This one was a miss, the fabric is see-through.")
        body.append(f"All from {t1rng.choice(MARKETS)}.")
    if dna.get("narrative") == "reveal_then_explain":
        body.insert(0, "Now let me show you how I put it together.")
    if dna.get("narrative") == "comparison":
        body.insert(0, "Last year I went traditional, this year I want to try something new.")
    ending_line = {
        "choice_question": {"listicle": "Which one were you making, one, two or three?",
                            "tutorial": "Which step do you skip, one, two or three?",
                            "haul": "Which one would you buy, one, two or three?"}.get(
                                fmt, "Which look would you pick, one, two or three?")
        + (" Tell me in the comments." if cta == "comment_prompt" else ""),
        "recap": ("Quick recap: window in front, grid on, exposure locked." if filming
                  else "Quick recap: one statement piece, a matching dupatta, pressed pleats.")
        if fmt in ("listicle", "tutorial") else "Quick recap of all the looks.",
        "final_look": "And that's the final look.",
        "reveal": "And that's the reveal.",
        "cliffhanger": "Part two tomorrow.",
        "open_question": "What would you add? Let me know.",
    }.get(ending, "")
    cta_line = {
        "save_prompt": "Save this before your next shoot." if fmt in ("listicle", "tutorial")
        else "Save this for the season.",
        "share_prompt": "Send this to the friend who needs it.",
        "follow_prompt": "Follow for more.",
        "part_two_tease": "Follow for part two.",
        "comment_prompt": "" if ending == "choice_question" else "Tell me in the comments.",
    }.get(cta, "")

    words: list[dict] = []
    speech = dna["audio"] in ("original_speech", "voiceover", "mixed")
    if speech:
        t = 0.4
        for line in [hook_line, *body, ending_line, cta_line]:
            if line:
                t = _say(words, t, line)
        if words and t > dur - 0.3:  # squeeze into the video's length
            k = (dur - 0.6) / t
            for w in words:
                w["t"] = round(w["t"] * k, 2)

    # --- cuts
    n_cuts = max(1, round(dna["cuts"] * dur / 10 * t1rng.uniform(0.92, 1.08)))
    cuts = sorted(round(t1rng.uniform(0.8, dur - 0.5), 2) for _ in range(n_cuts))
    edges = [0.0, *cuts, dur]
    shots = [{"start": a, "end": b} for a, b in zip(edges, edges[1:], strict=False) if b - a > 0.05]

    # --- on-screen text
    onscreen: list[dict] = []
    if t1rng.random() < dna["onscreen"]:
        onscreen.append({"t": 0.2, "text": title})
        label = {"listicle": "Mistake" if hook == "mistake" else "Tip", "tutorial": "Step",
                 "lookbook": "Look", "multi_look": "Look"}.get(fmt)
        if label:
            for k in range(n):
                onscreen.append({"t": round(2 + k * (dur - 6) / max(1, n), 1), "text": f"{label} {k + 1}"})
    elif not speech:
        onscreen.append({"t": 0.2, "text": title})
    if not speech:  # no voice: the ending and the call to action are written on screen
        dna["pov"] = "observational"
        if dna["audio"] == "trending_audio":  # the viewer only has the title to read
            dna["hook_type"] = _strong_hook(title) or "trend_audio"
        # These need words: spoken, or step and tip labels on screen.
        labels = any(o["text"].startswith(("Step", "Tip", "Mistake")) for o in onscreen)
        if dna["core_tension"] == "relatable_struggle" or (
            dna["core_tension"] == "insider_tip" and not labels
        ):
            dna["core_tension"] = "none"
        end_text = {"choice_question": "Which one would you pick?", "recap": "Quick recap",
                    "final_look": "Final look"}.get(ending)
        cta_text = {"comment_prompt": "Comment below", "save_prompt": "Save this",
                    "share_prompt": "Send this to a friend", "follow_prompt": "Follow for more"}.get(cta)
        for k, text in enumerate(x for x in (end_text, cta_text) if x):
            onscreen.append({"t": round(max(0.5, dur - 2.5 + k), 1), "text": text})

    # --- a description per second
    show_setting = t1rng.random() > 0.12  # sometimes the place can't be told
    show_light = t1rng.random() > 0.08
    cam = t1rng.choice(CAMERA_PHRASES[dna["camera"]]) if dna["camera"] in CAMERA_PHRASES else None
    visual = {
        "listicle": ["The creator demonstrates on the phone screen", "Side-by-side of the wrong and the right shot",
                     "The creator points at the window"] if filming else
                    ["Side-by-side of the wrong and the right way to wear it", f"Detail shot of the {accessory}",
                     "The creator points at the outfit"],
        "tutorial": ["The creator demonstrates each step", "Screen recording of the camera settings"] if filming
                    else ["The creator demonstrates each step", f"Close-up of the {garment} pleats"],
        "lookbook": [f"The creator turns to show the {color} {garment}", f"Detail shot of the {accessory}",
                     "Full-length shot of the next look"],
        "multi_look": [f"The same {base} restyled for the next look", "Quick change to the next look",
                       f"Detail shot of the {accessory}"],
        "grwm": ["The creator applies skincare", "Close-up of the makeup", f"The creator puts on the {garment}"],
        "haul": ["Items laid out on the sofa", f"The creator holds up the {item}", "Price tag shown to the camera"],
    }[fmt]
    if dna.get("characters") == "creator_with_friend":
        visual = [v + " with a friend" for v in visual]
    seconds = []
    for s in range(int(math.ceil(dur))):
        if s < 2:
            subject = OPENING_DESC[dna["opening_style"]].format(item=item)
        elif s == int(dna["payoff_s"]):
            subject = {"listicle": "The first tip is shown", "tutorial": "The first step is shown",
                       "haul": f"The first item, a {item}, is shown"}.get(fmt, "The first look is shown")
        elif s >= dur - 2 and ending in ("choice_question", "final_look", "reveal"):
            subject = {"choice_question": "The creator asks viewers to pick one",
                       "final_look": "Full-length final look", "reveal": "The final reveal"}[ending]
        else:
            subject = visual[(s // 3) % len(visual)]
        parts = [subject]
        if cam and (s % 3 == 0 or t1rng.random() < 0.3):
            parts.append(cam)
        if s % 4 == 1 or t1rng.random() < 0.2:
            parts.append(t1rng.choice(SETTING_PHRASES[dna["setting"]]) if show_setting else "plain background")
        if show_light and (s % 4 == 2 or t1rng.random() < 0.2):
            parts.append(t1rng.choice(LIGHT_PHRASES[dna["visual_style"]]))
        seconds.append({"t": float(s), "description": ", ".join(parts)})

    return {
        "duration_s": dur,
        "transcript": words,
        "shots": shots,
        "onscreen_text": onscreen,
        "seconds": seconds,
        "audio_type": dna["audio"],
        "first_payoff_s": dna["payoff_s"],
    }


def add_understanding(all_reels: dict[str, list[dict]]) -> dict[str, dict[str, dict]]:
    """Finish each reel's DNA (stored in its meta for tests) and build its T1 output."""
    creator_truth(all_reels[DEMO])
    out: dict[str, dict[str, dict]] = {}
    for owner, reels in all_reels.items():
        if owner != DEMO:
            peer_truth(reels)
        out[owner] = {r["shortcode"]: build_t1(r) for r in reels}
    return out


# ---------------------------------------------------------------------------- main


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "reels").mkdir(parents=True)
    (OUT / "comments").mkdir()
    (OUT / "t1").mkdir()

    accounts = [
        {
            "username": DEMO,
            "full_name": "Curo Demo",
            "bio": "Mumbai · festive styling, GRWMs & reel-making tips ✨ (CURO demo account)",
            "category": "Fashion",
            "followers": {"base": 48_200, "per_day": 45, "jumps": [{"at_h": -48, "add": 650}]},
            "following": 612,
            "posts_at_anchor": 412,
            "region": "Mumbai",
            "role": "creator",
        }
    ]
    all_reels: dict[str, list[dict]] = {DEMO: demo_reels()}
    for username, name, followers, reach in PEERS:
        accounts.append(
            {
                "username": username,
                "full_name": name,
                "bio": f"{name} · fashion & styling",
                "category": "Fashion",
                "followers": {"base": followers, "per_day": round(followers * 0.0008)},
                "following": rng.randrange(300, 1200),
                "posts_at_anchor": rng.randrange(180, 900),
                "region": rng.choice(["Mumbai", "Pune", "Delhi", "Bengaluru"]),
                "role": "peer",
            }
        )
        all_reels[username] = peer_reels(username, followers, reach)

    # Video understanding (separate random stream; also finishes each reel's DNA in meta).
    understanding = add_understanding(all_reels)
    for owner, by_code in understanding.items():
        (OUT / "t1" / f"{owner}.json").write_text(
            json.dumps(by_code, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )

    # Comments: up to ~60 texts on the creator's reels, ~12 on peers'.
    for owner, reels in all_reels.items():
        by_reel = {}
        for r in reels:
            peer = owner != DEMO
            age_now = max(0.0, -r["posted_h"])
            expected = r["rates"]["comment"] * views_at(age_now or 72, r["curve"])
            n = min(12 if peer else 60, max(4, round(expected * (0.3 if peer else 0.6))))
            story = None if peer else r["meta"].get("story")
            by_reel[r["shortcode"]] = comments_for(r, owner, n, story, peer)
        (OUT / "comments" / f"{owner}.json").write_text(
            json.dumps(by_reel, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        (OUT / "reels" / f"{owner}.json").write_text(
            json.dumps(reels, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    (OUT / "accounts.json").write_text(
        json.dumps(accounts, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (OUT / "hashtags.json").write_text(
        json.dumps(hashtag_pages(all_reels), ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (OUT / "festivals.json").write_text(
        json.dumps(festivals(), ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (OUT / "meta.json").write_text(
        json.dumps(
            {
                "version": 1,
                "seed": SEED,
                "anchor": ANCHOR,
                "demo_handle": DEMO,
                "peers": [p[0] for p in PEERS],
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    n_reels = sum(len(v) for v in all_reels.values())
    samples = sample_recordings()
    print(f"wrote {len(accounts)} accounts, {n_reels} reels, {len(samples)} samples to {OUT}")


# ---------------------------------------------------------------------------- Simulator samples

# Two recordings of the Ganpati "one outfit, three looks" draft, for trying the Simulator in
# demo mode (Phase 7): a first take, and the same reel re-recorded with the edits a creator
# would be offered (final look first, a label on each look, a send-to-a-friend ending).
# Like the reels, each is a DNA description a video model's report is written from.
SAMPLE_TAKES = [
    {
        "name": "take1",
        "title": "First take",
        "description": "One outfit, three Ganpati looks · 0:41",
        "duration_s": 41,
        "meta": {
            "title": "Same outfit, three looks for Ganpati",
            "dna": {
                "niche": "fashion_styling", "format": "multi_look",
                "opening_style": "product_closeup", "narrative": "list",
                "ending": "choice_question", "cta_type": "comment_prompt",
                "pov": "first_person", "camera": "tripod", "audio": "original_speech",
                "visual_style": "natural_light", "setting": "bedroom",
                "core_tension": "choice_dilemma", "cuts": 2.6, "onscreen": 0.0,
                "payoff_s": 3.8, "hook_type": "number_list", "context": "festive",
                "characters": "creator_solo",
            },
        },
    },
    {
        "name": "take2",
        "title": "Re-recorded with the edits",
        "description": "Final look first · a send-to-a-friend ending · 0:32",
        "duration_s": 32,
        "meta": {
            "title": "Same outfit, three looks for Ganpati",
            "dna": {
                "niche": "fashion_styling", "format": "multi_look",
                "opening_style": "final_look_first", "narrative": "reveal_then_explain",
                "ending": "choice_question", "cta_type": "share_prompt",
                "pov": "first_person", "camera": "tripod", "audio": "original_speech",
                "visual_style": "natural_light", "setting": "bedroom",
                "core_tension": "choice_dilemma", "cuts": 3.9, "onscreen": 1.0,
                "payoff_s": 0.9, "hook_type": "reveal", "context": "festive",
                "characters": "creator_solo",
            },
        },
    },
]  # fmt: skip


def sample_recordings() -> list[dict]:
    """Write fixtures/data/samples.json and the takes' T1 (t1/samples.json), on their own
    random stream so the reels' data never changes because of them."""
    global t1rng
    saved, t1rng = t1rng, random.Random(SEED + 707)
    try:
        t1 = {f"sample-{t['name']}": build_t1(t) for t in SAMPLE_TAKES}
    finally:
        t1rng = saved
    listing = [
        {
            "name": t["name"],
            "title": t["title"],
            "description": t["description"],
            "shortcode": f"sample-{t['name']}",
            "caption": f"{t['meta']['title']} #ganpatioutfit #festivestyling",
            "duration_s": t["duration_s"],
            "width": 1080,
            "height": 1920,
        }
        for t in SAMPLE_TAKES
    ]
    (OUT / "t1" / "samples.json").write_text(
        json.dumps(t1, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    (OUT / "samples.json").write_text(json.dumps(listing, indent=1), encoding="utf-8")
    return listing


if __name__ == "__main__":
    main()
