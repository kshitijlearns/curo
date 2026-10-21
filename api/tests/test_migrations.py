import shutil
import uuid

import psycopg
import pytest
from psycopg.conninfo import make_conninfo

from curo.db import connect, creator_session
from curo.db import migrate as migrations

pytestmark = pytest.mark.db


def test_migrations_are_idempotent(database_url):
    assert migrations.run(database_url, shim=True, quiet=True) == []


def test_baseline_installs_pgvector_in_extensions_schema(database_url):
    with connect(database_url) as conn:
        row = conn.execute(
            "select n.nspname as schema from pg_extension e "
            "join pg_namespace n on n.oid = e.extnamespace where e.extname = 'vector'"
        ).fetchone()
        assert row["schema"] == "extensions"
        dist = conn.execute("select '[1,0]'::vector <=> '[0,1]'::vector as d").fetchone()["d"]
        assert dist == pytest.approx(1.0)


def test_auth_uid_reads_request_claims_like_supabase(db):
    user_id = uuid.uuid4()
    with creator_session(user_id) as conn:
        row = conn.execute("select auth.uid() as uid, current_user as role").fetchone()
    assert row["uid"] == user_id
    assert row["role"] == "authenticated"


def test_editing_an_applied_migration_is_refused(database_url, tmp_path):
    # A scratch database with a copy of the migrations we can edit.
    server_db = f"curo_mig_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(database_url, autocommit=True) as admin:
        admin.execute(f'create database "{server_db}"')
    url = make_conninfo(database_url, dbname=server_db)
    try:
        for path in migrations.migration_files():
            shutil.copy(path, tmp_path / path.name)
        migrations.run(url, shim=True, quiet=True, migrations_dir=tmp_path)
        first = sorted(tmp_path.glob("*.sql"))[0]
        first.write_text(first.read_text() + "\n-- edited\n")
        with pytest.raises(migrations.MigrationError):
            migrations.run(url, shim=True, quiet=True, migrations_dir=tmp_path)
    finally:
        with psycopg.connect(database_url, autocommit=True) as admin:
            admin.execute(f'drop database if exists "{server_db}" with (force)')
