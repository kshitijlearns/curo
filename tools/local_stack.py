"""Run CURO's backend on this computer without Docker.

    python tools/local_stack.py up [--seed] [--port 8000]   # API + worker + scheduler
    python tools/local_stack.py seed                        # (re)load the demo creator

Windows: ./dev.ps1 local [-seed]   then, in a second terminal, ./dev.ps1 web (Next.js).

What runs, in one process:
- Postgres + pgvector embedded through pgserver (``pip install -e "api[localdb]"``, part of
  ``make setup``), its data kept in ``.data/pgserver-dev``.
- A Redis stand-in (fakeredis over TCP on port 6390), so the clock, heartbeats and
  ``tools/timetravel.py`` work as with Docker (``REDIS_URL=redis://127.0.0.1:6390/0``).
- The API (uvicorn on 0.0.0.0, so a phone on the same Wi-Fi can reach it), the worker as a
  background thread (QUEUE_MODE=thread: RQ's worker forks, which Windows can't do) and the
  scheduler loop.

The code is the same as in Docker; only where it runs differs. Docker remains the setup
that matches production (DECISIONS D115).
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import socket
import sys
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "api"))
sys.path.insert(0, str(REPO / "worker"))

PG_DIR = REPO / ".data" / "pgserver-dev"
REDIS_PORT = 6390
DB_NAME = "curo"


def _port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _start_redis() -> None:
    """A Redis stand-in shared by every local process (reuse one that's already running)."""
    if _port_open(REDIS_PORT):
        return
    from fakeredis import TcpFakeServer

    server = TcpFakeServer(("127.0.0.1", REDIS_PORT), server_type="redis")
    threading.Thread(target=server.serve_forever, name="fake-redis", daemon=True).start()


def _start_postgres() -> str:
    try:
        import pgserver
    except ImportError:
        raise SystemExit(
            'Embedded Postgres is missing: run  pip install -e "api[localdb]"  (make setup does).'
        ) from None
    import psycopg

    PG_DIR.mkdir(parents=True, exist_ok=True)
    server = pgserver.get_server(str(PG_DIR), cleanup_mode="stop")
    with psycopg.connect(server.get_uri(), autocommit=True) as conn:
        if not conn.execute("select 1 from pg_database where datname = %s", (DB_NAME,)).fetchone():
            conn.execute(f"create database {DB_NAME}")
    return server.get_uri(DB_NAME)


def _prepare() -> None:
    """Services first, then settings: curo reads the environment once, on first use."""
    env_file = REPO / ".env"
    if not env_file.exists():
        shutil.copy(REPO / ".env.example", env_file)
        print("created .env from .env.example")
    print("starting embedded Postgres (first start takes a minute)…", flush=True)
    os.environ["DATABASE_URL"] = _start_postgres()
    _start_redis()
    os.environ["REDIS_URL"] = f"redis://127.0.0.1:{REDIS_PORT}/0"
    os.environ["QUEUE_MODE"] = "thread"

    from curo.config import get_settings
    from curo.db import migrate

    get_settings.cache_clear()
    if get_settings().provider("storage") != "local" or get_settings().provider("auth") != "local":
        raise SystemExit("The local stack needs local storage and sign-in (keep MOCK_MODE=true).")
    migrate.run(quiet=True)


def _seed() -> None:
    from curo import seed
    from curo.config import get_settings

    print("replaying two weeks of the demo creator's collection (about two minutes)…", flush=True)
    seed.seed_demo(reset=True)
    os.environ["QUEUE_MODE"] = "thread"  # the replay runs its jobs inline
    get_settings.cache_clear()


def up(port: int, with_seed: bool) -> None:
    _prepare()
    if with_seed:
        _seed()
    import uvicorn

    from curo import local_worker
    from curo_worker.scheduler import run_scheduler

    local_worker.start()
    threading.Thread(target=run_scheduler, name="curo-scheduler", daemon=True).start()
    print(f"CURO API on http://localhost:{port}  (health: http://localhost:{port}/health)")
    print("Start the web app in another terminal:  ./dev.ps1 web   (or: cd web && npm run dev)")
    uvicorn.run("curo.main:app", host="0.0.0.0", port=port, log_level="info")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_up = sub.add_parser("up", help="run the API, worker and scheduler")
    p_up.add_argument("--port", type=int, default=8000)
    p_up.add_argument("--seed", action="store_true", help="(re)load the demo creator first")
    sub.add_parser("seed", help="(re)load the demo creator @curo.demo")
    args = parser.parse_args(argv)
    if args.cmd == "up":
        up(args.port, args.seed)
    else:
        _prepare()
        _seed()
    return 0


if __name__ == "__main__":
    sys.exit(main())
