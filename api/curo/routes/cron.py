"""POST /v1/cron/tick: the scheduler, for a host cron (Vercel Cron later; DECISIONS D200).

Enqueues whatever is due. Needs ``Authorization: Bearer <CRON_SECRET>``; with no secret set
it is off.
"""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Header, HTTPException, status

from curo.config import get_settings

router = APIRouter(tags=["system"])


@router.post("/v1/cron/tick")
def cron_tick(authorization: str = Header("")) -> dict:
    from curo.jobs.scheduler import tick

    secret = get_settings().cron_secret
    if not secret or not hmac.compare_digest(authorization, f"Bearer {secret}"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not allowed")
    return {"queued": tick()}
