import pytest
from fastapi.testclient import TestClient

from curo import heartbeat
from curo.db import make_pool, set_pool
from curo.db.migrate import migration_files
from curo.main import create_app


@pytest.mark.db
def test_health_ok_with_database_and_redis(db):
    heartbeat.beat("worker")
    body = TestClient(create_app()).get("/health").json()
    assert body["status"] == "ok"
    assert body["checks"]["database"]["ok"] is True
    latest = migration_files()[-1].stem
    assert body["checks"]["database"]["detail"] == f"migrations at {latest}"
    assert body["checks"]["redis"]["ok"] is True
    assert body["checks"]["worker"]["ok"] is True
    assert body["checks"]["scheduler"]["ok"] is False  # never beat in this test
    assert body["mock_mode"] is True
    assert body["providers"]["llm"] == "mock"


def test_health_is_503_when_database_is_down():
    set_pool(make_pool("postgresql://postgres@127.0.0.1:1/nowhere", max_size=1))
    try:
        response = TestClient(create_app()).get("/health")
    finally:
        set_pool(None)
    assert response.status_code == 503
    assert response.json()["status"] == "error"
    assert response.json()["checks"]["database"]["ok"] is False
