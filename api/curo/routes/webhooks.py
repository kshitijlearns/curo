"""POST /v1/webhooks/apify — Apify reports a finished run.

Checked against APIFY_WEBHOOK_SECRET and recorded. TODO (with the Apify provider): resume
the waiting collection job with the run's dataset.
"""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Header, HTTPException, Request, status
from psycopg.types.json import Jsonb

from curo.config import get_settings
from curo.db import service_connection

router = APIRouter(prefix="/v1/webhooks", tags=["system"])


@router.post("/apify", status_code=status.HTTP_202_ACCEPTED)
async def apify_webhook(
    request: Request, x_apify_webhook_secret: str | None = Header(default=None)
) -> dict:
    secret = get_settings().apify_webhook_secret
    if not secret or not hmac.compare_digest(secret, x_apify_webhook_secret or ""):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bad webhook secret")
    body = await request.json()
    with service_connection() as conn:
        conn.execute(
            "insert into public.events (name, props) values ('apify_webhook', %s)", (Jsonb(body),)
        )
    return {"accepted": True}
