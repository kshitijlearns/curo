"""Phase 2 end to end: sign-in, onboarding, collected reels, snapshots over time, RLS, seed.

v2 removed Home's carousel (GET /v1/reels); the tests read the same per-reel cards through
``services.insights`` as the creator, under Row Level Security."""

from datetime import timedelta

import psycopg
import pytest
from fastapi.testclient import TestClient

from curo import clock, providers
from curo.db import connect, creator_session, service_connection
from curo.jobs.scheduler import tick
from curo.main import create_app
from curo.providers.public_data.failover import FailoverProvider
from curo.providers.public_data.mock import MockPublicDataProvider
from curo.queue import enqueue

pytestmark = pytest.mark.db
ANCHOR = MockPublicDataProvider().anchor


def sign_in(client: TestClient, email: str) -> dict[str, str]:
    code = client.post("/v1/auth/otp", json={"email": email}).json()["dev_code"]
    session = client.post("/v1/auth/verify", json={"email": email, "code": code}).json()
    return {"Authorization": f"Bearer {session['access_token']}", "X-Email": email}


def reel_cards(headers: dict[str, str], limit: int = 10) -> list[dict]:
    """The creator's latest reels as they see them (RLS), newest first."""
    from curo.services import insights

    with service_connection() as conn:
        user_id = conn.execute(
            "select id from auth.users where email = %s", (headers["X-Email"].lower(),)
        ).fetchone()["id"]
    with creator_session(user_id) as conn:
        creator = conn.execute("select account_id from public.creators").fetchone()
        if creator is None or creator["account_id"] is None:
            return []
        cards = insights.latest_cards(insights.load_account(conn, creator["account_id"]), limit)
    return [c.model_dump(mode="json") for c in cards]


@pytest.fixture
def client(db):
    with clock.frozen_at(ANCHOR):
        yield TestClient(create_app())


# ---------------------------------------------------------------- sign-in


def test_sign_in_with_a_code(client):
    client.post("/v1/auth/otp", json={"email": "Creator@Example.com"})
    assert (
        client.post(
            "/v1/auth/verify", json={"email": "creator@example.com", "code": "000000"}
        ).status_code
        == 401
    )
    headers = sign_in(client, "creator@example.com")
    me = client.get("/v1/me", headers=headers).json()
    assert me["email"] == "creator@example.com" and me["creator"] is None
    assert me["onboarded"] is False
    assert client.get("/v1/me").status_code == 401
    assert client.get("/v1/me", headers={"Authorization": "Bearer nonsense"}).status_code == 401


def test_code_stops_working_after_five_wrong_tries(client):
    code = client.post("/v1/auth/otp", json={"email": "a@b.co"}).json()["dev_code"]
    for _ in range(5):
        client.post(
            "/v1/auth/verify",
            json={"email": "a@b.co", "code": "999999" if code != "999999" else "111111"},
        )
    assert client.post("/v1/auth/verify", json={"email": "a@b.co", "code": code}).status_code == 401


# ---------------------------------------------------------------- onboarding → Home


def test_entering_the_demo_handle_fills_home_from_the_database(client):
    headers = sign_in(client, "me@example.com")
    started = client.post(
        "/v1/onboarding/username", json={"username": "@Curo.Demo"}, headers=headers
    )
    assert started.status_code == 202 and started.json()["username"] == "curo.demo"

    status = client.get("/v1/onboarding/status", headers=headers).json()
    assert status["status"] == "ready"
    assert status["reels_found"] == 49
    assert status["comments_done"] == status["comments_total"] == 30

    cards = reel_cards(headers)
    assert len(cards) == 10
    first = cards[0]
    assert first["title"] == "3 mistakes ruining your aesthetic reel"
    assert first["metrics"] == {"views": 104000, "likes": 3744, "comments": 302, "shares": 281}

    by_title = {c["title"]: c for c in cards}
    hidden = by_title["GRWM: monsoon office look"]
    assert hidden["metrics"]["likes"] is None and hidden["likes_hidden"]  # shown as a dash, never 0
    assert by_title["How I light my reels with one window"]["metrics"]["shares"] is None
    off = by_title["My monsoon skincare routine"]
    assert (
        off["metrics"]["comments"] is None
        and off["comments_disabled"]
        and off["is_paid_partnership"]
    )

    me = client.get("/v1/me", headers=headers).json()
    assert me["account"]["username"] == "curo.demo"
    assert me["account"]["followers"] == 48_200
    assert me["reels"] == 49 and me["onboarded"] is True


def test_public_account_without_reels_still_finishes_onboarding(client):
    data = {
        "meta": {"anchor": ANCHOR.isoformat()},
        "accounts": [{"username": "new.creator", "followers": {"base": 40}, "posts_at_anchor": 0}],
        "reels": {},
    }
    providers.override("public_data", FailoverProvider(MockPublicDataProvider(data=data)))
    headers = sign_in(client, "n@example.com")
    client.post("/v1/onboarding/username", json={"username": "new.creator"}, headers=headers)
    assert client.get("/v1/onboarding/status", headers=headers).json()["status"] == "ready"
    me = client.get("/v1/me", headers=headers).json()
    assert me["reels"] == 0 and me["onboarded"] is True  # Home's empty state, no loop
    assert reel_cards(headers) == []


