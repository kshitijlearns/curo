"""Shared test fixtures.

Tests never read the developer's .env, never call outside services, and use fakeredis.

Database tests (marked ``db``) need Postgres + pgvector. In order of preference:

1. ``TEST_DATABASE_URL`` — any server we may create databases on (CI, Docker).
2. pgserver — embedded Postgres + pgvector (``pip install -e "api[localdb]"``),
   so the suite runs on a laptop without Docker.

Each test session creates a fresh database, migrates it, and drops it at the end.
"""

from __future__ import annotations

import os

# Must happen before anything imports curo.config.
os.environ["CURO_ENV_FILE"] = ""
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("MOCK_MODE", "true")
os.environ["QUEUE_MODE"] = "inline"  # jobs run in-process in tests

import uuid
from collections.abc import Iterator

import fakeredis
import psycopg
import pytest
from psycopg.conninfo import make_conninfo

from curo import clock, providers
from curo.config import REPO_ROOT, get_settings
from curo.db import make_pool, set_pool
from curo.db import migrate as migrations
from curo.redis_client import set_redis


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path) -> Iterator[fakeredis.FakeRedis]:
    """Fresh settings, fakeredis, clock state, providers and file storage for every test."""
    monkeypatch.delenv("FAKE_NOW", raising=False)
    monkeypatch.setenv("QUEUE_MODE", "inline")
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "storage"))
    # Plan limits don't get in the way of other tests; test_billing sets the real ones.
    for key in ("FREE_PROJECTS", "FREE_SIMULATIONS", "FREE_CHAT", "PROJECT_REVISIONS"):
        monkeypatch.setenv(key, "1000")
    get_settings.cache_clear()
    redis = fakeredis.FakeRedis()
    set_redis(redis)
    clock.reset()
    providers.reset()
    yield redis
    providers.reset()
    clock.reset()
    set_redis(None)
    get_settings.cache_clear()


@pytest.fixture
def redis(_isolated) -> fakeredis.FakeRedis:
    return _isolated


def _postgres_server_url() -> str | None:
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        return url
    try:
        import pgserver
    except ImportError:
        return None
    data_dir = REPO_ROOT / ".data" / "pgserver-test"
    data_dir.mkdir(parents=True, exist_ok=True)
    return pgserver.get_server(str(data_dir), cleanup_mode="stop").get_uri()


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """URL of a fresh, fully migrated test database."""
    server = _postgres_server_url()
    if server is None:
        pytest.skip("no Postgres: set TEST_DATABASE_URL or pip install -e 'api[localdb]'")
    name = f"curo_test_{uuid.uuid4().hex[:10]}"
    with psycopg.connect(server, autocommit=True) as admin:
        admin.execute(f'create database "{name}"')
    url = make_conninfo(server, dbname=name)
    migrations.run(url, shim=True, quiet=True)
    yield url
    set_pool(None)
    with psycopg.connect(server, autocommit=True) as admin:
        admin.execute(f'drop database if exists "{name}" with (force)')


@pytest.fixture(scope="session")
def demo_database_url(tmp_path_factory) -> Iterator[str]:
    """A separate database holding the full 14-day demo replay (creator, peers, learning,
    opportunities), seeded once per session for the modules that read it."""
    from curo.seed import seed_demo

    server = _postgres_server_url()
    if server is None:
        pytest.skip("no Postgres: set TEST_DATABASE_URL or pip install -e 'api[localdb]'")
    name = f"curo_demo_{uuid.uuid4().hex[:10]}"
    with psycopg.connect(server, autocommit=True) as admin:
        admin.execute(f'create database "{name}"')
    url = make_conninfo(server, dbname=name)
    migrations.run(url, shim=True, quiet=True)
    old_storage = os.environ.get("LOCAL_STORAGE_DIR")
    os.environ["LOCAL_STORAGE_DIR"] = str(tmp_path_factory.mktemp("demo-storage"))
    get_settings.cache_clear()
    set_redis(fakeredis.FakeRedis())
    clock.reset()
    providers.reset()
    set_pool(make_pool(url, max_size=6))
    try:
        seed_demo(days=14, quiet=True)
    finally:
        set_pool(None)
        providers.reset()
        set_redis(None)
        if old_storage is None:
            os.environ.pop("LOCAL_STORAGE_DIR", None)
        else:
            os.environ["LOCAL_STORAGE_DIR"] = old_storage
        get_settings.cache_clear()
    yield url
    with psycopg.connect(server, autocommit=True) as admin:
        admin.execute(f'drop database if exists "{name}" with (force)')


@pytest.fixture
def demo_db(demo_database_url) -> Iterator[str]:
    """The seeded demo database, with the app's connection pool pointed at it."""
    set_pool(make_pool(demo_database_url, max_size=6))
    yield demo_database_url
    set_pool(None)


_TABLES = (
    "events, jobs, creator_memory, chat_messages, simulation_edits, simulations, captions, "
    "storyboard_versions, script_versions, ideas, projects, opportunities, festival_calendar, "
    "hashtag_pages, pattern_cards, comment_themes, subclusters, baselines, reel_embeddings, "
    "reel_dna, comments, metric_snapshots, reels, account_snapshots, creators, accounts"
)


@pytest.fixture
def db(database_url) -> Iterator[str]:
    """An empty database, with the app's connection pool pointed at it."""
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(f"truncate {_TABLES} cascade")
        conn.execute("truncate auth.users, auth.local_otp_codes cascade")
    pool = make_pool(database_url, max_size=6)
    set_pool(pool)
    yield database_url
    set_pool(None)
