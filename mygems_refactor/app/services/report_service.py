from app.repositories.report_repository import ReportRepository


class ReportService:
    def __init__(self, repository: ReportRepository | None = None):
        self.repository = repository or ReportRepository()

    def get_overview(self):
        try:
            return self.repository.get_dashboard_overview()
        except Exception:
            return {
                "customers": 0,
                "vendors": 0,
                "orders": 0,
                "jobs": 0,
                "purchases": 0,
                "sales_value": 0,
                "payment_value": 0,
            }

    def get_recent_orders(self, limit: int = 10):
        try:
            return self.repository.get_recent_orders(limit)
        except Exception:
            return []

    def get_recent_purchases(self, limit: int = 10):
        try:
            return self.repository.get_recent_purchases(limit)
        except Exception:
            return []

    def get_recent_jobs(self, limit: int = 10):
        try:
            return self.repository.get_recent_jobs(limit)
        except Exception:
            return []
