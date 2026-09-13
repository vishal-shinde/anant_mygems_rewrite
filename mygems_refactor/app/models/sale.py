from dataclasses import dataclass


@dataclass
class SaleOrderItem:
    order_item_id: int | None = None
    order_id: int | None = None
    item_code: str | None = None
    lot_no: str | None = None
    sold_amount: float = 0.0
    paid_amount: float = 0.0
    balance_amount: float = 0.0
    item_status: str = "PENDING_STOCK"


@dataclass
class SaleOrder:
    order_id: int | None = None
    customer_id: int | None = None
    customer_name: str | None = None
    order_status: str = "OPEN"
    total_amount: float = 0.0
    total_paid: float = 0.0
    total_balance: float = 0.0
