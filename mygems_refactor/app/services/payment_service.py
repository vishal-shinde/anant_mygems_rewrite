from app.repositories.payment_repository import PaymentRepository


class PaymentService:
    def __init__(self, repo: PaymentRepository | None = None):
        self.repo = repo or PaymentRepository()

    def get_recent_payments(self, limit: int = 50):
        try:
            return self.repo.get_recent_payments(limit)
        except Exception:
            return []

    def create_payment(self, order_id: int, payment_mode: str, amount: float):
        if not order_id:
            raise ValueError("Order ID is required.")
        if amount <= 0:
            raise ValueError("Payment amount must be greater than zero.")
        try:
            return self.repo.save_payment(order_id, payment_mode, float(amount), "PAID")
        except Exception:
            raise
