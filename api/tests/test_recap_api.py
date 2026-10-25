"""v2.1 first run end to end on mocks: anonymous session → username → recap (v2.2: with
"Meet your followers") → save the account → Home's four sections; plus the monthly recap and
the account-taken path."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from curo import clock
from curo.db import service_connection
from curo.jobs.recap import monthly_tick
from curo.main import create_app
from curo.providers.public_data.mock import MockPublicDataProvider
from curo.services.validator import new_numbers

pytestmark = pytest.mark.db
ANCHOR = MockPublicDataProvider().anchor


def anonymous(client: TestClient) -> dict[str, str]:
    session = client.post("/v1/auth/anonymous").json()
    return {"Authorization": f"Bearer {session['access_token']}"}


def test_first_run_anonymous_to_recap_to_saved_account_to_home(db):
    with clock.frozen_at(ANCHOR):
        client = TestClient(create_app())
        h = anonymous(client)
        assert client.get("/v1/me", headers=h).json()["is_anonymous"] is True

        res = client.post("/v1/onboarding/username", json={"username": "@curo.demo"}, headers=h)
        assert res.status_code == 202
        status = client.get("/v1/onboarding/status", headers=h).json()
        assert status["status"] == "ready" and status["recap_status"] == "ready"
        assert status["step"] == "recap_ready" and status["followers"] == 48_200

        recap = client.get("/v1/recaps/latest", headers=h).json()
        assert recap["kind"] == "first" and recap["period_label"] == "Your story so far"
        assert recap["is_new"] and 5 <= len(recap["slides"]) <= 18
        ids = [s["slide_id"] for s in recap["slides"]]
        # v2.2: the persona sequence comes right after the creator-type reveal.
        assert ids[0] == "intro" and ids[-9:] == [
            "creator_type",
            "followers_intro",
            "persona_1",
            "persona_2",
            "persona_3",
            "persona_4",
            "followers_summary",
            "share_card",
            "next_up",
        ]
        personas = [s["facts"] for s in recap["slides"] if s["slide_id"].startswith("persona_")]
        assert sum(p["share_pct"] for p in personas) == 100
        assert [p["color"] for p in personas] == ["blue", "lavender", "pink", "ink"]
        assert recap["creator_level"] == "The Rising Voice" and recap["archetype"]
        for s in recap["slides"]:
            line = f"{s['copy']['headline']} {s['copy']['subline']}"
            assert not new_numbers(line, [*s["facts"]["display"], "@curo.demo"]), s
            assert "0 " not in s["facts"]["display"][0][:2]  # nothing missing shown as 0
        # Slides that need video analysis are left out of the first recap when DNA isn't in.
        assert all(
            "@" not in str(s["facts"].get("top_comment", "")).replace("@…", "")
            for s in recap["slides"]
        )

        svg = client.get(f"/v1/recaps/{recap['id']}/share-image", headers=h)
        assert svg.status_code == 200 and svg.headers["content-type"].startswith("image/svg+xml")
        assert (
            "@curo.demo" in svg.text and 'width="1080"' in svg.text and "gradient" not in svg.text
        )
        assert "Your followers" in svg.text and personas[0]["short_name"] in svg.text

        seen = client.post(f"/v1/recaps/{recap['id']}/viewed", headers=h).json()
        assert seen["is_new"] is False and seen["viewed_at"]

        # Save the account: the anonymous session becomes a real one, data kept.
        code = client.post("/v1/auth/otp", json={"email": "new@example.com"}).json()["dev_code"]
        saved = client.post(
            "/v1/auth/convert", json={"email": "new@example.com", "code": code}, headers=h
        ).json()
        h2 = {"Authorization": f"Bearer {saved['access_token']}"}
        me = client.get("/v1/me", headers=h2).json()
        assert me["is_anonymous"] is False and me["email"] == "new@example.com"
        assert me["account"]["username"] == "curo.demo"
        assert client.get("/v1/recaps", headers=h2).json()[0]["id"] == recap["id"]

        # Home's four sections, in order, all answer (v2.2: the personas first).
        home = client.get("/v1/home", headers=h2).json()
        assert [x["id"] for x in home["sections"]] == [
            "personas",
            "recap",
            "opportunities",
            "trends",
        ]
        for x in home["sections"]:
            assert client.get(x["endpoint"], headers=h2).status_code == 200
        cards = client.get("/v1/personas", headers=h2).json()
        assert cards["status"] == "ready" and len(cards["personas"]) == 4
        # "What your followers will love" is gone.
        assert client.get("/v1/follower-ideas", headers=h2).status_code == 404


def test_a_handle_already_on_curo_offers_sign_in_instead(db):
    with clock.frozen_at(ANCHOR):
        client = TestClient(create_app())
        first = anonymous(client)
        client.post("/v1/onboarding/username", json={"username": "curo.demo"}, headers=first)
        second = anonymous(client)
        res = client.post("/v1/onboarding/username", json={"username": "curo.demo"}, headers=second)
        assert res.status_code == 409 and res.json()["detail"]["code"] == "account_taken"


def test_saving_with_an_email_that_already_has_an_account_is_refused(db):
    with clock.frozen_at(ANCHOR):
        client = TestClient(create_app())
        code = client.post("/v1/auth/otp", json={"email": "old@example.com"}).json()["dev_code"]
        client.post("/v1/auth/verify", json={"email": "old@example.com", "code": code})
        h = anonymous(client)
        code = client.post("/v1/auth/otp", json={"email": "old@example.com"}).json()["dev_code"]
        res = client.post(
            "/v1/auth/convert", json={"email": "old@example.com", "code": code}, headers=h
        )
        assert res.status_code == 409 and res.json()["detail"]["code"] == "email_taken"


def test_the_monthly_recap_is_built_once_for_last_month(db):
    with clock.frozen_at(ANCHOR):
        client = TestClient(create_app())
        h = anonymous(client)
        client.post("/v1/onboarding/username", json={"username": "curo.demo"}, headers=h)
        with service_connection() as conn:  # on CURO since before last month
            conn.execute(
                "update public.creators set created_at = %s", (ANCHOR - timedelta(days=90),)
            )
        queued = monthly_tick(ANCHOR)
        assert len(queued) == 1
        assert monthly_tick(ANCHOR) == []  # already built: never twice
        months = [r for r in client.get("/v1/recaps", headers=h).json() if r["kind"] == "monthly"]
        assert len(months) == 1 and months[0]["period_label"] == "July 2027"


def test_another_creator_cannot_read_a_recap(db):
    with clock.frozen_at(ANCHOR):
        client = TestClient(create_app())
        h = anonymous(client)
        client.post("/v1/onboarding/username", json={"username": "curo.demo"}, headers=h)
        recap_id = client.get("/v1/recaps/latest", headers=h).json()["id"]
        other = anonymous(client)
        client.post("/v1/onboarding/username", json={"username": "mumbaiwardrobe"}, headers=other)
        assert client.get(f"/v1/recaps/{recap_id}", headers=other).status_code == 404
