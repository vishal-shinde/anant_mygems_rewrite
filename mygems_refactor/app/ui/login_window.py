from PySide6.QtWidgets import QDialog, QFormLayout, QHBoxLayout, QLineEdit, QMessageBox, QPushButton

from app.services.auth_service import AuthService


class LoginWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MYGEMS Login")
        self.resize(420, 220)
        self._auth_service = AuthService()
        self.logged_in_user = None

        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)

        submit_button = QPushButton("Login")
        submit_button.clicked.connect(self.handle_login)

        form = QFormLayout()
        form.addRow("Username", self.username_input)
        form.addRow("Password", self.password_input)

        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(submit_button)

        layout = QFormLayout(self)
        layout.addRow(form)
        layout.addRow(actions)

    def handle_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            QMessageBox.warning(self, "Validation", "Username and password are required.")
            return

        try:
            user = self._auth_service.login(username, password)
        except Exception as exc:
            QMessageBox.critical(self, "Database error", f"Unable to connect to the database.\n\n{exc}")
            return

        if user is None:
            QMessageBox.critical(self, "Login failed", "Invalid username or password.")
            return

        self.logged_in_user = user
        QMessageBox.information(self, "Welcome", f"Welcome {user.full_name}!")
        self.accept()
