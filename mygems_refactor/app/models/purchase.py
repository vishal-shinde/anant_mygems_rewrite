from dataclasses import dataclass


@dataclass
class PurchaseEntry:
    purchase_id: int | None = None
    vendor_name: str | None = None
    metal_type: str | None = None
    quantity: float = 0.0
    rate: float = 0.0
    amount: float = 0.0
