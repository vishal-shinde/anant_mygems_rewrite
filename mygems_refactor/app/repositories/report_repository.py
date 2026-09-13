from app.repositories.base_repository import BaseRepository


class ReportRepository(BaseRepository):
    def get_dashboard_overview(self):
        return {
            "customers": self.fetch_one("SELECT COUNT(*) FROM customers")[0],
            "vendors": self.fetch_one("SELECT COUNT(*) FROM vendors")[0],
            "orders": self.fetch_one("SELECT COUNT(*) FROM sales_orders")[0],
            "jobs": self.fetch_one("SELECT COUNT(*) FROM jobs")[0],
            "purchases": self.fetch_one("SELECT COUNT(*) FROM metal_purchases")[0],
            "sales_value": self.fetch_one("SELECT COALESCE(SUM(total_amount), 0) FROM sales_orders")[0],
            "payment_value": self.fetch_one("SELECT COALESCE(SUM(amount), 0) FROM sales_payments")[0],
        }

    def get_recent_orders(self, limit: int = 10):
        return self.fetch_all(
            """
            SELECT o.order_id, c.customer_name, o.order_status, o.total_amount, o.total_paid, o.total_balance
            FROM sales_orders o
            LEFT JOIN customers c ON c.customer_id = o.customer_id
            ORDER BY o.order_id DESC
            LIMIT %s
            """,
            (limit,),
        )

    def get_recent_purchases(self, limit: int = 10):
        return self.fetch_all(
            """
            SELECT purchase_id, vendor_name, metal_type, quantity, rate, amount
            FROM metal_purchases
            ORDER BY purchase_id DESC
            LIMIT %s
            """,
            (limit,),
        )

    def get_recent_jobs(self, limit: int = 10):
        return self.fetch_all(
            """
            SELECT job_id, job_code, customer_name, status, assigned_to
            FROM jobs
            ORDER BY job_id DESC
            LIMIT %s
            """,
            (limit,),
        )
