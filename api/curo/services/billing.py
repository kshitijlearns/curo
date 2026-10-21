"""Plans, credits and usage (PLAN_V2 §4.6). The server enforces every limit.

* Plans: Free (2 projects, 2 simulations, 10 Ask Curo messages a month) and Pro ($30: 10, 10
  and 100). Amounts come from settings so they can change without a migration.
* Credits live in an append-only ledger. Each period the plan grants its credits; they expire
  at the period's end. Top-ups never expire. A spend draws on the plan's credits first, then
  on top-ups, and records which (``reason`` = "plan" | "topup"), so the balance is exact.
* A spend is recorded once per thing (``ref_id``): a retried request is never charged twice.
* Revisions: up to PROJECT_REVISIONS per project; agent chat: AGENT_CHAT_MESSAGES per
  simulation (counted on the simulation, routes/simulations.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from curo.config import get_settings

RESOURCES = ("project", "simulation", "chat")


class OutOfCredits(Exception):
    """Answered as 402 {code: "out_of_credits", resource, plan}."""

    def __init__(self, resource: str, plan: str, message: str | None = None):
        self.resource, self.plan = resource, plan
        names = {"project": "projects", "simulation": "simulations", "chat": "Ask Curo messages"}
        self.message = message or (
            f"You've used this month's {names[resource]} on the {plan.title()} plan."
        )
        super().__init__(self.message)


class RevisionLimit(Exception):
    def __init__(self, limit: int):
        self.limit = limit
        super().__init__(f"This project has used its {limit} revisions.")


def allowance(plan: str) -> dict[str, int]:
    s = get_settings()
    if plan == "pro":
        return {"project": s.pro_projects, "simulation": s.pro_simulations, "chat": s.pro_chat}
    return {"project": s.free_projects, "simulation": s.free_simulations, "chat": s.free_chat}


def month_window(now: datetime) -> tuple[datetime, datetime]:
    now = now.astimezone(UTC)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = (
        start.replace(year=start.year + 1, month=1)
        if start.month == 12
        else start.replace(month=start.month + 1)
    )
    return start, end


@dataclass
class Subscription:
    plan: str
    status: str
    period_start: datetime
    period_end: datetime


def subscription(conn, creator_id: UUID, now: datetime) -> Subscription:
    """The creator's subscription for the current period, starting Free and rolling monthly;
    each new period's grants are written once."""
    row = conn.execute(
        "select * from public.subscriptions where creator_id = %s", (creator_id,)
    ).fetchone()
    if row is None:
        start, end = month_window(now)
        conn.execute(
            """
            insert into public.subscriptions (creator_id, plan, period_start, period_end)
            values (%s, 'free', %s, %s) on conflict (creator_id) do nothing
            """,
            (creator_id, start, end),
        )
        row = conn.execute(
            "select * from public.subscriptions where creator_id = %s", (creator_id,)
        ).fetchone()
    if row["period_end"] <= now:
        start, end = month_window(now)
        plan = row["plan"] if row["status"] == "active" else "free"
        conn.execute(
            """
            update public.subscriptions set plan = %s, status = 'active', period_start = %s,
                   period_end = %s where creator_id = %s
            """,
            (plan, start, end, creator_id),
        )
        row = conn.execute(
            "select * from public.subscriptions where creator_id = %s", (creator_id,)
        ).fetchone()
    sub = Subscription(row["plan"], row["status"], row["period_start"], row["period_end"])
    grant_period(conn, creator_id, sub)
    return sub


def grant_period(conn, creator_id: UUID, sub: Subscription) -> None:
    for resource, amount in allowance(sub.plan).items():
        if amount <= 0:
            continue
        conn.execute(
            """
            insert into public.credit_ledger
              (creator_id, kind, resource, amount, reason, ref_id, period_end, created_at)
            values (%s, 'grant', %s, %s, %s, %s, %s, %s)
            on conflict do nothing
            """,
            (
                creator_id,
                resource,
                amount,
                f"{sub.plan} plan",
                f"grant:{sub.plan}:{sub.period_start:%Y-%m-%d}:{resource}",
                sub.period_end,
                sub.period_start,
            ),
        )


@dataclass
class Balance:
    resource: str
    plan_left: int
    plan_total: int
    topup_left: int

    @property
    def left(self) -> int:
        return self.plan_left + self.topup_left


def balance(conn, creator_id: UUID, resource: str, sub: Subscription) -> Balance:
    rows = conn.execute(
        """
        select id, kind, reason, amount, period_end, created_at from public.credit_ledger
         where creator_id = %s and resource = %s
        """,
        (creator_id, resource),
    ).fetchall()
    grants = [
        r
        for r in rows
        if r["kind"] == "grant"
        and r["period_end"] == sub.period_end
        and r["created_at"] >= sub.period_start
    ]
    granted = sum(r["amount"] for r in grants)
    # Plan spends since this period's grant (ledger order, so a mid-month upgrade starts clean).
    since = min((r["id"] for r in grants), default=None)
    plan_spent = sum(
        r["amount"] * (1 if r["kind"] == "spend" else -1)
        for r in rows
        if since is not None
        and r["id"] > since
        and r["kind"] in ("spend", "refund")
        and r["reason"] == "plan"
    )
    topups = sum(r["amount"] for r in rows if r["kind"] == "topup")
    topup_spent = sum(
        r["amount"] * (1 if r["kind"] == "spend" else -1)
        for r in rows
        if r["kind"] in ("spend", "refund") and r["reason"] == "topup"
    )
    return Balance(resource, max(0, granted - plan_spent), granted, max(0, topups - topup_spent))


