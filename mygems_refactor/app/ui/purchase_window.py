from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.services.purchase_service import PurchaseService
from app.services.vendor_service import VendorService


class PurchaseEntryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Purchase")
        self.resize(480, 260)
        self.service = PurchaseService()
        self.vendor_service = VendorService()

        form_layout = QFormLayout(self)
        self.vendor_combo = QComboBox()
        self.vendor_combo.addItem("Select vendor", "")
        for row in self.vendor_service.list_vendors():
            self.vendor_combo.addItem(f"{row[0]} - {row[1]}", row[1])

        self.metal_combo = QComboBox()
        self.metal_combo.addItems(["Gold", "Silver"])
        self.quantity_input = QDoubleSpinBox()
        self.quantity_input.setRange(0, 1000000)
        self.quantity_input.setDecimals(3)
        self.quantity_input.setValue(0)
        self.rate_input = QDoubleSpinBox()
        self.rate_input.setRange(0, 1000000000)
        self.rate_input.setDecimals(2)
        self.rate_input.setValue(0)
        self.amount_input = QDoubleSpinBox()
        self.amount_input.setRange(0, 1000000000)
        self.amount_input.setDecimals(2)
        self.amount_input.setValue(0)

        form_layout.addRow("Vendor:", self.vendor_combo)
        form_layout.addRow("Metal:", self.metal_combo)
        form_layout.addRow("Quantity:", self.quantity_input)
        form_layout.addRow("Rate:", self.rate_input)
        form_layout.addRow("Amount:", self.amount_input)

        buttons = QHBoxLayout()
        save_btn = QPushButton("Save Purchase")
        cancel_btn = QPushButton("Cancel")
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        form_layout.addRow(buttons)

        save_btn.clicked.connect(self.save)
        cancel_btn.clicked.connect(self.reject)

    def save(self):
        vendor_name = self.vendor_combo.currentData()
        if not vendor_name:
            QMessageBox.warning(self, "Validation Error", "Please select a vendor.")
            return

        try:
            ok = self.service.create_purchase(
                vendor_name=str(vendor_name),
                metal_type=self.metal_combo.currentText(),
                quantity=float(self.quantity_input.value()),
                rate=float(self.rate_input.value()),
                amount=float(self.amount_input.value()),
            )
            if not ok:
                raise RuntimeError("Purchase save returned false")
            QMessageBox.information(self, "Success", "Purchase saved successfully.")
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", f"Unable to save purchase: {exc}")


class PurchaseWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Metal Purchase")
        self.resize(1100, 650)
        self.service = PurchaseService()

        self.summary = QLabel("Recent purchases")
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["ID", "Vendor", "Metal", "Qty", "Rate", "Amount"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        add_action = QPushButton("Add Purchase")
        add_action.clicked.connect(self.open_entry_form)

        layout = QVBoxLayout(self)
        layout.addWidget(self.summary)
        layout.addWidget(add_action)
        layout.addWidget(self.table)

        self.load_data()

    def open_entry_form(self):
        dialog = PurchaseEntryDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_data()

    def load_data(self):
        rows = self.service.get_recent_purchases()
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            if len(row) >= 6:
                purchase_id, vendor_name, metal_type, quantity, rate, amount = row
            else:
                purchase_id, vendor_name, metal_type, quantity, rate, amount = (*row, 0.0, 0.0)[:6]

            self.table.setItem(index, 0, QTableWidgetItem(str(purchase_id or '')))
            self.table.setItem(index, 1, QTableWidgetItem(str(vendor_name or '')))
            self.table.setItem(index, 2, QTableWidgetItem(str(metal_type or '')))
            self.table.setItem(index, 3, QTableWidgetItem(str(quantity or '0')))
            self.table.setItem(index, 4, QTableWidgetItem(str(rate or '0')))
            self.table.setItem(index, 5, QTableWidgetItem(str(amount or '0')))

        self.summary.setText(f"Purchase rows loaded: {len(rows)}")
