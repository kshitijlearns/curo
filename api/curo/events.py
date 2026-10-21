"""Product events: kept in ``public.events`` (the learning loop reads them) and sent to
product analytics through the Monitoring provider."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from curo import clock, providers


def record(conn, creator_id: UUID | str | None, name: str, props: dict[str, Any]) -> None:
    conn.execute(
        "insert into public.events (creator_id, name, props, created_at) values (%s, %s, %s, %s)",
        (creator_id, name, Jsonb(props), clock.now()),
    )
    providers.get_monitoring().capture_event(name, props, str(creator_id) if creator_id else None)