def spend(conn, creator_id: UUID, resource: str, ref_id: str, now: datetime) -> Balance:
    """One credit for ``ref_id`` (once). Raises OutOfCredits when none is left."""
    sub = subscription(conn, creator_id, now)
    done = conn.execute(
        """
        select 1 from public.credit_ledger
         where creator_id = %s and kind = 'spend' and resource = %s and ref_id = %s
        """,
        (creator_id, resource, ref_id),
    ).fetchone()
    b = balance(conn, creator_id, resource, sub)
    if done:
        return b
    if b.left <= 0:
        raise OutOfCredits(resource, sub.plan)
    pool = "plan" if b.plan_left > 0 else "topup"
    conn.execute(
        """
        insert into public.credit_ledger (creator_id, kind, resource, amount, reason, ref_id, created_at)
        values (%s, 'spend', %s, 1, %s, %s, %s)
        """,
        (creator_id, resource, pool, ref_id, now),
    )
    return balance(conn, creator_id, resource, sub)


def require(conn, creator_id: UUID, resource: str, now: datetime) -> Balance:
    """Raise OutOfCredits unless one credit of ``resource`` is left (spend it after)."""
    sub = subscription(conn, creator_id, now)
    b = balance(conn, creator_id, resource, sub)
    if b.left <= 0:
        raise OutOfCredits(resource, sub.plan)
    return b


def refund(conn, creator_id: UUID, resource: str, ref_id: str, now: datetime) -> None:
    """Give back a spend whose work failed before it produced anything."""
    row = conn.execute(
        """
        select reason from public.credit_ledger
         where creator_id = %s and kind = 'spend' and resource = %s and ref_id = %s
        """,
        (creator_id, resource, ref_id),
    ).fetchone()
    if row is None:
        return
    conn.execute(
        """
        insert into public.credit_ledger (creator_id, kind, resource, amount, reason, ref_id, created_at)
        values (%s, 'refund', %s, 1, %s, %s, %s) on conflict do nothing
        """,
        (creator_id, resource, row["reason"], ref_id, now),
    )


def topup(conn, creator_id: UUID, resource: str, amount: int, ref_id: str, now: datetime) -> None:
    conn.execute(
        """
        insert into public.credit_ledger (creator_id, kind, resource, amount, reason, ref_id, created_at)
        values (%s, 'topup', %s, %s, 'top-up', %s, %s) on conflict do nothing
        """,
        (creator_id, resource, amount, ref_id, now),
    )


def set_plan(conn, creator_id: UUID, plan: str, provider: str, ref: str | None, now: datetime):
    """Start (or end) Pro now: a fresh period with the new plan's grants."""
    _start, end = month_window(now)
    subscription(conn, creator_id, now)
    conn.execute(
        """
        update public.subscriptions set plan = %s, status = 'active', provider = %s,
               provider_ref = %s, period_start = %s, period_end = %s where creator_id = %s
        """,
        (plan, provider, ref, now, end, creator_id),
    )
    grant_period(conn, creator_id, Subscription(plan, "active", now, end))


def revise(conn, project_id: UUID) -> int:
    """Count one revision of a project; raises RevisionLimit past PROJECT_REVISIONS."""
    limit = get_settings().project_revisions
    row = conn.execute(
        "select revisions from public.projects where id = %s for update", (project_id,)
    ).fetchone()
    used = row["revisions"] if row else 0
    if used >= limit:
        raise RevisionLimit(limit)
    conn.execute(
        "update public.projects set revisions = revisions + 1 where id = %s", (project_id,)
    )
    return used + 1


# ------------------------------------------------------------------ usage and costs

# USD per million tokens (input, output). Estimates for the cost page, not a bill.
PRICES = {
    "claude-sonnet-5-5": (3.0, 15.0),
    "claude-haiku-5-5": (0.1, 0.5),
    "gemini-3.6-flash": (0.3, 2.5),
    "gemini-embedding-2": (0.15, 0.0),
    # The mocks are priced as the models they stand in for: what this would cost live.
    "mock-main-v1": (3.0, 15.0),
    "mock-fast-v1": (0.1, 0.5),
    "mock-agents-v1": (0.1, 0.5),
    "mock-video-v1": (0.3, 2.5),
}
APIFY_PER_1K_RESULTS = 2.3


def cost_usd(model: str | None, tokens_in: int, tokens_out: int, results: int = 0) -> float:
    pin, pout = PRICES.get(model or "", (0.0, 0.0))
    return round(
        (tokens_in * pin + tokens_out * pout) / 1_000_000 + results * APIFY_PER_1K_RESULTS / 1000,
        6,
    )
