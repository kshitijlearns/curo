"""PaymentProvider (PLAN_V2 §4.6): checkout for Pro or a top-up, webhooks, cancel.

The provider answers what was bought; ``routes/billing.py`` grants it through the credit
ledger. Which provider runs is chosen by PAYMENT_PROVIDER in the provider factory only.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

Item = Literal["pro", "topup_project", "topup_simulation", "topup_chat"]


@dataclass
class Checkout:
    status: Literal["completed", "pending"]
    ref: str
    url: str | None = None  # where to pay, for a real provider


@dataclass
class Paid:
    """What a webhook confirms: the creator, the item and the provider's reference."""

    creator_id: UUID
    item: Item
    ref: str


class PaymentProvider(ABC):
    name = "abstract"

    @abstractmethod
    def create_checkout(self, creator_id: UUID, item: Item) -> Checkout: ...

    @abstractmethod
    def handle_webhook(self, body: bytes, headers: dict[str, str]) -> Paid | None: ...

    @abstractmethod
    def cancel(self, creator_id: UUID, ref: str | None) -> None: ...
