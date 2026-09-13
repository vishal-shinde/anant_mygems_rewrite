from app.repositories.inventory_repository import InventoryRepository


class InventoryService:
    def __init__(self, repo: InventoryRepository | None = None):
        self.repo = repo or InventoryRepository()

    def get_stock_summary(self):
        try:
            rows = self.repo.get_stock_summary()
        except Exception:
            return {"gold": 0, "silver": 0}

        summary = {"gold": 0, "silver": 0}
        for metal_type, count, weight in rows or []:
            if metal_type in summary:
                summary[metal_type] = int(count or 0)
        return summary

    def get_stock_rows(self, limit: int = 200):
        try:
            return self.repo.get_stock_rows(limit)
        except Exception:
            return []

    def create_inventory_item(self, item_type: str, lot_no: str, item_code: str, current_weight: float, purity: float, status: str = "AVAILABLE", purchase_id: int | None = None):
        try:
            return self.repo.create_inventory_item(item_type, lot_no, item_code, current_weight, purity, status, purchase_id)
        except Exception:
            return None
