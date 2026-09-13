import bcrypt

from app.repositories.user_repository import UserRepository


class AuthService:
    def __init__(self, user_repository: UserRepository | None = None):
        self.user_repository = user_repository or UserRepository()

    def login(self, username: str, password: str):
        user = self.user_repository.get_by_username(username)
        if user is None:
            return None

        if not user.is_active:
            return None

        if user.password_hash is None:
            return None

        if not bcrypt.checkpw(password.encode("utf-8"), user.password_hash.encode("utf-8")):
            return None

        return user
