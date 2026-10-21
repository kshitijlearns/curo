"""Local sign-in stub (AUTH_PROVIDER=local). With Supabase Auth, the app signs in with
supabase-js instead and these routes aren't mounted."""

from __future__ import annotations

import logging

from fastapi import APIRouter

from curo.auth import issue_token, request_code, verify_code
from curo.config import get_settings
from curo.schemas.api import OtpRequest, OtpSent, OtpVerify, Session

router = APIRouter(prefix="/v1/auth", tags=["auth"])
log = logging.getLogger("curo.auth")


@router.post("/otp", response_model=OtpSent)
def send_code(body: OtpRequest) -> OtpSent:
    """Send a 6-digit sign-in code. Locally there's no email service: the code is logged,
    and returned in development so the app can show it."""
    code = request_code(body.email)
    log.info("sign-in code for %s: %s", body.email, code)
    dev = get_settings().app_env in ("development", "test")
    return OtpSent(dev_code=code if dev else None)


@router.post("/verify", response_model=Session)
def verify(body: OtpVerify) -> Session:
    user = verify_code(body.email, body.code)
    token, ttl = issue_token(user.id, user.email)
    return Session(access_token=token, expires_in=ttl, user_id=user.id, email=user.email)
