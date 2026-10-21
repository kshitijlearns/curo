"""Phase 3 end to end: process_reel, label_comments, recompute_learning, the scheduler's
learning and nightly runs, privacy of learned data, and the demo replay's pattern cards."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from curo import clock, providers
from curo.config import get_settings
from curo.db import creator_session, service_connection
from curo.jobs.scheduler import tick
from curo.main import create_app
from curo.providers.public_data.mock import MockPublicDataProvider
from curo.queue import enqueue
from curo.schemas.taxonomy import ALL_FIELDS, MIN_CONFIDENCE, UNKNOWN
from curo.services import collection as store
from curo.services.patterns import shrink

pytestmark = pytest.mark.db
ANCHOR = MockPublicDataProvider().anchor


def sign_in(client: TestClient, email: str) -> dict[str, str]:
    code = client.post("/v1/auth/otp", json={"email": email}).json()["dev_code"]
    session = client.post("/v1/auth/verify", json={"email": email, "code": code}).json()
    return {"Authorization": f"Bearer {session['access_token']}"}


def onboard(client: TestClient, email: str, handle: str) -> dict[str, str]:
    headers = sign_in(client, email)
    client.post("/v1/onboarding/username", json={"username": handle}, headers=headers)
    return headers


def account_id(handle: str):
    with service_connection() as conn:
        return conn.execute(
            "select id from public.accounts where username = %s", (handle,)
        ).fetchone()["id"]


@pytest.fixture
def client(db):
    with clock.frozen_at(ANCHOR):
        yield TestClient(create_app())


@pytest.fixture
def demo(client):
    headers = onboard(client, "me@example.com", "curo.demo")
    return headers, account_id("curo.demo")


# ---------------------------------------------------------------- process_reel


def test_onboarding_understands_the_newest_30_reels(client, demo):
    headers, aid = demo
    with service_connection() as conn:
        rows = conn.execute(
            """
            select r.id, r.video_path, r.posted_at, d.content, d.production, d.confidence, d.model_version,
                   e.model as emb_model
              from public.reels r
              left join public.reel_dna d on d.reel_id = r.id
              left join public.reel_embeddings e on e.reel_id = r.id
             where r.account_id = %s order by r.posted_at desc
            """,
            (aid,),
        ).fetchall()
    processed = [r for r in rows if r["content"] is not None]
    assert len(processed) == 30
    assert all(r["content"] is not None for r in rows[:30])  # the newest 30
    assert {r["emb_model"] for r in processed} == {"mock-hash-768-v1"}
    assert (
        processed[0]["model_version"] == "T1.v1:mock-video-v1|T2.v1:mock-fast-v1|mock-hash-768-v1"
    )
    storage = providers.get_storage()
    bucket = get_settings().storage_bucket_videos
    assert all(r["video_path"] and storage.exists(bucket, r["video_path"]) for r in processed)
    status = client.get("/v1/onboarding/status", headers=headers).json()
    assert status["reels_processed"] == 30


def test_stored_dna_follows_the_confidence_rule(demo):
    _, aid = demo
    with service_connection() as conn:
        rows = conn.execute(
            """
            select d.content, d.production, d.confidence from public.reel_dna d
              join public.reels r on r.id = d.reel_id where r.account_id = %s
            """,
            (aid,),
        ).fetchall()
    unknowns = 0
    for r in rows:
        dna = r["content"] | r["production"]
        for field in ALL_FIELDS:
            confident = r["confidence"].get(field, 0) >= MIN_CONFIDENCE
            assert (dna[field] != UNKNOWN) == confident, field
            unknowns += dna[field] == UNKNOWN
    assert unknowns > 0  # some fields really can't be told from the video, and say so


def test_processing_twice_does_nothing_new(demo):
    _, aid = demo
    with service_connection() as conn:
        reel = conn.execute(
            "select r.id from public.reels r join public.reel_dna d on d.reel_id = r.id where r.account_id = %s limit 1",
            (aid,),
        ).fetchone()
    job = enqueue("process_reel", {"reel_id": str(reel["id"]), "account_id": str(aid)})
    with service_connection() as conn:
        result = conn.execute("select result from public.jobs where id = %s", (job,)).fetchone()[
            "result"
        ]
    assert result == {"skipped": "already processed"}


def add_peer_reel(handle: str = "theoutfitdiaries", at=ANCHOR):
    """Collect one public reel of an account that isn't a creator (e.g. one opted out of being a creator)."""
    provider = MockPublicDataProvider(now=lambda: at)
    with service_connection() as conn:
        aid = store.upsert_account(conn, provider.get_profile(handle), at)
        reel = store.upsert_reel(conn, aid, provider.get_reels(handle, limit=1)[0], at, "discovery")
    return aid, reel


