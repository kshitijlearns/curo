"""Authentication.

The API accepts Supabase-format JWTs (HS256, ``aud=authenticated``, signed with
SUPABASE_JWT_SECRET) — the same tokens Supabase Auth issues, so nothing changes when real
Supabase is switched on. With AUTH_PROVIDER=local, a small email one-time-code stub issues
them (``/v1/auth/otp`` → ``/v1/auth/verify``).

Auth uses real time, not CURO's time-travel clock: tokens and codes must really expire.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from fastapi import Header, HTTPException, status

from curo.config import get_settings
from curo.db import service_connection

TOKEN_TTL = timedelta(days=30)
OTP_TTL = timedelta(minutes=10)
OTP_MAX_ATTEMPTS = 5
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class User:
    id: UUID
    email: str | None = None


def _secret() -> str:
    return get_settings().supabase_jwt_secret


def issue_token(user_id: UUID, email: str | None) -> tuple[str, int]:
    now = datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "email": email,
        "role": "authenticated",
        "aud": "authenticated",
        "iat": int(now.timestamp()),
        "exp": int((now + TOKEN_TTL).timestamp()),
    }
    return jwt.encode(claims, _secret(), algorithm="HS256"), int(TOKEN_TTL.total_seconds())


def verify_token(token: str) -> User:
    try:
        claims = jwt.decode(token, _secret(), algorithms=["HS256"], audience="authenticated")
        return User(UUID(claims["sub"]), claims.get("email"))
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session") from exc


def current_user(authorization: str | None = Header(default=None)) -> User:
    """FastAPI dependency: the signed-in user from ``Authorization: Bearer <jwt>``."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in first")
    user = verify_token(authorization.split(" ", 1)[1].strip())
    # A valid token for a deleted account (DELETE /v1/me) is no longer a session.
    with service_connection() as conn:
        exists = conn.execute("select 1 from auth.users where id = %s", (user.id,)).fetchone()
    if exists is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This account no longer exists")
    return user


# --------------------------------------------------------------------------- local OTP stub


def normalize_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not _EMAIL.match(email):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Enter a valid email address")
    return email


def _hash(email: str, code: str) -> str:
    return hmac.new(_secret().encode(), f"{email}:{code}".encode(), hashlib.sha256).hexdigest()


def request_code(email: str) -> str:
    """Create a 6-digit sign-in code (stored only as a keyed hash). Returns the code."""
    email = normalize_email(email)
    code = f"{secrets.randbelow(1_000_000):06d}"
    with service_connection() as conn:
        conn.execute(
            """
            insert into auth.local_otp_codes (email, code_hash, expires_at, attempts)
            values (%s, %s, %s, 0)
            on conflict (email) do update set code_hash = excluded.code_hash,
              expires_at = excluded.expires_at, attempts = 0
            """,
            (email, _hash(email, code), datetime.now(UTC) + OTP_TTL),
        )
    return code


def verify_code(email: str, code: str) -> User:
    """Check a sign-in code; create the user on first sign-in."""
    email = normalize_email(email)
    user = None
    # Decide inside the transaction, raise after it commits (so failed attempts are counted).
    with service_connection() as conn:
        row = conn.execute(
            "select code_hash, expires_at, attempts from auth.local_otp_codes where email = %s for update",
            (email,),
        ).fetchone()
        usable = (
            row is not None
            and row["expires_at"] >= datetime.now(UTC)
            and row["attempts"] < OTP_MAX_ATTEMPTS
        )
        if usable and hmac.compare_digest(row["code_hash"], _hash(email, (code or "").strip())):
            conn.execute("delete from auth.local_otp_codes where email = %s", (email,))
            user = conn.execute(
                """
                insert into auth.users (email, last_sign_in_at) values (%s, now())
                on conflict (email) do update set last_sign_in_at = now()
                returning id
                """,
                (email,),
            ).fetchone()
        elif usable:
            conn.execute(
                "update auth.local_otp_codes set attempts = attempts + 1 where email = %s", (email,)
            )
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "That code didn't work. Request a new one."
        )
    return User(user["id"], email)
