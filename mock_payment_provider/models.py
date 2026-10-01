"""HTTP DTOs for the mock payment provider."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Scenario = Literal["success", "declined", "temporary_failure", "temporary_failure_always"]
ChargeStatus = Literal["succeeded", "declined"]


class ChargeRequest(BaseModel):
    """A charge request.

    ``scenario`` exists solely for deterministic local tests and is not meant
    to model a real processor's public API.  ``order_id`` is an opaque caller
    reference and is echoed in the response.
    """

    amount_minor: int = Field(gt=0, description="Amount in the smallest currency unit")
    currency: str = Field(default="USD", min_length=3, max_length=3)
    order_id: str | None = Field(default=None, max_length=128)
    # The header is canonical, but accepting these fields keeps the service
    # convenient for simple local workers that serialize metadata as JSON.
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=255)
    metadata: dict[str, str] = Field(default_factory=dict)
    scenario: Scenario = "success"

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class ChargeResponse(BaseModel):
    provider_charge_id: str
    # Compatibility name used by the ordering application's payment worker.
    provider_reference: str
    idempotency_key: str
    amount_minor: int
    currency: str
    status: ChargeStatus
    order_id: str | None = None
    created_at: datetime
    failure_code: str | None = None
    failure_message: str | None = None


class ProviderErrorBody(BaseModel):
    code: str
    message: str
    retryable: bool = False


class ProviderError(BaseModel):
    error: ProviderErrorBody


class WebhookEvent(BaseModel):
    """Canonical event shape callers can sign and deliver to the app."""

    event_id: str
    event_type: Literal["payment.succeeded", "payment.declined"]
    provider_charge_id: str
    idempotency_key: str
    amount_minor: int
    currency: str
    order_id: str | None = None
    created_at: datetime