def test_peer_videos_are_deleted_once_their_dna_is_extracted(db):
    with clock.frozen_at(ANCHOR):
        aid, reel = add_peer_reel()
        enqueue("process_reel", {"reel_id": str(reel.id), "account_id": str(aid)})
    with service_connection() as conn:
        row = conn.execute(
            """
            select r.video_path, r.shortcode, d.reel_id from public.reels r
              left join public.reel_dna d on d.reel_id = r.id where r.id = %s
            """,
            (reel.id,),
        ).fetchone()
    assert row["reel_id"] is not None and row["video_path"] is None
    path = f"{aid}/{row['shortcode']}.mp4"
    assert not providers.get_storage().exists(get_settings().storage_bucket_videos, path)


def test_an_expired_media_link_is_refreshed(db):
    with clock.frozen_at(ANCHOR):
        aid, reel = add_peer_reel()
        with service_connection() as conn:
            conn.execute(
                "update public.reels set video_url = 'https://cdn.example.invalid/expired.mp4' where id = %s",
                (reel.id,),
            )
        enqueue("process_reel", {"reel_id": str(reel.id), "account_id": str(aid)})
    with service_connection() as conn:
        row = conn.execute(
            "select r.video_url, d.reel_id from public.reels r left join public.reel_dna d on d.reel_id = r.id where r.id = %s",
            (reel.id,),
        ).fetchone()
    assert row["reel_id"] is not None and "expired" not in row["video_url"]


def test_a_reel_that_vanished_fails_cleanly(db):
    # Collected 50 hours before the anchor, deleted 40 hours before it.
    earlier = ANCHOR - timedelta(hours=50)
    provider = MockPublicDataProvider(now=lambda: earlier)
    target = next(r for r in provider.get_reels("curo.demo", 50) if "editing routine" in r.caption)
    with service_connection() as conn:
        aid = store.upsert_account(conn, provider.get_profile("curo.demo"), earlier)
        reel = store.upsert_reel(conn, aid, target, earlier, "onboarding")
    with clock.frozen_at(ANCHOR):
        job = enqueue("process_reel", {"reel_id": str(reel.id), "account_id": str(aid)})
    with service_connection() as conn:
        row = conn.execute("select status, error from public.jobs where id = %s", (job,)).fetchone()
        dna = conn.execute(
            "select 1 from public.reel_dna where reel_id = %s", (reel.id,)
        ).fetchone()
    assert row["status"] == "failed" and "no longer available" in row["error"] and dna is None


# ---------------------------------------------------------------- comments


def test_comments_are_labelled_and_grouped_into_themes(demo):
    _, aid = demo
    with service_connection() as conn:
        counts = conn.execute(
            """
            select count(*) filter (where c.labelled_at is null and not c.is_creator) as unlabelled,
                   count(*) filter (where c.is_creator and c.labelled_at is not null) as creator_labelled,
                   count(*) filter (where c.is_bot) as bots,
                   count(*) filter (where c.language = 'hinglish') as hinglish,
                   count(*) filter (where c.language = 'hi') as hindi
              from public.comments c join public.reels r on r.id = c.reel_id where r.account_id = %s
            """,
            (aid,),
        ).fetchone()
        themes = conn.execute(
            "select * from public.comment_themes where account_id = %s order by share desc", (aid,)
        ).fetchall()
        members = conn.execute(
            "select count(*) as n from public.comments where theme_id = %s", (themes[0]["id"],)
        ).fetchone()["n"]
    assert counts["unlabelled"] == 0 and counts["creator_labelled"] == 0
    assert counts["bots"] > 0 and counts["hinglish"] > 0 and counts["hindi"] > 0
    assert themes[0]["label"] == "Asks where it's from" and themes[0]["kind"] == "question"
    assert members == themes[0]["n"] and 0 < themes[0]["share"] < 1
    labels = {t["label"]: t["kind"] for t in themes}
    assert labels["Wants budget versions"] == "request" and labels["Asks the price"] == "question"


# ---------------------------------------------------------------- learning


