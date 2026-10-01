import hashlib
import hmac
import json
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.db.models import Order, OrderStatus, Payment, PaymentStatus, WebhookEvent
from app.db.session import get_session
from app.orders.state_machine import transition_order

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class PaymentWebhook(BaseModel):
    event_id: str
    provider_reference: str
    idempotency_key: str
    status: str


@router.post("/payments", status_code=204)
async def payment_webhook(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    signature: Annotated[str | None, Header(alias="X-Webhook-Signature")] = None,
):
    raw = await request.body()
    expected = hmac.new(get_settings().webhook_secret.encode(), raw, hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(signature, expected):
        raise AppError("invalid_signature", "Invalid webhook signature", 401)
    try:
        event = PaymentWebhook.model_validate(json.loads(raw))
    except (ValueError, json.JSONDecodeError):
        raise AppError("invalid_webhook", "Invalid webhook payload", 400) from None
    if await session.get(WebhookEvent, event.event_id):
        return Response(status_code=204)
    payment = await session.scalar(
        select(Payment).where(Payment.idempotency_key == event.idempotency_key).with_for_update()
    )
    if payment is None:
        raise AppError("payment_not_found", "Payment not found", 404)
    session.add(WebhookEvent(event_id=event.event_id))
    if payment.status not in {PaymentStatus.SUCCEEDED, PaymentStatus.FAILED}:
        order = await session.scalar(
            select(Order).where(Order.id == payment.order_id).with_for_update()
        )
        if order is None:
            raise AppError("order_not_found", "Payment order not found", 409)
        payment.provider_reference = event.provider_reference
        if event.status == "succeeded":
            payment.status = PaymentStatus.SUCCEEDED
            transition_order(order, OrderStatus.PAID)
        elif event.status == "failed":
            # Same compensation path as an explicit provider decline in the worker.
            from app.tasks import _fail_and_release

            await _fail_and_release(session, payment, order)
    await session.commit()
    return Response(status_code=204)