def test_reseeding_the_demo_sends_its_users_back_to_onboarding(client):
    from curo.seed import reset_demo

    headers = sign_in(client, "early@example.com")
    client.post("/v1/onboarding/username", json={"username": "curo.demo"}, headers=headers)
    assert client.get("/v1/me", headers=headers).json()["onboarded"] is True
    reset_demo()  # deletes the fixture accounts; creators.account_id is set to null
    assert client.get("/v1/me", headers=headers).json()["onboarded"] is False
    status = client.get("/v1/onboarding/status", headers=headers).json()
    assert status["status"] == "not_started"  # the form again, not a stale "ready"


def test_private_account_is_refused(client):
    data = {
        "meta": {"anchor": ANCHOR.isoformat()},
        "accounts": [
            {
                "username": "secret.style",
                "is_private": True,
                "followers": {"base": 10},
                "posts_at_anchor": 0,
            }
        ],
        "reels": {},
    }
    providers.override("public_data", FailoverProvider(MockPublicDataProvider(data=data)))
    headers = sign_in(client, "p@example.com")
    client.post("/v1/onboarding/username", json={"username": "secret.style"}, headers=headers)
    status = client.get("/v1/onboarding/status", headers=headers).json()
    assert status["status"] == "failed"
    assert "private" in status["error"] and "never asks you to log in" in status["error"]
    assert client.get("/v1/me", headers=headers).json()["onboarded"] is False


def test_bad_usernames_are_rejected(client):
    headers = sign_in(client, "x@example.com")
    assert (
        client.post(
            "/v1/onboarding/username", json={"username": "not a handle!"}, headers=headers
        ).status_code
        == 422
    )


def test_comments_are_stored_without_handles(client):
    headers = sign_in(client, "c@example.com")
    client.post("/v1/onboarding/username", json={"username": "curo.demo"}, headers=headers)
    with service_connection() as conn:
        cols = {
            r["column_name"]
            for r in conn.execute(
                "select column_name from information_schema.columns where table_name = 'comments'"
            ).fetchall()
        }
        texts = [r["text"] for r in conn.execute("select text from public.comments").fetchall()]
        tagged = conn.execute(
            "select count(*) as n from public.comments where tags_friend"
        ).fetchone()["n"]
        own = conn.execute("select count(*) as n from public.comments where is_creator").fetchone()[
            "n"
        ]
    assert not {"author", "author_handle", "handle", "username"} & cols
    assert not any("@riya.k" in t or "@meera_s" in t for t in texts)
    assert any("@…" in t for t in texts)
    assert tagged > 0 and own > 0


def test_refresh_only_when_data_is_three_hours_old(client):
    headers = sign_in(client, "r@example.com")
    client.post("/v1/onboarding/username", json={"username": "curo.demo"}, headers=headers)
    assert client.post("/v1/reels/refresh", headers=headers).json()["status"] == "fresh"
    with clock.frozen_at(ANCHOR + timedelta(hours=4)):
        r = client.post("/v1/reels/refresh", headers=headers)
        assert r.status_code == 202 and r.json()["status"] == "queued"
        job = client.get(f"/v1/jobs/{r.json()['job_id']}", headers=headers).json()
        assert job["status"] == "succeeded"
        cards = reel_cards(headers)
    assert cards[0]["snapshots"] == 2
    assert cards[0]["metrics"]["views"] > 104_000


# ---------------------------------------------------------------- the scheduler over time


def _onboard_at(when, email="s@example.com"):
    with clock.frozen_at(when):
        client = TestClient(create_app())
        headers = sign_in(client, email)
        client.post("/v1/onboarding/username", json={"username": "curo.demo"}, headers=headers)


def _run_schedule(start, hours):
    t = start
    for _ in range(hours):
        t += timedelta(hours=1)
        with clock.frozen_at(t):
            tick(t)


def _snapshots(title_prefix):
    with service_connection() as conn:
        return conn.execute(
            """
            select m.* from public.metric_snapshots m join public.reels r on r.id = m.reel_id
             where r.caption like %s order by m.taken_at
            """,
            (title_prefix + "%",),
        ).fetchall()


def test_new_reel_is_tracked_from_its_first_hours(db):
    start = ANCHOR - timedelta(hours=72)  # "3 mistakes" was posted 2 h earlier
    _onboard_at(start)
    _run_schedule(start, 72)
    snaps = _snapshots("3 mistakes ruining")
    ages = [float(s["age_hours"]) for s in snaps]
    assert ages[0] == pytest.approx(2.0, abs=0.01)
    # At the planned ages: 6-hourly to 48 h, then daily (the anchor is at 74 h).
    assert ages == pytest.approx([2, 6, 12, 18, 24, 30, 36, 42, 48, 72], abs=0.01)
    views = [s["views"] for s in snaps]
    assert views == sorted(views)  # public counts only grow
    assert 95_000 < views[-1] <= 104_000
    with service_connection() as conn:
        followers = conn.execute("select count(*) as n from public.account_snapshots").fetchone()[
            "n"
        ]
    assert followers >= 10  # the follower count is saved with every run


