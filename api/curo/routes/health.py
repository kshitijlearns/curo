"""GET /health — used by hosting and by `make dev` to know the stack is up."""

from __future__ import annotations

from fastapi import APIRouter, Response
from pydantic import BaseModel

from curo import __version__, clock, heartbeat
from curo.config import get_settings
from curo.db import get_pool
from curo.db.migrate import current_version
from curo.redis_client import get_redis

router = APIRouter(tags=["system"])

PROVIDERS = ("public_data", "video", "embedding", "llm", "storage", "monitoring", "auth")


class Check(BaseModel):
    ok: bool
    detail: str


class HealthOut(BaseModel):
    status: str  # "ok" when the database and Redis are reachable, else "error"
    version: str
    app_env: str
    mock_mode: bool
    providers: dict[str, str]
    clock: dict
    checks: dict[str, Check]


def _db_check() -> Check:
    try:
        with get_pool().connection(timeout=3) as conn:
            version = current_version(conn)
        return Check(ok=True, detail=f"migrations at {version or 'none'}")
    except Exception as exc:
        return Check(ok=False, detail=f"{type(exc).__name__}: {exc}"[:200])


def _redis_check() -> Check:
    try:
        get_redis().ping()
        return Check(ok=True, detail="ping ok")
    except Exception as exc:
        return Check(ok=False, detail=f"{type(exc).__name__}: {exc}"[:200])


def _process_check(name: str, redis_ok: bool) -> Check:
    if not redis_ok:
        return Check(ok=False, detail="unknown (Redis unreachable)")
    age = heartbeat.seconds_since_beat(name)
    if age is None:
        return Check(ok=False, detail="no heartbeat in the last minute")
    return Check(ok=True, detail=f"last heartbeat {age:.0f}s ago")


@router.get("/health", response_model=HealthOut)
def health(response: Response) -> HealthOut:
    settings = get_settings()
    db = _db_check()
    redis = _redis_check()
    checks = {
        "database": db,
        "redis": redis,
        # Background processes are reported but don't fail the API's own health check.
        "worker": _process_check("worker", redis.ok),
        "scheduler": _process_check("scheduler", redis.ok),
    }
    ok = db.ok and redis.ok
    if not ok:
        response.status_code = 503
    return HealthOut(
        status="ok" if ok else "error",
        version=__version__,
        app_env=settings.app_env,
        mock_mode=settings.mock_mode,
        providers={name: settings.provider(name) for name in PROVIDERS},
        clock=clock.describe() if redis.ok else {"now": clock.now().isoformat()},
        checks=checks,
    )
