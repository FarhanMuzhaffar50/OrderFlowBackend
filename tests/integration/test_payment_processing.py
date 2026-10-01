import uuid

import httpx
import pytest

from app.core.security import hash_password
from app.db.models import Cart, CartItem, Inventory, Order, Payment, PaymentStatus, Product, User
from app.db.session import SessionLocal
from app.orders.service import checkout
from app.tasks import _process_payment

pytestmark = pytest.mark.integration


class FakeClient:
    def __init__(self, response: httpx.Response, **_):
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def post(self, *_args, **_kwargs):
        return self.response


async def pending_payment() -> tuple[uuid.UUID, uuid.UUID]:
    async with SessionLocal() as session:
        user = User(
            email=f"pay-{uuid.uuid4()}@example.com", password_hash=hash_password("password-long")
        )
        product = Product(sku=f"PAY-{uuid.uuid4()}", name="Payment item", unit_price_minor=500)
        session.add_all([user, product])
        await session.flush()
        cart = Cart(user_id=user.id)
        session.add(cart)
        session.add(Inventory(product_id=product.id, available_quantity=1))
        await session.flush()
        session.add(CartItem(cart_id=cart.id, product_id=product.id, quantity=1))
        await session.commit()
        user_id, product_id = user.id, product.id
    async with SessionLocal() as session:
        order = await checkout(session, user_id, f"payment-{uuid.uuid4()}")
        return order.payment.id, product_id


@pytest.mark.asyncio
async def test_duplicate_payment_processing_does_not_charge_again(monkeypatch):
    payment_id, _ = await pending_payment()
    calls = 0
    response = httpx.Response(
        201,
        json={"status": "succeeded", "provider_charge_id": f"ch_{uuid.uuid4()}"},
        request=httpx.Request("POST", "http://provider/charges"),
    )

    def client_factory(**kwargs):
        nonlocal calls
        calls += 1
        return FakeClient(response, **kwargs)

    monkeypatch.setattr("app.tasks.httpx.AsyncClient", client_factory)
    await _process_payment(payment_id)
    await _process_payment(payment_id)
    assert calls == 1
    async with SessionLocal() as session:
        payment = await session.get(Payment, payment_id)
        assert payment.status == PaymentStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_decline_releases_reserved_inventory(monkeypatch):
    payment_id, product_id = await pending_payment()
    response = httpx.Response(
        402,
        json={"status": "declined", "provider_charge_id": f"ch_{uuid.uuid4()}"},
        request=httpx.Request("POST", "http://provider/charges"),
    )
    monkeypatch.setattr(
        "app.tasks.httpx.AsyncClient", lambda **kwargs: FakeClient(response, **kwargs)
    )
    await _process_payment(payment_id)
    async with SessionLocal() as session:
        payment = await session.get(Payment, payment_id)
        inventory = await session.get(Inventory, product_id)
        order = await session.get(Order, payment.order_id)
        assert payment.status == PaymentStatus.FAILED
        assert order.status.value == "PAYMENT_FAILED"
        assert inventory.available_quantity == 1
        assert inventory.reserved_quantity == 0
