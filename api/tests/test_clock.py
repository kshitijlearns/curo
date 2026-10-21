from datetime import UTC, datetime, timedelta

from curo import clock
from curo.config import get_settings

ANCHOR = "2027-08-23T10:00:00+05:30"
ANCHOR_UTC = datetime(2027, 8, 23, 4, 30, tzinfo=UTC)


def _use_fake_now(monkeypatch, value: str) -> None:
    monkeypatch.setenv("FAKE_NOW", value)
    get_settings.cache_clear()
    clock._cache = (0.0, None)  # forget the 2-second cache, as a new request would


def test_real_time_by_default():
    assert abs((clock.now() - datetime.now(UTC)).total_seconds()) < 2
    assert clock.now().tzinfo is not None
    assert clock.describe()["source"] == "real"


def test_frozen_at_for_tests():
    with clock.frozen_at(ANCHOR_UTC):
        assert clock.now() == ANCHOR_UTC
    assert clock.now() != ANCHOR_UTC


def test_fake_now_from_env_runs_forward_from_anchor(monkeypatch):
    _use_fake_now(monkeypatch, ANCHOR)
    now = clock.now()
    assert ANCHOR_UTC <= now < ANCHOR_UTC + timedelta(seconds=5)
    assert clock.describe()["source"] == "FAKE_NOW"


def test_time_travel_is_shared_through_redis(monkeypatch):
    _use_fake_now(monkeypatch, ANCHOR)
    clock.set_time(ANCHOR_UTC + timedelta(days=3), frozen=True)
    clock._cache = (0.0, None)
    clock._local_state = None  # another process has no local copy; it must read Redis
    assert clock.now() == ANCHOR_UTC + timedelta(days=3)
    clock.advance(timedelta(hours=6))
    clock._cache = (0.0, None)
    assert clock.now() == ANCHOR_UTC + timedelta(days=3, hours=6)
    assert clock.describe() == {
        "now": (ANCHOR_UTC + timedelta(days=3, hours=6)).isoformat(),
        "fake": True,
        "frozen": True,
        "source": "time travel",
    }


def test_changing_fake_now_replaces_earlier_time_travel(monkeypatch):
    _use_fake_now(monkeypatch, ANCHOR)
    clock.set_time(ANCHOR_UTC + timedelta(days=30), frozen=True)
    _use_fake_now(monkeypatch, "2028-01-01T00:00:00+00:00")
    assert clock.now() >= datetime(2028, 1, 1, tzinfo=UTC)
    assert clock.now() < datetime(2028, 1, 1, 0, 0, 5, tzinfo=UTC)


def test_reset_returns_to_fake_now(monkeypatch):
    _use_fake_now(monkeypatch, ANCHOR)
    clock.set_time(ANCHOR_UTC + timedelta(days=30), frozen=True)
    clock.reset()
    assert ANCHOR_UTC <= clock.now() < ANCHOR_UTC + timedelta(seconds=5)


def test_works_without_redis(monkeypatch):
    from curo.redis_client import set_redis

    class DownRedis:
        def ping(self):
            raise ConnectionError("down")

    set_redis(DownRedis())
    clock.reset()
    _use_fake_now(monkeypatch, ANCHOR)
    assert ANCHOR_UTC <= clock.now() < ANCHOR_UTC + timedelta(seconds=5)


def test_naive_datetimes_are_read_in_default_timezone():
    # DEFAULT_TIMEZONE is Asia/Kolkata (UTC+05:30)
    assert clock.to_utc(datetime(2027, 8, 23, 10, 0)) == ANCHOR_UTC
