from dataclasses import dataclass


@dataclass
class Vendor:
    vendor_id: int | None = None
    vendor_name: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    is_active: bool = True
