"""Plans, credits and costs (PLAN_V2 §4.6).

``GET /v1/billing`` is Settings → Plan: the plan, this period and what's left of each credit.
``POST /v1/billing/checkout`` buys Pro or a top-up through the PaymentProvider (the mock
completes at once); ``POST /v1/billing/cancel`` ends Pro at the period's end;
``POST /v1/billing/webhook/{provider}`` takes a real provider's confirmations.
``GET /v1/admin/costs`` is for admins only (ADMIN_EMAILS or ``creators.is_admin``).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from curo import clock, providers
from curo.auth import User, current_user
from curo.config import get_settings
from curo.db import service_connection
from curo.providers.payments.base import Item
from curo.routes.deps import require_creator, rls_conn
from curo.services import billing

router = APIRouter(tags=["billing"])

TOPUP_AMOUNT = {"topup_project": 1, "topup_simulation": 1, "topup_chat": 20}


class CreditOut(BaseModel):
    left: int
    plan_left: int
    plan_total: int
    topup_left: int


class PlanOut(BaseModel):
    key: str
    label: str
    price_usd: float
    projects: int
    simulations: int
    chat: int


class BillingOut(BaseModel):
    plan: str
    status: str
    period_start: datetime
    period_end: datetime
    credits: dict[str, CreditOut]
    plans: list[PlanOut]
    topup_price_usd: float
    topups: dict[str, int]
    revisions_per_project: int
    agent_messages_per_simulation: int


class CheckoutIn(BaseModel):
    item: Item


class CheckoutOut(BaseModel):
    status: str
    ref: str
    url: str | None = None
    billing: BillingOut


def _plans() -> list[PlanOut]:
    s = get_settings()
    out = []
    for key, label, price in (("free", "Free", 0.0), ("pro", "Pro", s.pro_price_usd)):
        a = billing.allowance(key)
        out.append(PlanOut(key=key, label=label, price_usd=price, projects=a["project"],
                           simulations=a["simulation"], chat=a["chat"]))  # fmt: skip
    return out


def billing_state(creator_id: UUID) -> BillingOut:
    now = clock.now()
    with service_connection() as conn:
        sub = billing.subscription(conn, creator_id, now)
        credits = {}
        for r in billing.RESOURCES:
            b = billing.balance(conn, creator_id, r, sub)
            credits[r] = CreditOut(
                left=b.left, plan_left=b.plan_left, plan_total=b.plan_total, topup_left=b.topup_left
            )
    s = get_settings()
    return BillingOut(
        plan=sub.plan,
        status=sub.status,
        period_start=sub.period_start,
        period_end=sub.period_end,
        credits=credits,
        plans=_plans(),
        topup_price_usd=s.topup_price_usd,
        topups=TOPUP_AMOUNT,
        revisions_per_project=s.project_revisions,
        agent_messages_per_simulation=s.agent_chat_messages,
    )


def _grant(creator_id: UUID, item: str, provider: str, ref: str) -> None:
    now = clock.now()
    with service_connection() as conn:
        if item == "pro":
            billing.set_plan(conn, creator_id, "pro", provider, ref, now)
        else:
            resource = item.removeprefix("topup_")
            billing.topup(conn, creator_id, resource, TOPUP_AMOUNT[item], ref, now)


@router.get("/v1/billing", response_model=BillingOut)
def get_billing(conn: psycopg.Connection = Depends(rls_conn)) -> BillingOut:
    creator = require_creator(conn)
    return billing_state(creator["id"])


@router.post("/v1/billing/checkout", response_model=CheckoutOut)
def checkout(body: CheckoutIn, conn: psycopg.Connection = Depends(rls_conn)) -> CheckoutOut:
    creator = require_creator(conn)
    payments = providers.get_payments()
    try:
        done = payments.create_checkout(creator["id"], body.item)
    except NotImplementedError as exc:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, str(exc)) from exc
    if done.status == "completed":
        _grant(creator["id"], body.item, payments.name, done.ref)
    return CheckoutOut(
        status=done.status, ref=done.ref, url=done.url, billing=billing_state(creator["id"])
    )


@router.post("/v1/billing/cancel", response_model=BillingOut)
def cancel(conn: psycopg.Connection = Depends(rls_conn)) -> BillingOut:
    """Pro stays until the period ends, then the plan is Free."""
    creator = require_creator(conn)
    with service_connection() as sc:
        row = sc.execute(
            "select provider_ref from public.subscriptions where creator_id = %s", (creator["id"],)
        ).fetchone()
        try:
            providers.get_payments().cancel(creator["id"], row["provider_ref"] if row else None)
        except NotImplementedError as exc:
            raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, str(exc)) from exc
        sc.execute(
            "update public.subscriptions set status = 'cancelled' where creator_id = %s",
            (creator["id"],),
        )
    return billing_state(creator["id"])


@router.post("/v1/billing/webhook/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def webhook(provider: str, request: Request) -> None:
    payments = providers.get_payments()
    if provider != payments.name:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown payment provider")
    try:
        paid = payments.handle_webhook(await request.body(), dict(request.headers))
    except NotImplementedError as exc:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, str(exc)) from exc
    if paid is not None:
        _grant(paid.creator_id, paid.item, payments.name, paid.ref)


# ---------------------------------------------------------------------- admin: costs


class CreatorCost(BaseModel):
    creator_id: UUID | None
    username: str | None
    cost_usd: float
    calls: int
    over_alert: bool


class FeatureCost(BaseModel):
    task: str | None
    provider: str
    cost_usd: float
    calls: int


class CostsOut(BaseModel):
    month: str
    total_usd: float
    alert_usd: float
    creators: list[CreatorCost]
    features: list[FeatureCost]


def _is_admin(user: User) -> bool:
    admins = {e.strip().lower() for e in get_settings().admin_emails.split(",") if e.strip()}
    if user.email and user.email.lower() in admins:
        return True
    with service_connection() as conn:
        row = conn.execute(
            "select is_admin from public.creators where user_id = %s", (user.id,)
        ).fetchone()
    return bool(row and row["is_admin"])


@router.get("/v1/admin/costs", response_model=CostsOut)
def admin_costs(user: User = Depends(current_user)) -> CostsOut:
    if not _is_admin(user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    start, end = billing.month_window(clock.now())
    alert = get_settings().cost_alert_usd
    with service_connection() as conn:
        creators = conn.execute(
            """
            select u.creator_id, a.username, sum(u.cost_usd) as cost, count(*) as calls
              from public.usage_ledger u
              left join public.creators c on c.id = u.creator_id
              left join public.accounts a on a.id = c.account_id
             where u.created_at >= %s and u.created_at < %s
             group by u.creator_id, a.username order by cost desc nulls last
            """,
            (start, end),
        ).fetchall()
        features = conn.execute(
            """
            select task, provider, sum(cost_usd) as cost, count(*) as calls
              from public.usage_ledger where created_at >= %s and created_at < %s
             group by task, provider order by cost desc nulls last, task
            """,
            (start, end),
        ).fetchall()
    return CostsOut(
        month=f"{start:%Y-%m}",
        total_usd=round(sum(float(c["cost"] or 0) for c in creators), 4),
        alert_usd=alert,
        creators=[
            CreatorCost(
                creator_id=c["creator_id"],
                username=c["username"],
                cost_usd=round(float(c["cost"] or 0), 4),
                calls=c["calls"],
                over_alert=float(c["cost"] or 0) > alert,
            )
            for c in creators
        ],
        features=[
            FeatureCost(
                task=f["task"],
                provider=f["provider"],
                cost_usd=round(float(f["cost"] or 0), 4),
                calls=f["calls"],
            )
            for f in features
        ],
    )
