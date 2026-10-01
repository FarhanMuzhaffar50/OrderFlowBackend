"""FastAPI application for the standalone mock payment provider."""

from __future__ import annotations

from typing import Annotated

from fastapi import FastAPI, Header, HTTPException, status
from fastapi.responses import JSONResponse

from .config import ProviderSettings
from .models import ChargeRequest, ChargeResponse, ProviderError, ProviderErrorBody
from .service import IdempotencyConflict, InMemoryPaymentProvider


def create_app(
    *, provider: InMemoryPaymentProvider | None = None, settings: ProviderSettings | None = None
) -> FastAPI:
    """Create an isolated provider app.

    Dependency injection here keeps tests independent and ensures each app
    instance has its own idempotency store.  The module-level ``app`` is the
    convenient ASGI entry point for ``uvicorn mock_payment_provider:app``.
    """

    payment_provider = provider or InMemoryPaymentProvider()
    provider_settings = settings or ProviderSettings.from_env()
    api = FastAPI(title="OrderFlow Mock Payment Provider", version="1.0.0")

    @api.get("/health", tags=["ops"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.post(
        "/charges",
        response_model=ChargeResponse,
        responses={
            402: {"model": ChargeResponse, "description": "Charge declined"},
            409: {"model": ProviderError, "description": "Idempotency key conflict"},
            503: {"model": ProviderError, "description": "Retryable provider failure"},
        },
        status_code=status.HTTP_201_CREATED,
        tags=["payments"],
    )
    def create_charge(
        request: ChargeRequest,
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> ChargeResponse | JSONResponse:
        # The header is the public contract. The JSON fallback is useful for
        # lightweight local workers and goes through the same atomic store.
        idempotency_key = idempotency_key or request.idempotency_key
        if not idempotency_key or not idempotency_key.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Idempotency-Key header is required",
            )
        key = idempotency_key.strip()
        try:
            outcome, response = payment_provider.charge(key, request)
        except IdempotencyConflict:
            body = ProviderError(
                error=ProviderErrorBody(
                    code="idempotency_key_reused",
                    message=(
                        "The idempotency key was already used with different charge parameters."
                    ),
                )
            )
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content=body.model_dump(mode="json"),
            )

        if outcome == "temporary_failure":
            body = ProviderError(
                error=ProviderErrorBody(
                    code="provider_temporary_failure",
                    message=(
                        "The mock provider is temporarily unavailable; retry with the same key."
                    ),
                    retryable=True,
                )
            )
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=body.model_dump(mode="json"),
            )

        assert response is not None
        if outcome == "declined":
            return JSONResponse(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                content=response.model_dump(mode="json"),
            )
        return response

    # Keep settings reachable for integrations/diagnostics without adding a
    # public secret endpoint.  This also makes the HMAC configuration explicit
    # to code embedding the app while avoiding accidental secret exposure.
    api.state.provider_settings = provider_settings
    api.state.payment_provider = payment_provider
    return api


app = create_app()
