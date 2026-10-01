"""Thread-safe in-memory payment provider implementation."""

from __future__ import annotations

import hashlib
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .models import ChargeRequest, ChargeResponse


class IdempotencyConflict(Exception):
    """Raised when a key is reused for a different logical charge."""


class UnknownScenario(Exception):
    """Raised when a non-validated caller bypasses request validation."""


@dataclass(frozen=True, slots=True)
class StoredCharge:
    fingerprint: str
    response: ChargeResponse


class InMemoryPaymentProvider:
    """Deterministic provider state with atomic idempotency handling.

    Terminal results (success or decline) are stored and replayed byte-for-
    byte at the DTO level.  A temporary failure represents a request that did
    not reach the processor and therefore is intentionally not stored as a
    charge; ``temporary_failure`` fails once per key and then succeeds on a
    retry.  ``temporary_failure_always`` is available when a test needs every
    attempt to remain retryable.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._charges: dict[str, StoredCharge] = {}
        self._attempts: dict[str, int] = {}
        self._request_fingerprints: dict[str, str] = {}

    @staticmethod
    def fingerprint(request: ChargeRequest) -> str:
        # Scenario is test control, rather than charge identity: a retry after
        # a temporary failure may use the default success scenario. All actual
        # charge parameters remain part of the identity.
        raw = "|".join(
            [
                str(request.amount_minor),
                request.currency,
                request.order_id or request.metadata.get("order_id", ""),
            ]
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def charge(
        self, idempotency_key: str, request: ChargeRequest
    ) -> tuple[str, ChargeResponse | None]:
        """Process a charge and return ``(outcome, response)``.

        ``outcome`` is one of ``succeeded``, ``declined``, or
        ``temporary_failure``.  The lock covers lookup, attempt counting, and
        terminal insertion so concurrent requests with the same key cannot
        create two charges.
        """

        with self._lock:
            fingerprint = self.fingerprint(request)
            known_fingerprint = self._request_fingerprints.get(idempotency_key)
            if known_fingerprint is not None and known_fingerprint != fingerprint:
                raise IdempotencyConflict(idempotency_key)
            self._request_fingerprints.setdefault(idempotency_key, fingerprint)

            if idempotency_key in self._charges:
                stored = self._charges[idempotency_key]
                return stored.response.status, stored.response

            attempts = self._attempts.get(idempotency_key, 0)
            self._attempts[idempotency_key] = attempts + 1

            if request.scenario == "temporary_failure_always":
                return "temporary_failure", None
            if request.scenario == "temporary_failure" and attempts == 0:
                return "temporary_failure", None
            if request.scenario not in {
                "success",
                "declined",
                "temporary_failure",
                "temporary_failure_always",
            }:
                raise UnknownScenario(request.scenario)

            status: str = "declined" if request.scenario == "declined" else "succeeded"
            provider_reference = f"ch_{uuid.uuid4().hex}"
            response = ChargeResponse(
                provider_charge_id=provider_reference,
                provider_reference=provider_reference,
                idempotency_key=idempotency_key,
                amount_minor=request.amount_minor,
                currency=request.currency,
                status=status,
                order_id=request.order_id or request.metadata.get("order_id"),
                created_at=datetime.now(UTC),
                failure_code="card_declined" if status == "declined" else None,
                failure_message=(
                    "The mock issuer declined this charge." if status == "declined" else None
                ),
            )
            self._charges[idempotency_key] = StoredCharge(fingerprint, response)
            return status, response

    def snapshot(self) -> dict[str, dict[str, Any]]:
        """Return a safe diagnostic snapshot (useful in tests, never required)."""

        with self._lock:
            return {
                key: stored.response.model_dump(mode="json")
                for key, stored in self._charges.items()
            }
