from app.repositories.base_repository import BaseRepository


class PaymentRepository(BaseRepository):
    def get_recent_payments(self, limit: int = 50):
        return self.fetch_all(
            """
            SELECT payment_id, order_id, payment_mode, amount, paid_on, status
            FROM sales_payments
            ORDER BY payment_id DESC
            LIMIT %s
            """,
            (limit,),
        )

    def save_payment(self, order_id: int, payment_mode: str, amount: float, status: str = "PAID"):
        return self.execute(
            """
            INSERT INTO sales_payments (order_id, payment_mode, amount, status)
            VALUES (%s, %s, %s, %s)
            """,
            (order_id, payment_mode, amount, status),
        )
