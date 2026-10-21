"""Understanding providers and helpers (no database): prompts, stubs, mocks, comment themes,
sub-clusters. The mocks only ever see a task's input; these tests check that what they read
from the fixture's video descriptions matches the DNA the fixture was written from."""

import json
from collections import Counter

import numpy as np
import pytest

from curo import prompts
from curo.config import REPO_ROOT
from curo.providers.embedding.gemini import GeminiEmbeddingProvider
from curo.providers.embedding.mock import MockEmbeddingProvider
from curo.providers.llm.claude import ClaudeProvider
from curo.providers.llm.mock import MockLLMProvider, label_comment
from curo.providers.storage.local import LocalStorage
from curo.providers.storage.supabase import SupabaseStorage
from curo.providers.video.gemini import GeminiVideoProvider
from curo.providers.video.mock import MockVideoProvider
from curo.schemas.tasks import (
    T2,
    T3,
    T4,
    TASKS,
    CommentIn,
    T1Input,
    T1Output,
    T2Input,
    T2Output,
    T3Input,
    T4Input,
)
from curo.schemas.taxonomy import MIN_CONFIDENCE, UNKNOWN
from curo.services import dna
from curo.services.comments import group_themes, language_of, theme_key
from curo.services.subclusters import find_groups, match_previous, nearest_to_centroid
from curo.services.text import mask_mentions, reel_title

DATA = REPO_ROOT / "fixtures" / "data"
TRUTH_FIELDS = {
    "format": "format", "hook_type": "hook_type", "opening_style": "opening_style",
    "narrative": "narrative", "ending": "ending", "cta_type": "cta_type", "pov": "pov",
    "camera": "camera", "audio": "audio", "visual_style": "visual_style", "setting": "setting",
    "context": "context", "characters": "characters", "core_tension": "core_tension",
    "niche": "cluster",
}  # fmt: skip


def fixture(owner: str):
    reels = json.loads((DATA / "reels" / f"{owner}.json").read_text(encoding="utf-8"))
    t1 = json.loads((DATA / "t1" / f"{owner}.json").read_text(encoding="utf-8"))
    return reels, t1


def all_reels():
    for p in sorted((DATA / "reels").glob("*.json")):
        reels, t1 = fixture(p.stem)
        for r in reels:
            yield r, T1Output.model_validate(t1[r["shortcode"]])


# ---------------------------------------------------------------- prompts and stubs


def test_every_task_has_a_versioned_prompt():
    for task in TASKS.values():
        text = prompts.load(task)
        assert task.id in text and f"(v{task.version})" in text


def test_real_providers_are_stubs_until_keys_arrive(tmp_path):
    storage = LocalStorage(tmp_path)
    with pytest.raises(NotImplementedError, match="LLM_PROVIDER=mock"):
        ClaudeProvider("", "m", "f").run(T4, T4Input(kind="reels", samples=["x"]))
    with pytest.raises(NotImplementedError, match="VIDEO_PROVIDER=mock"):
        GeminiVideoProvider("", "", storage).understand(T1Input(bucket="b", path="p"))
    with pytest.raises(NotImplementedError, match="EMBEDDING_PROVIDER=mock"):
        GeminiEmbeddingProvider("", "").embed(["x"])
    with pytest.raises(NotImplementedError, match="STORAGE_PROVIDER=local"):
        SupabaseStorage("", "").get("b", "p")


def test_local_storage_round_trip_and_no_escaping_the_bucket(tmp_path):
    s = LocalStorage(tmp_path)
    s.put("videos", "a/b.mp4", b"data", "video/mp4")
    assert s.exists("videos", "a/b.mp4") and s.get("videos", "a/b.mp4") == b"data"
    s.delete("videos", "a/b.mp4")
    s.delete("videos", "a/b.mp4")  # missing is fine
    assert not s.exists("videos", "a/b.mp4")
    with pytest.raises(Exception, match="escapes"):
        s.put("videos", "../../outside.txt", b"x", "text/plain")


def test_llm_outputs_are_validated_against_the_task_schema():
    llm = MockLLMProvider()
    out = llm.run(T4, {"kind": "comments", "samples": ["part 2 please!!", "need a part 2 asap"]})
    assert out.label == "Wants a part 2"
    assert llm.version(T2) == "T2.v1:mock-fast-v1"


# ---------------------------------------------------------------- embeddings


