from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
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
from app.services.job_service import JobService


class JobEntryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Job")
        self.resize(480, 240)
        self.service = JobService()
        self.customer_service = CustomerService()

        form_layout = QFormLayout(self)
        self.customer_combo = QComboBox()
        self.customer_combo.addItem("Select customer", -1)
        for customer_id, customer_name, *_ in self.customer_service.list_customers():
            self.customer_combo.addItem(f"{customer_id} - {customer_name}", customer_id)

        self.job_code_input = QLineEdit()
        self.job_type_input = QLineEdit()
        self.assignee_input = QLineEdit()

        form_layout.addRow("Customer:", self.customer_combo)
        form_layout.addRow("Job Code:", self.job_code_input)
        form_layout.addRow("Job Type:", self.job_type_input)
        form_layout.addRow("Assigned To:", self.assignee_input)

        buttons = QHBoxLayout()
        save_btn = QPushButton("Save Job")
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

        customer_name = self.customer_combo.currentText().split(" - ", 1)[-1] if " - " in self.customer_combo.currentText() else ""
        try:
            self.service.create_job(
                job_code=self.job_code_input.text(),
                customer_id=int(customer_id),
                customer_name=customer_name,
                job_type=self.job_type_input.text(),
                assigned_to=self.assignee_input.text() or None,
            )
            QMessageBox.information(self, "Success", "Job created successfully.")
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", f"Unable to create job: {exc}")


class JobWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Job Assign")
        self.resize(1000, 650)
        self.service = JobService()

        self.summary = QLabel("Recent jobs")
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Job ID", "Job Code", "Customer", "Status", "Assigned To"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        add_btn = QPushButton("Create Job")
        add_btn.clicked.connect(self.open_entry_form)

        layout = QVBoxLayout(self)
        layout.addWidget(self.summary)
        layout.addWidget(add_btn)
        layout.addWidget(self.table)

        self.load_data()

    def open_entry_form(self):
        dialog = JobEntryDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_data()

    def load_data(self):
        rows = self.service.get_jobs()
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            if len(row) >= 5:
                job_id, job_code, customer_name, status, assigned_to = row
            else:
                job_id, job_code, customer_name, status, assigned_to = (*row, None, None)[:5]

            self.table.setItem(index, 0, QTableWidgetItem(str(job_id or '')))
            self.table.setItem(index, 1, QTableWidgetItem(str(job_code or '')))
            self.table.setItem(index, 2, QTableWidgetItem(str(customer_name or '')))
            self.table.setItem(index, 3, QTableWidgetItem(str(status or '')))
            self.table.setItem(index, 4, QTableWidgetItem(str(assigned_to or '')))

        self.summary.setText(f"Jobs loaded: {len(rows)}")
