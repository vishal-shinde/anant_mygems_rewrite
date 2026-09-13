import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from app.services.dashboard_service import DashboardService
from app.services.system_service import SystemService
from app.ui.dashboard_window import DashboardWindow
from app.ui.login_window import LoginWindow


class App:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("MYGEMS")

    def run(self):
        db_ok, db_error = SystemService().check_database()
        if not db_ok:
            QMessageBox.critical(
                None,
                "Database connection failed",
                f"Unable to connect to the PostgreSQL database.\n\n{db_error}\n\nUpdate the .env file with the correct database credentials.",
            )
            return

        login = LoginWindow()
        result = login.exec()
        if result != 1:
            return

        summary = {}
        try:
            summary = DashboardService().get_dashboard_summary()
        except Exception:
            summary = {"user_count": 0, "role_count": 0}

        main_window = DashboardWindow(user=login.logged_in_user, summary=summary)
        main_window.show()
        sys.exit(self.app.exec())


if __name__ == "__main__":
    App().run()
