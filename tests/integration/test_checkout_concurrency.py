import asyncio
import uuid

import pytest
from sqlalchemy import select

from app.core.exceptions import AppError
from app.core.security import hash_password
from app.db.models import Cart, CartItem, Inventory, Product, Role, User
from app.db.session import SessionLocal
from app.orders.service import checkout

pytestmark = [pytest.mark.integration, pytest.mark.concurrency]


async def _customer_with_cart(product_id: uuid.UUID) -> uuid.UUID:
    async with SessionLocal() as session:
        user = User(
            email=f"race-{uuid.uuid4()}@example.com",
            password_hash=hash_password("password-long"),
            role=Role.CUSTOMER,
        )
        session.add(user)
        await session.flush()
        cart = Cart(user_id=user.id)
        session.add(cart)
        await session.flush()
        session.add(CartItem(cart_id=cart.id, product_id=product_id, quantity=1))
        await session.commit()
        return user.id


async def _attempt(user_id: uuid.UUID):
    async with SessionLocal() as session:
        try:
            return await checkout(session, user_id, f"race-{uuid.uuid4()}")
        except AppError as exc:
            await session.rollback()
            return exc


@pytest.mark.asyncio
async def test_two_customers_cannot_buy_last_unit():
    async with SessionLocal() as session:
        product = Product(
            sku=f"RACE-{uuid.uuid4()}", name="Last item", unit_price_minor=1000, active=True
        )
        session.add(product)
        await session.flush()
        session.add(Inventory(product_id=product.id, available_quantity=1, reserved_quantity=0))
        await session.commit()
        product_id = product.id
    users = await asyncio.gather(_customer_with_cart(product_id), _customer_with_cart(product_id))
    results = await asyncio.gather(*(_attempt(user_id) for user_id in users))
    assert sum(not isinstance(result, AppError) for result in results) == 1
    errors = [result for result in results if isinstance(result, AppError)]
    assert errors[0].code == "out_of_stock"
    async with SessionLocal() as session:
        inventory = await session.scalar(
            select(Inventory).where(Inventory.product_id == product_id)
        )
        assert inventory.available_quantity == 0
        assert inventory.reserved_quantity == 1
