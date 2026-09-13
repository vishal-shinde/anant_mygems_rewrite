from app.repositories.base_repository import BaseRepository


class VendorRepository(BaseRepository):
    def list_vendors(self):
        return self.fetch_all(
            """
            SELECT vendor_id, vendor_name, phone, email, address, is_active
            FROM vendors
            ORDER BY vendor_id
            """
        )

    def create_vendor(self, vendor_name: str, phone: str | None, email: str | None, address: str | None, is_active: bool):
        return self.execute(
            """
            INSERT INTO vendors (vendor_name, phone, email, address, is_active)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (vendor_name, phone, email, address, is_active),
        )