def test_mock_embeddings_are_deterministic_unit_vectors_of_768():
    emb = MockEmbeddingProvider()
    a, b = emb.embed(["One kurta, five dupattas", "One kurta, five dupattas"])
    assert a == b and len(a) == 768
    assert np.linalg.norm(a) == pytest.approx(1.0, abs=1e-5)
    assert emb.embed([""])[0][0] == 1.0  # empty text: a fixed unit vector


def test_similar_texts_land_closer_than_different_ones():
    emb = MockEmbeddingProvider()
    kurta, saree, lighting = (
        np.array(v)
        for v in emb.embed(
            [
                "Same kurta restyled three ways with a dupatta",
                "One saree, three drapes and a new dupatta",
                "How I light my reels with one window, lock exposure",
            ]
        )
    )
    assert kurta @ saree > kurta @ lighting


# ---------------------------------------------------------------- T1 mock video


def test_mock_video_reads_the_stored_file(tmp_path):
    from curo.providers.public_data.mock import MockPublicDataProvider

    reels, _ = fixture("curo.demo")
    storage = LocalStorage(tmp_path)
    public = MockPublicDataProvider(now=lambda: MockPublicDataProvider().anchor)
    r = next(x for x in reels if x["meta"]["title"].startswith("3 mistakes"))
    storage.put(
        "v",
        "x.mp4",
        public.download(f"https://cdn.example.invalid/{r['shortcode']}.mp4"),
        "video/mp4",
    )
    out = MockVideoProvider(storage).understand(T1Input(bucket="v", path="x.mp4"))
    assert out.first_payoff_s == 1.8 and out.audio_type == "voiceover"
    # An unknown file (e.g. a creator's own upload) gets a deliberately thin description.
    storage.put("v", "upload.mp4", b"\x00\x00\x00\x18ftypmp42", "video/mp4")
    thin = MockVideoProvider(storage).understand(
        T1Input(bucket="v", path="upload.mp4", duration_s=12)
    )
    assert thin.transcript == [] and len(thin.seconds) == 12


# ---------------------------------------------------------------- T2 mock DNA and the confidence rule


def test_mock_dna_matches_the_fixture_truth():
    right = wrong = unknown = 0
    llm = MockLLMProvider()
    for r, t1 in all_reels():
        out = llm.run(T2, T2Input(understanding=t1, caption=r["caption"], hashtags=r["hashtags"]))
        got = {**out.content.model_dump(), **out.production.model_dump()}
        for truth_field, field in TRUTH_FIELDS.items():
            if out.confidence.get(field, 0) < MIN_CONFIDENCE or got[field] == UNKNOWN:
                unknown += 1
            elif got[field] == r["meta"]["dna"][truth_field]:
                right += 1
            else:
                wrong += 1
    assert right / (right + wrong) >= 0.98
    assert 0.0 < unknown / (right + wrong + unknown) < 0.08  # some honest unknowns, not many


def test_fields_below_point_six_are_stored_as_unknown():
    out = T2Output.model_validate(
        {
            "content": {"cluster": "beauty", "context": "festive", "key_entities": ["saree"]},
            "production": {"format": "grwm", "setting": "bedroom", "hook_text": "Get ready", "cuts_per_10s": 2.4},
            "confidence": {"cluster": 0.9, "context": 0.59, "key_entities": 0.4, "format": 0.6,
                           "setting": 0.3, "hook_text": 0.2, "cuts_per_10s": 0.9},
        }
    )  # fmt: skip
    content, production, conf = dna.apply_confidence(out)
    assert content["cluster"] == "beauty" and production["format"] == "grwm"
    assert content["context"] == UNKNOWN and production["setting"] == UNKNOWN
    assert content["key_entities"] == [] and production["hook_text"] == ""
    assert production["cuts_per_10s"] == 2.4
    assert production["camera"] == UNKNOWN  # no confidence given: unknown
    assert conf["context"] == 0.59


def test_mining_features_and_bands():
    feats = dna.features(
        {"cluster": "fashion_styling", "context": UNKNOWN},
        {"format": "multi_look", "cuts_per_10s": 4.1},
        {"first_payoff_s": 1.2, "onscreen_text": [{"t": 0, "text": "Look 1"}]},
        28,
    )
    assert feats == {
        "cluster": "fashion_styling",
        "format": "multi_look",
        "duration_band": "20_to_40s",
        "payoff_band": "under_2s",
        "pace": "fast",
        "onscreen_text": "yes",
    }


# ---------------------------------------------------------------- T3 / T4 mocks


