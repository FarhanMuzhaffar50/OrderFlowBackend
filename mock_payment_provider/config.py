"""Configuration for the standalone mock payment provider."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProviderSettings:
    """Runtime settings loaded from environment variables.

    ``MOCK_PAYMENT_WEBHOOK_SECRET`` is used by :func:`sign_webhook_payload`
    and is deliberately optional: the provider does not make outbound calls
    by default.  Applications that deliver webhook events should set it to a
    non-empty shared secret.
    """

    default_currency: str = "USD"
    webhook_secret: str = ""
    webhook_url: str | None = None

    @classmethod
    def from_env(cls) -> ProviderSettings:
        currency = os.getenv("MOCK_PAYMENT_DEFAULT_CURRENCY", "USD").strip().upper()
        if not currency:
            currency = "USD"
        secret = os.getenv("MOCK_PAYMENT_WEBHOOK_SECRET", "")
        webhook_url = os.getenv("MOCK_PAYMENT_WEBHOOK_URL") or None
        return cls(default_currency=currency, webhook_secret=secret, webhook_url=webhook_url)
