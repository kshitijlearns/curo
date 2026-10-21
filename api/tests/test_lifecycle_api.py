"""Phase 9: deleting an account, the daily cleanup, and the learning loop after posting
(match_posted_reel, confirmation, accuracy_report) — through the real endpoints and jobs."""

import os
import time
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from curo import clock, providers
from curo.config import get_settings
from curo.db import service_connection
from curo.jobs import simulation as sim_jobs
from curo.jobs.lifecycle import queue_match
from curo.main import create_app
from curo.providers.public_data.mock import MockPublicDataProvider
from curo.queue import enqueue

pytestmark = pytest.mark.db
ANCHOR = MockPublicDataProvider().anchor


def sign_in(client: TestClient, email: str) -> dict[str, str]:
    code = client.post("/v1/auth/otp", json={"email": email}).json()["dev_code"]
    token = client.post("/v1/auth/verify", json={"email": email, "code": code}).json()
    return {"Authorization": f"Bearer {token['access_token']}"}


def onboard(client: TestClient, email: str, handle: str) -> dict[str, str]:
    headers = sign_in(client, email)
    res = client.post("/v1/onboarding/username", json={"username": handle}, headers=headers)
    assert res.status_code == 202, res.text
    return headers


def creator_of(handle: str) -> dict:
    with service_connection() as conn:
        return conn.execute(
            "select c.* from public.creators c join public.accounts a on a.id = c.account_id "
            "where a.username = %s",
            (handle,),
        ).fetchone()


def count(sql: str, *args) -> int:
    with service_connection() as conn:
        return conn.execute(f"select count(*) as n from ({sql}) x", args).fetchone()["n"]


def remember(client: TestClient, headers: dict, message: str) -> None:
    body = {"message": message, "screen": "studio:validate"}
    with client.stream("POST", "/v1/chat", json=body, headers=headers) as res:
        assert res.status_code == 200
        assert "I’ll remember" in "".join(res.iter_text())


@pytest.fixture
def client(db):
    with clock.frozen_at(ANCHOR):
        yield TestClient(create_app())


# ------------------------------------------------------------------ deleting an account


def test_deleting_an_account_removes_everything_and_keeps_the_handle_out(client):
    a = onboard(client, "a@example.com", "kavyawears")
    onboard(client, "b@example.com", "stylewithrhea")
    creator = creator_of("kavyawears")
    account_id, user_id = creator["account_id"], creator["user_id"]
    # A has something of every kind: a simulated upload, a stray upload, chat and memory.
    take = client.post("/v1/uploads/sample", json={"name": "take1"}, headers=a).json()
    res = client.post(
        "/v1/simulations",
        json={"upload_path": take["path"], "caption": take["caption"]},
        headers=a,
    )
    assert res.status_code == 202
    stray = client.post("/v1/uploads/sample", json={"name": "take2"}, headers=a).json()
    remember(client, a, "Never suggest dance trends")
    storage, videos = providers.get_storage(), get_settings().storage_bucket_videos
    with service_connection() as conn:
        reel_videos = [
            r["video_path"]
            for r in conn.execute(
                "select video_path from public.reels where account_id = %s and video_path is not null",
                (account_id,),
            ).fetchall()
        ]
    assert (
        reel_videos
        and storage.exists(videos, take["path"])
        and storage.exists(videos, stray["path"])
    )

    res = client.delete("/v1/me", headers=a)
    assert res.status_code == 202 and res.json()["status"] == "deleting"

    assert count("select 1 from auth.users where id = %s", user_id) == 0
    assert count("select 1 from public.creators where id = %s", creator["id"]) == 0
    for table in (
        "projects",
        "simulations",
        "chat_messages",
        "creator_memory",
        "opportunities",
        "jobs",
    ):
        assert count(f"select 1 from public.{table} where creator_id = %s", creator["id"]) == 0
    for table in ("reels", "baselines", "pattern_cards", "subclusters", "comment_themes"):
        assert count(f"select 1 from public.{table} where account_id = %s", account_id) == 0
    with service_connection() as conn:
        account = conn.execute(
            "select status, followers, full_name from public.accounts where id = %s", (account_id,)
        ).fetchone()
        logged = conn.execute(
            "select creator_id, props from public.events where name = 'account_deleted'"
        ).fetchone()
    assert account == {"status": "opted_out", "followers": None, "full_name": None}
    assert logged["creator_id"] is None and logged["props"]["reels"] > 0
    assert not storage.exists(videos, take["path"]) and not storage.exists(videos, stray["path"])
    assert not any(storage.exists(videos, p) for p in reel_videos)
    # The old session is over.
    assert client.get("/v1/me", headers=a).status_code == 401

    # B's own data is untouched.
    assert creator_of("stylewithrhea") is not None
    assert (
        count(
            "select 1 from public.reels r join public.accounts a on a.id = r.account_id where a.username = %s",
            "stylewithrhea",
        )
        > 0
    )

    # Someone onboarding the handle again brings it back as a creator's own account.
    onboard(client, "a.again@example.com", "kavyawears")
    with service_connection() as conn:
        assert (
            conn.execute(
                "select status from public.accounts where id = %s", (account_id,)
            ).fetchone()["status"]
            == "active"
        )
    assert count("select 1 from public.reels where account_id = %s", account_id) > 0


