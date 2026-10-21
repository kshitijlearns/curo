"""Postgres access.

Two ways in:

* ``service_connection()`` — full access, used by the worker, jobs and migrations
  (the connecting role owns the tables, so RLS does not apply).
* ``creator_session(user_id)`` — used by API requests. It opens a transaction,
  switches to the ``authenticated`` role and sets the JWT claims, exactly as
  Supabase does, so Row Level Security decides which rows a creator can see.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from curo.config import get_settings

# pgvector lives in the `extensions` schema (as on Supabase).
SEARCH_PATH_OPTION = "-c search_path=public,extensions"

_pool: ConnectionPool | None = None
_lock = threading.Lock()


def make_pool(conninfo: str, max_size: int = 10) -> ConnectionPool:
    return ConnectionPool(
        conninfo=conninfo,
        min_size=1,
        max_size=max_size,
        kwargs={"options": SEARCH_PATH_OPTION, "row_factory": dict_row},
        open=True,
        timeout=10,
    )


def get_pool() -> ConnectionPool:
    global _pool
    with _lock:
        if _pool is None:
            _pool = make_pool(get_settings().database_url)
        return _pool


def set_pool(pool: ConnectionPool | None) -> None:
    """Replace the shared pool (tests point it at their own database)."""
    global _pool
    with _lock:
        if _pool is not None and _pool is not pool:
            _pool.close()
        _pool = pool


def close_pool() -> None:
    set_pool(None)


@contextmanager
def service_connection() -> Iterator[psycopg.Connection]:
    """A pooled connection with full access, inside one transaction."""
    with get_pool().connection() as conn, conn.transaction():
        yield conn


@contextmanager
def creator_session(user_id: UUID | str) -> Iterator[psycopg.Connection]:
    """A transaction in which RLS applies as the given Supabase user."""
    claims = json.dumps({"sub": str(user_id), "role": "authenticated"})
    with get_pool().connection() as conn, conn.transaction():
        conn.execute("set local role authenticated")
        conn.execute("select set_config('request.jwt.claims', %s, true)", (claims,))
        yield conn


def connect(conninfo: str | None = None, **kwargs) -> psycopg.Connection:
    """A standalone connection (scripts, migrations, tests)."""
    return psycopg.connect(
        conninfo or get_settings().database_url,
        options=SEARCH_PATH_OPTION,
        row_factory=dict_row,
        **kwargs,
    )
