"""Background jobs (MVP doc §9).

Each job is a plain function registered with ``@job("name")``. ``run_job(job_id)`` loads the
row from ``public.jobs``, runs it and records status, progress and result there (the app
follows progress by watching that row). Jobs are idempotent: a retry never duplicates data.

``JobFailed`` is a clean, user-facing failure (e.g. a private account): no retry.
Any other exception marks the job failed and is re-raised so RQ can retry it once.
"""

from __future__ import annotations

import json
import logging
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from curo import clock
from curo.db import service_connection

log = logging.getLogger("curo.jobs")

JobFn = Callable[["JobContext"], dict | None]
JOBS: dict[str, JobFn] = {}


class JobFailed(Exception):
    """A clean failure with a message the creator can read. Not retried."""


def job(name: str) -> Callable[[JobFn], JobFn]:
    def register(fn: JobFn) -> JobFn:
        JOBS[name] = fn
        return fn

    return register


@dataclass
class JobContext:
    job_id: UUID
    type: str
    creator_id: UUID | None
    payload: dict[str, Any]

    def progress(self, **fields: Any) -> None:
        """Merge fields into the job's progress (its own transaction, so polling sees it)."""
        with service_connection() as conn:
            conn.execute(
                "update public.jobs set progress = progress || %s, updated_at = %s where id = %s",
                (Jsonb(fields), clock.now(), self.job_id),
            )


def run_job(job_id: UUID | str) -> str:
    """Run one job by id. Returns its final status."""
    _load_handlers()
    with service_connection() as conn:
        row = conn.execute(
            "select * from public.jobs where id = %s for update", (str(job_id),)
        ).fetchone()
        if row is None:
            raise LookupError(f"job {job_id} not found")
        if row["status"] == "succeeded":
            return "succeeded"
        conn.execute(
            """
            update public.jobs set status = 'running', attempts = attempts + 1,
                   started_at = %s, updated_at = %s, error = null
             where id = %s
            """,
            (clock.now(), clock.now(), row["id"]),
        )
    handler = JOBS.get(row["type"])
    ctx = JobContext(row["id"], row["type"], row["creator_id"], row["payload"] or {})
    from curo import usage

    usage.current_creator.set(row["creator_id"])
    try:
        if handler is None:
            raise JobFailed(f"unknown job type {row['type']!r}")
        result = handler(ctx) or {}
    except JobFailed as exc:
        _finish(row["id"], "failed", error=str(exc))
        log.info("job %s %s failed: %s", row["type"], row["id"], exc)
        return "failed"
    except Exception as exc:
        _finish(row["id"], "failed", error=f"{type(exc).__name__}: {exc}"[:1000])
        log.error("job %s %s crashed:\n%s", row["type"], row["id"], traceback.format_exc())
        from curo import providers

        providers.get_monitoring().capture_exception(
            exc, {"job": row["type"], "job_id": str(row["id"]), "attempt": row["attempts"] + 1}
        )
        raise
    _finish(row["id"], "succeeded", result=result)
    return "succeeded"


def _finish(
    job_id: UUID, status: str, *, result: dict | None = None, error: str | None = None
) -> None:
    with service_connection() as conn:
        conn.execute(
            """
            update public.jobs set status = %s, result = %s, error = %s,
                   finished_at = %s, updated_at = %s
             where id = %s
            """,
            (
                status,
                Jsonb(json.loads(json.dumps(result, default=str))) if result is not None else None,
                error,
                clock.now(),
                clock.now(),
                job_id,
            ),
        )


def _load_handlers() -> None:
    """Import the job modules so their @job decorators register."""
    from curo.jobs import (  # noqa: F401
        cleanup,
        collect,
        comment_labels,
        hashtags,
        learning,
        lifecycle,
        opportunities,
        simulation,
        studio,
        trends,
        understand,
    )