EXPECTED_INTENT = {
    "thats_me": {"thats_me"}, "question_where": {"question"}, "question_price": {"question"},
    "question_how": {"question"}, "request_part2": {"request"}, "request_budget": {"request"},
    "request_festive": {"request"}, "friend_tag": {"tags_friend"},
    "praise": {"praise", "plans_to_save", "other"}, "pick": {"other", "praise"},
    "negative": {"disagreement"}, "places": {"other", "question"}, "emoji": {"praise", "other"},
    "bot": {"bot"},
}  # fmt: skip


def test_mock_comment_labels_match_the_kind_of_comment_written():
    checked = Counter()
    for p in sorted((DATA / "comments").glob("*.json")):
        for cs in json.loads(p.read_text(encoding="utf-8")).values():
            for c in cs:
                expected = EXPECTED_INTENT.get(c["kind"])
                if expected is None:
                    continue
                label = label_comment(c["id"], mask_mentions(c["text"]))
                checked[
                    "ok" if ("bot" if label.is_bot else label.intent) in expected else "bad"
                ] += 1
    assert checked["ok"] > 1000 and checked["bad"] / checked["ok"] < 0.01


@pytest.mark.parametrize(
    ("text", "intent", "theme"),
    [
        ("ye dupatta kahan se liya?", "question", "asks where it's from"),
        ("कितने का है?", "question", "asks the price"),
        ("sasta version bhi dikhao 😅", "request", "wants budget versions"),
        ("part 2 pleaseee", "request", "wants a part 2"),
        ("kya baat hai 🔥", "praise", None),
        ("bilkul mera haal hai 😂", "thats_me", None),
        ("@… this is so you", "tags_friend", None),
    ],
)
def test_comments_in_english_hinglish_and_hindi(text, intent, theme):
    label = label_comment("c", text)
    assert (label.intent, label.theme, label.is_bot) == (intent, theme, False)


def test_bots_are_flagged():
    out = MockLLMProvider().run(
        T3, T3Input(comments=[CommentIn(id="1", text="Earn $500 daily click link in bio")])
    )
    assert out.labels[0].is_bot


def test_language_of():
    assert language_of("यह लहंगा कहाँ से लिया?") == "hi"
    assert language_of("ye dupatta kahan se liya?") == "hinglish"
    assert language_of("where is this kurta from?") == "en"
    assert language_of("😍😍") is None


def test_themes_group_by_phrase_and_keep_different_asks_apart():
    items = [
        ("1", "question", theme_key("Asks where it's from")),
        ("2", "question", theme_key("asks where it's from.")),
        ("3", "question", theme_key("asks the price")),
        ("4", "request", theme_key("wants a part 2")),
        ("5", "praise", None),
        ("6", "question", theme_key("other question")),
    ]
    groups = group_themes(items, MockEmbeddingProvider().embed)
    assert [(g.key, g.kind, sorted(g.comment_ids)) for g in groups] == [
        ("asks where it's from", "question", ["1", "2"]),
        ("asks the price", "question", ["3"]),
        ("wants a part 2", "request", ["4"]),
    ]


# ---------------------------------------------------------------- sub-clusters


def test_sub_clusters_of_the_demo_creator_are_its_five_kinds_of_reel():
    reels, t1 = fixture("curo.demo")
    reels = sorted((r for r in reels if r["posted_h"] <= 0), key=lambda r: -r["posted_h"])[:30]
    emb = MockEmbeddingProvider()
    vectors = {
        r["shortcode"]: emb.embed(
            [dna.embedding_text(r["caption"], T1Output.model_validate(t1[r["shortcode"]]))]
        )[0]
        for r in reels
    }
    groups = find_groups(vectors)
    truth = {r["shortcode"]: r["meta"]["cluster"] for r in reels}
    titles = {r["shortcode"]: reel_title(r["caption"]) for r in reels}
    assert len(groups) == 5 and all(len(g.reel_ids) >= 3 for g in groups)
    names = set()
    for g in groups:
        assert len({truth[r] for r in g.reel_ids}) == 1  # each group is one kind of reel
        samples = [titles[r] for r in nearest_to_centroid(g, vectors)]
        names.add(MockLLMProvider().run(T4, T4Input(kind="reels", samples=samples)).label)
    assert names == {
        "Festive styling",
        "Reel-making tips",
        "Get ready with me",
        "Hauls",
        "One item, many looks",
    }


def test_never_a_group_of_one_and_ids_survive_recomputes():
    assert find_groups({"a": [1.0] + [0.0] * 767}) == []
    assert match_previous(
        [["a", "b", "c"], ["x", "y", "z"]], {"old1": ["a", "b", "d"], "old2": ["q"]}
    ) == {0: "old1"}
