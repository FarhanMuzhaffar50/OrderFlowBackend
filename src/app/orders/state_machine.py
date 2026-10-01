from app.core.exceptions import AppError
from app.db.models import Order, OrderStatus

ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.CREATED: {OrderStatus.INVENTORY_RESERVED, OrderStatus.CANCELLED},
    OrderStatus.INVENTORY_RESERVED: {OrderStatus.PAYMENT_PENDING, OrderStatus.CANCELLED},
    OrderStatus.PAYMENT_PENDING: {
        OrderStatus.PAID,
        OrderStatus.PAYMENT_FAILED,
        OrderStatus.CANCELLED,
    },
    OrderStatus.PAID: {OrderStatus.PROCESSING, OrderStatus.REFUNDED},
    OrderStatus.PROCESSING: {OrderStatus.SHIPPED, OrderStatus.REFUNDED},
    OrderStatus.SHIPPED: {OrderStatus.DELIVERED, OrderStatus.REFUNDED},
    OrderStatus.DELIVERED: {OrderStatus.REFUNDED},
    OrderStatus.PAYMENT_FAILED: {OrderStatus.CANCELLED},
    OrderStatus.CANCELLED: set(),
    OrderStatus.REFUNDED: set(),
}


def transition_order(order: Order, target: OrderStatus) -> None:
    if target not in ALLOWED_TRANSITIONS[order.status]:
        raise AppError(
            "invalid_order_transition",
            f"Cannot transition {order.status.value} to {target.value}",
            409,
        )
    order.status = target
