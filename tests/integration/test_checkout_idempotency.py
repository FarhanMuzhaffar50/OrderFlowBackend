import uuid

import pytest

from app.core.security import hash_password
from app.db.models import Cart, CartItem, Inventory, Product, User
from app.db.session import SessionLocal
from app.orders.service import checkout

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_duplicate_checkout_returns_same_order():
    async with SessionLocal() as session:
        user = User(
            email=f"idem-{uuid.uuid4()}@example.com", password_hash=hash_password("password-long")
        )
        product = Product(sku=f"IDEM-{uuid.uuid4()}", name="Idempotent item", unit_price_minor=750)
        session.add_all([user, product])
        await session.flush()
        cart = Cart(user_id=user.id)
        session.add(cart)
        session.add(Inventory(product_id=product.id, available_quantity=2))
        await session.flush()
        session.add(CartItem(cart_id=cart.id, product_id=product.id, quantity=1))
        await session.commit()
        user_id = user.id
    async with SessionLocal() as session:
        first = await checkout(session, user_id, "same-key")
    async with SessionLocal() as session:
        second = await checkout(session, user_id, "same-key")
    assert first.id == second.id
