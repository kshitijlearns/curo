"""Studio logic (logic doc §9–§12), checked against the doc's own worked numbers."""

import math
from datetime import date

import pytest

from curo.schemas.tasks import VoiceProfile
from curo.services import captions as cap
from curo.services import ideas, script, storyboard, voice

TODAY = date(2027, 8, 23)


def unit(angle_deg: float) -> list[float]:
    """A 2-d unit vector: cosine similarity between two of them is cos(angle difference)."""
    a = math.radians(angle_deg)
    return [math.cos(a), math.sin(a)]


def scored(
    text: str, parts: dict[str, float], vector: list[float], fmt: str = "lookbook"
) -> ideas.Scored:
    c = ideas.Candidate(text=text, format=fmt, hook_type="unknown", target="views", vector=vector)
    return ideas.Scored(
        c, {k: ideas.Part(v, []) for k, v in parts.items()}, round(ideas.idea_score(parts), 4)
    )


def empty_ctx(**kw) -> ideas.Context:
    return ideas.Context(
        today=TODAY,
        groups=kw.get("groups", []),
        formats=kw.get("formats", {}),
        cards=[],
        themes=kw.get("themes", []),
        trend=kw.get("trend", ideas.TrendFact()),
        recent=[],
    )


# ---------------------------------------------------------------- the idea score


def test_the_v2_worked_example_scores_0_760_and_0_620():
    """PLAN_V2 §4.1: 0.40 H + 0.30 A + 0.20 T + 0.10 N (no peers).
    H .80 A .70 T .90 N .50 → 0.320 + 0.210 + 0.180 + 0.050 = 0.760, shares 42/28/24/6."""
    first = {"H": 0.80, "A": 0.70, "T": 0.90, "N": 0.50}
    second = {"H": 0.30, "A": 0.80, "T": 0.85, "N": 0.90}
    assert ideas.idea_score(first) == pytest.approx(0.760)
    assert ideas.shares(first) == {"H": 42, "A": 28, "T": 24, "N": 6}
    assert ideas.idea_score(second) == pytest.approx(0.620)
    assert ideas.WEIGHTS == {"H": 0.40, "A": 0.30, "T": 0.20, "N": 0.10}


def test_the_diversity_rule_gives_the_third_slot_to_prasad_not_the_budget_idea():
    """Budget idea 0.74 but 0.82 similar to idea 1 → 0.27; prasad 0.62, 0.25 similar → 0.36."""
    first = scored(
        "Styling the same outfit 3 ways",
        {"H": 0.9, "A": 0.7, "T": 0.8, "N": 0.4},
        unit(0),
    )
    budget = scored(
        "5 Ganpati outfits under ₹1,000",
        {"H": 0.74, "A": 0.74, "T": 0.74, "N": 0.74},
        unit(math.degrees(math.acos(0.82))),
    )
    prasad = scored("Quick prasad recipes", {"H": 0.3, "A": 0.8, "T": 0.85, "N": 0.9}, unit(math.degrees(math.acos(0.25))))  # fmt: skip
    assert budget.score == pytest.approx(0.74)
    assert ideas.diversity_value(budget, [first]) == pytest.approx(0.7 * 0.74 - 0.3 * 0.82)
    assert ideas.diversity_value(prasad, [first]) == pytest.approx(0.7 * 0.62 - 0.3 * 0.25)
    assert round(ideas.diversity_value(budget, [first]), 2) == 0.27
    assert round(ideas.diversity_value(prasad, [first]), 2) == 0.36


