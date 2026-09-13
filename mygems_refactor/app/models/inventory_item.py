from dataclasses import dataclass


@dataclass
class InventoryItem:
    lot_no: str | None = None
    item_code: str | None = None
    metal_type: str | None = None
    current_weight: float = 0.0
    purity: float = 0.0
    status: str = "AVAILABLE"
    purchase_id: int | None = None
