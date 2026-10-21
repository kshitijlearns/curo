"""Shared route dependencies."""

from __future__ import annotations

from collections.abc import Iterator

import psycopg
from fastapi import Depends, HTTPException, status

from curo import usage
from curo.auth import User, current_user
from curo.db import creator_session


def rls_conn(user: User = Depends(current_user)) -> Iterator[psycopg.Connection]:
    """A per-request transaction where Row Level Security applies as the signed-in user."""
    with creator_session(user.id) as conn:
        yield conn


def require_creator(conn: psycopg.Connection) -> dict:
    """The signed-in user's creator row, or 409 if they haven't entered a username yet."""
    row = conn.execute("select * from public.creators where user_id = auth.uid()").fetchone()
    if row is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Start onboarding with your Instagram username first"
        )
    usage.current_creator.set(row["id"])
    return row
