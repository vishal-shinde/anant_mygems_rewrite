from dataclasses import dataclass


@dataclass
class Payment:
    payment_id: int | None = None
    order_id: int | None = None
    payment_mode: str | None = None
    amount: float = 0.0
    paid_on: str | None = None
    status: str = "PENDING"
