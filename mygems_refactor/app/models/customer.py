from dataclasses import dataclass


@dataclass
class Customer:
    customer_id: int | None = None
    customer_name: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    city: str | None = None
    gst_no: str | None = None
    is_active: bool = True
