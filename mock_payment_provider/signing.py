"""Helpers for authenticating payment webhooks with HMAC-SHA256."""

from __future__ import annotations

import hashlib
import hmac


def sign_webhook_payload(payload: bytes | str, secret: str) -> str:
    """Return the lowercase hex HMAC-SHA256 signature for *payload*.

    The receiver can compare this value with a constant-time comparison.  The
    helper accepts both raw bytes and text so callers can sign the exact HTTP
    body they send.
    """

    body = payload.encode("utf-8") if isinstance(payload, str) else payload
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def verify_webhook_signature(payload: bytes | str, signature: str, secret: str) -> bool:
    """Verify a signature using constant-time comparison."""

    expected = sign_webhook_payload(payload, secret)
    return hmac.compare_digest(expected, signature.strip().lower())
