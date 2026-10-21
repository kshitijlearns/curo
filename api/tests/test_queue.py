"""Jobs survive Redis being briefly unreachable: the row is the record, and the scheduler
hands over again what the worker never received — never a job that is merely waiting."""

from datetime import timedelta

import fakeredis
import pytest
from rq import Queue

from curo import clock
from curo.config import get_settings
from curo.db import service_connection
from curo.queue import QUEUE_NAME, enqueue, redispatch_orphans
from curo.redis_client import set_redis

pytestmark = pytest.mark.db


@pytest.fixture
def rq_mode(db, monkeypatch):
    monkeypatch.setenv("QUEUE_MODE", "rq")
    get_settings.cache_clear()
    server = fakeredis.FakeServer()
    set_redis(fakeredis.FakeRedis(server=server))
    yield server
    get_settings.cache_clear()


def queued_ids() -> list[str]:
    from curo.redis_client import get_redis

    return Queue(QUEUE_NAME, connection=get_redis()).get_job_ids()


def status(job_id) -> str:
    with service_connection() as conn:
        return conn.execute("select status from public.jobs where id = %s", (job_id,)).fetchone()[
            "status"
        ]


def test_a_job_goes_to_the_worker_under_its_own_id(rq_mode):
    job_id = enqueue("collect_hashtags", {})
    assert queued_ids() == [str(job_id)]


def test_a_job_saved_while_redis_is_down_is_handed_over_later_and_only_once(rq_mode):
    rq_mode.connected = False
    job_id = enqueue("collect_hashtags", {"account_id": "x"})  # no error for the request
    assert status(job_id) == "queued"

    rq_mode.connected = True
    soon = clock.now() + timedelta(minutes=1)
    assert redispatch_orphans(soon) == []  # too recent to call it lost
    later = clock.now() + timedelta(minutes=6)
    assert redispatch_orphans(later) == [f"redispatch:collect_hashtags:{job_id}"]
    assert queued_ids() == [str(job_id)]
    assert redispatch_orphans(later) == []  # now waiting its turn: not sent twice
    assert queued_ids() == [str(job_id)]


def test_while_redis_stays_down_nothing_is_lost(rq_mode):
    rq_mode.connected = False
    job_id = enqueue("collect_hashtags", {})
    assert redispatch_orphans(clock.now() + timedelta(minutes=6)) == []
    assert status(job_id) == "queued"


def test_inline_mode_has_nothing_to_hand_over(db):
    assert redispatch_orphans(clock.now() + timedelta(hours=1)) == []


# ------------------------------------------- without Docker: the worker as a thread (D115)


@pytest.fixture
def thread_mode(db, monkeypatch):
    monkeypatch.setenv("QUEUE_MODE", "thread")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def wait_for(job_id, seconds: float = 20) -> str:
    import time

    deadline = time.monotonic() + seconds
    while status(job_id) in ("queued", "running") and time.monotonic() < deadline:
        time.sleep(0.05)
    return status(job_id)


def test_thread_mode_runs_the_job_in_the_background(thread_mode):
    from curo.jobs import job

    @job("test_thread_job")
    def _job(ctx):
        return {"ran": True}

    job_id = enqueue("test_thread_job", {})
    assert wait_for(job_id) == "succeeded"


def test_thread_mode_hands_over_jobs_left_from_before_a_restart(thread_mode, monkeypatch):
    from curo import local_worker

    held: list[str] = []
    monkeypatch.setattr(local_worker, "submit", lambda job_id, priority: held.append(str(job_id)))
    job_id = enqueue("collect_hashtags", {})
    held.clear()  # the API stopped before the thread ran it
    later = clock.now() + timedelta(minutes=6)
    assert redispatch_orphans(later) == [f"redispatch:collect_hashtags:{job_id}"]
    assert held == [str(job_id)]
