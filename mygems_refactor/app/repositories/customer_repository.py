from app.repositories.base_repository import BaseRepository


class CustomerRepository(BaseRepository):
    def list_customers(self):
        return self.fetch_all(
            """
            SELECT customer_id, customer_name, phone, email, city, gst_no, is_active
            FROM customers
            ORDER BY customer_id
            """
        )

    def create_customer(self, customer_name: str, phone: str | None, email: str | None, address: str | None, city: str | None, gst_no: str | None, is_active: bool):
        return self.execute(
            """
            INSERT INTO customers (customer_name, phone, email, address, city, gst_no, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (customer_name, phone, email, address, city, gst_no, is_active),
        )
