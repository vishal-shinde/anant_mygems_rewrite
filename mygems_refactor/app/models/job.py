from dataclasses import dataclass


@dataclass
class Job:
    job_id: int | None = None
    job_code: str | None = None
    customer_name: str | None = None
    status: str = "OPEN"
    assigned_to: str | None = None
