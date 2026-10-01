import hashlib
import hmac
import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import Inventory, Payment, Product
from app.db.session import SessionLocal
from app.main import app

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_customer_api_flow_and_duplicate_webhook():
    async with SessionLocal() as session:
        product = Product(
            sku=f"API-{uuid.uuid4()}", name="API product", unit_price_minor=1250, active=True
        )
        session.add(product)
        await session.flush()
        session.add(Inventory(product_id=product.id, available_quantity=3))
        await session.commit()
        product_id = product.id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        register = await client.post(
            "/auth/register",
            json={"email": f"api-{uuid.uuid4()}@example.com", "password": "StrongPassword123!"},
        )
        assert register.status_code == 201
        headers = {"Authorization": f"Bearer {register.json()['access_token']}"}
        added = await client.post(
            "/cart/items", json={"product_id": str(product_id), "quantity": 2}, headers=headers
        )
        assert added.status_code == 200
        assert added.json()["total_amount_minor"] == 2500

        checkout_headers = {**headers, "Idempotency-Key": "api-flow-key"}
        first = await client.post("/orders/checkout", headers=checkout_headers)
        second = await client.post("/orders/checkout", headers=checkout_headers)
        assert first.status_code == second.status_code == 201
        assert first.json()["id"] == second.json()["id"]
        order_id = uuid.UUID(first.json()["id"])

        own_order = await client.get(f"/orders/{order_id}", headers=headers)
        assert own_order.status_code == 200
        assert own_order.json()["status"] == "PAYMENT_PENDING"

        async with SessionLocal() as session:
            payment = await session.scalar(select(Payment).where(Payment.order_id == order_id))
            assert payment is not None
            payment_key = payment.idempotency_key

        event = {
            "event_id": f"evt-{uuid.uuid4()}",
            "provider_reference": f"ch-{uuid.uuid4()}",
            "idempotency_key": payment_key,
            "status": "succeeded",
        }
        raw = json.dumps(event, separators=(",", ":")).encode()
        signature = hmac.new(
            get_settings().webhook_secret.encode(), raw, hashlib.sha256
        ).hexdigest()
        webhook_headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
        }
        delivered = await client.post("/webhooks/payments", content=raw, headers=webhook_headers)
        duplicate = await client.post("/webhooks/payments", content=raw, headers=webhook_headers)
        assert delivered.status_code == duplicate.status_code == 204

        paid = await client.get(f"/orders/{order_id}", headers=headers)
        assert paid.json()["status"] == "PAID"
