from app.repositories.base_repository import BaseRepository


class RoleRepository(BaseRepository):
    def list_roles(self):
        return self.fetch_all(
            """
            SELECT role_id, role_name
            FROM roles
            ORDER BY role_id
            """
        )
