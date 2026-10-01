import uuid

from pydantic import BaseModel, Field


class CartItemRequest(BaseModel):
    product_id: uuid.UUID
    quantity: int = Field(gt=0)


class QuantityUpdate(BaseModel):
    quantity: int = Field(gt=0)


class CartItemResponse(BaseModel):
    product_id: uuid.UUID
    sku: str
    name: str
    quantity: int
    unit_price_minor: int
    line_total_minor: int


class CartResponse(BaseModel):
    id: uuid.UUID
    items: list[CartItemResponse]
    total_amount_minor: int
