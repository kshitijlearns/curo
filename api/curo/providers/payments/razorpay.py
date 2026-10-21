"""Razorpay (subscriptions for Pro, orders for top-ups). Not implemented yet.

TODO (INTEGRATION.md "Payments"): create a Razorpay subscription for Pro and an order for
each top-up; verify webhook signatures with the webhook secret; map ``subscription.charged``
and ``payment.captured`` to ``Paid``; cancel with ``subscriptions.cancel``. A Stripe provider
would follow the same interface.
"""

from __future__ import annotations

from uuid import UUID

from .base import Checkout, Item, Paid, PaymentProvider

_TODO = "Razorpay payments not implemented yet: set PAYMENT_PROVIDER=mock (see INTEGRATION.md)"


class RazorpayPaymentProvider(PaymentProvider):
    name = "razorpay"

    def create_checkout(self, creator_id: UUID, item: Item) -> Checkout:
        raise NotImplementedError(_TODO)

    def handle_webhook(self, body: bytes, headers: dict[str, str]) -> Paid | None:
        raise NotImplementedError(_TODO)

    def cancel(self, creator_id: UUID, ref: str | None) -> None:
        raise NotImplementedError(_TODO)
