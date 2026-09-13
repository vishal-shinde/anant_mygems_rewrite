from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget


class StockWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stock")
        self.resize(900, 600)

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.addWidget(QLabel("Stock dashboard placeholder"))
        self.setCentralWidget(container)