def test_three_slots_get_three_different_kinds_of_idea():
    ctx = empty_ctx(formats={"multi_look": ideas.FormatStat("multi_look", 8, {"views": 1.4})})
    proven = scored(
        "Same outfit 3 ways",
        {"H": 0.9, "A": 0.5, "T": 0.3, "N": 0.3},
        unit(0),
        "multi_look",
    )
    copy = scored(
        "Same outfit 4 ways",
        {"H": 0.9, "A": 0.5, "T": 0.3, "N": 0.3},
        unit(2),
        "multi_look",
    )
    trend = scored(
        "Ganpati looks for #ganpatioutfit",
        {"H": 0.5, "A": 0.3, "T": 0.9, "N": 0.5},
        unit(60),
        "vlog",
    )
    fresh = scored("My mom styles me", {"H": 0.3, "A": 0.4, "T": 0.3, "N": 0.9}, unit(120), "skit")  # fmt: skip
    picked = ideas.pick_three([copy, trend, fresh, proven], ctx)
    assert [s.slot for s in picked] == ["proven", "adapted", "explore"]
    assert picked[0].candidate.text in ("Same outfit 3 ways", "Same outfit 4 ways")
    assert {p.candidate.text for p in picked[1:]} == {
        "Ganpati looks for #ganpatioutfit",
        "My mom styles me",
    }


def test_shares_are_each_parts_share_of_the_score_in_whole_percents():
    parts = {"H": 0.90, "A": 0.70, "T": 0.80, "N": 0.40}
    shares = ideas.shares(parts)
    assert sum(shares.values()) == 100
    total = ideas.idea_score(parts)
    for k, v in shares.items():
        assert abs(v - 100 * ideas.WEIGHTS[k] * parts[k] / total) < 1


def test_verdict_bands():
    assert ideas.verdict(0.75) == "Strong"
    assert ideas.verdict(0.749) == "Worth trying"
    assert ideas.verdict(0.55) == "Worth trying"
    assert ideas.verdict(0.549) == "Risky"


def test_history_counts_usual_as_half_and_one_and_a_half_times_as_full():
    assert ideas.lift_credit(1.0) == 0.5
    assert ideas.lift_credit(1.5) == 1.0
    assert ideas.lift_credit(0.4) == 0.0


def test_a_theme_is_answered_when_cited_or_named_not_by_vague_similarity():
    theme = ideas.ThemeFact(
        "asks where it's from", "Asks where it's from", 0.16, 248, unit(80), {"where"}
    )
    ctx = empty_ctx(themes=[theme])
    named = ideas.Candidate(
        "Where every piece of my look is from", "lookbook", "question", "comments", unit(0)
    )
    cited = ideas.Candidate(
        "Shopping links, finally",
        "lookbook",
        "question",
        "comments",
        unit(0),
        evidence_ids=["theme:asks where it's from"],
    )
    neither = ideas.Candidate("Three looks", "lookbook", "number_list", "views", unit(0))  # fmt: skip
    assert ideas.matched_themes(named, ctx) == [theme]
    assert ideas.matched_themes(cited, ctx) == [theme]
    assert ideas.matched_themes(neither, ctx) == []


def test_timing_uses_the_festival_the_idea_is_about():
    trend = ideas.TrendFact(
        festival="Ganesh Chaturthi",
        starts_on=date(2027, 9, 4),
        ends_on=date(2027, 9, 14),
        keywords={"ganpati"},
        others=[ideas.Festival("Navratri", date(2027, 9, 30), date(2027, 10, 8), {"navratri"})],
    )
    ctx = empty_ctx(trend=trend)
    ganpati = ideas.Candidate("Ganpati looks", "lookbook", "unknown", "views", unit(0))
    navratri = ideas.Candidate("Navratri looks", "lookbook", "unknown", "views", unit(0))
    plain = ideas.Candidate("Office looks", "lookbook", "unknown", "views", unit(0))
    assert ideas.part_t(ganpati, ctx).facts[0] == "Ganesh Chaturthi starts in 12 days."
    assert ideas.part_t(navratri, ctx).facts[0] == "Navratri starts in 38 days."
    assert ideas.part_t(plain, ctx).value == pytest.approx(0.6 * 0.2 + 0.4 * 0.3)


# ---------------------------------------------------------------- the script


def test_word_budget_2_6_words_a_second_for_32_seconds_is_about_83_words():
    v = VoiceProfile(words_per_second=2.6, sentence_words=8)
    assert voice.word_budget(32, v) == 83


