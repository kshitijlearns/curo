"""Phase 9: matching a posted reel to its simulation, the accuracy record, monitoring and
storage listing — pure functions and providers, no database."""

import os
import time
from datetime import UTC, datetime, timedelta

from curo.providers.monitoring.noop import NoopMonitoring
from curo.providers.storage.local import LocalStorage
from curo.services import accuracy, matching

NOW = datetime(2027, 8, 23, 10, tzinfo=UTC)


def cand(vector, duration, made_at, sim="s1"):
    return matching.Candidate(sim, "p1", vector, duration, made_at)


def test_a_reel_matches_the_simulation_it_came_from():
    same = [1.0, 0.0]
    m = matching.score(same, 32.4, NOW + timedelta(days=1), cand(same, 32.0, NOW))
    assert m.score == 1.0
    assert m.reasons == [
        "Its caption is close to your draft’s.",
        "It’s the same length as the video you simulated.",
        "You posted it 1 day after simulating it.",
    ]
    assert matching.best(same, 32.4, NOW + timedelta(days=1), [cand(same, 32.0, NOW)]).score == 1.0


def test_weak_or_impossible_matches_are_not_suggested():
    same, other = [1.0, 0.0], [0.0, 1.0]
    later = NOW + timedelta(days=1)
    # Same length and timing, but a different caption: 0.5, under the bar.
    assert matching.best(other, 32.0, later, [cand(same, 32.0, NOW)]) is None
    # Posted before it was simulated: timing can't count.
    assert matching.score(same, 32.0, NOW - timedelta(days=1), cand(same, 32.0, NOW)).score == 0.8
    # Long after: the window has closed.
    assert matching._timing(NOW + timedelta(days=20), NOW) == 0.0
    # No caption on the reel: caption can't count, so a match needs the rest to be perfect.
    assert matching.best(None, 32.0, later, [cand(same, 32.0, NOW)]) is None


def test_the_closest_of_several_simulations_is_suggested():
    a, b = [1.0, 0.0], [0.6, 0.8]
    later = NOW + timedelta(days=2)
    best = matching.best(
        a, 41.0, later, [cand(b, 41.0, NOW, sim="near"), cand(a, 41.0, NOW, sim="same")]
    )
    assert best.candidate.simulation_id == "same"


def test_a_reel_is_in_range_when_every_count_seen_at_day_7_is():
    predicted = {
        "views": {"low": 40000, "mid": 60000, "high": 90000},
        "likes": {"low": 1000, "mid": 3000, "high": 9000},
        "shares": {"low": 200, "mid": 600, "high": 1700},
    }
    ok, detail = accuracy.check(predicted, {"views": 61000, "likes": None, "shares": 900})
    assert ok is True and set(detail) == {"views", "shares"}  # hidden likes: unknown, not a miss
    miss, detail = accuracy.check(predicted, {"views": 120000, "shares": 900})
    assert miss is False and detail["views"]["in_range"] is False
    assert accuracy.check(predicted, {"views": None}) == (None, {})


def test_ranges_widen_when_estimates_keep_missing():
    assert accuracy.record([True] * 8 + [False] * 2) == {"hits": 8, "total": 10, "widen": 1.0}
    assert accuracy.record([True, False, False, True, False]) == {
        "hits": 2,
        "total": 5,
        "widen": 1.25,
    }
    assert accuracy.record([False] * 4)["widen"] == 1.0  # too few to judge
    assert accuracy.record([True] * 12)["total"] == 10  # the last ten


def test_monitoring_keeps_events_and_logs_errors(caplog):
    m = NoopMonitoring()
    m.capture_event("simulation_done", {"score": 52}, "c1")
    assert m.events == [("simulation_done", {"score": 52}, "c1")]
    m.capture_exception(ValueError("boom"), {"route": "/v1/reels"})
    assert "captured ValueError: boom" in caplog.text


def test_storage_lists_a_prefix_with_file_times(tmp_path):
    s = LocalStorage(tmp_path)
    for p in ("uploads/c1/a.mp4", "uploads/c1/b.mp4", "uploads/c2/z.mp4", "acc/r.mp4"):
        s.put("v", p, b"x", "video/mp4")
    old = time.time() - 3 * 86400
    os.utime(tmp_path / "v" / "uploads" / "c1" / "a.mp4", (old, old))
    listed = {o.path: o.created_at for o in s.list("v", "uploads/c1/")}
    assert set(listed) == {"uploads/c1/a.mp4", "uploads/c1/b.mp4"}
    assert listed["uploads/c1/a.mp4"] < datetime.now(UTC) - timedelta(days=2)
    assert [o.path for o in s.list("v", "uploads/")] == [
        "uploads/c1/a.mp4",
        "uploads/c1/b.mp4",
        "uploads/c2/z.mp4",
    ]
    assert s.list("v", "nothing/") == [] and s.list("other", "x/") == []
