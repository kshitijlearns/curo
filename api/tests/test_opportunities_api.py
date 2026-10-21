"""Opportunities (v2, no peers): "Ganpati dress ideas" comes out of the real scoring on top,
with parts that add up; save, dismiss and Saved behave; Trending for you ranks the niche's
shared trend cards for this creator."""

import pytest
from fastapi.testclient import TestClient

from curo import clock
from curo.db import service_connection
from curo.main import create_app
from curo.providers.public_data.mock import MockPublicDataProvider
from curo.queue import enqueue

pytestmark = pytest.mark.db
ANCHOR = MockPublicDataProvider().anchor


def signed_in(email: str) -> TestClient:
    client = TestClient(create_app())
    code = client.post("/v1/auth/otp", json={"email": email}).json()["dev_code"]
    token = client.post("/v1/auth/verify", json={"email": email, "code": code}).json()
    client.headers["Authorization"] = f"Bearer {token['access_token']}"
    return client


@pytest.fixture
def demo(demo_db):
    with clock.frozen_at(ANCHOR):
        yield signed_in("demo@curo.local")


def test_ganpati_dress_ideas_is_top(demo):
    cards = demo.get("/v1/opportunities").json()
    assert 1 <= len(cards) <= 5
    top = cards[0]
    assert top["name"] == "Ganpati dress ideas"
    assert top["tag"] == "Trend" and top["score_shown"] >= 7
    assert "creators you track" not in top["card"]  # v2: no peers
    assert [c["score"] for c in cards] == sorted((c["score"] for c in cards), reverse=True)


def test_the_parts_add_up_to_the_score(demo):
    top = demo.get("/v1/opportunities").json()[0]
    detail = demo.get(f"/v1/opportunities/{top['id']}").json()
    parts = {p["key"]: p for p in detail["parts"]}
    assert {k: p["weight"] for k, p in parts.items()} == {
        "F": 0.35,
        "D": 0.25,
        "T": 0.25,
        "O": 0.15,
    }
    total = 10 * sum(p["weight"] * p["value"] for p in parts.values())
    assert total == pytest.approx(detail["score"], abs=0.01)
    assert sum(p["share"] for p in detail["parts"]) == pytest.approx(1.0, abs=0.01)
    # The evidence behind it: the festival window, the audience, what's trending in the niche.
    assert detail["trending"] and all(t["name"] and t["why_rising"] for t in detail["trending"])
    assert "competitor_handles" not in detail and "peer_reels" not in detail
    assert any("Ganesh Chaturthi starts in 12 days." in f for f in parts["T"]["facts"])
    assert detail["fit"][0]["k"] == "Your content" and "Festive styling" in detail["fit"][0]["t"]
    assert "Trend" in detail["signals"] and "Competitors" not in detail["signals"]


def test_detail_texts_add_no_numbers_of_their_own(demo):
    from curo.services.validator import new_numbers

    for card in demo.get("/v1/opportunities").json():
        d = demo.get(f"/v1/opportunities/{card['id']}").json()
        facts = [f for p in d["parts"] for f in p["facts"]] + [d["name"]]
        assert new_numbers(d["description"], facts) == set(), d["name"]


def test_save_keeps_the_score_then_and_dismiss_hides_it_for_good(demo):
    cards = demo.get("/v1/opportunities").json()
    first, second = cards[0], cards[1]
    saved = demo.post(f"/v1/opportunities/{first['id']}/save").json()
    assert saved["saved"] is True
    with service_connection() as conn:  # the score moves on; the saved score stays
        conn.execute(
            "update public.opportunities set score = score - 1, window_ends_on = '2027-08-01' where id = %s",
            (first["id"],),
        )
    listing = demo.get("/v1/saved").json()["opportunities"]
    entry = next(o for o in listing if o["id"] == first["id"])
    assert entry["score_when_saved"] == pytest.approx(entry["score_today"] + 1)
    assert entry["window_passed"] is True
    assert demo.get("/v1/me").json()["saved_opportunities"] == 1
    demo.delete(f"/v1/opportunities/{first['id']}/save")
    assert demo.get("/v1/saved").json()["opportunities"] == []

    assert demo.post(f"/v1/opportunities/{second['id']}/dismiss").status_code == 204
    assert second["id"] not in {c["id"] for c in demo.get("/v1/opportunities").json()}
    with service_connection() as conn:
        creator = conn.execute(
            "select id from public.creators where ig_username = 'curo.demo'"
        ).fetchone()["id"]
        event = conn.execute(
            "select props from public.events where name = 'opportunity_dismissed' order by created_at desc limit 1"
        ).fetchone()
    assert event["props"]["opportunity_id"] == second["id"]
    enqueue("build_opportunities", {"creator_id": str(creator)})  # the nightly rebuild
    assert second["id"] not in {c["id"] for c in demo.get("/v1/opportunities").json()}


def test_only_the_creators_own_opportunities(demo_db):
    with clock.frozen_at(ANCHOR):
        other = signed_in("someone@example.com")
        top = signed_in("demo@curo.local").get("/v1/opportunities").json()[0]
        assert other.get(f"/v1/opportunities/{top['id']}").status_code in (404, 409)


def test_trending_for_you_ranks_the_niches_cards_for_this_creator(demo):
    cards = demo.get("/v1/trends").json()
    assert 1 <= len(cards) <= 4
    assert all(c["name"] and c["why_rising"] and c["example_angles"] for c in cards)
    assert all(c["saturation"] in ("low", "medium", "high", "unknown") for c in cards)
    assert all(0 <= c["fit"] <= 1 for c in cards)


def test_the_peer_endpoints_are_gone(demo):
    assert demo.get("/v1/peers/suggestions").status_code == 404
    assert demo.post("/v1/peers", json={"username": "x"}).status_code in (404, 405)


# ---------------------------------------------------------------- a fresh creator (empty database)


def test_a_private_handle_is_refused_at_onboarding(db):
    data = {
        "meta": {"anchor": ANCHOR.isoformat()},
        "accounts": [{"username": "secret.style", "is_private": True, "followers": {"base": 10}, "posts_at_anchor": 0}],
        "reels": {},
    }  # fmt: skip
    from curo import providers
    from curo.providers.public_data.failover import FailoverProvider

    providers.override("public_data", FailoverProvider(MockPublicDataProvider(data=data)))
    with clock.frozen_at(ANCHOR):
        client = signed_in("fresh@example.com")
        client.post("/v1/onboarding/username", json={"username": "@secret.style"})
        status = client.get("/v1/onboarding/status").json()
        assert status["status"] == "failed" and "private" in (status.get("error") or "").lower()
