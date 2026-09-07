import tkinter as tk
from tksheet import Sheet

class ExcelForm(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Desktop Excel-like Form")
        self.geometry("800x500")

        # Sample Data
        headers = ["Product", "Price", "Quantity", "Category"]
        data = [
            ["Laptop", "1200", "5", "Electronics"],
            ["Coffee", "15", "100", "Food"],
            ["Desk", "250", "2", "Furniture"]
        ]

        # Create the Sheet
        self.sheet = Sheet(self, 
                           headers=headers,
                           data=data,
                           height=400, 
                           width=750)
        
        # Enable Excel-like features
        self.sheet.enable_bindings((
            "single_select",
            "row_select",
            "column_width_resize",
            "double_click_column_resize",
            "row_height_resize",
            "column_select",
            "drag_select",
            "edit_cell",     # Key feature: Edit each cell
            "rc_insert_row", # Right-click to add row
            "rc_delete_row", # Right-click to delete row
            "copy",
            "cut",
            "paste",
            "undo"
        ))

        self.sheet.pack(padx=20, pady=20, fill="both", expand=True)

        # Simple Filter Button
        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=10)
        
        tk.Label(btn_frame, text="Filter Category:").pack(side="left")
        self.filter_entry = tk.Entry(btn_frame)
        self.filter_entry.pack(side="left", padx=5)
        
        tk.Button(btn_frame, text="Apply Filter", command=self.apply_filter).pack(side="left")

    def apply_filter(self):
        target = self.filter_entry.get().lower()
        # Simple filtering logic: hide rows that don't match
        all_data = self.sheet.get_total_data()
        filtered_rows = [row for row in all_data if target in row[3].lower()]
        self.sheet.set_sheet_data(filtered_rows)

if __name__ == "__main__":
    app = ExcelForm()
    app.mainloop()