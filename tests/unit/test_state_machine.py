import uuid

import pytest

from app.core.exceptions import AppError
from app.db.models import Order, OrderStatus
from app.orders.state_machine import transition_order


def order(status: OrderStatus) -> Order:
    return Order(id=uuid.uuid4(), user_id=uuid.uuid4(), status=status, total_amount_minor=0)


def test_valid_transition():
    value = order(OrderStatus.CREATED)
    transition_order(value, OrderStatus.INVENTORY_RESERVED)
    assert value.status == OrderStatus.INVENTORY_RESERVED


def test_invalid_transition_is_rejected():
    with pytest.raises(AppError) as error:
        transition_order(order(OrderStatus.CREATED), OrderStatus.SHIPPED)
    assert error.value.status_code == 409


def test_terminal_state_has_no_transitions():
    with pytest.raises(AppError):
        transition_order(order(OrderStatus.CANCELLED), OrderStatus.CREATED)
