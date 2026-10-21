"""The worker as a thread inside the API process (QUEUE_MODE=thread).

Used by ``tools/local_stack.py`` to run CURO without Docker: RQ's worker forks, which
Windows can't do. One thread runs jobs one at a time, Studio and Simulator jobs first, like
the Docker worker on its ``studio`` and ``curo`` queues. Jobs are the same functions
(``curo.jobs.run_job``); only the hand-over differs.
"""

from __future__ import annotations

import itertools
import logging
import queue
import threading
from uuid import UUID

from curo import heartbeat

log = logging.getLogger("curo.local_worker")
HEARTBEAT_SECONDS = 10

_queue: queue.PriorityQueue[tuple[int, int, str]] = queue.PriorityQueue()
_order = itertools.count()
_pending: set[str] = set()
_lock = threading.Lock()
_thread: threading.Thread | None = None


def submit(job_id: UUID | str, priority: bool) -> None:
    """Hand a job to the thread (once: a job already waiting isn't queued twice)."""
    key = str(job_id)
    with _lock:
        if key in _pending:
            return
        _pending.add(key)
    _queue.put((0 if priority else 1, next(_order), key))
    _ensure_started()


def is_pending(job_id: UUID | str) -> bool:
    with _lock:
        return str(job_id) in _pending


def _ensure_started() -> None:
    global _thread
    with _lock:
        if _thread is None or not _thread.is_alive():
            _thread = threading.Thread(target=_run, name="curo-local-worker", daemon=True)
            _thread.start()


def _run() -> None:
    from curo.jobs import run_job

    while True:
        try:
            heartbeat.beat("worker")
        except Exception as exc:  # Redis hiccup: the next beat retries
            log.warning("heartbeat failed: %s", exc)
        try:
            _, _, job_id = _queue.get(timeout=HEARTBEAT_SECONDS)
        except queue.Empty:
            continue
        try:
            run_job(job_id)
        except Exception:  # recorded on the job row (and reported) by run_job
            log.exception("job %s failed", job_id)
        finally:
            with _lock:
                _pending.discard(job_id)


def start() -> None:
    """Start the thread now, so /health shows a worker before the first job."""
    _ensure_started()
