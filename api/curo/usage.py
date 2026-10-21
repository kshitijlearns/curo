"""The usage ledger (PLAN_V2 §4.6): one row per model call or collection run, with an
estimated cost, so /v1/admin/costs can show totals per creator and per feature.

Who a call is for comes from a context variable, set by the job runner (the job's creator)
and by the API's creator dependency. Recording never breaks the work it measures.
"""

from __future__ import annotations

import logging
import threading
from contextvars import ContextVar
from uuid import UUID

from curo import clock
from curo.services.billing import cost_usd

log = logging.getLogger(__name__)
current_creator: ContextVar[UUID | None] = ContextVar("current_creator", default=None)


def tokens(text: str) -> int:
    """A rough token count (about four characters a token) for the cost estimate."""
    return max(1, len(text) // 4) if text else 0


# Its own connection, outside the pool: model calls often happen while the caller holds a
# pooled connection, and borrowing a second one from the pool for every call can exhaust it.
_conn = None
_conn_info: str | None = None
_lock = threading.Lock()


def _connection():
    """The ledger's connection, or None while this process has no database yet."""
    global _conn, _conn_info
    from curo import db

    if db._pool is None:  # nothing has used the database: nowhere to record (unit tests)
        return None
    info = db._pool.conninfo
    if _conn is None or _conn.closed or _conn_info != info:
        if _conn is not None and not _conn.closed:
            _conn.close()
        _conn = db.connect(info, autocommit=True, connect_timeout=3)
        # Never wait on a row the caller's own transaction holds: give up and move on.
        _conn.execute("set lock_timeout = '1s'; set statement_timeout = '3s'")
        _conn_info = info
    return _conn


def record(
    provider: str,
    model: str | None,
    task: str | None,
    tokens_in: int = 0,
    tokens_out: int = 0,
    results: int = 0,
    ref_id: str | None = None,
    creator_id: UUID | None = None,
) -> None:
    try:
        with _lock:
            conn = _connection()
            if conn is None:
                return
            conn.execute(
                """
                insert into public.usage_ledger
                  (creator_id, provider, model, task, tokens_in, tokens_out, results, cost_usd,
                   ref_id, created_at)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    creator_id or current_creator.get(),
                    provider,
                    model,
                    task,
                    tokens_in,
                    tokens_out,
                    results,
                    cost_usd(model, tokens_in, tokens_out, results),
                    ref_id,
                    clock.now(),
                ),
            )
    except Exception:
        log.warning("usage not recorded", exc_info=True)
