"""Phase 7: the Simulator's estimate (MVP doc T9; logic doc §13), the upload checks and
signed uploads — pure functions and providers, no database."""

import base64
import json
import math
import struct
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from curo import clock
from curo.providers.public_data.mock import MOCK_VIDEO_MAGIC
from curo.providers.storage.base import StorageError
from curo.providers.storage.local import LocalStorage
from curo.providers.video.mock import MockVideoProvider
from curo.schemas.tasks import T1Input
from curo.services import mp4, simulator
from curo.services import storyboard as sb
from curo.services.simulator import Card, Past

IST = ZoneInfo("Asia/Kolkata")


def past(rid, own, vector, lifts, fmt="multi_look", **features) -> Past:
    return Past(
        reel_id=rid,
        own=own,
        vector=vector,
        lifts=lifts,
        features={"format": fmt, **features},
        title=f"Reel {rid}",
        username="me" if own else "peer",
    )


# ------------------------------------------------------------------ uploads: MP4 / MOV headers


def test_mp4_headers_give_length_and_size():
    meta = mp4.read(mp4.build(32.5, 720, 1280))
    assert (meta.duration_s, meta.width, meta.height, meta.brand) == (32.5, 720, 1280, "isom")


def test_a_mov_is_read_like_an_mp4():
    data = bytearray(mp4.build(12, 1080, 1920))
    data[8:12] = b"qt  "  # QuickTime's brand
    assert mp4.check(bytes(data)).duration_s == 12


def test_the_simulator_refuses_long_videos_and_other_files():
    assert mp4.check(mp4.build(90, 1080, 1920)).duration_s == 90
    with pytest.raises(mp4.NotAVideo, match="91 seconds long"):
        mp4.check(mp4.build(91, 1080, 1920))
    with pytest.raises(mp4.NotAVideo, match="isn't an MP4 or MOV"):
        mp4.check(b"GIF89a" + bytes(64))
    with pytest.raises(mp4.NotAVideo, match="length"):
        mp4.check(struct.pack(">I4s", 16, b"ftyp") + b"isom" + bytes(4))  # no moov


def test_a_64_bit_mvhd_is_read():
    body = struct.pack(">B3xQQIQ", 1, 0, 0, 600, 600 * 45) + bytes(80)
    moov = (
        struct.pack(">I4s", 8 + 8 + len(body), b"moov")
        + struct.pack(">I4s", 8 + len(body), b"mvhd")
        + body
    )
    data = struct.pack(">I4s", 16, b"ftyp") + b"isom" + bytes(4) + moov
    assert mp4.read(data).duration_s == 45


# ------------------------------------------------------------------ signed uploads (local storage)


def test_a_signed_upload_stores_exactly_its_path(tmp_path):
    storage = LocalStorage(tmp_path, secret="s3cret")
    signed = storage.signed_upload("reel-videos", "uploads/c1/a.mp4", "video/mp4")
    assert signed.url.startswith("/v1/uploads/local/") and signed.method == "PUT"
    token = signed.url.rsplit("/", 1)[1]
    assert storage.accept_upload(token, b"video") == ("reel-videos", "uploads/c1/a.mp4")
    assert storage.get("reel-videos", "uploads/c1/a.mp4") == b"video"


def test_a_tampered_or_expired_upload_link_is_refused(tmp_path):
    storage = LocalStorage(tmp_path, secret="s3cret")
    token = storage.signed_upload("reel-videos", "uploads/c1/a.mp4", "video/mp4").url.rsplit(
        "/", 1
    )[1]
    _body, sig = token.split(".")
    other = LocalStorage(tmp_path, secret="different")
    with pytest.raises(StorageError, match="isn't valid"):
        other.accept_upload(token, b"x")
    forged = json.dumps({"b": "reel-videos", "p": "uploads/c2/b.mp4", "t": "video/mp4", "e": 9e9})
    forged_body = base64.urlsafe_b64encode(forged.encode()).rstrip(b"=").decode()
    with pytest.raises(StorageError, match="isn't valid"):
        storage.accept_upload(f"{forged_body}.{sig}", b"x")
    later = clock.now() + timedelta(hours=1)
    with clock.frozen_at(later), pytest.raises(StorageError, match="expired"):
        storage.accept_upload(token, b"x")
    with pytest.raises(StorageError):
        storage.signed_upload("reel-videos", "../escape.mp4", "video/mp4")


# ------------------------------------------------------------------ the demo's sample recordings


