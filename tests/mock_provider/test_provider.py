from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from mock_payment_provider import create_app
from mock_payment_provider.signing import sign_webhook_payload, verify_webhook_signature


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def charge_body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "amount_minor": 1250,
        "currency": "usd",
        "order_id": "order-123",
        "scenario": "success",
    }
    body.update(overrides)
    return body


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_success_charge_and_terminal_replay(client: TestClient) -> None:
    headers = {"Idempotency-Key": "payment-1"}
    first = client.post("/charges", json=charge_body(), headers=headers)
    replay = client.post("/charges", json=charge_body(), headers=headers)

    assert first.status_code == 201
    assert first.json()["status"] == "succeeded"
    assert first.json()["currency"] == "USD"
    assert replay.status_code == 201
    assert replay.json() == first.json()


def test_decline_is_a_replayed_terminal_outcome(client: TestClient) -> None:
    headers = {"Idempotency-Key": "payment-declined"}
    first = client.post("/charges", json=charge_body(scenario="declined"), headers=headers)
    replay = client.post("/charges", json=charge_body(scenario="declined"), headers=headers)

    assert first.status_code == 402
    assert first.json()["status"] == "declined"
    assert replay.status_code == 402
    assert replay.json() == first.json()


def test_temporary_failure_is_retryable_with_same_key(client: TestClient) -> None:
    headers = {"Idempotency-Key": "payment-retry"}
    failed = client.post(
        "/charges", json=charge_body(scenario="temporary_failure"), headers=headers
    )
    succeeded = client.post(
        "/charges", json=charge_body(scenario="temporary_failure"), headers=headers
    )

    assert failed.status_code == 503
    assert failed.json()["error"]["retryable"] is True
    assert succeeded.status_code == 201
    assert succeeded.json()["status"] == "succeeded"


def test_temporary_retry_with_changed_amount_is_conflict(client: TestClient) -> None:
    headers = {"Idempotency-Key": "payment-retry-conflict"}
    assert (
        client.post(
            "/charges", json=charge_body(scenario="temporary_failure"), headers=headers
        ).status_code
        == 503
    )
    conflict = client.post("/charges", json=charge_body(amount_minor=1300), headers=headers)

    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_key_reused"


def test_same_key_with_different_parameters_is_conflict(client: TestClient) -> None:
    headers = {"Idempotency-Key": "payment-conflict"}
    assert client.post("/charges", json=charge_body(), headers=headers).status_code == 201
    conflict = client.post("/charges", json=charge_body(amount_minor=1300), headers=headers)

    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_key_reused"


def test_key_is_required(client: TestClient) -> None:
    response = client.post("/charges", json=charge_body())
    assert response.status_code == 400


def test_json_idempotency_fallback_and_metadata_order_id(client: TestClient) -> None:
    body = charge_body(
        idempotency_key="json-key",
        order_id=None,
        metadata={"order_id": "order-from-metadata"},
    )
    response = client.post("/charges", json=body)

    assert response.status_code == 201
    assert response.json()["idempotency_key"] == "json-key"
    assert response.json()["provider_reference"] == response.json()["provider_charge_id"]
    assert response.json()["order_id"] == "order-from-metadata"


def test_hmac_signing_uses_exact_payload() -> None:
    payload = json.dumps({"event_id": "evt-1", "type": "payment.succeeded"}, separators=(",", ":"))
    signature = sign_webhook_payload(payload, "local-webhook-secret")

    assert verify_webhook_signature(payload, signature, "local-webhook-secret")
    assert not verify_webhook_signature(payload + " ", signature, "local-webhook-secret")