def test_voice_profile_is_measured_from_transcripts():
    def t(words: list[str], span: float) -> dict:
        step = span / (len(words) - 1)
        return {"transcript": [{"t": i * step, "word": w} for i, w in enumerate(words)]}

    lines = [
        "Tell",
        "me",
        "in",
        "the",
        "comments",
        "which",
        "look",
        "you",
        "would",
        "pick",
        "today.",
    ]
    profile = voice.profile([t(lines * 2, 10.0), t(lines * 2, 8.0), t(lines * 2, 12.0)])
    assert profile.reels == 3
    assert profile.words_per_second == pytest.approx(22 / 10.0, abs=0.01)
    assert "Tell me in the comments" in profile.phrases  # opening words, up to five
    thin = voice.profile([t(lines, 5.0)])
    assert thin.reels == 1 and thin.words_per_second == voice.DEFAULT_WPS


def test_length_band_is_where_the_format_does_best():
    reels = [
        script.ReelLength("multi_look", 28, 1.6),
        script.ReelLength("multi_look", 32, 1.4),
        script.ReelLength("multi_look", 50, 0.9),
        script.ReelLength("multi_look", 55, 1.0),
        script.ReelLength("haul", 30, 0.4),
    ]
    band = script.length_band(reels, "multi_look")
    assert (band.low, band.high, band.seconds, band.n) == (25, 35, 30, 2)
    fallback = script.length_band(reels, "grwm")
    assert fallback.basis == "all your reels"


def test_structure_follows_the_idea_and_the_creators_strongest_reels():
    examples = [
        script.Example("One kurta, five looks. Look number 1: belted.", ["Look 1", "Look 5"], "choice_question"),
        script.Example("One saree. Look number 1: draped.", ["Look 3"], "choice_question"),
        script.Example("One shirt. Look number 1: tucked.", ["Look 4"], "final_look"),
    ]  # fmt: skip
    beats = script.structure(
        "multi_look", "Styling the same outfit 3 different ways", "views", examples
    )
    assert [r for r, _ in beats] == ["hook", "item", "item", "item", "ending"]
    assert beats[-1][1] == script.ENDINGS["comments"][1]  # their usual ending
    shares = script.structure("multi_look", "Same outfit", "shares", examples)
    assert shares[-1][1] == script.ENDINGS["shares"][1]  # the idea aims at shares
    assert sum(1 for r, _ in shares if r == "item") == 4  # the median of 5, 3 and 4 looks


def test_plan_splits_the_budget():
    plan = script.plan([("hook", ""), ("item", ""), ("item", ""), ("item", ""), ("ending", "")], 83)
    words = [p.words for p in plan]
    assert words[0] == round(83 * 0.15) and words[-1] == round(83 * 0.15)
    assert words[1] == words[2] == words[3] == round(83 * 0.7 / 3)


def note_card(**kw) -> script.NoteCard:
    base = dict(
        id="c1",
        feature="ending",
        value="choice_question",
        metric="comment_rate",
        effect=1.66,
        n=9,
        scope="yours",
    )
    return script.NoteCard(**{**base, **kw})  # fmt: skip


def test_only_notes_a_pattern_card_backs_are_kept():
    cards = {
        "c1": note_card(),
        "c2": note_card(id="c2", value="final_look", metric="comment_rate", effect=0.63),
        "c3": note_card(
            id="c3", feature="cta_type", value="share_prompt", metric="share_rate", effect=1.43
        ),
    }
    labels = [
        ("b6", "comments", "c1"),  # backed
        ("b5", "likes", "c2"),  # wrong metric and an effect below 1: dropped
        ("b1", "hook", "nope"),  # no such card: dropped
        ("b6", "shares", "c3"),  # one note per line
    ]
    kept = script.keep_supported(labels, cards)
    assert list(kept) == ["b6"]
    n = kept["b6"]
    assert n["title"] == "Drives comments"
    assert (
        n["evidence"]
        == "Your reels with choice-question endings got 1.66× your usual comments per view (9 reels)."
    )
    assert "will" not in n["desc"] and n["desc"].startswith("Curo links this kind of line")


