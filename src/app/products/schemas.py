import uuid

from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    unit_price_minor: int = Field(ge=0)
    active: bool = True
    initial_quantity: int = Field(default=0, ge=0)


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    unit_price_minor: int | None = Field(default=None, ge=0)
    active: bool | None = None


class ProductResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    sku: str
    name: str
    description: str
    unit_price_minor: int
    active: bool


class InventoryAdjustment(BaseModel):
    delta: int


class InventoryResponse(BaseModel):
    product_id: uuid.UUID
    available_quantity: int
    reserved_quantity: int
