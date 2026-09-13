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

from app.services.vendor_service import VendorService


class VendorWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.service = VendorService()
        self.setWindowTitle("Vendors")
        self.resize(900, 520)

        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        title = QLabel("Vendors")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        self.refresh_btn = QPushButton("Refresh")
        self.new_btn = QPushButton("Add Vendor")
        header.addWidget(self.refresh_btn)
        header.addWidget(self.new_btn)
        layout.addLayout(header)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["ID", "Vendor", "Phone", "Email", "Address", "Active"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(self.table.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        self.form = QWidget()
        form_layout = QFormLayout(self.form)
        self.name_input = QLineEdit()
        self.phone_input = QLineEdit()
        self.email_input = QLineEdit()
        self.address_input = QLineEdit()
        form_layout.addRow("Vendor Name:", self.name_input)
        form_layout.addRow("Phone:", self.phone_input)
        form_layout.addRow("Email:", self.email_input)
        form_layout.addRow("Address:", self.address_input)
        self.save_btn = QPushButton("Save Vendor")
        form_layout.addRow(self.save_btn)
        layout.addWidget(self.form)

        self.refresh_btn.clicked.connect(self.load_vendors)
        self.new_btn.clicked.connect(self.reset_form)
        self.save_btn.clicked.connect(self.save_vendor)

        self.load_vendors()

    def reset_form(self):
        self.name_input.clear()
        self.phone_input.clear()
        self.email_input.clear()
        self.address_input.clear()
        self.name_input.setFocus()

    def load_vendors(self):
        try:
            records = self.service.list_vendors()
            self.table.setRowCount(len(records))
            for row_index, row in enumerate(records):
                values = [
                    str(row[0]),
                    row[1] or "",
                    row[2] or "",
                    row[3] or "",
                    row[4] or "",
                    "Yes" if row[5] else "No",
                ]
                for col_index, value in enumerate(values):
                    self.table.setItem(row_index, col_index, QTableWidgetItem(value))
        except Exception as exc:
            QMessageBox.critical(self, "Load Error", f"Unable to load vendors: {exc}")

    def save_vendor(self):
        try:
            self.service.create_vendor(
                vendor_name=self.name_input.text(),
                phone=self.phone_input.text() or None,
                email=self.email_input.text() or None,
                address=self.address_input.text() or None,
            )
            QMessageBox.information(self, "Success", "Vendor saved successfully.")
            self.reset_form()
            self.load_vendors()
        except ValueError as exc:
            QMessageBox.warning(self, "Validation Error", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", f"Unable to save vendor: {exc}")
