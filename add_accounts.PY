import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import psycopg2


# ---------------- DATABASE CONNECTION ----------------
def get_connection():
    return psycopg2.connect(
        host="localhost",
        database="mygems",
        user="myuser",
        password="28116"
    )


# ---------------- MAIN APPLICATION ----------------
class AccountMaster(tb.Window):

    def __init__(self):
        super().__init__(themename="flatly")

        self.title("Account Master")
        self.geometry("950x800")
        self.resizable(False, False)

        self.selected_account_id = None

        self.build_ui()
        self.load_types()

    # ---------------- UI ----------------
    def build_ui(self):

        main = tb.Frame(self, padding=15)
        main.pack(fill=BOTH, expand=True)

        # ---------------- HEADER ----------------
        header_frame = tb.Frame(main)
        header_frame.pack(fill=X, pady=(0, 15))

        # ICON (emoji version – safe & clean)
        icon_label = tb.Label(
            header_frame,
            text="🏦",
            font=("Segoe UI Emoji", 20)
        )
        icon_label.pack(side=LEFT)

        # TITLE TEXT
        title_label = tb.Label(
            header_frame,
            text="ADD ACCOUNTS",
            font=("Segoe UI", 18, "bold")
        )
        title_label.pack(side=LEFT, padx=10)

        # Separator line
        tb.Separator(main, bootstyle="secondary").pack(fill=X, pady=(5, 15))

        # ---------------- SEARCH BUTTON ----------------
        top_frame = tb.Frame(main)
        top_frame.pack(fill=X)

        tb.Button(
            top_frame,
            text="🔍 SEARCH EXISTING ACCOUNT",
            bootstyle="info-outline",
            width=28,
            command=self.open_search_window
        ).pack(anchor="e", pady=(0, 10))

        # ---------------- SCROLLABLE FORM AREA ----------------
        canvas = tk.Canvas(main, highlightthickness=0)
        scrollbar = tb.Scrollbar(main, orient="vertical", command=canvas.yview)

        scroll_frame = tb.Frame(canvas)

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        form = scroll_frame

        row = 0

        # ---------------- ACCOUNT TYPE ----------------
        tb.Label(form, text="Account Type").grid(row=row, column=0, sticky=W, pady=8)

        self.type_combo = tb.Combobox(form, width=45, state="readonly")
        self.type_combo.grid(row=row, column=1, pady=8)
        self.type_combo.bind("<<ComboboxSelected>>", self.on_type_change)

        tb.Button(form, text="+", width=3,
                  command=self.add_type_popup).grid(row=row, column=2)
        row += 1

        # ---------------- SUB TYPE ----------------
        tb.Label(form, text="Sub Type").grid(row=row, column=0, sticky=W, pady=8)

        self.subtype_combo = tb.Combobox(form, width=45, state="readonly")
        self.subtype_combo.grid(row=row, column=1, pady=8)

        tb.Button(form, text="+", width=3,
                  command=self.add_subtype_popup).grid(row=row, column=2)
        row += 1

        # ---------------- DYNAMIC NAME ----------------
        self.account_name_label = tb.Label(form, text="Account Name")
        self.account_name_label.grid(row=row, column=0, sticky=W, pady=8)
        
        self.account_name_entry = tb.Entry(form, width=48)
        self.account_name_entry.grid(row=row, column=1, pady=8)
        self.account_name_entry.bind(
            "<KeyRelease>",
            self.force_uppercase
        )
        row += 1

        # ---------------- OTHER FIELDS ----------------
        self.entries = {}

        fields = [
            "Short Name",
            "Phone",
            "LINE ID",
            "Email",
            "Address",
            "Account Number",
            "Account Holder"
        ]

        for field in fields:
            tb.Label(form, text=field).grid(row=row, column=0, sticky=W, pady=8)
            entry = tb.Entry(form, width=48)
            entry.grid(row=row, column=1, pady=8)
            self.account_name_entry.bind(
                "<KeyRelease>",
                self.force_uppercase
            )
            self.entries[field] = entry
            row += 1
            

        # ---------------- BUTTONS ----------------
        btn_frame = tb.Frame(form)
        btn_frame.grid(row=row, column=0, columnspan=3, pady=30)

        tb.Button(btn_frame, text="Save",
                  bootstyle=SUCCESS, width=12,
                  command=self.save_account).grid(row=0, column=0, padx=5)

        tb.Button(btn_frame, text="Update",
                  bootstyle=PRIMARY, width=12,
                  command=self.update_account).grid(row=0, column=1, padx=5)

        tb.Button(btn_frame, text="Delete",
                  bootstyle=DANGER, width=12,
                  command=self.delete_account).grid(row=0, column=2, padx=5)

        tb.Button(btn_frame, text="Clear",
                  bootstyle=WARNING, width=12,
                  command=self.clear_form).grid(row=0, column=3, padx=5)

        tb.Button(btn_frame, text="Exit",
                  bootstyle=SECONDARY, width=12,
                  command=self.destroy).grid(row=0, column=4, padx=5)

    # ---------------- FORCE UPPERCASE ----------------
    def force_uppercase(self, event):
        widget = event.widget

        if isinstance(widget, tk.Entry):
            current_text = widget.get()
            cursor_pos = widget.index(INSERT)

            widget.delete(0, END)
            widget.insert(0, current_text.upper())

            widget.icursor(cursor_pos)
            
    # ---------------- LOAD TYPES ----------------
    def load_types(self):
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT type_name FROM account_types ORDER BY type_name")
            rows = cur.fetchall()
            conn.close()
            self.type_combo["values"] = [r[0] for r in rows]
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ---------------- TYPE CHANGE ----------------
    def on_type_change(self, event=None):
        self.load_subtypes()
        if self.type_combo.get():
            self.account_name_label.config(
                text=f"{self.type_combo.get()} Name"
            )
        else:
            self.account_name_label.config(text="Account Name")

    # ---------------- LOAD SUBTYPES ----------------
    def load_subtypes(self):
        if not self.type_combo.get():
            return

        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT type_id FROM account_types WHERE type_name=%s",
                (self.type_combo.get(),)
            )
            type_id = cur.fetchone()[0]

            cur.execute("""
                SELECT sub_type_name
                FROM account_sub_types
                WHERE type_id=%s
                ORDER BY sub_type_name
            """, (type_id,))

            rows = cur.fetchall()
            conn.close()

            self.subtype_combo["values"] = [r[0] for r in rows]
            self.subtype_combo.set("")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ---------------- SAVE ----------------
    def save_account(self):

        if not self.account_name_entry.get().strip():
            messagebox.showwarning("Warning", "Account Name is required")
            return

        if not self.entries["Short Name"].get().strip():
            messagebox.showwarning("Warning", "Short Name is required")
            return

        if not self.entries["Phone"].get().strip():
            messagebox.showwarning("Warning", "Phone Number is required")
            return

        try:
            conn = get_connection()
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO accounts
                (
                    account_name,
                    short_name,
                    type_id,
                    subtype_id,
                    phone_number,
                    line_id,
                    email,
                    address,
                    account_number,
                    account_holder_name
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING account_id
            """, (
                self.account_name_entry.get().strip(),
                self.entries["Short Name"].get().strip(),
                self.get_type_id(),
                self.get_subtype_id(),
                self.entries["Phone"].get().strip(),
                self.entries["LINE ID"].get() or None,
                self.entries["Email"].get() or None,
                self.entries["Address"].get() or None,
                self.entries["Account Number"].get() or None,
                self.entries["Account Holder"].get() or None
            ))

            self.selected_account_id = cur.fetchone()[0]

            conn.commit()
            conn.close()

            self.clear_form()

            messagebox.showinfo("Success", "Account saved successfully")

        except Exception as e:
            messagebox.showerror("Error", str(e))
            
    
    # ---------------- UPDATE ----------------
    def update_account(self):

        # ---------------- REQUIRED FIELD VALIDATION ----------------

        if not self.account_name_entry.get().strip():
            messagebox.showwarning(
                "Validation Error",
                "Account Name is required"
            )
            self.account_name_entry.focus()
            return

        if not self.entries["Short Name"].get().strip():
            messagebox.showwarning(
                "Validation Error",
                "Short Name is required"
            )
            self.entries["Short Name"].focus()
            return

        if not self.entries["Phone"].get().strip():
            messagebox.showwarning(
                "Validation Error",
                "Phone Number is required"
            )
            self.entries["Phone"].focus()
            return
        try:
            conn = get_connection()
            cur = conn.cursor()

            cur.execute("""
                UPDATE accounts
                SET
                    account_name=%s,
                    short_name=%s,
                    type_id=%s,
                    subtype_id=%s,
                    phone_number=%s,
                    line_id=%s,
                    email=%s,
                    address=%s,
                    account_number=%s,
                    account_holder_name=%s
                WHERE account_id=%s
            """, (
                self.account_name_entry.get(),
                self.entries["Short Name"].get(),
                self.get_type_id(),
                self.get_subtype_id(),
                self.entries["Phone"].get(),
                self.entries["LINE ID"].get(),
                self.entries["Email"].get(),
                self.entries["Address"].get(),
                self.entries["Account Number"].get(),
                self.entries["Account Holder"].get(),
                self.selected_account_id
            ))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Account updated")

        except Exception as e:
            messagebox.showerror("Error", str(e))
            
    # ---------------- DELETE ----------------
    def delete_account(self):

        if not self.selected_account_id:
            return

        if not messagebox.askyesno("Confirm", "Delete this account?"):
            return

        try:
            conn = get_connection()
            cur = conn.cursor()

            cur.execute(
                "DELETE FROM accounts WHERE account_id=%s",
                (self.selected_account_id,)
            )

            conn.commit()
            conn.close()

            self.clear_form()

            messagebox.showinfo("Success", "Account deleted")

        except Exception as e:
            messagebox.showerror("Error", str(e))
    # ---------------- SEARCH WINDOW ----------------
    def open_search_window(self):

        win = tb.Toplevel(self)
        win.title("Search Accounts")
        win.geometry("700x500")
        win.grab_set()

        filter_frame = tb.Frame(win)
        filter_frame.pack(fill=X, padx=10, pady=10)

        tb.Label(filter_frame, text="Filter by Type").pack(side=LEFT)

        type_filter = tb.Combobox(filter_frame, width=30, state="readonly")
        type_filter.pack(side=LEFT, padx=10)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT type_name FROM account_types ORDER BY type_name")
        rows = cur.fetchall()
        conn.close()

        type_filter["values"] = ["All"] + [r[0] for r in rows]
        type_filter.set("All")

        tree = ttk.Treeview(win, columns=("ID", "Name", "Type"), show="headings")
        tree.heading("ID", text="ID")
        tree.heading("Name", text="Name")
        tree.heading("Type", text="Type")
        tree.pack(fill=BOTH, expand=True, padx=10, pady=10)

        def load(filter_type="All"):
            for r in tree.get_children():
                tree.delete(r)

            conn = get_connection()
            cur = conn.cursor()

            if filter_type == "All":
                cur.execute("""
                    SELECT a.account_id,
                           a.account_name,
                           COALESCE(at.type_name,'')
                    FROM accounts a
                    LEFT JOIN account_types at
                    ON a.type_id = at.type_id
                """)
            else:
                cur.execute("""
                    SELECT a.account_id,
                           a.account_name,
                           at.type_name
                    FROM accounts a
                    JOIN account_types at
                    ON a.type_id = at.type_id
                    WHERE at.type_name=%s
                """, (filter_type,))

            for row in cur.fetchall():
                tree.insert("", END, values=row)

            conn.close()

        load()

        type_filter.bind("<<ComboboxSelected>>",
                         lambda e: load(type_filter.get()))

        def select(event):
            item = tree.focus()
            if not item:
                return
            self.selected_account_id = tree.item(item)["values"][0]
            win.destroy()
            self.load_selected_account()

        tree.bind("<Double-1>", select)


    # ---------------- LOAD SELECTED ACCOUNT ----------------
    def load_selected_account(self):

        try:
            conn = get_connection()
            cur = conn.cursor()

            cur.execute("""
                SELECT
                    account_name,
                    short_name,
                    phone_number,
                    line_id,
                    email,
                    address,
                    account_number,
                    account_holder_name,
                    at.type_name,
                    ast.sub_type_name
                FROM accounts a
                LEFT JOIN account_types at
                    ON a.type_id = at.type_id
                LEFT JOIN account_sub_types ast
                    ON a.subtype_id = ast.sub_type_id
                WHERE a.account_id=%s
            """, (self.selected_account_id,))

            data = cur.fetchone()

            conn.close()

            if not data:
                return

            self.account_name_entry.delete(0, END)
            self.account_name_entry.insert(0, data[0])

            for key, value in zip(self.entries.keys(), data[1:8]):
                self.entries[key].delete(0, END)

                if value:
                    self.entries[key].insert(0, value)

            self.type_combo.set(data[8])

            self.on_type_change()

            if data[9]:
                self.subtype_combo.set(data[9])

        except Exception as e:
            messagebox.showerror("Error", str(e))
    # ---------------- HELPERS ----------------
    def get_type_id(self):
        if not self.type_combo.get():
            return None
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT type_id FROM account_types WHERE type_name=%s",
                    (self.type_combo.get(),))
        r = cur.fetchone()
        conn.close()
        return r[0] if r else None

    def get_subtype_id(self):
        if not self.subtype_combo.get():
            return None
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT sub_type_id FROM account_sub_types WHERE sub_type_name=%s",
                    (self.subtype_combo.get(),))
        r = cur.fetchone()
        conn.close()
        return r[0] if r else None

    def clear_form(self):
        self.account_name_entry.delete(0, END)
        for e in self.entries.values():
            e.delete(0, END)
        self.type_combo.set("")
        self.subtype_combo.set("")
        self.account_name_label.config(text="Account Name")
        self.selected_account_id = None

    # ---------------- POPUPS ----------------
    def add_type_popup(self):
        win = tb.Toplevel(self)
        win.title("Add Account Type")
        win.geometry("300x150")
        win.grab_set()

        tb.Label(win, text="Type Name").pack(pady=10)
        entry = tb.Entry(win)
        entry.pack()

        def save():
            if not entry.get().strip():
                return
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO account_types (type_name)
                VALUES (%s)
                ON CONFLICT DO NOTHING
            """, (entry.get().strip(),))
            conn.commit()
            conn.close()
            self.load_types()
            win.destroy()

        tb.Button(win, text="Save", command=save).pack(pady=10)

    def add_subtype_popup(self):
        if not self.type_combo.get():
            messagebox.showwarning("Warning", "Select type first")
            return

        win = tb.Toplevel(self)
        win.title("Add Sub Type")
        win.geometry("300x150")
        win.grab_set()

        tb.Label(win, text="Sub Type Name").pack(pady=10)
        entry = tb.Entry(win)
        entry.pack()

        def save():
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT type_id FROM account_types WHERE type_name=%s",
                        (self.type_combo.get(),))
            type_id = cur.fetchone()[0]

            cur.execute("""
                INSERT INTO account_sub_types (type_id, sub_type_name)
                VALUES (%s,%s)
                ON CONFLICT DO NOTHING
            """, (type_id, entry.get().strip()))
            conn.commit()
            conn.close()
            self.load_subtypes()
            win.destroy()

        tb.Button(win, text="Save", command=save).pack(pady=10)


# ---------------- RUN ----------------
if __name__ == "__main__":
    app = AccountMaster()
    app.mainloop()