def test_learning_runs_once_processing_has_settled(demo):
    _, aid = demo
    with clock.frozen_at(ANCHOR):
        assert tick(ANCHOR) == [f"recompute_learning:{aid}"]
        assert tick(ANCHOR + timedelta(minutes=1)) == []  # nothing changed since
    with service_connection() as conn:
        baselines = conn.execute(
            "select count(*) as n from public.baselines where account_id = %s", (aid,)
        ).fetchone()
        groups = conn.execute(
            "select label, cardinality(reel_ids) as n from public.subclusters where account_id = %s",
            (aid,),
        ).fetchall()
        cards = conn.execute(
            "select * from public.pattern_cards where account_id = %s", (aid,)
        ).fetchall()
    assert baselines["n"] == 8 * 5  # 7 metrics + the growth curve, at 5 ages
    assert groups and all(g["n"] >= 3 for g in groups)  # always a group, never one reel
    for c in cards:
        if c["scope"] == "yours":
            assert c["n"] >= 8
            assert c["effect"] == pytest.approx(
                shrink(c["n"], c["creator_effect"], c["prior_effect"] or 1.0), abs=0.002
            )


def test_the_nightly_batch_runs_once_a_night(demo):
    _, aid = demo
    two_am = ANCHOR.replace(hour=20, minute=30) - timedelta(days=1)  # 02:00 IST on the anchor day
    with clock.frozen_at(ANCHOR):
        first = tick(two_am)
        again = tick(two_am + timedelta(minutes=20))
        nine_am = tick(ANCHOR - timedelta(hours=1))
    assert "recompute_learning:priors" in first and f"recompute_learning:{aid}" in first
    assert again == [] and not any(x.startswith("label_comments") for x in nine_am)


def test_learned_data_stays_private(client, demo):
    _, demo_aid = demo
    other = onboard(client, "other@example.com", "theoutfitdiaries")
    assert other
    with clock.frozen_at(ANCHOR):
        tick(ANCHOR)
    with service_connection() as conn:
        users = {
            r["email"]: r["id"] for r in conn.execute("select id, email from auth.users").fetchall()
        }
    for email, expect_rows in (("me@example.com", True), ("other@example.com", False)):
        with creator_session(users[email]) as conn:
            for table, where in (
                ("reel_dna", "reel_id in (select id from public.reels where account_id = %s)"),
                (
                    "reel_embeddings",
                    "reel_id in (select id from public.reels where account_id = %s)",
                ),
                ("baselines", "account_id = %s"),
                ("subclusters", "account_id = %s"),
                ("comment_themes", "account_id = %s"),
            ):
                n = conn.execute(
                    f"select count(*) as n from public.{table} where {where}", (demo_aid,)
                ).fetchone()["n"]
                assert (n > 0) == expect_rows, (email, table)


# ---------------------------------------------------------------- the demo replay


def test_demo_replay_learns_sensible_patterns(demo_db):
    """Done-when for Phase 3: every processed reel has DNA with confidence, and the pattern
    cards are the patterns really in the data — not topic differences in disguise."""
    aid = account_id("curo.demo")
    with service_connection() as conn:
        with_dna = conn.execute(
            """
            select count(*) as n from public.reel_dna d join public.reels r on r.id = d.reel_id
             where r.account_id = %s
            """,
            (aid,),
        ).fetchone()["n"]
        priors = conn.execute(
            "select count(*) as n from public.pattern_cards where account_id is null"
        ).fetchone()["n"]
    assert with_dna >= 30 and priors > 0  # creators like you: the pooled priors
    with service_connection() as conn:
        cards = {
            (c["feature"], c["value"], c["metric"]): c
            for c in conn.execute(
                "select * from public.pattern_cards where account_id = %s", (aid,)
            ).fetchall()
        }
        groups = {
            g["label"]: g
            for g in conn.execute(
                "select * from public.subclusters where account_id = %s", (aid,)
            ).fetchall()
        }
    yours = {k: c for k, c in cards.items() if c["scope"] == "yours"}
    # The production patterns built into the synthetic data, found by the real mining:
    assert yours[("ending", "choice_question", "comment_rate")]["creator_effect"] > 1.4
    assert yours[("cta_type", "share_prompt", "share_rate")]["creator_effect"] > 1.25
    assert yours[("payoff_band", "under_2s", "like_rate")]["creator_effect"] > 1.15
    # With peers' evidence the blend moves toward the shared pattern (built in at 1.7×).
    assert yours[("ending", "choice_question", "comment_rate")]["effect"] > 1.5
    # Topic markers don't become the creator's own cards (compared within sub-clusters).
    assert not any(
        f in ("camera", "setting", "opening_style", "cluster", "format") for f, _v, _m in yours
    )
    assert set(groups) == {
        "Festive styling",
        "Reel-making tips",
        "Get ready with me",
        "Hauls",
        "One item, many looks",
    }
    assert groups["Festive styling"]["lifts"]["views"]["lift"] > 1.3
    assert groups["Hauls"]["lifts"]["views"]["lift"] < 0.8
