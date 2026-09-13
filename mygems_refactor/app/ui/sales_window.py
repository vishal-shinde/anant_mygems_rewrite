from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.services.customer_service import CustomerService
from app.services.sales_service import SalesService


class CreateSaleDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Sales Order")
        self.resize(520, 260)
        self.sales_service = SalesService()
        self.customer_service = CustomerService()

        form_layout = QFormLayout(self)

        self.customer_combo = QComboBox()
        self.customer_combo.addItem("Select customer", -1)
        for customer_id, customer_name, *_ in self.customer_service.list_customers():
            self.customer_combo.addItem(f"{customer_id} - {customer_name}", customer_id)

        self.item_code_input = QLineEdit()
        self.lot_no_input = QLineEdit()
        self.metal_input = QComboBox()
        self.metal_input.addItems(["Gold", "Silver"])
        self.sold_amount_input = QDoubleSpinBox()
        self.sold_amount_input.setRange(0, 1000000000)
        self.sold_amount_input.setDecimals(2)
        self.sold_amount_input.setValue(0)
        self.paid_amount_input = QDoubleSpinBox()
        self.paid_amount_input.setRange(0, 1000000000)
        self.paid_amount_input.setDecimals(2)
        self.paid_amount_input.setValue(0)

        form_layout.addRow("Customer:", self.customer_combo)
        form_layout.addRow("Item Code:", self.item_code_input)
        form_layout.addRow("Lot No:", self.lot_no_input)
        form_layout.addRow("Metal:", self.metal_input)
        form_layout.addRow("Sold Amount:", self.sold_amount_input)
        form_layout.addRow("Paid Amount:", self.paid_amount_input)

        buttons = QHBoxLayout()
        save_btn = QPushButton("Save Order")
        cancel_btn = QPushButton("Cancel")
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        form_layout.addRow(buttons)

        save_btn.clicked.connect(self.save)
        cancel_btn.clicked.connect(self.reject)

    def save(self):
        customer_id = self.customer_combo.currentData()
        if customer_id in (None, -1):
            QMessageBox.warning(self, "Validation Error", "Please select a customer.")
            return

        item_code = self.item_code_input.text().strip()
        lot_no = self.lot_no_input.text().strip()
        if not item_code or not lot_no:
            QMessageBox.warning(self, "Validation Error", "Item code and lot number are required.")
            return

        try:
            order_id = self.sales_service.create_sale(
                customer_id,
                [{
                    "item_code": item_code,
                    "lot_no": lot_no,
                    "metal_type": self.metal_input.currentText(),
                    "sold_amount": float(self.sold_amount_input.value()),
                    "paid_amount": float(self.paid_amount_input.value()),
                    "balance_amount": float(self.sold_amount_input.value() - self.paid_amount_input.value()),
                    "item_status": "PENDING_STOCK",
                }],
            )
            QMessageBox.information(self, "Success", f"Sales order #{order_id} created successfully.")
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", f"Unable to create sale order: {exc}")


class SalesWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sales / Orders")
        self.resize(1100, 700)
        self.service = SalesService()

        self.summary = QLabel("Sales order flow placeholder")
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Order ID", "Customer", "Status", "Total", "Paid", "Balance"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        add_action = QAction("New Sale", self)
        add_action.triggered.connect(self.open_sale_form)
        self.addAction(add_action)

        layout = QVBoxLayout(self)
        layout.addWidget(self.summary)
        layout.addWidget(self.table)

        self.load_data()

    def open_sale_form(self):
        dialog = CreateSaleDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_data()

    def load_data(self):
        rows = self.service.get_pending_orders()
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            order_id, customer_id, order_status, total_amount, total_paid, total_balance = row
            self.table.setItem(index, 0, QTableWidgetItem(str(order_id or '')))
            self.table.setItem(index, 1, QTableWidgetItem(str(customer_id or '')))
            self.table.setItem(index, 2, QTableWidgetItem(str(order_status or '')))
            self.table.setItem(index, 3, QTableWidgetItem(str(total_amount or '0')))
            self.table.setItem(index, 4, QTableWidgetItem(str(total_paid or '0')))
            self.table.setItem(index, 5, QTableWidgetItem(str(total_balance or '0')))

        self.summary.setText(
            f"Orders loaded: {len(rows)}"
        )