def test_deleting_an_account_that_never_onboarded(client):
    headers = sign_in(client, "just.looking@example.com")
    res = client.delete("/v1/me", headers=headers)
    assert res.status_code == 202 and res.json() == {"status": "deleted", "job_id": None}
    assert client.get("/v1/me", headers=headers).status_code == 401


# ------------------------------------------------------------------ the daily cleanup


def test_the_daily_cleanup(client):
    a = onboard(client, "a@example.com", "kavyawears")
    onboard(client, "b@example.com", "stylewithrhea")
    creator = creator_of("kavyawears")
    storage, videos = providers.get_storage(), get_settings().storage_bucket_videos
    take = client.post("/v1/uploads/sample", json={"name": "take1"}, headers=a).json()
    sid = client.post("/v1/simulations", json={"upload_path": take["path"]}, headers=a).json()[
        "simulation_id"
    ]
    old_orphan = client.post("/v1/uploads/sample", json={"name": "take2"}, headers=a).json()
    new_orphan = client.post("/v1/uploads/sample", json={"name": "take2"}, headers=a).json()
    root = storage.root / videos  # type: ignore[attr-defined]
    two_days_ago = time.time() - 2 * 86400
    os.utime(root / old_orphan["path"], (two_days_ago, two_days_ago))
    with service_connection() as conn:
        conn.execute(  # a simulation from 100 days ago
            "update public.simulations set created_at = %s where id = %s",
            (clock.now() - timedelta(days=100), sid),
        )
        conn.execute(  # a deletion that stopped part-way
            "update public.creators set deletion_requested_at = %s where id = %s",
            (clock.now(), creator_of("stylewithrhea")["id"]),
        )
        conn.execute(
            """
            insert into public.opportunities (creator_id, topic_key, name, tag, score, parts, window_ends_on)
            values (%s, 'past', 'A festival that has passed', 'trend', 6, '{}', %s)
            """,
            (creator["id"], clock.now().date() - timedelta(days=1)),
        )

    job_id = enqueue("cleanup", {}, idempotency_key=f"test-cleanup-{uuid.uuid4()}")
    with service_connection() as conn:
        job = conn.execute(
            "select status, result from public.jobs where id = %s", (job_id,)
        ).fetchone()
        sim = conn.execute(
            "select video_path, result from public.simulations where id = %s", (sid,)
        ).fetchone()
        opp = conn.execute(
            "select status from public.opportunities where topic_key = 'past'"
        ).fetchone()
    assert job["status"] == "succeeded", job
    assert sim["video_path"] is None and sim["result"]  # the video goes, the estimate stays
    assert not storage.exists(videos, take["path"])
    assert not storage.exists(videos, old_orphan["path"])
    assert storage.exists(videos, new_orphan["path"])  # uploaded today: kept
    assert creator_of("stylewithrhea") is None
    assert opp["status"] == "expired"
    assert job["result"]["opportunities_expired"] == 1


# ------------------------------------------------------------------ after posting


@pytest.fixture
def demo(demo_db):
    with clock.frozen_at(ANCHOR):
        yield TestClient(create_app()), sign_in(TestClient(create_app()), "demo@curo.local")


def _posted_reel(account_id, caption: str, duration: float, counts: dict | None) -> uuid.UUID:
    posted = ANCHOR + timedelta(days=1)
    with service_connection() as conn:
        reel_id = conn.execute(
            """
            insert into public.reels
              (account_id, ig_media_id, shortcode, permalink, posted_at, duration_s, caption, first_seen_at)
            values (%s, %s, %s, %s, %s, %s, %s, %s) returning id
            """,
            (
                account_id,
                f"test-{uuid.uuid4()}",
                f"test{uuid.uuid4().hex[:8]}",
                "https://instagram.example/reel/test",
                posted,
                duration,
                caption,
                posted + timedelta(hours=2),
            ),
        ).fetchone()["id"]
        if counts:
            conn.execute(
                """
                insert into public.metric_snapshots (reel_id, taken_at, age_hours, views, likes, comments, shares)
                values (%s, %s, 168, %s, %s, %s, %s)
                """,
                (
                    reel_id,
                    posted + timedelta(hours=168),
                    counts["views"],
                    counts["likes"],
                    counts["comments"],
                    counts["shares"],
                ),
            )
    return reel_id


