from app.repositories.purchase_repository import PurchaseRepository


class PurchaseService:
    def __init__(self, repo: PurchaseRepository | None = None):
        self.repo = repo or PurchaseRepository()

    def get_recent_purchases(self, limit: int = 50):
        try:
            return self.repo.get_recent_purchases(limit)
        except Exception:
            return []

    def create_purchase(self, vendor_name: str, metal_type: str, quantity: float, rate: float, amount: float):
        try:
            self.repo.save_purchase(vendor_name, metal_type, quantity, rate, amount)
            return True
        except Exception:
            return False
