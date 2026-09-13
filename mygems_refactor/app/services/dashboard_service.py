from app.repositories.base_repository import BaseRepository


class DashboardService:
    def __init__(self, repo: BaseRepository | None = None):
        self.repo = repo or BaseRepository()

    def get_dashboard_summary(self):
        summary = {}
        for query, key in [
            ("SELECT COUNT(*) FROM users", "user_count"),
            ("SELECT COUNT(*) FROM roles", "role_count"),
            ("SELECT COUNT(*) FROM customers", "customer_count"),
            ("SELECT COUNT(*) FROM sales_orders", "sales_order_count"),
            ("SELECT COUNT(*) FROM jobs", "job_count"),
            ("SELECT COUNT(*) FROM metal_purchases", "purchase_count"),
        ]:
            try:
                value = self.repo.fetch_one(query)
                summary[key] = int(value[0]) if value else 0
            except Exception:
                summary[key] = 0
        return summary
