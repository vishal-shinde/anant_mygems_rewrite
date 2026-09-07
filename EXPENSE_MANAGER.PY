import customtkinter as ctk
from tkinter import messagebox, ttk
import psycopg2
from datetime import datetime

# =========================
# CONFIGURATION
# =========================
DB_CONFIG = {
    "host": "localhost",
    "database": "mygems",
    "user": "myuser",
    "password": "28116",
    "port": "5432"
}

# =========================
# APP SETTINGS
# =========================
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# =========================
# DATABASE CLASS
# =========================
class DatabaseManager:
    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id SERIAL PRIMARY KEY,
                category_name VARCHAR(100) UNIQUE NOT NULL
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id SERIAL PRIMARY KEY,
                expense_name VARCHAR(255) NOT NULL,
                category_id INTEGER REFERENCES categories(id),
                amount NUMERIC(12,2) NOT NULL,
                expense_date DATE NOT NULL,
                notes TEXT
            )
        """)

        self.conn.commit()

    # -----------------------------
    # CATEGORY FUNCTIONS
    # -----------------------------
    def add_category(self, category_name):
        try:
            self.cursor.execute(
                "INSERT INTO categories (category_name) VALUES (%s)",
                (category_name,)
            )
            self.conn.commit()
            return True
        except Exception as e:
            self.conn.rollback()
            print(e)
            return False

    def get_categories(self):
        self.cursor.execute("SELECT id, category_name FROM categories ORDER BY category_name")
        return self.cursor.fetchall()

    # -----------------------------
    # EXPENSE FUNCTIONS
    # -----------------------------
    def add_expense(self, expense_name, category_id, amount, expense_date, notes):
        self.cursor.execute("""
            INSERT INTO expenses
            (expense_name, category_id, amount, expense_date, notes)
            VALUES (%s, %s, %s, %s, %s)
        """, (expense_name, category_id, amount, expense_date, notes))

        self.conn.commit()

    def get_expenses(self):
        self.cursor.execute("""
            SELECT
                e.id,
                e.expense_name,
                c.category_name,
                e.amount,
                e.expense_date,
                e.notes
            FROM expenses e
            LEFT JOIN categories c ON e.category_id = c.id
            ORDER BY e.id DESC
        """)

        return self.cursor.fetchall()

    def get_total_expense(self):
        self.cursor.execute("SELECT COALESCE(SUM(amount),0) FROM expenses")
        return self.cursor.fetchone()[0]


# =========================
# MAIN APPLICATION
# =========================
class JewelryERPApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.db = DatabaseManager()

        self.title("💎 Jewelry ERP System")
        self.geometry("1200x700")
        self.configure(fg_color="#0f172a")

        self.create_sidebar()
        self.create_dashboard()
        self.create_expense_form()
        self.create_expense_table()

        self.load_categories()
        self.load_expenses()
        self.update_total_expense()

    # =========================
    # SIDEBAR
    # =========================
    def create_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color="#1e293b")
        self.sidebar.pack(side="left", fill="y")

        title = ctk.CTkLabel(
            self.sidebar,
            text="💎 Jewelry ERP",
            font=("Arial", 24, "bold"),
            text_color="#38bdf8"
        )
        title.pack(pady=30)

        info = ctk.CTkLabel(
            self.sidebar,
            text="Expense Management\nPostgreSQL Database",
            font=("Arial", 14),
            text_color="#f8fafc"
        )
        info.pack(pady=10)

    # =========================
    # DASHBOARD
    # =========================
    def create_dashboard(self):
        self.dashboard_frame = ctk.CTkFrame(self, fg_color="#0f172a")
        self.dashboard_frame.pack(fill="x", padx=20, pady=20)

        self.total_card = ctk.CTkFrame(
            self.dashboard_frame,
            width=300,
            height=120,
            corner_radius=20,
            fg_color="#7c3aed"
        )
        self.total_card.pack(side="left", padx=10)

        self.total_label = ctk.CTkLabel(
            self.total_card,
            text="Total Expenses",
            font=("Arial", 20, "bold"),
            text_color="white"
        )
        self.total_label.pack(pady=(20, 5))

        self.total_amount_label = ctk.CTkLabel(
            self.total_card,
            text="₹0.00",
            font=("Arial", 28, "bold"),
            text_color="#facc15"
        )
        self.total_amount_label.pack()

    # =========================
    # EXPENSE FORM
    # =========================
    def create_expense_form(self):
        self.form_frame = ctk.CTkFrame(self, fg_color="#111827", corner_radius=20)
        self.form_frame.pack(fill="x", padx=20, pady=10)

        title = ctk.CTkLabel(
            self.form_frame,
            text="➕ Add Jewelry Expense",
            font=("Arial", 22, "bold"),
            text_color="#22d3ee"
        )
        title.grid(row=0, column=0, columnspan=4, pady=20)

        # Expense Name
        self.expense_name_entry = ctk.CTkEntry(
            self.form_frame,
            placeholder_text="Expense Name",
            width=250,
            height=40
        )
        self.expense_name_entry.grid(row=1, column=0, padx=15, pady=10)

        # Category
        self.category_combo = ctk.CTkComboBox(
            self.form_frame,
            width=200,
            height=40,
            values=[]
        )
        self.category_combo.grid(row=1, column=1, padx=15, pady=10)

        # Amount
        self.amount_entry = ctk.CTkEntry(
            self.form_frame,
            placeholder_text="Amount",
            width=200,
            height=40
        )
        self.amount_entry.grid(row=1, column=2, padx=15, pady=10)

        # Date
        self.date_entry = ctk.CTkEntry(
            self.form_frame,
            placeholder_text="YYYY-MM-DD",
            width=200,
            height=40
        )
        self.date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.date_entry.grid(row=1, column=3, padx=15, pady=10)

        # Notes
        self.notes_entry = ctk.CTkTextbox(
            self.form_frame,
            width=700,
            height=100
        )
        self.notes_entry.grid(row=2, column=0, columnspan=4, padx=15, pady=10)

        # Buttons
        add_expense_btn = ctk.CTkButton(
            self.form_frame,
            text="💾 Save Expense",
            fg_color="#16a34a",
            hover_color="#15803d",
            font=("Arial", 16, "bold"),
            command=self.save_expense,
            width=180,
            height=45
        )
        add_expense_btn.grid(row=3, column=0, pady=20)

        add_category_btn = ctk.CTkButton(
            self.form_frame,
            text="📂 Add Category",
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            font=("Arial", 16, "bold"),
            command=self.open_category_popup,
            width=180,
            height=45
        )
        add_category_btn.grid(row=3, column=1, pady=20)

    # =========================
    # EXPENSE TABLE
    # =========================
    def create_expense_table(self):
        self.table_frame = ctk.CTkFrame(self, fg_color="#111827", corner_radius=20)
        self.table_frame.pack(fill="both", expand=True, padx=20, pady=20)

        title = ctk.CTkLabel(
            self.table_frame,
            text="📊 Expense Records",
            font=("Arial", 22, "bold"),
            text_color="#f97316"
        )
        title.pack(pady=15)

        columns = ("ID", "Expense", "Category", "Amount", "Date", "Notes")

        style = ttk.Style()
        style.theme_use("default")

        style.configure(
            "Treeview",
            background="#1e293b",
            foreground="white",
            rowheight=30,
            fieldbackground="#1e293b",
            font=("Arial", 11)
        )

        style.configure(
            "Treeview.Heading",
            background="#0ea5e9",
            foreground="white",
            font=("Arial", 12, "bold")
        )

        self.tree = ttk.Treeview(self.table_frame, columns=columns, show="headings")

        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, anchor="center", width=150)

        self.tree.pack(fill="both", expand=True, padx=15, pady=15)

    # =========================
    # CATEGORY POPUP
    # =========================
    def open_category_popup(self):
        popup = ctk.CTkToplevel(self)
        popup.title("Add Category")
        popup.geometry("400x200")
        popup.configure(fg_color="#111827")

        label = ctk.CTkLabel(
            popup,
            text="Enter Category Name",
            font=("Arial", 18, "bold")
        )
        label.pack(pady=20)

        category_entry = ctk.CTkEntry(popup, width=250, height=40)
        category_entry.pack(pady=10)

        def save_category():
            category_name = category_entry.get()

            if category_name.strip() == "":
                messagebox.showerror("Error", "Category name is required")
                return

            success = self.db.add_category(category_name)

            if success:
                messagebox.showinfo("Success", "Category added successfully")
                self.load_categories()
                popup.destroy()
            else:
                messagebox.showerror("Error", "Category already exists")

        btn = ctk.CTkButton(
            popup,
            text="Save Category",
            command=save_category,
            fg_color="#7c3aed",
            hover_color="#6d28d9"
        )
        btn.pack(pady=20)

    # =========================
    # LOAD CATEGORIES
    # =========================
    def load_categories(self):
        categories = self.db.get_categories()

        self.category_map = {}
        category_names = []

        for cat in categories:
            self.category_map[cat[1]] = cat[0]
            category_names.append(cat[1])

        self.category_combo.configure(values=category_names)

        if category_names:
            self.category_combo.set(category_names[0])

    # =========================
    # SAVE EXPENSE
    # =========================
    def save_expense(self):
        try:
            expense_name = self.expense_name_entry.get()
            category_name = self.category_combo.get()
            amount = float(self.amount_entry.get())
            expense_date = self.date_entry.get()
            notes = self.notes_entry.get("1.0", "end").strip()

            if expense_name.strip() == "":
                messagebox.showerror("Error", "Expense name is required")
                return

            category_id = self.category_map.get(category_name)

            self.db.add_expense(
                expense_name,
                category_id,
                amount,
                expense_date,
                notes
            )

            messagebox.showinfo("Success", "Expense added successfully")

            self.clear_form()
            self.load_expenses()
            self.update_total_expense()

        except ValueError:
            messagebox.showerror("Error", "Amount must be numeric")

        except Exception as e:
            messagebox.showerror("Error", str(e))

    # =========================
    # LOAD EXPENSES
    # =========================
    def load_expenses(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        expenses = self.db.get_expenses()

        for expense in expenses:
            self.tree.insert("", "end", values=expense)

    # =========================
    # UPDATE TOTAL
    # =========================
    def update_total_expense(self):
        total = self.db.get_total_expense()
        self.total_amount_label.configure(text=f"₹ {total:,.2f}")

    # =========================
    # CLEAR FORM
    # =========================
    def clear_form(self):
        self.expense_name_entry.delete(0, "end")
        self.amount_entry.delete(0, "end")
        self.notes_entry.delete("1.0", "end")


# =========================
# RUN APPLICATION
# =========================
if __name__ == "__main__":
    app = JewelryERPApp()
    app.mainloop()


# ==========================================
# REQUIRED INSTALLATION COMMANDS
# ==========================================
# pip install customtkinter
# pip install psycopg2
#
# ==========================================
# CREATE POSTGRES DATABASE
# ==========================================
# CREATE DATABASE jewelry_erp;
#
# Then update DB_CONFIG password.
# ==========================================
