"""Enqueue background jobs.

``enqueue`` writes the job row (deduplicated by ``idempotency_key``) and hands it to the
runner: RQ on Redis in Docker, inline in-process (QUEUE_MODE=inline: tests, the seed
replay, and scripts), or a background thread in the API process (QUEUE_MODE=thread:
``tools/local_stack.py``, for running without Docker).

The row in Postgres is the record of what must run; handing it to Redis can fail (a dropped
connection, a Redis restart). Then the request still succeeds, the row stays queued, and the
scheduler hands it over again (``redispatch_orphans``). RQ jobs carry the row's id, so a
job that is merely waiting its turn is never sent twice.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from curo import clock
from curo.config import get_settings
from curo.db import service_connection

log = logging.getLogger("curo.queue")
QUEUE_NAME = "curo"
# A creator waiting in Studio or the Simulator comes before background work: the worker serves
# this queue first.
PRIORITY_QUEUE = "studio"
PRIORITY_TYPES = frozenset({"studio", "run_simulation", "apply_sim_edit", "cleanup"})
ORPHAN_AFTER = timedelta(minutes=5)


def enqueue(
    job_type: str,
    payload: dict[str, Any] | None = None,
    *,
    creator_id: UUID | str | None = None,
    idempotency_key: str | None = None,
) -> UUID:
    """Create the job and dispatch it. With a key already used, returns the existing job."""
    return _enqueue(job_type, payload, creator_id, idempotency_key)[0]


def enqueue_new(
    job_type: str,
    payload: dict[str, Any] | None = None,
    *,
    idempotency_key: str,
    creator_id: UUID | str | None = None,
) -> bool:
    """Like ``enqueue``; True only if this call created the job (the scheduler reports these)."""
    return _enqueue(job_type, payload, creator_id, idempotency_key)[1]


def _enqueue(
    job_type: str,
    payload: dict[str, Any] | None,
    creator_id: UUID | str | None,
    idempotency_key: str | None,
) -> tuple[UUID, bool]:
    now = clock.now()
    with service_connection() as conn:
        row = conn.execute(
            """
            insert into public.jobs (creator_id, type, payload, idempotency_key, created_at, updated_at)
            values (%s, %s, %s, %s, %s, %s)
            on conflict (idempotency_key) do nothing
            returning id
            """,
            (creator_id, job_type, Jsonb(payload or {}), idempotency_key, now, now),
        ).fetchone()
        if row is None:
            existing = conn.execute(
                "select id from public.jobs where idempotency_key = %s", (idempotency_key,)
            ).fetchone()
            return existing["id"], False
    dispatch(row["id"], job_type)
    return row["id"], True


def queue_for(job_type: str | None) -> str:
    return PRIORITY_QUEUE if job_type in PRIORITY_TYPES else QUEUE_NAME


def dispatch(job_id: UUID, job_type: str | None = None) -> None:
    mode = get_settings().queue_mode
    if mode == "inline":
        from curo.jobs import run_job

        try:
            run_job(job_id)
        except Exception:  # recorded on the job row; inline callers carry on
            log.exception("inline job %s failed", job_id)
        return
    if mode == "thread":
        from curo import local_worker

        local_worker.submit(job_id, priority=queue_for(job_type) == PRIORITY_QUEUE)
        return
    from redis.exceptions import RedisError
    from rq import Queue, Retry

    from curo.redis_client import get_redis

    try:
        Queue(queue_for(job_type), connection=get_redis()).enqueue(
            "curo.jobs.run_job",
            str(job_id),
            job_id=str(job_id),
            job_timeout=900,
            retry=Retry(max=1),
        )
    except RedisError as exc:
        log.warning("job %s is saved but not yet with the worker (%s); retrying later", job_id, exc)


def redispatch_orphans(now: datetime) -> list[str]:
    """Hand over again the jobs still queued a while after creation that RQ never received."""
    mode = get_settings().queue_mode
    if mode == "inline":
        return []  # inline jobs run as they're created; nothing can be left behind
    if mode == "thread":  # jobs queued before the API last stopped
        return _redispatch_local(now)
    from redis.exceptions import RedisError
    from rq.job import Job

    from curo.redis_client import get_redis

    with service_connection() as conn:
        rows = conn.execute(
            """
            select id, type from public.jobs
             where status = 'queued' and created_at < %s
             order by created_at limit 200
            """,
            (now - ORPHAN_AFTER,),
        ).fetchall()
    out = []
    for r in rows:
        try:
            if Job.exists(str(r["id"]), connection=get_redis()):
                continue  # waiting its turn
        except RedisError:
            return out  # Redis is still unreachable; the next tick tries again
        dispatch(r["id"], r["type"])
        out.append(f"redispatch:{r['type']}:{r['id']}")
    return out


def _redispatch_local(now: datetime) -> list[str]:
    from curo import local_worker

    with service_connection() as conn:
        rows = conn.execute(
            """
            select id, type from public.jobs
             where status = 'queued' and created_at < %s
             order by created_at limit 200
            """,
            (now - ORPHAN_AFTER,),
        ).fetchall()
    out = []
    for r in rows:
        if not local_worker.is_pending(r["id"]):
            dispatch(r["id"], r["type"])
            out.append(f"redispatch:{r['type']}:{r['id']}")
    return out
