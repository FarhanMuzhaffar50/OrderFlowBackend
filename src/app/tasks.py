import asyncio
import uuid
from datetime import UTC, datetime

import httpx
import structlog
from celery import Celery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.models import Inventory, Order, OrderStatus, OutboxEvent, Payment, PaymentStatus
from app.orders.state_machine import transition_order

settings = get_settings()
celery_app = Celery("orderflow", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_acks_late=True, task_reject_on_worker_lost=True, broker_connection_retry_on_startup=True
)
logger = structlog.get_logger()


@celery_app.task(
    bind=True,
    autoretry_for=(httpx.TransportError,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def process_payment(self, payment_id: str) -> None:
    asyncio.run(_process_payment(uuid.UUID(payment_id)))


async def _process_payment(payment_id: uuid.UUID) -> None:
    # Celery's prefork workers call asyncio.run repeatedly. A fresh engine prevents
    # asyncpg pooled connections from being reused across closed event loops.
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    task_sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with task_sessions() as session:
            payment = await session.scalar(
                select(Payment).where(Payment.id == payment_id).with_for_update()
            )
            if payment is None or payment.status in {PaymentStatus.SUCCEEDED, PaymentStatus.FAILED}:
                return
            payment.status = PaymentStatus.PROCESSING
            request = {
                "amount_minor": payment.amount_minor,
                "currency": "USD",
                "order_id": str(payment.order_id),
                "scenario": "success",
            }
            idempotency_key = payment.idempotency_key
            await session.commit()

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{settings.payment_provider_url}/charges",
                json=request,
                headers={"Idempotency-Key": idempotency_key},
            )
        if response.status_code >= 500:
            raise httpx.TransportError(f"provider temporary failure: {response.status_code}")
        result = response.json()

        async with task_sessions() as session:
            payment = await session.scalar(
                select(Payment).where(Payment.id == payment_id).with_for_update()
            )
            if payment is None or payment.status in {PaymentStatus.SUCCEEDED, PaymentStatus.FAILED}:
                return
            order = await session.scalar(
                select(Order).where(Order.id == payment.order_id).with_for_update()
            )
            if order is None:
                raise RuntimeError("payment references a missing order")
            payment.provider_reference = result.get("provider_charge_id")
            if response.is_success and result.get("status") == "succeeded":
                payment.status = PaymentStatus.SUCCEEDED
                transition_order(order, OrderStatus.PAID)
            else:
                await _fail_and_release(session, payment, order)
            await session.commit()
    finally:
        await engine.dispose()


async def _fail_and_release(session, payment: Payment, order: Order) -> None:
    payment.status = PaymentStatus.FAILED
    transition_order(order, OrderStatus.PAYMENT_FAILED)
    await session.refresh(order, ["items"])
    product_ids = sorted((item.product_id for item in order.items), key=str)
    rows = list(
        (
            await session.scalars(
                select(Inventory)
                .where(Inventory.product_id.in_(product_ids))
                .order_by(Inventory.product_id)
                .with_for_update()
            )
        ).all()
    )
    by_id = {row.product_id: row for row in rows}
    for item in order.items:
        by_id[item.product_id].reserved_quantity -= item.quantity
        by_id[item.product_id].available_quantity += item.quantity


@celery_app.task
def publish_outbox() -> int:
    return asyncio.run(_publish_outbox())


async def _publish_outbox() -> int:
    count = 0
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    task_sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with task_sessions() as session:
            events = list(
                (
                    await session.scalars(
                        select(OutboxEvent)
                        .where(OutboxEvent.processed_at.is_(None))
                        .order_by(OutboxEvent.created_at)
                        .limit(100)
                        .with_for_update(skip_locked=True)
                    )
                ).all()
            )
            for event in events:
                if event.event_type == "payment.requested":
                    payment = await session.scalar(
                        select(Payment).where(Payment.order_id == event.aggregate_id)
                    )
                    if payment is None:
                        raise RuntimeError("outbox event references a missing payment")
                    process_payment.delay(str(payment.id))
                event.processed_at = datetime.now(UTC)
                event.attempts += 1
                count += 1
            await session.commit()
    finally:
        await engine.dispose()
    return count


celery_app.conf.beat_schedule = {
    "publish-outbox": {"task": "app.tasks.publish_outbox", "schedule": 2.0}
}