def test_sample_recordings_are_real_mp4s_the_mock_understands(tmp_path):
    storage = LocalStorage(tmp_path)
    video = MockVideoProvider(storage)
    names = [s.name for s in video.samples()]
    assert names == ["take1", "take2"]
    for s in video.samples():
        data = video.sample_file(s.name)
        assert mp4.check(data).duration_s == s.duration_s
        storage.put("v", f"{s.name}.mp4", data, "video/mp4")
        t1 = video.understand(T1Input(bucket="v", path=f"{s.name}.mp4", duration_s=s.duration_s))
        assert t1.transcript and t1.first_payoff_s is not None
    assert video.sample_file("nope") is None
    # Anything else a creator records gets a deliberately thin description.
    storage.put("v", "mine.mp4", mp4.build(20, 1080, 1920), "video/mp4")
    thin = video.understand(T1Input(bucket="v", path="mine.mp4", duration_s=20))
    assert not thin.transcript and thin.first_payoff_s is None
    assert MOCK_VIDEO_MAGIC in video.sample_file("take1")[:4096]


# ------------------------------------------------------------------ 1–4. neighbours, estimate, range


def test_neighbours_prefer_the_same_format_and_own_reels_count_double():
    up = [1.0, 0.0]
    pool = [
        past("a", False, [1.0, 0.0], {"views": 2.0}, fmt="haul"),
        past("b", True, [0.95, 0.05], {"views": 1.0}),
        past("c", False, [0.0, 1.0], {"views": 9.0}),  # unrelated: no similarity at all
    ]
    near = simulator.neighbours(up, "multi_look", pool)
    assert [n.past.reel_id for n in near] == ["b", "a"]  # same format ranks first
    assert near[0].weight == pytest.approx(2 * near[0].similarity)
    assert near[1].weight == pytest.approx(near[1].similarity)


def test_the_estimate_is_the_weighted_average_of_neighbour_lifts():
    near = [
        simulator.Neighbour(past(str(i), True, [1], {"views": v}), 1.0, w)
        for i, (v, w) in enumerate([(2.0, 2.0), (0.5, 1.0), (1.0, 1.0)])
    ]
    est = simulator.estimate({}, near, [])
    expected = math.exp((2 * math.log(2.0) + math.log(0.5) + math.log(1.0)) / 4)
    assert est.lifts["views"].mid == pytest.approx(expected, abs=1e-3)
    assert "like_rate" not in est.lifts  # no neighbour shows it: unknown, never zero


def test_pattern_cards_adjust_where_the_upload_differs_capped_at_30_percent():
    near = [
        simulator.Neighbour(
            past(str(i), True, [1], {"like_rate": 1.0}, payoff_band="2_to_4s"), 1, 2
        )
        for i in range(10)
    ]
    cards = [
        Card("1", "payoff_band", "under_2s", "like_rate", 1.23, 15, "yours"),
        Card("2", "payoff_band", "2_to_4s", "like_rate", 0.83, 9, "yours"),
    ]
    same = simulator.estimate({"payoff_band": "2_to_4s"}, near, cards)
    assert same.lifts["like_rate"].mid == pytest.approx(1.0)  # like most neighbours: no change
    faster = simulator.estimate({"payoff_band": "under_2s"}, near, cards)
    assert faster.adjustments["like_rate"] == pytest.approx(1.3)  # 1.23 / 0.83 = 1.48, capped
    slower = simulator.estimate(
        {"payoff_band": "over_4s"},
        near,
        [Card("3", "payoff_band", "over_4s", "like_rate", 0.5, 9, "yours"), *cards],
    )
    assert slower.adjustments["like_rate"] == pytest.approx(0.7)


def test_the_range_widens_with_fewer_than_8_own_neighbours():
    lifts = [0.6, 0.8, 1.0, 1.2, 1.5, 1.8, 2.0, 0.9, 1.1, 1.3]

    def run(own: bool):
        near = [
            simulator.Neighbour(past(str(i), own, [1], {"views": v}), 1.0, 1.0)
            for i, v in enumerate(lifts)
        ]
        return simulator.estimate({}, near, []).lifts["views"]

    mine, theirs = run(True), run(False)
    assert mine.mid == theirs.mid
    assert theirs.low < mine.low <= mine.mid <= mine.high < theirs.high


# ------------------------------------------------------------------ 5. the score


def test_the_score_is_a_percentile_of_the_last_50_reels_on_the_audience_mix():
    history = [
        {"views": 1.0, "like_rate": x, "comment_rate": 1.0, "share_rate": 1.0}
        for x in (0.5, 0.8, 1.2, 2.0)
    ]
    predicted = {"views": 1.0, "like_rate": 1.0, "comment_rate": 1.0, "share_rate": 1.0}
    assert simulator.score(predicted, history, "both") == 50  # beats 2 of 4
    # Followers weigh likes 40%, new audiences 10%: a likes-heavy history moves them apart.
    likes_up = {**predicted, "like_rate": 1.5}
    assert simulator.score(likes_up, history, "followers") == 75
    assert simulator.score(predicted, [], "both") == 50  # nothing to rank against


