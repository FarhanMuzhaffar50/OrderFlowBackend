import uuid

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppError
from app.db.models import (
    Cart,
    CartItem,
    IdempotencyRecord,
    Inventory,
    Order,
    OrderItem,
    OrderStatus,
    OutboxEvent,
    Payment,
    PaymentStatus,
)
from app.orders.state_machine import transition_order


async def checkout(session: AsyncSession, user_id: uuid.UUID, idempotency_key: str) -> Order:
    # Serializes same-user/key attempts even before the unique row exists.
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"{user_id}:{idempotency_key}"},
    )
    existing = await session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.user_id == user_id, IdempotencyRecord.key == idempotency_key
        )
    )
    if existing and existing.order_id:
        return await _load_order(session, existing.order_id)

    cart = await session.scalar(
        select(Cart)
        .where(Cart.user_id == user_id)
        .options(selectinload(Cart.items).selectinload(CartItem.product))
    )
    if cart is None or not cart.items:
        raise AppError("empty_cart", "Cart is empty", 409)

    product_ids = sorted((item.product_id for item in cart.items), key=str)
    inventories = list(
        (
            await session.scalars(
                select(Inventory)
                .where(Inventory.product_id.in_(product_ids))
                .order_by(Inventory.product_id)
                .with_for_update()
            )
        ).all()
    )
    inventory_by_id = {row.product_id: row for row in inventories}
    if len(inventories) != len(product_ids):
        raise AppError("inventory_missing", "Inventory record missing", 409)

    for item in cart.items:
        if not item.product.active:
            raise AppError("product_unavailable", f"Product {item.product.sku} is unavailable", 409)
        if inventory_by_id[item.product_id].available_quantity < item.quantity:
            raise AppError("out_of_stock", f"Insufficient stock for {item.product.sku}", 409)

    order = Order(user_id=user_id, status=OrderStatus.CREATED, total_amount_minor=0)
    session.add(order)
    await session.flush()
    total = 0
    for item in cart.items:
        inventory = inventory_by_id[item.product_id]
        inventory.available_quantity -= item.quantity
        inventory.reserved_quantity += item.quantity
        line_total = item.product.unit_price_minor * item.quantity
        total += line_total
        session.add(
            OrderItem(
                order_id=order.id,
                product_id=item.product_id,
                sku=item.product.sku,
                product_name=item.product.name,
                unit_price_minor=item.product.unit_price_minor,
                quantity=item.quantity,
                line_total_minor=line_total,
            )
        )
    order.total_amount_minor = total
    transition_order(order, OrderStatus.INVENTORY_RESERVED)
    transition_order(order, OrderStatus.PAYMENT_PENDING)
    payment = Payment(
        order_id=order.id,
        status=PaymentStatus.PENDING,
        amount_minor=total,
        idempotency_key=f"payment:{order.id}",
    )
    session.add(payment)
    session.add(
        IdempotencyRecord(
            user_id=user_id, key=idempotency_key, request_hash="checkout-v1", order_id=order.id
        )
    )
    session.add(
        OutboxEvent(
            event_type="payment.requested",
            aggregate_id=order.id,
            payload={"order_id": str(order.id)},
        )
    )
    await session.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
    await session.commit()
    return await _load_order(session, order.id)


async def _load_order(session: AsyncSession, order_id: uuid.UUID) -> Order:
    order = await session.scalar(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.items), selectinload(Order.payment))
    )
    if order is None:
        raise AppError("order_not_found", "Order not found", 404)
    return order


async def get_owned_order(session: AsyncSession, order_id: uuid.UUID, user_id: uuid.UUID) -> Order:
    order = await _load_order(session, order_id)
    if order.user_id != user_id:
        raise AppError("order_not_found", "Order not found", 404)
    return order
