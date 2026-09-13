from app.repositories.base_repository import BaseRepository


class PurchaseRepository(BaseRepository):
    def get_recent_purchases(self, limit: int = 50):
        queries = [
            ("""
            SELECT purchase_id, vendor_name, metal_type, quantity, rate, amount
            FROM metal_purchases
            ORDER BY purchase_id DESC
            LIMIT %s
            """, (limit,)),
            ("""
            SELECT purchase_id, vendor_name, metal_type, quantity, rate, amount
            FROM purchases
            ORDER BY purchase_id DESC
            LIMIT %s
            """, (limit,)),
        ]

        for query, params in queries:
            try:
                return self.fetch_all(query, params)
            except Exception:
                continue
        return []

    def save_purchase(self, vendor_name: str, metal_type: str, quantity: float, rate: float, amount: float):
        queries = [
            ("""
            INSERT INTO metal_purchases (vendor_name, metal_type, quantity, rate, amount)
            VALUES (%s, %s, %s, %s, %s)
            """, (vendor_name, metal_type, quantity, rate, amount)),
            ("""
            INSERT INTO purchases (vendor_name, metal_type, quantity, rate, amount)
            VALUES (%s, %s, %s, %s, %s)
            """, (vendor_name, metal_type, quantity, rate, amount)),
        ]

        for query, params in queries:
            try:
                return self.execute(query, params)
            except Exception:
                continue
        raise RuntimeError("No compatible purchase table found")
