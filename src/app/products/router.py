import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import AdminUser
from app.common.redis import redis_client
from app.core.exceptions import AppError
from app.db.models import Inventory, Product
from app.db.session import get_session
from app.products.schemas import (
    InventoryAdjustment,
    InventoryResponse,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
)

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductResponse])
async def list_products(
    session: Annotated[AsyncSession, Depends(get_session)],
    search: str | None = None,
    active: bool = True,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    stmt = select(Product).where(Product.active == active)
    if search:
        term = f"%{search}%"
        stmt = stmt.where(or_(Product.name.ilike(term), Product.sku.ilike(term)))
    return list(
        (await session.scalars(stmt.order_by(Product.name).offset(offset).limit(limit))).all()
    )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: uuid.UUID, session: Annotated[AsyncSession, Depends(get_session)]
):
    key = f"orderflow:product:{product_id}"
    try:
        if cached := await redis_client.get(key):
            return ProductResponse.model_validate_json(cached)
    except Exception:
        pass
    product = await session.get(Product, product_id)
    if product is None:
        raise AppError("product_not_found", "Product not found", 404)
    response = ProductResponse.model_validate(product)
    try:
        await redis_client.set(key, response.model_dump_json(), ex=300)
    except Exception:
        pass
    return response


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(
    body: ProductCreate, _: AdminUser, session: Annotated[AsyncSession, Depends(get_session)]
):
    if await session.scalar(select(Product).where(Product.sku == body.sku)):
        raise AppError("sku_exists", "SKU already exists", 409)
    product = Product(
        sku=body.sku,
        name=body.name,
        description=body.description,
        unit_price_minor=body.unit_price_minor,
        active=body.active,
    )
    session.add(product)
    await session.flush()
    session.add(Inventory(product_id=product.id, available_quantity=body.initial_quantity))
    await session.commit()
    return product


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: uuid.UUID,
    body: ProductUpdate,
    _: AdminUser,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    product = await session.get(Product, product_id)
    if product is None:
        raise AppError("product_not_found", "Product not found", 404)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    await session.commit()
    try:
        await redis_client.delete(f"orderflow:product:{product_id}")
    except Exception:
        pass
    return product


@router.post("/{product_id}/inventory", response_model=InventoryResponse)
async def adjust_inventory(
    product_id: uuid.UUID,
    body: InventoryAdjustment,
    _: AdminUser,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    inventory = await session.scalar(
        select(Inventory).where(Inventory.product_id == product_id).with_for_update()
    )
    if inventory is None:
        raise AppError("product_not_found", "Product inventory not found", 404)
    if inventory.available_quantity + body.delta < 0:
        raise AppError("invalid_inventory", "Adjustment would make inventory negative", 409)
    inventory.available_quantity += body.delta
    await session.commit()
    return inventory
