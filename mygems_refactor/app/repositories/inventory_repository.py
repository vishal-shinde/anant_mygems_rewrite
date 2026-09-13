from app.repositories.base_repository import BaseRepository


class InventoryRepository(BaseRepository):
    def get_stock_summary(self):
        queries = [
            (
                """
                SELECT 'gold' AS metal_type, COUNT(*) AS count, COALESCE(SUM(current_weight), 0) AS weight
                FROM gold_jewelry
                WHERE status = 'AVAILABLE'
                """,
                (),
            ),
            (
                """
                SELECT 'silver' AS metal_type, COUNT(*) AS count, COALESCE(SUM(current_weight), 0) AS weight
                FROM silver_jewelry
                WHERE status = 'AVAILABLE'
                """,
                (),
            ),
        ]
        rows = []
        for query, params in queries:
            try:
                rows.extend(self.fetch_all(query, params))
            except Exception:
                continue
        return rows

    def get_stock_rows(self, limit: int = 200):
        queries = [
            (
                """
                SELECT lot_no, item_code, 'gold' AS metal_type, current_weight, status, purchase_id
                FROM gold_jewelry
                WHERE status = 'AVAILABLE'
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            ),
            (
                """
                SELECT lot_no, item_code, 'silver' AS metal_type, current_weight, status, purchase_id
                FROM silver_jewelry
                WHERE status = 'AVAILABLE'
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            ),
        ]
        rows = []
        for query, params in queries:
            try:
                rows.extend(self.fetch_all(query, params))
            except Exception:
                continue
        return rows

    def create_inventory_item(self, item_type: str, lot_no: str, item_code: str, current_weight: float, purity: float, status: str, purchase_id: int | None = None):
        table_name = 'gold_jewelry' if item_type.lower() == 'gold' else 'silver_jewelry'
        return self.execute(
            f"""
            INSERT INTO {table_name} (lot_no, item_code, metal_type, current_weight, purity, status, purchase_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (lot_no, item_code, item_type.lower(), current_weight, purity, status, purchase_id),
        )
