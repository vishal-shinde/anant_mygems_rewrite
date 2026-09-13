from dataclasses import dataclass


@dataclass
class User:
    user_id: int
    username: str
    full_name: str
    role_id: int
    is_active: bool = True
    password_hash: str | None = None
