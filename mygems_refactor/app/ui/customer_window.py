from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QLineEdit,
    QMessageBox,
    QFormLayout,
    QHeaderView,
)

from app.services.customer_service import CustomerService


class CustomerWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.service = CustomerService()
        self.setWindowTitle("Customers")
        self.resize(900, 520)

        main_layout = QVBoxLayout(self)

        header_layout = QHBoxLayout()
        title = QLabel("Customers")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.refresh_btn = QPushButton("Refresh")
        self.add_btn = QPushButton("Add Customer")
        header_layout.addWidget(self.refresh_btn)
        header_layout.addWidget(self.add_btn)
        main_layout.addLayout(header_layout)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Phone", "Email", "City", "GST", "Active"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(self.table.EditTrigger.NoEditTriggers)
        main_layout.addWidget(self.table)

        self.form_widget = QWidget()
        form_layout = QFormLayout(self.form_widget)
        self.name_input = QLineEdit()
        self.phone_input = QLineEdit()
        self.email_input = QLineEdit()
        self.city_input = QLineEdit()
        self.gst_input = QLineEdit()
        self.address_input = QLineEdit()

        form_layout.addRow("Customer Name:", self.name_input)
        form_layout.addRow("Phone:", self.phone_input)
        form_layout.addRow("Email:", self.email_input)
        form_layout.addRow("City:", self.city_input)
        form_layout.addRow("GST:", self.gst_input)
        form_layout.addRow("Address:", self.address_input)

        self.save_btn = QPushButton("Save Customer")
        form_layout.addRow(self.save_btn)
        main_layout.addWidget(self.form_widget)

        self.refresh_btn.clicked.connect(self.load_customers)
        self.add_btn.clicked.connect(self.reset_form)
        self.save_btn.clicked.connect(self.save_customer)

        self.load_customers()

    def reset_form(self):
        self.name_input.clear()
        self.phone_input.clear()
        self.email_input.clear()
        self.city_input.clear()
        self.gst_input.clear()
        self.address_input.clear()
        self.name_input.setFocus()

    def load_customers(self):
        try:
            records = self.service.list_customers()
            self.table.setRowCount(len(records))
            for row_index, row in enumerate(records):
                values = [
                    str(row[0]),
                    row[1] or "",
                    row[2] or "",
                    row[3] or "",
                    row[4] or "",
                    row[5] or "",
                    "Yes" if row[6] else "No",
                ]
                for col_index, value in enumerate(values):
                    self.table.setItem(row_index, col_index, QTableWidgetItem(value))
        except Exception as exc:
            QMessageBox.critical(self, "Load Error", f"Unable to load customers: {exc}")

    def save_customer(self):
        try:
            self.service.create_customer(
                customer_name=self.name_input.text(),
                phone=self.phone_input.text() or None,
                email=self.email_input.text() or None,
                address=self.address_input.text() or None,
                city=self.city_input.text() or None,
                gst_no=self.gst_input.text() or None,
            )
            QMessageBox.information(self, "Success", "Customer saved successfully.")
            self.reset_form()
            self.load_customers()
        except ValueError as exc:
            QMessageBox.warning(self, "Validation Error", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", f"Unable to save customer: {exc}")
