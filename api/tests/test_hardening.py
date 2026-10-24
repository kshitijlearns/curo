"""Phase 9 hardening: every route needs a session, unexpected errors are reported and answered
plainly, failing jobs are reported, product events reach analytics."""

import re
import uuid

import pytest
from fastapi.testclient import TestClient

from curo import clock, events, providers
from curo.db import service_connection
from curo.jobs import JobFailed, job
from curo.main import create_app
from curo.providers.monitoring.noop import NoopMonitoring
from curo.queue import enqueue

pytestmark = pytest.mark.db

# Public by design: health, signing in, the signed upload URL (its token is the permission),
# and the vendor webhook (its own secret).
PUBLIC = {
    ("get", "/health"),
    ("post", "/v1/auth/otp"),
    ("post", "/v1/auth/verify"),
    ("post", "/v1/auth/anonymous"),  # a first-run session before any email (v2.1)
    ("put", "/v1/uploads/local/{token}"),
    ("post", "/v1/webhooks/apify"),
    ("post", "/v1/billing/webhook/{provider}"),  # the provider's own signature (D208)
    ("post", "/v1/cron/tick"),  # CRON_SECRET (D200)
}


def test_the_cron_and_payment_webhook_refuse_strangers(db, monkeypatch):
    client = TestClient(create_app())
    assert client.post("/v1/cron/tick").status_code == 401  # no secret set: off
    monkeypatch.setenv("CRON_SECRET", "s3cret-for-tests")
    from curo.config import get_settings

    get_settings.cache_clear()
    client = TestClient(create_app())
    assert client.post("/v1/cron/tick", headers={"Authorization": "Bearer nope"}).status_code == 401
    ok = client.post("/v1/cron/tick", headers={"Authorization": "Bearer s3cret-for-tests"})
    assert ok.status_code == 200 and isinstance(ok.json()["queued"], list)
    assert client.post("/v1/billing/webhook/stripe").status_code == 404  # not the provider


class Recording(NoopMonitoring):
    def __init__(self):
        super().__init__()
        self.errors: list[tuple[str, dict]] = []

    def capture_exception(self, exc, context=None):
        self.errors.append((f"{type(exc).__name__}: {exc}", context or {}))


@pytest.fixture
def monitoring():
    m = Recording()
    providers.override("monitoring", m)
    return m


def test_every_route_needs_a_session(db):
    app = create_app()
    client = TestClient(app)
    checked = 0
    for path, ops in app.openapi()["paths"].items():
        for method in ops:
            if (method, path) in PUBLIC:
                continue
            url = re.sub(r"\{[^}]+\}", str(uuid.uuid4()), path)
            res = client.request(method.upper(), url, json={})
            assert res.status_code == 401, f"{method.upper()} {path} answered {res.status_code}"
            assert res.json()["detail"] in ("Sign in first",)
            checked += 1
    assert checked >= 40


def test_a_forged_or_expired_session_is_refused(db):
    client = TestClient(create_app())
    for token in ("not-a-jwt", "eyJhbGciOiJIUzI1NiJ9.e30.x"):
        res = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401 and res.json()["detail"] == "Invalid or expired session"


def test_an_unexpected_error_is_reported_and_answered_plainly(db, monitoring, monkeypatch):
    client = TestClient(create_app(), raise_server_exceptions=False)
    code = client.post("/v1/auth/otp", json={"email": "err@example.com"}).json()["dev_code"]
    token = client.post("/v1/auth/verify", json={"email": "err@example.com", "code": code}).json()

    class Broken:
        @staticmethod
        def now():
            raise RuntimeError("clock unplugged")

    monkeypatch.setattr("curo.routes.me.clock", Broken)
    res = client.get("/v1/me", headers={"Authorization": f"Bearer {token['access_token']}"})
    assert res.status_code == 500
    assert res.json() == {"detail": "Something went wrong on Curo’s side. Try again in a moment."}
    assert monitoring.errors == [
        ("RuntimeError: clock unplugged", {"route": "/v1/me", "method": "GET"})
    ]


@job("test_crash")
def _crash(ctx):
    raise ValueError("a bug in a job")


@job("test_refused")
def _refused(ctx):
    raise JobFailed("A plain reason for the creator.")


def test_a_crashing_job_is_reported_but_a_refusal_is_not(db, monitoring):
    with clock.frozen_at(clock.now()):
        crashed = enqueue("test_crash", {}, idempotency_key=f"crash-{uuid.uuid4()}")
        refused = enqueue("test_refused", {}, idempotency_key=f"refused-{uuid.uuid4()}")
    with service_connection() as conn:
        rows = {
            r["id"]: r
            for r in conn.execute(
                "select id, status, error from public.jobs where id = any(%s)",
                ([crashed, refused],),
            ).fetchall()
        }
    assert rows[crashed]["status"] == "failed" and rows[refused]["status"] == "failed"
    assert rows[refused]["error"] == "A plain reason for the creator."
    assert [(e, c["job"]) for e, c in monitoring.errors] == [
        ("ValueError: a bug in a job", "test_crash")
    ]


def test_product_events_reach_analytics(db, monitoring):
    with service_connection() as conn:
        events.record(conn, None, "app_test_event", {"n": 1})
        stored = conn.execute(
            "select props from public.events where name = 'app_test_event'"
        ).fetchone()
    assert stored["props"] == {"n": 1}
    assert monitoring.events == [("app_test_event", {"n": 1}, None)]
