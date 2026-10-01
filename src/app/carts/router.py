import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import CurrentUser
from app.carts.schemas import CartItemRequest, CartItemResponse, CartResponse, QuantityUpdate
from app.core.exceptions import AppError
from app.db.models import Cart, CartItem, Product
from app.db.session import get_session

router = APIRouter(prefix="/cart", tags=["cart"])


async def load_cart(session: AsyncSession, user_id: uuid.UUID) -> Cart:
    cart = await session.scalar(
        select(Cart)
        .where(Cart.user_id == user_id)
        .options(selectinload(Cart.items).selectinload(CartItem.product))
        .execution_options(populate_existing=True)
    )
    if cart is None:
        cart = Cart(user_id=user_id)
        session.add(cart)
        await session.flush()
    return cart


def render_cart(cart: Cart) -> CartResponse:
    items = [
        CartItemResponse(
            product_id=i.product_id,
            sku=i.product.sku,
            name=i.product.name,
            quantity=i.quantity,
            unit_price_minor=i.product.unit_price_minor,
            line_total_minor=i.quantity * i.product.unit_price_minor,
        )
        for i in cart.items
    ]
    return CartResponse(
        id=cart.id, items=items, total_amount_minor=sum(i.line_total_minor for i in items)
    )


@router.get("", response_model=CartResponse)
async def get_cart(user: CurrentUser, session: Annotated[AsyncSession, Depends(get_session)]):
    return render_cart(await load_cart(session, user.id))


@router.post("/items", response_model=CartResponse)
async def add_item(
    body: CartItemRequest, user: CurrentUser, session: Annotated[AsyncSession, Depends(get_session)]
):
    product = await session.get(Product, body.product_id)
    if product is None or not product.active:
        raise AppError("product_unavailable", "Product is unavailable", 409)
    cart = await load_cart(session, user.id)
    item = next((i for i in cart.items if i.product_id == body.product_id), None)
    if item:
        item.quantity += body.quantity
    else:
        session.add(CartItem(cart_id=cart.id, product_id=body.product_id, quantity=body.quantity))
    await session.commit()
    return render_cart(await load_cart(session, user.id))


@router.put("/items/{product_id}", response_model=CartResponse)
async def update_item(
    product_id: uuid.UUID,
    body: QuantityUpdate,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    cart = await load_cart(session, user.id)
    item = await session.get(CartItem, (cart.id, product_id))
    if item is None:
        raise AppError("cart_item_not_found", "Cart item not found", 404)
    item.quantity = body.quantity
    await session.commit()
    return render_cart(await load_cart(session, user.id))


@router.delete("/items/{product_id}", response_model=CartResponse)
async def remove_item(
    product_id: uuid.UUID, user: CurrentUser, session: Annotated[AsyncSession, Depends(get_session)]
):
    cart = await load_cart(session, user.id)
    item = await session.get(CartItem, (cart.id, product_id))
    if item is None:
        raise AppError("cart_item_not_found", "Cart item not found", 404)
    await session.delete(item)
    await session.commit()
    return render_cart(await load_cart(session, user.id))


@router.delete("", status_code=204)
async def clear_cart(user: CurrentUser, session: Annotated[AsyncSession, Depends(get_session)]):
    cart = await load_cart(session, user.id)
    await session.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
    await session.commit()
    return Response(status_code=204)
