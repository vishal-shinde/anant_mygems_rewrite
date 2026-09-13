from app.repositories.base_repository import BaseRepository


class SalesRepository(BaseRepository):
    def get_pending_orders(self):
        return self.fetch_all(
            """
            SELECT order_id, customer_id, order_status, total_amount, total_paid, total_balance
            FROM sales_orders
            WHERE order_status IN ('OPEN', 'PENDING_STOCK', 'PENDING_SEND')
            ORDER BY order_id DESC
            LIMIT 50
            """
        )

    def get_order_items(self, order_id: int):
        return self.fetch_all(
            """
            SELECT order_item_id, order_id, item_code, lot_no, sold_amount, paid_amount, balance_amount, item_status
            FROM sales_order_items
            WHERE order_id = %s
            ORDER BY order_item_id
            """,
            (order_id,),
        )

    def get_inventory_available(self):
        return self.fetch_all(
            """
            SELECT lot_no, item_code, 'gold' AS metal_type, current_weight, status
            FROM gold_jewelry
            WHERE status = 'AVAILABLE'
            UNION ALL
            SELECT lot_no, item_code, 'silver' AS metal_type, current_weight, status
            FROM silver_jewelry
            WHERE status = 'AVAILABLE'
            ORDER BY lot_no
            LIMIT 200
            """
        )

    def save_order(self, customer_id: int, total_amount: float, total_paid: float, total_balance: float):
        return self.execute(
            """
            INSERT INTO sales_orders (customer_id, order_status, total_amount, total_paid, total_balance)
            VALUES (%s, 'OPEN', %s, %s, %s)
            RETURNING order_id
            """,
            (customer_id, total_amount, total_paid, total_balance),
        )

    def save_order_item(self, order_id: int, item_code: str, lot_no: str, sold_amount: float, paid_amount: float, balance_amount: float, item_status: str):
        return self.execute(
            """
            INSERT INTO sales_order_items (
                order_id, item_code, lot_no, sold_amount, paid_amount, balance_amount, item_status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (order_id, item_code, lot_no, sold_amount, paid_amount, balance_amount, item_status),
        )
