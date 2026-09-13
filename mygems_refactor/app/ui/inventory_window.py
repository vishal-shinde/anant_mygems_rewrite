from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialog,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.services.inventory_service import InventoryService
from app.ui.inventory_form_window import InventoryFormWindow


class InventoryWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Inventory")
        self.resize(1000, 650)
        self.service = InventoryService()

        self.summary_label = QLabel()
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Lot No", "Item Code", "Metal", "Weight", "Status", "Purchase ID"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        add_action = QAction("Add Item", self)
        add_action.triggered.connect(self.open_form)

        toolbar = self.addAction(add_action)
        _ = toolbar

        layout = QVBoxLayout(self)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.table)

        self.load_data()

    def open_form(self):
        self.form_window = InventoryFormWindow(self)
        self.form_window.show()

    def load_data(self):
        summary = self.service.get_stock_summary()
        self.summary_label.setText(
            f"Available stock: Gold={summary.get('gold', 0)} | Silver={summary.get('silver', 0)}"
        )

        rows = self.service.get_stock_rows(200)
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            lot_no, item_code, metal_type, current_weight, status, purchase_id = ((row + (None,))[:6])
            self.table.setItem(index, 0, QTableWidgetItem(str(lot_no or '')))
            self.table.setItem(index, 1, QTableWidgetItem(str(item_code or '')))
            self.table.setItem(index, 2, QTableWidgetItem(str(metal_type or '')))
            self.table.setItem(index, 3, QTableWidgetItem(str(current_weight or '')))
            self.table.setItem(index, 4, QTableWidgetItem(str(status or '')))
            self.table.setItem(index, 5, QTableWidgetItem(str(purchase_id or '')))