def test_a_metric_that_isnt_known_is_left_out_of_the_mix():
    assert simulator.mixed({"views": 2.0}, "new") == pytest.approx(2.0)
    assert simulator.mixed({}, "both") is None
    w = simulator.AUDIENCE_WEIGHTS
    assert all(sum(v.values()) == pytest.approx(1.0) for v in w.values())
    assert w["followers"] == {
        "views": 0.15,
        "share_rate": 0.20,
        "like_rate": 0.40,
        "comment_rate": 0.25,
    }
    assert w["new"] == {"views": 0.45, "share_rate": 0.35, "like_rate": 0.10, "comment_rate": 0.10}


# ------------------------------------------------------------------ 6. reasons, 7. edits

CARDS = [
    Card("1", "ending", "choice_question", "comment_rate", 1.66, 9, "yours"),
    Card("2", "cta_type", "share_prompt", "share_rate", 1.43, 10, "yours"),
    Card("3", "cta_type", "comment_prompt", "share_rate", 0.73, 13, "yours"),
    Card("4", "payoff_band", "under_2s", "like_rate", 1.23, 15, "yours"),
    Card("5", "payoff_band", "2_to_4s", "like_rate", 0.83, 9, "yours"),
    Card("6", "ending", "choice_question", "share_rate", 0.87, 8, "yours"),
]
TAKE1 = {"ending": "choice_question", "cta_type": "comment_prompt", "payoff_band": "2_to_4s"}


def test_reasons_come_from_the_patterns_present_and_missing():
    working, holding = simulator.reasons(TAKE1, CARDS, "both", 3.8)
    assert [r.key for r in working] == ["ending:choice_question"]
    assert working[0].text == (
        "It has a choice-question ending — your reels with it got 1.66× your usual comments per "
        "view (9 reels)."
    )
    assert {r.key for r in holding} == {"cta_type:comment_prompt", "payoff_band:2_to_4s"}
    payoff = next(r for r in holding if r.feature == "payoff_band")
    assert payoff.text.startswith(
        "The payoff lands at 3.8 seconds. Your reels with the payoff in the first 2"
    )
    assert payoff.moment == "hook" and payoff.short == "the slow payoff"
    # A value shows once, on its stronger side (the choice question isn't also "holding").
    assert all(r.key != "ending:choice_question" for r in holding)


def test_the_audience_changes_which_reason_leads():
    _, followers = simulator.reasons(TAKE1, CARDS, "followers", 3.8)
    _, new = simulator.reasons(TAKE1, CARDS, "new", 3.8)
    assert followers[0].feature == "payoff_band"  # likes count 40% for followers
    assert new[0].feature == "cta_type"  # shares count 35% for new audiences


def test_edits_are_rescored_and_ranked_by_gain_for_effort():
    near = [
        simulator.Neighbour(
            past(
                str(i),
                True,
                [1],
                {"views": 1.0, "like_rate": 1.0, "comment_rate": 1.0, "share_rate": 1.0},
                **TAKE1,
            ),
            1.0,
            2.0,
        )
        for i in range(10)
    ]
    history = [
        {"views": 1.0, "like_rate": x, "comment_rate": 1.0, "share_rate": x}
        for x in (0.7, 0.9, 1.0, 1.1, 1.3)
    ]
    before = simulator.scores(simulator.estimate(TAKE1, near, CARDS), history)
    gain = simulator.rescore_edit(TAKE1, {"payoff_band": "under_2s"}, near, CARDS, history, before)
    assert gain["followers"] > 0
    nothing = simulator.rescore_edit(TAKE1, {"setting": "studio"}, near, CARDS, history, before)
    assert set(nothing.values()) == {0}
    ranked = simulator.best_edits(
        [
            ("reshoot", {"both": 6, "new": 0, "followers": 1}, "reshoot"),
            ("edit", {"both": 4, "new": 0, "followers": 1}, "edit_only"),
            ("none", {"both": 0, "new": 0, "followers": 0}, "edit_only"),
        ],
        "both",
    )
    assert ranked == ["edit", "reshoot"]  # 4 for an edit beats 6 for a reshoot; 0 isn't shown
    assert [(f.feature, f.better) for f in simulator.factors(TAKE1, CARDS)] == [
        ("cta_type", "share_prompt"),
        ("payoff_band", "under_2s"),
    ]


