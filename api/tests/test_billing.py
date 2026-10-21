"""Plans, credits and costs (PLAN_V2 §4.6): server-side limits, 402 with an upgrade path,
top-ups that never expire, the append-only ledger and the admin costs page."""

from datetime import timedelta

import psycopg
import pytest
from fastapi.testclient import TestClient

from curo import clock
from curo.config import get_settings
from curo.db import service_connection
from curo.main import create_app
from curo.providers.public_data.mock import MockPublicDataProvider
from curo.services import billing

pytestmark = pytest.mark.db
ANCHOR = MockPublicDataProvider().anchor


@pytest.fixture
def real_limits(monkeypatch):
    for key, value in (
        ("FREE_PROJECTS", "2"),
        ("FREE_SIMULATIONS", "2"),
        ("FREE_CHAT", "10"),
        ("PROJECT_REVISIONS", "10"),
    ):
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()


def signed_in(email: str, username: str = "curo.demo") -> TestClient:
    client = TestClient(create_app())
    code = client.post("/v1/auth/otp", json={"email": email}).json()["dev_code"]
    token = client.post("/v1/auth/verify", json={"email": email, "code": code}).json()
    client.headers["Authorization"] = f"Bearer {token['access_token']}"
    client.post("/v1/onboarding/username", json={"username": username})
    return client


def test_free_plan_two_projects_then_402_then_pro(db, real_limits):
    with clock.frozen_at(ANCHOR):
        c = signed_in("free@example.com")
        state = c.get("/v1/billing").json()
        assert state["plan"] == "free" and state["credits"]["project"]["left"] == 2
        assert [p["key"] for p in state["plans"]] == ["free", "pro"]
        for _ in range(2):
            assert (
                c.post(
                    "/v1/projects", json={"idea_text": "Three ways to drape a dupatta"}
                ).status_code
                == 201
            )
        over = c.post("/v1/projects", json={"idea_text": "One more idea"})
        assert over.status_code == 402
        assert over.json()["detail"]["code"] == "out_of_credits"
        assert over.json()["detail"]["resource"] == "project"
        # Upgrade (the mock completes at once): a fresh Pro allowance.
        out = c.post("/v1/billing/checkout", json={"item": "pro"}).json()
        assert out["status"] == "completed" and out["billing"]["plan"] == "pro"
        assert out["billing"]["credits"]["project"]["left"] == 10
        assert c.post("/v1/projects", json={"idea_text": "Now on Pro"}).status_code == 201


def test_top_ups_are_spent_after_the_plan_and_never_expire(db, real_limits):
    with clock.frozen_at(ANCHOR):
        c = signed_in("topup@example.com")
        out = c.post("/v1/billing/checkout", json={"item": "topup_project"}).json()
        assert out["billing"]["credits"]["project"] == {
            "left": 3, "plan_left": 2, "plan_total": 2, "topup_left": 1,
        }  # fmt: skip
        for _ in range(3):
            assert c.post("/v1/projects", json={"idea_text": "An idea"}).status_code == 201
        assert c.post("/v1/projects", json={"idea_text": "An idea"}).status_code == 402
    # Next month: the plan's credits are back; nothing was left over to carry.
    with clock.frozen_at(ANCHOR + timedelta(days=40)):
        c.post("/v1/billing/checkout", json={"item": "topup_project"})
        credits = c.get("/v1/billing").json()["credits"]["project"]
        assert credits["plan_left"] == 2 and credits["topup_left"] == 1


def test_revisions_are_capped_per_project(db, real_limits, monkeypatch):
    monkeypatch.setenv("PROJECT_REVISIONS", "1")
    get_settings.cache_clear()
    with clock.frozen_at(ANCHOR):
        c = signed_in("rev@example.com")
        pid = c.post("/v1/projects", json={"idea_text": "Dupatta drapes"}).json()["project_id"]
        assert c.post(f"/v1/projects/{pid}/ideas", json={"prompt": None}).status_code == 202
        over = c.post(f"/v1/projects/{pid}/ideas", json={"prompt": None})
        assert over.status_code == 402 and over.json()["detail"]["code"] == "revision_limit"
        assert "1 revisions" in over.json()["detail"]["message"]


def test_ask_curo_says_out_of_messages_in_the_stream(db, real_limits, monkeypatch):
    monkeypatch.setenv("FREE_CHAT", "0")
    get_settings.cache_clear()
    with clock.frozen_at(ANCHOR):
        c = signed_in("chat@example.com")
        res = c.post("/v1/chat", json={"message": "Hi", "screen": "studio:ideas"})
        assert res.status_code == 200
        assert "out_of_credits" in res.text and "event: error" in res.text


def test_the_ledger_is_append_only_and_spends_are_recorded_once(db):
    with clock.frozen_at(ANCHOR):
        signed_in("ledger@example.com")
        with service_connection() as conn:
            creator = conn.execute(
                "select c.id from public.creators c join auth.users u on u.id = c.user_id "
                "where u.email = 'ledger@example.com'"
            ).fetchone()["id"]
            billing.spend(conn, creator, "simulation", "simulation:x", clock.now())
            billing.spend(conn, creator, "simulation", "simulation:x", clock.now())  # retried
            n = conn.execute(
                "select count(*) as n from public.credit_ledger where kind = 'spend' and creator_id = %s",
                (creator,),
            ).fetchone()["n"]
            assert n == 1
        with pytest.raises(psycopg.errors.RaiseException), service_connection() as conn:
            conn.execute(
                "update public.credit_ledger set amount = 99 where creator_id = %s", (creator,)
            )


def test_admin_costs_only_for_admins_and_flags_big_spenders(db, monkeypatch):
    with clock.frozen_at(ANCHOR):
        c = signed_in("someone@example.com")
        assert c.get("/v1/admin/costs").status_code == 404
        monkeypatch.setenv("ADMIN_EMAILS", "boss@example.com")
        monkeypatch.setenv("COST_ALERT_USD", "0")
        get_settings.cache_clear()
        boss = signed_in("boss@example.com", "mumbaiwardrobe")
        c.post("/v1/projects", json={"idea_text": "Dupatta drapes"})  # model calls cost something
        costs = boss.get("/v1/admin/costs").json()
        assert costs["total_usd"] > 0 and costs["features"]
        assert any(x["over_alert"] for x in costs["creators"])
