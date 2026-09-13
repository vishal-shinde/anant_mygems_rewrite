from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.user_service import UserService


class UserManagementWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("User Management")
        self.resize(900, 520)
        self.service = UserService()
        self.selected_user_id = None

        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.full_name_input = QLineEdit()
        self.role_combo = QComboBox()
        self.active_checkbox = QComboBox()
        self.active_checkbox.addItems(["Active", "Inactive"])
        self.active_checkbox.setCurrentIndex(0)

        submit_button = QPushButton("Create")
        update_button = QPushButton("Update")
        delete_button = QPushButton("Delete")
        clear_button = QPushButton("Clear")

        submit_button.clicked.connect(self.create_user)
        update_button.clicked.connect(self.update_user)
        delete_button.clicked.connect(self.delete_user)
        clear_button.clicked.connect(self.clear_form)

        form = QFormLayout()
        form.addRow("Username", self.username_input)
        form.addRow("Password", self.password_input)
        form.addRow("Full Name", self.full_name_input)
        form.addRow("Role", self.role_combo)
        form.addRow("Status", self.active_checkbox)

        buttons = QHBoxLayout()
        buttons.addWidget(submit_button)
        buttons.addWidget(update_button)
        buttons.addWidget(delete_button)
        buttons.addWidget(clear_button)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "Username", "Full Name", "Role", "Active"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self.on_row_select)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addWidget(self.table)

        self.load_roles()
        self.load_users()

    def load_roles(self):
        try:
            rows = self.service.list_roles()
        except Exception:
            rows = []

        self.role_combo.clear()
        if not rows:
            self.role_combo.addItem("No roles loaded", None)
            return

        for role_id, role_name in rows:
            self.role_combo.addItem(role_name, role_id)

    def load_users(self):
        try:
            rows = self.service.list_users()
        except Exception:
            rows = []

        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            user_id, username, full_name, role_name, is_active = row
            self.table.setItem(row_index, 0, QTableWidgetItem(str(user_id)))
            self.table.setItem(row_index, 1, QTableWidgetItem(username))
            self.table.setItem(row_index, 2, QTableWidgetItem(full_name))
            self.table.setItem(row_index, 3, QTableWidgetItem(role_name))
            self.table.setItem(row_index, 4, QTableWidgetItem("Yes" if is_active else "No"))

    def create_user(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()
        full_name = self.full_name_input.text().strip()
        role_id = self.role_combo.currentData()
        is_active = self.active_checkbox.currentIndex() == 0

        if not username or not password or not full_name or role_id is None:
            QMessageBox.warning(self, "Validation", "Username, password, full name, and role are required.")
            return

        try:
            self.service.create_user(username, password, full_name, int(role_id), is_active)
            self.load_users()
            self.clear_form()
            QMessageBox.information(self, "Success", "User created successfully.")
        except Exception as exc:  # pragma: no cover - UI validation path
            QMessageBox.critical(self, "Error", str(exc))

    def update_user(self):
        if self.selected_user_id is None:
            QMessageBox.warning(self, "Select a user", "Select a user first.")
            return

        full_name = self.full_name_input.text().strip()
        role_id = self.role_combo.currentData()
        is_active = self.active_checkbox.currentIndex() == 0

        if not full_name or role_id is None:
            QMessageBox.warning(self, "Validation", "Full name and role are required.")
            return

        try:
            self.service.update_user(int(self.selected_user_id), full_name, int(role_id), is_active)
            self.load_users()
            QMessageBox.information(self, "Success", "User updated successfully.")
        except Exception as exc:  # pragma: no cover - UI validation path
            QMessageBox.critical(self, "Error", str(exc))

    def delete_user(self):
        if self.selected_user_id is None:
            QMessageBox.warning(self, "Select a user", "Select a user first.")
            return

        reply = QMessageBox.question(self, "Confirm", "Delete this user?")
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self.service.delete_user(int(self.selected_user_id))
            self.clear_form()
            self.load_users()
            QMessageBox.information(self, "Success", "User deleted successfully.")
        except Exception as exc:  # pragma: no cover - UI validation path
            QMessageBox.critical(self, "Error", str(exc))

    def on_row_select(self):
        selected = self.table.selectedItems()
        if not selected:
            return

        row_index = self.table.currentRow()
        self.selected_user_id = self.table.item(row_index, 0).text()
        self.username_input.setText(self.table.item(row_index, 1).text())
        self.full_name_input.setText(self.table.item(row_index, 2).text())
        self.role_combo.setCurrentText(self.table.item(row_index, 3).text())
        self.active_checkbox.setCurrentIndex(0 if self.table.item(row_index, 4).text() == "Yes" else 1)
        self.password_input.clear()

    def clear_form(self):
        self.selected_user_id = None
        self.username_input.clear()
        self.password_input.clear()
        self.full_name_input.clear()
        self.role_combo.setCurrentIndex(0)
        self.active_checkbox.setCurrentIndex(0)
        self.table.clearSelection()
