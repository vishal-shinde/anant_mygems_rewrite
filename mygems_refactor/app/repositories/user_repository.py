from app.models.user import User
from app.repositories.base_repository import BaseRepository


class UserRepository(BaseRepository):
    def get_by_username(self, username: str) -> User | None:
        row = self.fetch_one(
            """
            SELECT user_id, username, full_name, role_id, is_active, password_hash
            FROM users
            WHERE username = %s
            LIMIT 1
            """,
            (username,),
        )
        if row is None:
            return None

        return User(
            user_id=row[0],
            username=row[1],
            full_name=row[2],
            role_id=row[3],
            is_active=row[4],
            password_hash=row[5],
        )

    def list_users(self):
        return self.fetch_all(
            """
            SELECT u.user_id, u.username, u.full_name, r.role_name, u.is_active
            FROM users u
            JOIN roles r ON u.role_id = r.role_id
            ORDER BY u.user_id
            """
        )

    def list_roles(self):
        return self.fetch_all(
            """
            SELECT role_id, role_name
            FROM roles
            ORDER BY role_id
            """
        )

    def create_user(self, username: str, password_hash: str, full_name: str, role_id: int, is_active: bool):
        return self.execute(
            """
            INSERT INTO users (username, password_hash, full_name, role_id, is_active)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (username, password_hash, full_name, role_id, is_active),
        )

    def update_user(self, user_id: int, full_name: str, role_id: int, is_active: bool):
        return self.execute(
            """
            UPDATE users
            SET full_name = %s,
                role_id = %s,
                is_active = %s
            WHERE user_id = %s
            """,
            (full_name, role_id, is_active, user_id),
        )

    def delete_user(self, user_id: int):
        return self.execute(
            "DELETE FROM users WHERE user_id = %s",
            (user_id,),
        )
