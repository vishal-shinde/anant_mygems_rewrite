#!/usr/bin/env python3
import os
import tkinter as tk
from tkinter import Menu
import sys
import subprocess
from tkinter import messagebox

try:
    from PIL import Image, ImageTk
    PIL_OK = True
except ImportError:
    PIL_OK = False

class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command=None, width=165, height=38,
                 radius=18, bg="#2e8bc0", fg="white",
                 hover_bg="#1f6fa5", font=("Segoe UI", 10, "bold")):
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=parent["bg"] if "bg" in parent.keys() else "#0f2740",
            highlightthickness=0,
            bd=0
        )

        self.command = command
        self.normal_bg = bg
        self.hover_bg = hover_bg
        self.fg = fg
        self.radius = radius
        self.width = width
        self.height = height
        self.text = text
        self.font = font

        self._draw_button(self.normal_bg)

        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _rounded_rect_points(self, x1, y1, x2, y2, r):
        return [
            x1+r, y1,
            x2-r, y1,
            x2, y1,
            x2, y1+r,
            x2, y2-r,
            x2, y2,
            x2-r, y2,
            x1+r, y2,
            x1, y2,
            x1, y2-r,
            x1, y1+r,
            x1, y1
        ]

    def _draw_button(self, color):
        self.delete("all")
        r = self.radius
        w = self.width
        h = self.height

        self.create_polygon(
            self._rounded_rect_points(2, 2, w-2, h-2, r),
            smooth=True,
            fill=color,
            outline=""
        )

        self.create_text(
            w//2, h//2,
            text=self.text,
            fill=self.fg,
            font=self.font
        )

    def _on_click(self, event):
        if self.command:
            self.command()

    def _on_enter(self, event):
        self.config(cursor="hand2")
        self._draw_button(self.hover_bg)

    def _on_leave(self, event):
        self._draw_button(self.normal_bg)

        
class InventoryApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("MyGems Inventory Management System")
        self.root.geometry("1400x800")
        self.root.minsize(1100, 650)

        # Colors
        self.navy = "#0f2740"
        self.dark_navy = "#0a1b2d"
        self.mid_blue = "#6d89a8"
        self.white = "#ffffff"
        self.light_text = "#d9e7f5"
        self.accent = "#9dc8f0"
        self.button_bg = "#ffffff"
        self.button_fg = "#0f2740"
        self.button_active = "#d9ecff"
        
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        
        self.file_map = {
            "Metal Purchase": os.path.join(BASE_DIR, "metal_purchase-WITH SPLIT LOT.py"),
            "Stone Purchase": os.path.join(BASE_DIR, "stone_purchase.py"),
            "Job Assign": os.path.join(BASE_DIR, "job_transaction.py"),
            "Metal Transfer": os.path.join(BASE_DIR, "metal_transfer-3.py"),
            "Stone Lot Mixing": os.path.join(BASE_DIR, "stone_mixing.py"),
            "Add Labor": os.path.join(BASE_DIR, "add_labor.py"),
            "Add Expense": os.path.join(BASE_DIR, "add_expense.py"),
            "View": os.path.join(BASE_DIR, "view.py"),
            "Add User": os.path.join(BASE_DIR, "add_user.py"),
            "Permissions": os.path.join(BASE_DIR, "permissions.py"),
        }

        # Background image
        self.bg_path = "logo.jpg"
        self.original_bg = None
        self.bg_tk = None

        if PIL_OK and os.path.exists(self.bg_path):
            self.original_bg = Image.open(self.bg_path).convert("RGBA")

        self.button_defs = [
            "Metal Purchase",
            "Job Assign",
            "Add Labor",
            "Add Sales",
            "View Stock",
            "Print Cert"
        ]

        self.button_windows = []
        self.buttons = []

        self._create_menu_bar()
        self._create_footer()
        self._create_main_canvas()
        self._create_left_buttons()

        self._bind_shortcuts()

    def _create_menu_bar(self):
        menubar = Menu(self.root, tearoff=0)

        purchase_menu = Menu(menubar, tearoff=0)
        purchase_menu.add_command(label="Metal Purchase", command=lambda: self.action("Metal Purchase"))
        purchase_menu.add_command(label="Stone Purchase", command=lambda: self.action("Stone Purchase"))
        menubar.add_cascade(label="New Purchase", menu=purchase_menu)

        lot_menu = Menu(menubar, tearoff=0)
        lot_menu.add_command(label="Metal Transfer", command=lambda: self.action("Metal Transfer"))
        lot_menu.add_command(label="Stone Lot Mixing", command=lambda: self.action("Stone Lot Mixing"))
        menubar.add_cascade(label="LOT MIXING", menu=lot_menu)

        expense_menu = Menu(menubar, tearoff=0)
        expense_menu.add_command(label="Add Labor", command=lambda: self.action("Add Labor"))
        expense_menu.add_command(label="Add Expense", command=lambda: self.action("Add Expense"))
        menubar.add_cascade(label="EXPENSE", menu=expense_menu)

        view_menu = Menu(menubar, tearoff=0)
        view_menu.add_command(label="Refresh", command=lambda: self.action("View"))
        menubar.add_cascade(label="VIEW", menu=view_menu)

        admin_menu = Menu(menubar, tearoff=0)
        admin_menu.add_command(label="Add User", command=lambda: self.action("Add User"))
        admin_menu.add_command(label="Permissions", command=lambda: self.action("Permissions"))
        menubar.add_cascade(label="ADMIN", menu=admin_menu)

        self.root.config(menu=menubar)

    def _create_footer(self):
        self.footer = tk.Frame(self.root, bg=self.dark_navy, height=42)
        self.footer.pack(side="bottom", fill="x")
        self.footer.pack_propagate(False)

        tk.Label(
            self.footer,
            text="© Created and developed by Anant Soni",
            bg=self.dark_navy,
            fg=self.white,
            font=("Segoe UI", 11)
        ).pack(expand=True)

    def _create_main_canvas(self):
        self.canvas = tk.Canvas(
            self.root,
            bg=self.navy,
            highlightthickness=0,
            bd=0
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self._draw_layout)

    def _create_left_buttons(self):
        button_data = [
            ("Metal Purchase", "#2e86de", "#1b6fc2"),
            ("Job Assign", "#20bf6b", "#179b56"),
            ("Add Labor", "#f39c12", "#d68910"),
            ("Add Sales", "#8e44ad", "#6c3483"),
            ("View Stock", "#16a085", "#117a65"),
            ("Print Cert", "#c0392b", "#922b21"),
        ]

        self.button_windows = []
        self.buttons = []

        for text, color, hover in button_data:
            btn = RoundedButton(
                self.canvas,
                text=text,
                command=lambda t=text: self.action(t),
                width=170,
                height=38,
                radius=18,
                bg=color,
                hover_bg=hover,
                fg="white",
                font=("Segoe UI", 10, "bold")
            )
            win_id = self.canvas.create_window(0, 0, window=btn, anchor="n")
            self.buttons.append(btn)
            self.button_windows.append(win_id)

    def _draw_layout(self, event=None):
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()

        if w < 10 or h < 10:
            return

        self.canvas.delete("paint")

        top_h = int(h * 0.80)
        split_x = int(w * 0.40)

        self._draw_background(w, h)

        # subtle separators only
        self.canvas.create_line(
            split_x, 25, split_x, top_h - 20,
            fill=self.mid_blue, width=1, tags="paint"
        )
        self.canvas.create_line(
            25, top_h, w - 25, top_h,
            fill=self.mid_blue, width=1, tags="paint"
        )

        # titles
        self.canvas.create_text(
            35, 28,
            text="QUICK ACTIONS",
            anchor="nw",
            fill=self.white,
            font=("Segoe UI", 16, "bold"),
            tags="paint"
        )

        self.canvas.create_text(
            split_x + 35, 28,
            text="NOTIFICATIONS / REPORTS",
            anchor="nw",
            fill=self.white,
            font=("Segoe UI", 16, "bold"),
            tags="paint"
        )

        # right side placeholder text
        right_text = (
            "Notifications and reports will be displayed here.\n\n"
            "Examples:\n"
            "• Daily sales summary\n"
            "• Pending jobs\n"
            "• Stock alerts\n"
            "• Certificate print status\n"
            "• Expense overview"
        )

        self.canvas.create_text(
            split_x + 35, 80,
            text=right_text,
            anchor="nw",
            fill=self.light_text,
            font=("Segoe UI", 11),
            width=w - split_x - 70,
            justify="left",
            tags="paint"
        )

        # bottom helper area
        self.canvas.create_rectangle(
            0, top_h, w, h,
            fill=self.dark_navy,
            outline="",
            tags="paint"
        )

        self.canvas.create_text(
            25, top_h + 16,
            text="HELPER",
            anchor="nw",
            fill=self.white,
            font=("Segoe UI", 13, "bold"),
            tags="paint"
        )

        helper_text = (
            "Quick Buttons: Metal Purchase  |  Job Assign  |  Add Labor  |  "
            "Add Sales  |  View Stock  |  Print Cert"
        )

        self.canvas.create_text(
            w // 2, top_h + ((h - top_h) // 2) + 8,
            text=helper_text,
            fill=self.accent,
            font=("Segoe UI", 11, "bold"),
            width=w - 80,
            justify="center",
            tags="paint"
        )

        # place left buttons
        button_start_y = 100
        gap_y = 52
        left_center_x = split_x // 2

        for i, win_id in enumerate(self.button_windows):
            self.canvas.coords(win_id, left_center_x, button_start_y + (i * gap_y))

        # keep background/separators behind buttons
        self.canvas.tag_lower("paint")

    def _draw_background(self, w, h):
        if self.original_bg:
            img = self.original_bg.resize((w, h), Image.LANCZOS)

            # more faded overlay
            overlay = Image.new("RGBA", (w, h), (10, 27, 45, 185))
            img = Image.alpha_composite(img, overlay)

            self.bg_tk = ImageTk.PhotoImage(img)
            self.canvas.create_image(0, 0, anchor="nw", image=self.bg_tk, tags="paint")
        else:
            self.canvas.create_rectangle(0, 0, w, h, fill=self.navy, outline="", tags="paint")

            # soft faded effect if image not available
            self.canvas.create_oval(
                -int(w * 0.18), -int(h * 0.20),
                int(w * 0.55), int(h * 0.70),
                fill="#173754", outline="", tags="paint"
            )
            self.canvas.create_oval(
                int(w * 0.22), int(h * 0.10),
                int(w * 0.95), int(h * 0.95),
                fill="#0c1f33", outline="", tags="paint"
            )


    def _bind_shortcuts(self):
        self.root.bind("<F1>", lambda e: self.action("Metal Purchase"))
        self.root.bind("<F5>", lambda e: self.action("Job Assign"))
        self.root.bind("<F3>", lambda e: self.action("Add Labor"))
        self.root.bind("<F7>", lambda e: self.action("Add Sales"))
        self.root.bind("<F2>", lambda e: self.action("View Stock"))
        self.root.bind("<F12>", lambda e: self.action("Print Cert"))


    def action(self, name):
        file_path = self.file_map.get(name)

        if not file_path:
            messagebox.showerror("Error", f"No file mapped for: {name}")
            return

        if not os.path.exists(file_path):
            messagebox.showerror("File Not Found", f"File does not exist:\n{file_path}")
            return

        try:
            subprocess.Popen([sys.executable, file_path])
        except Exception as e:
            messagebox.showerror("Open Error", f"Could not open file.\n\n{e}")

    
    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = InventoryApp()
    app.run()