def test_a_revision_keeps_untouched_beats_word_for_word():
    before = [
        {"id": "b1", "role": "hook", "text": "Old hook."},
        {"id": "b2", "role": "item", "text": "Look number 1: belted."},
        {"id": "b3", "role": "ending", "text": "Which one?"},
    ]
    after, changed = script.merge_revision(
        before, {"b1": "New hook.", "b2": "SHOULD NOT APPEAR", "b3": "Which one?"}, {"b1", "b3"}
    )
    assert [b["text"] for b in after] == ["New hook.", "Look number 1: belted.", "Which one?"]
    assert changed == ["b1"]


def test_the_creators_own_script_is_kept_as_written():
    text = "One outfit, three ways.\nLook one: belted\nLook two: layered.\nWhich is yours?"
    beats = script.split_own(text)
    assert [line for _, line in beats] == text.splitlines()
    assert [r for r, _ in beats] == ["hook", "item", "item", "ending"]


# ---------------------------------------------------------------- the storyboard


def frame(beat_id: str, **kw) -> dict:
    base = {
        "beat_id": beat_id,
        "id": f"f-{beat_id}",
        "line": f"line {beat_id}",
        "setting": "bedroom",
        "lighting": "natural_light",
        "camera": "tripod",
        "needs_helper": False,
        "outfit_change": False,
        "start_s": 0.0,
        "end_s": 4.0,
    }
    return {**base, **kw}


def test_frames_link_to_beats_by_id_with_the_beats_timing():
    beats = [
        {"id": "b1", "text": "Hook.", "start_s": 0.0, "end_s": 3.5},
        {"id": "b2", "text": "Look number 1.", "start_s": 3.5, "end_s": 7.0},
    ]
    drawn = [{"beat_id": "b2", "shot_type": "Full"}, {"beat_id": "b1", "shot_type": "Close"}]
    frames = storyboard.assemble(beats, drawn)
    assert [(f["beat_id"], f["shot_type"], f["t"]) for f in frames] == [
        ("b1", "Close", "0:00 – 0:04"),
        ("b2", "Full", "0:04 – 0:07"),
    ]


def test_feasibility_counts_four_costs():
    easy = storyboard.feasibility([frame("b1"), frame("b2")])
    assert (
        easy["label"] == "Easy"
        and easy["detail"] == "one location · no helper needed · one light setup"
    )
    hard = storyboard.feasibility(
        [
            frame("b1"),
            frame("b2", setting="outdoors", needs_helper=True, lighting="warm_light"),
            frame("b3", setting="market", outfit_change=True),
        ]
    )
    assert hard["costs"] == {"locations": 2, "helper": 1, "changes": 1, "lighting": 1}
    assert hard["label"] == "Hard"


def test_easier_merges_places_drops_the_helper_and_keeps_the_hook_frame():
    frames = [
        frame("b1", setting="outdoors", camera="handheld"),
        frame("b2", setting="bedroom", needs_helper=True, camera="handheld"),
        frame("b3", setting="bedroom", lighting="warm_light"),
    ]
    easier, changed = storyboard.make_easier(frames, "tripod")
    assert easier[0] == frames[0]  # the hook frame as it was
    assert {f["setting"] for f in easier[1:]} == {"bedroom"}
    assert not any(f["needs_helper"] for f in easier)
    assert storyboard.feasibility(easier)["score"] > storyboard.feasibility(frames)["score"]
    assert changed == ["b2", "b3"]


def test_pacing_keeps_the_total_inside_the_length_band():
    frames = [frame(f"b{i}", start_s=i * 6.0, end_s=(i + 1) * 6.0) for i in range(5)]  # 30 s
    faster = storyboard.repace(frames, True, (25, 35))
    assert faster[-1]["end_s"] == pytest.approx(25.5)
    much = storyboard.repace(faster, True, (25, 35))
    assert much[-1]["end_s"] == pytest.approx(25.0)  # never below the band


