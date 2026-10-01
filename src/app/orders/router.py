import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import CurrentUser
from app.common.rate_limit import enforce_rate_limit
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.db.models import Order
from app.db.session import get_session
from app.orders.schemas import OrderResponse
from app.orders.service import checkout, get_owned_order

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/checkout", response_model=OrderResponse, status_code=201)
async def checkout_order(
    request: Request,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    if not idempotency_key or len(idempotency_key) > 255:
        raise AppError(
            "idempotency_key_required", "A valid Idempotency-Key header is required", 400
        )
    await enforce_rate_limit(request, "checkout", get_settings().checkout_rate_limit)
    return await checkout(session, user.id, idempotency_key)


@router.get("", response_model=list[OrderResponse])
async def list_orders(
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    stmt = (
        select(Order)
        .where(Order.user_id == user.id)
        .options(selectinload(Order.items), selectinload(Order.payment))
        .order_by(Order.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list((await session.scalars(stmt)).all())


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: uuid.UUID, user: CurrentUser, session: Annotated[AsyncSession, Depends(get_session)]
):
    return await get_owned_order(session, order_id, user.id)
