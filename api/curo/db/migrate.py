"""Apply SQL migrations from db/migrations/ in filename order.

* Applied versions are recorded in ``public.schema_migrations`` with a checksum;
  editing an applied migration is an error (write a new one instead).
* A Postgres advisory lock makes concurrent runs (api + worker starting together) safe.
* Locally, the Supabase shim in db/local/ is applied first. It recreates what Supabase
  provides (auth schema, auth.uid(), roles, extensions schema) and is never run
  against Supabase itself.

Usage:  python -m curo.db.migrate [--database-url URL] [--no-shim]
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import psycopg

from curo.config import REPO_ROOT, get_settings

MIGRATIONS_DIR = REPO_ROOT / "db" / "migrations"
SHIM_DIR = REPO_ROOT / "db" / "local"
_LOCK_ID = 7_272_001


class MigrationError(RuntimeError):
    pass


def _checksum(sql: str) -> str:
    return hashlib.sha256(sql.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def migration_files(directory: Path = MIGRATIONS_DIR) -> list[Path]:
    return sorted(directory.glob("*.sql"))


def run(
    database_url: str | None = None,
    *,
    shim: bool | None = None,
    quiet: bool = False,
    migrations_dir: Path = MIGRATIONS_DIR,
) -> list[str]:
    """Apply pending migrations. Returns the versions applied in this run."""
    settings = get_settings()
    use_shim = settings.use_supabase_shim if shim is None else shim
    applied_now: list[str] = []

    def say(msg: str) -> None:
        if not quiet:
            print(msg)

    with psycopg.connect(database_url or settings.database_url, autocommit=True) as conn:
        conn.execute("select pg_advisory_lock(%s)", (_LOCK_ID,))
        try:
            if use_shim:
                for path in migration_files(SHIM_DIR):
                    conn.execute(path.read_text(encoding="utf-8"))
                    say(f"shim     {path.name}")

            conn.execute(
                """
                create table if not exists public.schema_migrations (
                  version    text primary key,
                  checksum   text not null,
                  applied_at timestamptz not null default now()
                )
                """
            )
            done = {
                row[0]: row[1]
                for row in conn.execute("select version, checksum from public.schema_migrations")
            }

            for path in migration_files(migrations_dir):
                version, sql = path.stem, path.read_text(encoding="utf-8")
                checksum = _checksum(sql)
                if version in done:
                    if done[version] != checksum:
                        raise MigrationError(
                            f"{path.name} changed after it was applied. "
                            "Write a new migration instead (or reset your local DB)."
                        )
                    continue
                with conn.transaction():
                    conn.execute(sql)
                    conn.execute(
                        "insert into public.schema_migrations (version, checksum) values (%s, %s)",
                        (version, checksum),
                    )
                applied_now.append(version)
                say(f"applied  {path.name}")
        finally:
            conn.execute("select pg_advisory_unlock(%s)", (_LOCK_ID,))

    say(f"migrations up to date ({len(applied_now)} applied now)")
    return applied_now


def current_version(conn: psycopg.Connection) -> str | None:
    row = conn.execute(
        "select version from public.schema_migrations order by version desc limit 1"
    ).fetchone()
    if row is None:
        return None
    return row["version"] if isinstance(row, dict) else row[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--no-shim", action="store_true", help="skip db/local (use on Supabase)")
    args = parser.parse_args(argv)
    try:
        run(args.database_url, shim=False if args.no_shim else None)
    except MigrationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