def test_an_edit_maps_to_the_studio_change_that_carries_it():
    changes = simulator.studio_changes(
        {"payoff_band": "under_2s", "opening_style": "final_look_first"}
    )
    assert [(c.step, c.action) for c in changes] == [("script", "rewrite_hook")]
    changes = simulator.studio_changes(
        {"cta_type": "share_prompt", "onscreen_text": "yes", "pace": "fast"}
    )
    assert [(c.step, c.action) for c in changes] == [
        ("script", "change_ending"),
        ("storyboard", "pacing"),
        ("storyboard", "label_frames"),
    ]
    trim = simulator.studio_changes({"duration_band": "20_to_40s"})[0]
    assert (trim.action, trim.params) == ("shorten", {"seconds": 32.0})


def test_frames_without_on_screen_text_get_their_first_words():
    frames = [
        {"beat_id": "b1", "line": "Look number 1: belted, with a potli bag.", "onscreen_text": ""},
        {"beat_id": "b2", "line": "Second", "onscreen_text": "Already labelled"},
    ]
    out, changed = sb.label_frames(frames)
    assert out[0]["onscreen_text"] == "Look number 1" and changed == ["b1"]
    assert out[1] == frames[1]


# ------------------------------------------------------------------ the report and timing


def test_the_report_is_the_7_day_usual_times_the_lift():
    est = simulator.Estimate(
        {"views": simulator.Range(0.8, 1.2, 1.6), "share_rate": simulator.Range(0.9, 1.5, 2.0)},
        {},
        [],
        3,
    )
    usual = {"views": 50000.0, "like_rate": 0.05, "comment_rate": None, "share_rate": 0.01}
    rows = {r["metric"]: r for r in simulator.report(est, usual)}
    assert (rows["views"]["low"], rows["views"]["mid"], rows["views"]["high"]) == (
        40000.0,
        60000.0,
        80000.0,
    )
    assert rows["views"]["change_pct"] == 20 and rows["share_rate"]["change_pct"] == 50
    assert rows["like_rate"]["known"] is False  # no estimate: unknown, not zero
    assert rows["comment_rate"]["known"] is False  # no usual: unknown, not zero
    counts = simulator.predicted_counts(est, usual)
    assert counts["views"]["mid"] == 60000 and counts["shares"]["mid"] == 900
    assert "likes" not in counts and "comments" not in counts


def test_best_time_uses_the_creators_own_slots():
    now = datetime(2027, 8, 23, 10, 0, tzinfo=IST)  # a Monday
    tue = datetime(2027, 8, 17, 19, 30, tzinfo=IST)
    posts = [
        (tue, 1.4),
        (tue - timedelta(days=7), 1.6),
        (tue.replace(hour=10), 0.9),
        (tue.replace(hour=10) - timedelta(days=7), 1.0),
    ]
    best = simulator.best_time(posts, now)
    assert best["label"] == "Tue, 6–9 PM"
    assert (
        best["fact"] == "Your reels posted on Tuesdays 6–9 PM got 1.5× your usual views (2 reels)."
    )
    assert simulator.best_time(posts[:1], now) is None  # one reel isn't a pattern


def test_the_accuracy_record_says_when_there_is_none():
    assert "no record to show" in simulator.accuracy_note(0, 0)
    assert (
        simulator.accuracy_note(8, 10)
        == "Curo’s range contained the result for 8 of your last 10 simulated reels."
    )


def test_comparing_with_the_studio_draft():
    beats = [
        {"id": "b1", "role": "hook", "text": "Same outfit, three Ganpati looks.", "end_s": 4},
        {"id": "b2", "role": "item", "text": "Look one is belted with a potli bag.", "end_s": 12},
        {
            "id": "b3",
            "role": "item",
            "text": "Look two adds a mirror-work dupatta.",
            "end_s": 20,
            "note": {"type": "likes"},
        },
        {"id": "b4", "role": "ending", "text": "Send this to your festive twin.", "end_s": 26},
    ]
    said = "Same outfit, three Ganpati looks. Look one is belted with a potli bag. Which one would you pick?"
    out = {x["kind"]: x["text"] for x in simulator.compare(said, 41, beats)}
    assert "hook" not in out
    assert out["cta"] == "The script’s last line (its call to action) isn’t in the video."
    assert out["skipped"] == "1 of the script’s lines isn’t in the video."
    assert out["note"].startswith("A line Curo linked with likes was dropped")
    assert out["length"] == "The video runs 41 seconds; the script planned 26."


def test_originality_flags_near_copies():
    near_copy = past("p", False, [1.0, 0.0], {"views": 1.0})
    value, closest = simulator.originality([1.0, 0.01], [near_copy])
    assert value < 0.1 and closest is near_copy
    assert simulator.originality_text(value, closest).startswith("Low · very close to")
    assert simulator.originality_text(*simulator.originality([1.0, 1.0], [near_copy])).startswith(
        "High"
    )
