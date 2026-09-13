from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.report_service import ReportService


class ReportWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Reports")
        self.resize(1200, 700)
        self.service = ReportService()

        layout = QVBoxLayout(self)

        overview = self.service.get_overview()
        metrics = QWidget()
        metrics_layout = QHBoxLayout(metrics)
        cards = [
            ("Customers", overview.get("customers", 0)),
            ("Vendors", overview.get("vendors", 0)),
            ("Orders", overview.get("orders", 0)),
            ("Jobs", overview.get("jobs", 0)),
            ("Purchases", overview.get("purchases", 0)),
            ("Sales Value", f"₹{overview.get('sales_value', 0):,.2f}"),
            ("Payment Value", f"₹{overview.get('payment_value', 0):,.2f}"),
        ]

        for title, value in cards:
            card = QWidget()
            card_layout = QVBoxLayout(card)
            title_label = QLabel(title)
            value_label = QLabel(str(value))
            title_label.setStyleSheet("font-size: 12px; color: #666;")
            value_label.setStyleSheet("font-size: 20px; font-weight: bold;")
            card_layout.addWidget(title_label)
            card_layout.addWidget(value_label)
            card.setStyleSheet("border: 1px solid #cfcfcf; background: #f8f8f8; padding: 8px;")
            metrics_layout.addWidget(card)

        layout.addWidget(metrics)

        recent_orders = self.service.get_recent_orders(10)
        orders_table = QTableWidget(0, 6)
        orders_table.setHorizontalHeaderLabels(["Order ID", "Customer", "Status", "Total", "Paid", "Balance"])
        orders_table.setRowCount(len(recent_orders))
        for index, row in enumerate(recent_orders):
            for col_index, value in enumerate(row):
                orders_table.setItem(index, col_index, QTableWidgetItem(str(value or "")))

        recent_purchases = self.service.get_recent_purchases(10)
        purchases_table = QTableWidget(0, 6)
        purchases_table.setHorizontalHeaderLabels(["ID", "Vendor", "Metal", "Qty", "Rate", "Amount"])
        purchases_table.setRowCount(len(recent_purchases))
        for index, row in enumerate(recent_purchases):
            for col_index, value in enumerate(row):
                purchases_table.setItem(index, col_index, QTableWidgetItem(str(value or "")))

        recent_jobs = self.service.get_recent_jobs(10)
        jobs_table = QTableWidget(0, 5)
        jobs_table.setHorizontalHeaderLabels(["Job ID", "Job Code", "Customer", "Status", "Assigned To"])
        jobs_table.setRowCount(len(recent_jobs))
        for index, row in enumerate(recent_jobs):
            for col_index, value in enumerate(row):
                jobs_table.setItem(index, col_index, QTableWidgetItem(str(value or "")))

        layout.addWidget(QLabel("Recent Orders"))
        layout.addWidget(orders_table)
        layout.addWidget(QLabel("Recent Purchases"))
        layout.addWidget(purchases_table)
        layout.addWidget(QLabel("Recent Jobs"))
        layout.addWidget(jobs_table)
