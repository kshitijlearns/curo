"""Mock payments: every checkout completes at once (no money moves)."""

from __future__ import annotations

import uuid
from uuid import UUID

from .base import Checkout, Item, Paid, PaymentProvider


class MockPaymentProvider(PaymentProvider):
    name = "mock"

    def create_checkout(self, creator_id: UUID, item: Item) -> Checkout:
        return Checkout(status="completed", ref=f"mock_{item}_{uuid.uuid4().hex[:12]}")

    def handle_webhook(self, body: bytes, headers: dict[str, str]) -> Paid | None:
        return None  # nothing to confirm: checkouts complete immediately

    def cancel(self, creator_id: UUID, ref: str | None) -> None:
        return None
