from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.services.inventory_service import InventoryService


class InventoryFormWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Inventory Item")
        self.resize(500, 320)
        self.service = InventoryService()

        self.item_type_combo = QComboBox()
        self.item_type_combo.addItems(["Gold", "Silver"])

        self.lot_no_input = QLineEdit()
        self.item_code_input = QLineEdit()
        self.weight_input = QLineEdit()
        self.purity_input = QLineEdit()
        self.status_combo = QComboBox()
        self.status_combo.addItems(["AVAILABLE", "MFG", "SOLD", "CANCELLED"])

        save_button = QPushButton("Save")
        save_button.clicked.connect(self.create_item)

        form = QFormLayout()
        form.addRow("Metal", self.item_type_combo)
        form.addRow("Lot No", self.lot_no_input)
        form.addRow("Item Code", self.item_code_input)
        form.addRow("Weight", self.weight_input)
        form.addRow("Purity", self.purity_input)
        form.addRow("Status", self.status_combo)

        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(save_button)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Inventory Entry"))
        layout.addLayout(form)
        layout.addLayout(actions)

    def create_item(self):
        item_type = self.item_type_combo.currentText()
        lot_no = self.lot_no_input.text().strip()
        item_code = self.item_code_input.text().strip()
        weight = self.weight_input.text().strip()
        purity = self.purity_input.text().strip()
        status = self.status_combo.currentText()

        if not lot_no or not item_code or not weight:
            QMessageBox.warning(self, "Validation", "Lot number, item code, and weight are required.")
            return

        try:
            result = self.service.create_inventory_item(
                item_type=item_type,
                lot_no=lot_no,
                item_code=item_code,
                current_weight=float(weight),
                purity=float(purity) if purity else 0.0,
                status=status,
            )
            if result is None:
                raise RuntimeError("Inventory insert failed")
            QMessageBox.information(self, "Success", "Inventory item added successfully.")
            self.close()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
