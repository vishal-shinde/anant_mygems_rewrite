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
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.services.payment_service import PaymentService


class PaymentEntryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Record Payment")
        self.resize(420, 220)
        self.service = PaymentService()

        form_layout = QFormLayout(self)
        self.order_id_input = QSpinBox()
        self.order_id_input.setRange(1, 1000000000)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["CASH", "CARD", "UPI", "BANK_TRANSFER"])
        self.amount_input = QDoubleSpinBox()
        self.amount_input.setRange(0, 1000000000)
        self.amount_input.setDecimals(2)
        self.amount_input.setValue(0)

        form_layout.addRow("Order ID:", self.order_id_input)
        form_layout.addRow("Mode:", self.mode_combo)
        form_layout.addRow("Amount:", self.amount_input)

        buttons = QHBoxLayout()
        save_btn = QPushButton("Save Payment")
        cancel_btn = QPushButton("Cancel")
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        form_layout.addRow(buttons)

        save_btn.clicked.connect(self.save)
        cancel_btn.clicked.connect(self.reject)

    def save(self):
        try:
            self.service.create_payment(
                order_id=int(self.order_id_input.value()),
                payment_mode=self.mode_combo.currentText(),
                amount=float(self.amount_input.value()),
            )
            QMessageBox.information(self, "Success", "Payment recorded successfully.")
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", f"Unable to record payment: {exc}")


class PaymentWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Payments")
        self.resize(900, 600)
        self.service = PaymentService()

        self.summary = QLabel("Recent payments")
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Payment ID", "Order ID", "Mode", "Amount", "Date", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        add_btn = QPushButton("Record Payment")
        add_btn.clicked.connect(self.open_entry_form)

        layout = QVBoxLayout(self)
        layout.addWidget(self.summary)
        layout.addWidget(add_btn)
        layout.addWidget(self.table)

        self.load_data()

    def open_entry_form(self):
        dialog = PaymentEntryDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_data()

    def load_data(self):
        rows = self.service.get_recent_payments()
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            if len(row) >= 6:
                payment_id, order_id, payment_mode, amount, paid_on, status = row
            else:
                payment_id, order_id, payment_mode, amount, paid_on, status = (*row, None, None)[:6]

            self.table.setItem(index, 0, QTableWidgetItem(str(payment_id or '')))
            self.table.setItem(index, 1, QTableWidgetItem(str(order_id or '')))
            self.table.setItem(index, 2, QTableWidgetItem(str(payment_mode or '')))
            self.table.setItem(index, 3, QTableWidgetItem(str(amount or '0')))
            self.table.setItem(index, 4, QTableWidgetItem(str(paid_on or '')))
            self.table.setItem(index, 5, QTableWidgetItem(str(status or '')))

        self.summary.setText(f"Payments loaded: {len(rows)}")
