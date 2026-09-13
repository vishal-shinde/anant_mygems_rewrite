from PySide6.QtGui import QAction
from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget

from app.ui.customer_window import CustomerWindow
from app.ui.inventory_window import InventoryWindow
from app.ui.job_window import JobWindow
from app.ui.payment_window import PaymentWindow
from app.ui.purchase_window import PurchaseWindow
from app.ui.report_window import ReportWindow
from app.ui.sales_window import SalesWindow
from app.ui.user_management_window import UserManagementWindow
from app.ui.vendor_window import VendorWindow


class DashboardWindow(QMainWindow):
    def __init__(self, user=None, summary=None):
        super().__init__()
        self.user = user
        self.summary = summary or {}
        self.setWindowTitle("MYGEMS Dashboard")
        self.resize(1200, 750)

        menubar = self.menuBar()
        admin_menu = menubar.addMenu("Admin")
        user_management_action = QAction("User Management", self)
        user_management_action.triggered.connect(self.open_user_management)
        admin_menu.addAction(user_management_action)

        customer_menu = menubar.addMenu("Customers")
        customer_action = QAction("Customer Management", self)
        customer_action.triggered.connect(self.open_customers)
        customer_menu.addAction(customer_action)

        vendor_menu = menubar.addMenu("Vendors")
        vendor_action = QAction("Vendor Management", self)
        vendor_action.triggered.connect(self.open_vendors)
        vendor_menu.addAction(vendor_action)

        purchase_menu = menubar.addMenu("Purchase")
        metal_purchase_action = QAction("Metal Purchase", self)
        metal_purchase_action.triggered.connect(self.open_purchase)
        purchase_menu.addAction(metal_purchase_action)

        inventory_menu = menubar.addMenu("Inventory")
        stock_action = QAction("Stock", self)
        stock_action.triggered.connect(self.open_inventory)
        inventory_menu.addAction(stock_action)

        sales_menu = menubar.addMenu("Sales")
        sales_action = QAction("Orders", self)
        sales_action.triggered.connect(self.open_sales)
        sales_menu.addAction(sales_action)

        payment_menu = menubar.addMenu("Payments")
        payments_action = QAction("Payment Ledger", self)
        payments_action.triggered.connect(self.open_payments)
        payment_menu.addAction(payments_action)

        jobs_menu = menubar.addMenu("Jobs")
        job_action = QAction("Job Assign", self)
        job_action.triggered.connect(self.open_jobs)
        jobs_menu.addAction(job_action)

        reports_menu = menubar.addMenu("Reports")
        report_action = QAction("Overview", self)
        report_action.triggered.connect(self.open_reports)
        reports_menu.addAction(report_action)

        container = QWidget(self)
        layout = QVBoxLayout(container)

        title = QLabel("Dashboard")
        title.setStyleSheet("font-size: 24px; font-weight: 600;")
        layout.addWidget(title)

        welcome = QLabel(f"Signed in as: {user.full_name if user else 'Guest'}")
        layout.addWidget(welcome)

        stats = QLabel(
            "Users: {user_count} | Roles: {role_count} | Customers: {customer_count} | "
            "Orders: {sales_order_count} | Jobs: {job_count} | Purchases: {purchase_count}".format(
                user_count=self.summary.get("user_count", 0),
                role_count=self.summary.get("role_count", 0),
                customer_count=self.summary.get("customer_count", 0),
                sales_order_count=self.summary.get("sales_order_count", 0),
                job_count=self.summary.get("job_count", 0),
                purchase_count=self.summary.get("purchase_count", 0),
            )
        )
        layout.addWidget(stats)

        self.setCentralWidget(container)

    def open_user_management(self):
        self.user_management_window = UserManagementWindow(self)
        self.user_management_window.show()

    def open_customers(self):
        self.customer_window = CustomerWindow(self)
        self.customer_window.show()

    def open_vendors(self):
        self.vendor_window = VendorWindow(self)
        self.vendor_window.show()

    def open_purchase(self):
        self.purchase_window = PurchaseWindow(self)
        self.purchase_window.show()

    def open_inventory(self):
        self.inventory_window = InventoryWindow(self)
        self.inventory_window.show()

    def open_sales(self):
        self.sales_window = SalesWindow(self)
        self.sales_window.show()

    def open_payments(self):
        self.payment_window = PaymentWindow(self)
        self.payment_window.show()

    def open_jobs(self):
        self.job_window = JobWindow(self)
        self.job_window.show()

    def open_reports(self):
        self.report_window = ReportWindow(self)
        self.report_window.show()