def test_a_posted_reel_is_matched_confirmed_and_checked_against_its_estimate(demo):
    client, headers = demo
    take = client.post("/v1/uploads/sample", json={"name": "take1"}, headers=headers).json()
    started = client.post(
        "/v1/simulations",
        json={"upload_path": take["path"], "caption": take["caption"]},
        headers=headers,
    ).json()
    sim = client.get(f"/v1/simulations/{started['simulation_id']}", headers=headers).json()
    creator = creator_of("curo.demo")
    with service_connection() as conn:
        predicted = conn.execute(
            "select predicted from public.simulations where id = %s", (sim["id"],)
        ).fetchone()["predicted"]
    inside = {m: round(predicted[m]["mid"]) for m in ("views", "likes", "comments", "shares")}
    reel_id = _posted_reel(creator["account_id"], take["caption"], 41.0, inside)
    other_id = _posted_reel(
        creator["account_id"], "A day at the office, nothing festive", 12.0, None
    )
    try:
        queue_match(reel_id, creator["id"])
        queue_match(other_id, creator["id"])
        matches = client.get("/v1/matches", headers=headers).json()
        assert [m["reel_id"] for m in matches] == [str(reel_id)]  # the unrelated reel isn't
        match = matches[0]
        assert match["simulation_id"] == sim["id"] and match["simulation_score"] == sim["score"]
        assert "It’s the same length as the video you simulated." in match["reasons"]

        confirmed = client.post(f"/v1/matches/{match['id']}/confirm", headers=headers).json()
        assert confirmed["status"] == "confirmed"
        assert client.get("/v1/matches", headers=headers).json() == []
        with service_connection() as conn:
            assert (
                conn.execute(
                    "select posted_reel_id from public.simulations where id = %s", (sim["id"],)
                ).fetchone()["posted_reel_id"]
                == reel_id
            )

        # A week on, the weekly report checks the estimate.
        with clock.frozen_at(ANCHOR + timedelta(days=9)):
            job_id = enqueue(
                "accuracy_report",
                {"creator_id": str(creator["id"])},
                idempotency_key=f"test-acc-{uuid.uuid4()}",
            )
        with service_connection() as conn:
            job = conn.execute(
                "select status, result from public.jobs where id = %s", (job_id,)
            ).fetchone()
            row = conn.execute(
                "select in_range, actual from public.simulations where id = %s", (sim["id"],)
            ).fetchone()
            record = conn.execute(
                "select accuracy from public.creators where id = %s", (creator["id"],)
            ).fetchone()["accuracy"]
            note = sim_jobs._accuracy(conn, creator["id"])
        assert job["status"] == "succeeded" and job["result"]["checked"] == 1
        assert row["in_range"] is True and set(row["actual"]) == {
            "views",
            "likes",
            "comments",
            "shares",
        }
        assert (record["hits"], record["total"], record["widen"]) == (1, 1, 1.0)
        assert note == "Curo’s range contained the result for 1 of your last 1 simulated reels."
    finally:
        with service_connection() as conn:
            conn.execute("delete from public.reels where id = any(%s)", ([reel_id, other_id],))
            conn.execute(
                "update public.creators set accuracy = null where id = %s", (creator["id"],)
            )
            conn.execute(
                "update public.simulations set in_range = null, actual = null where id = %s",
                (sim["id"],),
            )


def test_a_wrong_match_can_be_turned_down(demo):
    client, headers = demo
    take = client.post("/v1/uploads/sample", json={"name": "take2"}, headers=headers).json()
    client.post(
        "/v1/simulations",
        json={"upload_path": take["path"], "caption": take["caption"]},
        headers=headers,
    )
    creator = creator_of("curo.demo")
    reel_id = _posted_reel(creator["account_id"], take["caption"], 32.0, None)
    try:
        queue_match(reel_id, creator["id"])
        (match,) = client.get("/v1/matches", headers=headers).json()
        assert (
            client.post(f"/v1/matches/{match['id']}/reject", headers=headers).json()["status"]
            == "rejected"
        )
        other = sign_in(client, "someone.else.matching@example.com")
        assert client.post(f"/v1/matches/{match['id']}/confirm", headers=other).status_code in (
            404,
            409,
        )
        with service_connection() as conn:
            assert (
                conn.execute(
                    "select count(*) as n from public.simulations where posted_reel_id = %s",
                    (reel_id,),
                ).fetchone()["n"]
                == 0
            )
    finally:
        with service_connection() as conn:
            conn.execute("delete from public.reels where id = %s", (reel_id,))


def test_cleanup_runs_nightly_and_the_accuracy_report_weekly(client):
    from curo.jobs.scheduler import tick

    onboard(client, "a@example.com", "kavyawears")
    monday_2am = ANCHOR.replace(hour=20, minute=30) - timedelta(
        days=1
    )  # 02:00 IST, Mon 23 Aug 2027
    tuesday_2am = monday_2am + timedelta(days=1)
    with clock.frozen_at(monday_2am):
        monday = tick(monday_2am)
    with clock.frozen_at(tuesday_2am):
        tuesday = tick(tuesday_2am)
    assert "cleanup" in monday and "accuracy_report" in monday
    assert "cleanup" in tuesday and "accuracy_report" not in tuesday