def test_glitch_is_flagged_and_deleted_reel_keeps_its_history(db):
    start = ANCHOR - timedelta(days=6)
    _onboard_at(start)
    # A pull to refresh inside the vendor's glitch window (-120 h to -94 h), then the schedule.
    with clock.frozen_at(start + timedelta(hours=30)), service_connection() as conn:
        aid = conn.execute(
            "select id from public.accounts where username = 'curo.demo'"
        ).fetchone()["id"]
    with clock.frozen_at(start + timedelta(hours=30)):
        enqueue("snapshot_account", {"account_id": str(aid), "refresh": True})
    _run_schedule(start, 6 * 24)
    snaps = _snapshots("GRWM: monsoon office look")
    flagged = [s for s in snaps if s["flagged"]]
    # The glitch lowers views (and the counts that follow them): previous values are kept.
    assert flagged and "views_decreased" in flagged[0]["flag_reason"]
    views = [s["views"] for s in snaps]
    assert views == sorted(views)
    assert all(s["likes"] is None for s in snaps)  # hidden likes stay unknown throughout
    with service_connection() as conn:
        reel = conn.execute(
            "select * from public.reels where caption like 'My 10-minute reel editing routine%'"
        ).fetchone()
    assert reel["is_deleted"] and reel["deleted_at"] is not None
    assert len(_snapshots("My 10-minute reel editing routine")) >= 2


def test_discovery_finds_a_reel_posted_later(db):
    _onboard_at(ANCHOR)
    _run_schedule(ANCHOR, 44)  # the first post-anchor reel appears at +30 h
    snaps = _snapshots("One outfit, three Ganpati moods")
    assert snaps and snaps[0]["source"] == "discovery"
    assert float(snaps[0]["age_hours"]) <= 12.01  # caught within a new-reel check (12-hourly)


# ---------------------------------------------------------------- Row Level Security


def test_creators_only_see_their_own_rows(client):
    a = sign_in(client, "a@example.com")
    b = sign_in(client, "b@example.com")
    client.post("/v1/onboarding/username", json={"username": "curo.demo"}, headers=a)
    client.post("/v1/onboarding/username", json={"username": "mumbaiwardrobe"}, headers=b)
    assert reel_cards(a)[0]["title"].startswith("3 mistakes")
    assert not any("3 mistakes" in c["title"] for c in reel_cards(b, 50))

    with service_connection() as conn:
        users = {
            r["email"]: r["id"] for r in conn.execute("select id, email from auth.users").fetchall()
        }
        demo = conn.execute(
            "select id from public.accounts where username = 'curo.demo'"
        ).fetchone()["id"]
        a_creator = conn.execute(
            "select id from public.creators where user_id = %s", (users["a@example.com"],)
        ).fetchone()["id"]
        conn.execute(
            "insert into public.projects (creator_id, title) values (%s, 'A draft')", (a_creator,)
        )
        conn.execute(
            "insert into public.hashtag_pages (tag, fetched_at) values ('ganpatioutfit', now())"
        )
    with creator_session(users["b@example.com"]) as conn:
        # Another creator's account and reels are invisible (v2: no peers).
        assert (
            conn.execute("select username from public.accounts where id = %s", (demo,)).fetchone()
            is None
        )
        assert (
            conn.execute(
                "select count(*) as n from public.reels where account_id = %s", (demo,)
            ).fetchone()["n"]
            == 0
        )
        assert conn.execute("select count(*) as n from public.projects").fetchone()["n"] == 0
        assert conn.execute("select count(*) as n from public.creators").fetchone()["n"] == 1
        assert conn.execute("select count(*) as n from public.hashtag_pages").fetchone()["n"] == 1
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "insert into public.reels (account_id, ig_media_id, shortcode, permalink, posted_at, first_seen_at) values (%s, 'x', 'x', 'x', now(), now())",
                (demo,),
            )


def test_anonymous_role_sees_nothing(db):
    with connect(db) as conn, conn.transaction():
        conn.execute("set local role anon")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("select * from public.reels")


# ---------------------------------------------------------------- seed replay


def test_seed_replay_uses_the_real_path(db):
    from curo.seed import seed_demo

    summary = seed_demo(days=2, quiet=True)
    assert summary["reels"] == 50  # 49 live + the deleted one kept with its history
    assert summary["snapshots"] > summary["reels"]
    assert summary["snapshot_runs"] >= 6  # a run at least every 6 h for 2 days (v2)
    assert clock.describe()["source"] == "real"  # clock restored afterwards
    with pytest.raises(SystemExit):
        seed_demo(days=1, quiet=True)  # refuses to double-seed without --reset