def test_frames_whose_line_changed_are_stale():
    frames = [frame("b1", line="Hook."), frame("b2", line="Look 1.")]
    beats = [{"id": "b1", "text": "Hook."}, {"id": "b2", "text": "Look 1, now a saree."}]
    assert storyboard.stale(frames, beats) == ["f-b2"]


# ---------------------------------------------------------------- captions and hashtags


def test_never_more_than_five_hashtags():
    assert cap.normalise_tags(["#GanpatiOutfit", "ganpatioutfit", " #Festive "]) == [
        "ganpatioutfit",
        "festive",
    ]
    with pytest.raises(cap.HashtagLimit):
        cap.normalise_tags(["a", "b", "c", "d", "e", "f"])


def test_hashtag_score_is_half_relevance_three_tenths_results_a_fifth_specificity():
    vocab = {"ganpati", "outfit", "look"}
    tags = cap.score_tags(
        [
            cap.TagEvidence("ganpatioutfit", creator_lifts=[1.5], doc_share=0.05),
            cap.TagEvidence("reels", doc_share=0.5),
        ],
        vocab,
        festival_tags=set(),
        series=set(),
        region_words=set(),
    )
    top = tags[0]
    assert top.tag == "ganpatioutfit" and top.relevance == 1.0 and top.results == 1.0
    assert top.score == pytest.approx(0.5 + 0.3 + 0.2 * top.specificity, abs=0.001)
    assert next(t for t in tags if t.tag == "reels").specificity == 0.0  # generic


def test_five_tags_as_a_mix_broad_niche_niche_local_series():
    def t(tag, kind, score):
        return cap.ScoredTag(tag, kind, score, 1, 0.5, 0.5)

    picked = cap.suggest(
        [
            t("ganeshchaturthi", "broad", 0.9),
            t("ganpati", "broad", 0.85),
            t("ganpatioutfit", "niche", 0.8),
            t("festivedrapes", "niche", 0.7),
            t("ethnicstyling", "niche", 0.6),
            t("mumbaifashion", "local", 0.5),
            t("oneoutfitmanyways", "series", 0.4),
        ]
    )
    assert picked == [
        "ganeshchaturthi",
        "ganpatioutfit",
        "festivedrapes",
        "mumbaifashion",
        "oneoutfitmanyways",
    ]


def test_caption_style_follows_the_creators_own_captions():
    style = cap.caption_style(
        [
            "One kurta, five dupattas 💛 which one? #dupatta",
            "Thrift haul under ₹2,000 🛍️ #haul",
            "GRWM ☔ #grwm",
        ]
    )
    assert style.emoji == 1 and style.language == "en"


def test_validate_reasons_match_the_verdict():
    def with_parts(values: dict[str, float]) -> ideas.Scored:
        s = scored("An idea", values, unit(0))
        for k in s.parts:
            s.parts[k].facts = [f"{k} fact"]
        return s

    strong = with_parts({"H": 0.9, "A": 0.9, "T": 0.7, "N": 0.6})
    risky = with_parts({"H": 0.3, "A": 0.6, "T": 0.24, "N": 0.5})
    assert [r["evidence"] for r in ideas.reasons(strong)] == ["H fact", "A fact"]
    assert all(
        r["text"] == ideas.REASONS[k][0] for r, k in zip(ideas.reasons(strong), "HA", strict=True)
    )
    weak = ideas.reasons(risky)
    assert [r["evidence"] for r in weak] == ["H fact", "T fact"]  # the two holding it back most
    assert [r["text"] for r in weak] == [ideas.REASONS["H"][1], ideas.REASONS["T"][1]]


def test_each_slot_says_what_earned_it():
    s = scored("An idea", {"H": 0.9, "A": 0.5, "T": 0.9, "N": 0.4}, unit(0))
    s.parts["H"].facts = ["history fact"]
    s.parts["T"].facts = ["trend fact"]
    s.slot = "proven"
    assert ideas.why_line(s) == "history fact"
    s.slot = "adapted"
    assert ideas.why_line(s) == "trend fact"
