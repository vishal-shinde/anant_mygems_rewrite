import bcrypt

from app.repositories.user_repository import UserRepository


class UserService:
    def __init__(self, repo: UserRepository | None = None):
        self.repo = repo or UserRepository()

    def list_roles(self):
        return self.repo.list_roles()

    def list_users(self):
        return self.repo.list_users()

    def create_user(self, username: str, password: str, full_name: str, role_id: int, is_active: bool):
        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        return self.repo.create_user(username, password_hash, full_name, role_id, is_active)

    def update_user(self, user_id: int, full_name: str, role_id: int, is_active: bool):
        return self.repo.update_user(user_id, full_name, role_id, is_active)

    def delete_user(self, user_id: int):
        return self.repo.delete_user(user_id)
