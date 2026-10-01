import uuid
from datetime import datetime

from pydantic import BaseModel

from app.db.models import OrderStatus, PaymentStatus


class OrderItemResponse(BaseModel):
    model_config = {"from_attributes": True}
    product_id: uuid.UUID
    sku: str
    product_name: str
    unit_price_minor: int
    quantity: int
    line_total_minor: int


class PaymentResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    status: PaymentStatus
    amount_minor: int
    provider_reference: str | None


class OrderResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    status: OrderStatus
    total_amount_minor: int
    created_at: datetime
    items: list[OrderItemResponse]
    payment: PaymentResponse
