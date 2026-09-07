import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from db import get_connection


class CustomerForm:
    def __init__(self, root):
        self.root = root
        self.root.title("Customer Management")
        self.root.geometry("520x620")
        self.root.resizable(False, False)

        self.customer_id = None

        self.build_ui()

    # ---------------- UI ----------------
    def build_ui(self):
        tk.Label(
            self.root,
            text="👤 Customer Details",
            font=("Arial", 16, "bold")
        ).pack(pady=10)

        form = tk.Frame(self.root, padx=20)
        form.pack(fill="both", expand=True)

        top_actions = tk.Frame(self.root)
        top_actions.pack(pady=5)

        tk.Button(
            top_actions,
            text="🔍 Load Customer",
            width=18,
            command=self.search_popup
        ).pack()


        def row(label, widget, r):
            tk.Label(form, text=label, anchor="w", width=15).grid(row=r, column=0, sticky="w", pady=6)
            widget.grid(row=r, column=1, pady=6, sticky="w")

        self.entry_code = tk.Entry(form, width=30, state="readonly")
        row("Customer Code", self.entry_code, 0)

        self.entry_name = tk.Entry(form, width=30)
        row("Full Name *", self.entry_name, 1)

        self.entry_phone = tk.Entry(form, width=30)
        row("Phone *", self.entry_phone, 2)

        self.entry_email = tk.Entry(form, width=30)
        row("Email", self.entry_email, 3)

        self.entry_line = tk.Entry(form, width=30)
        row("Line ID", self.entry_line, 4)

        self.entry_address = tk.Text(form, width=30, height=3)
        row("Address", self.entry_address, 5)

        self.entry_city = tk.Entry(form, width=30)
        row("City *", self.entry_city, 6)

        self.entry_state = tk.Entry(form, width=30)
        row("State", self.entry_state, 7)

        self.entry_pincode = tk.Entry(form, width=30)
        row("Pincode *", self.entry_pincode, 8)

        # Bottom Buttons
        btns = tk.Frame(self.root)
        btns.pack(pady=15)

        tk.Button(
            btns,
            text="💾 Save",
            width=12,
            bg="#4CAF50",
            fg="white",
            command=self.save_customer
        ).pack(side="left", padx=6)

        tk.Button(
            btns,
            text="⬆ Update",
            width=12,
            bg="#2196F3",
            fg="white",
            command=self.update_customer
        ).pack(side="left", padx=6)

        tk.Button(
            btns,
            text="🧹 Clear",
            width=12,
            bg="#FFC107",
            command=self.clear_form
        ).pack(side="left", padx=6)

        tk.Button(
            btns,
            text="🗑 Delete",
            width=12,
            bg="#F44336",
            fg="white",
            command=self.delete_customer
        ).pack(side="left", padx=6)

        tk.Button(
            btns,
            text="❌ Exit",
            width=12,
            command=self.root.destroy
        ).pack(side="left", padx=6)

    # ---------------- Save ----------------
    def save_customer(self):
        if not self.entry_name.get() or not self.entry_phone.get() \
           or not self.entry_city.get() or not self.entry_pincode.get():
            messagebox.showerror("Error", "Name, Phone, City & Pincode are required")
            return

        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO customers
            (full_name, phone, email, line_id, address, city, state, pincode)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING customer_id
        """, (
            self.entry_name.get(),
            self.entry_phone.get(),
            self.entry_email.get(),
            self.entry_line.get(),
            self.entry_address.get("1.0", "end").strip(),
            self.entry_city.get(),
            self.entry_state.get(),
            self.entry_pincode.get()
        ))

        cid = cur.fetchone()[0]
        code = f"CUST-{cid:06d}"

        cur.execute(
            "UPDATE customers SET customer_code=%s WHERE customer_id=%s",
            (code, cid)
        )

        conn.commit()
        conn.close()

        self.entry_code.config(state="normal")
        self.entry_code.delete(0, tk.END)
        self.entry_code.insert(0, code)
        self.entry_code.config(state="readonly")

        self.customer_id = cid
        messagebox.showinfo("Success", "Customer saved successfully")

    # ---------------- Update ----------------
    def update_customer(self):
        if not self.customer_id:
            return

        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            UPDATE customers SET
            full_name=%s, phone=%s, email=%s, line_id=%s,
            address=%s, city=%s, state=%s, pincode=%s,
            updated_at=NOW()
            WHERE customer_id=%s
        """, (
            self.entry_name.get(),
            self.entry_phone.get(),
            self.entry_email.get(),
            self.entry_line.get(),
            self.entry_address.get("1.0", "end").strip(),
            self.entry_city.get(),
            self.entry_state.get(),
            self.entry_pincode.get(),
            self.customer_id
        ))

        conn.commit()
        conn.close()
        messagebox.showinfo("Updated", "Customer updated successfully")

    # ---------------- Delete ----------------
    def delete_customer(self):
        if not self.customer_id:
            return

        if not messagebox.askyesno("Confirm", "Delete this customer?"):
            return

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM customers WHERE customer_id=%s", (self.customer_id,))
        conn.commit()
        conn.close()

        messagebox.showinfo("Deleted", "Customer removed")
        self.clear_form()

    # ---------------- Search Popup ----------------
    def search_popup(self):
        pop = tk.Toplevel(self.root)
        pop.title("Search Customer")
        pop.geometry("420x380")

        tk.Label(pop, text="Search (Name / Phone)").pack(pady=5)
        search_var = tk.StringVar()
        entry = tk.Entry(pop, textvariable=search_var, width=40)
        entry.pack()

        tree = ttk.Treeview(pop, columns=("id", "name", "phone"), show="headings")
        tree.heading("id", text="ID")
        tree.heading("name", text="Name")
        tree.heading("phone", text="Phone")
        tree.pack(fill="both", expand=True, pady=10)

        def load_list(*_):
            for i in tree.get_children():
                tree.delete(i)

            conn = get_connection()
            cur = conn.cursor()
            q = f"%{search_var.get()}%"
            cur.execute("""
                SELECT customer_id, full_name, phone
                FROM customers
                WHERE full_name ILIKE %s OR phone ILIKE %s
                ORDER BY full_name
            """, (q, q))
            for r in cur.fetchall():
                tree.insert("", "end", values=r)
            conn.close()

        search_var.trace_add("write", load_list)
        load_list()

        def load_selected():
            item = tree.focus()
            if not item:
                return
            cid = tree.item(item)["values"][0]
            self.load_customer(cid)
            pop.destroy()

        tk.Button(pop, text="Load", command=load_selected).pack(side="left", padx=20, pady=10)
        tk.Button(pop, text="Close", command=pop.destroy).pack(side="right", padx=20, pady=10)

    # ---------------- Load ----------------
    def load_customer(self, cid):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM customers WHERE customer_id=%s", (cid,))
        r = cur.fetchone()
        conn.close()

        self.customer_id = r[0]

        self.entry_code.config(state="normal")
        self.entry_code.delete(0, tk.END)
        self.entry_code.insert(0, r[1])
        self.entry_code.config(state="readonly")

        self.entry_name.delete(0, tk.END)
        self.entry_name.insert(0, r[2])

        self.entry_phone.delete(0, tk.END)
        self.entry_phone.insert(0, r[3])

        self.entry_email.delete(0, tk.END)
        self.entry_email.insert(0, r[4] or "")

        self.entry_line.delete(0, tk.END)
        self.entry_line.insert(0, r[5] or "")

        self.entry_address.delete("1.0", tk.END)
        self.entry_address.insert("1.0", r[6] or "")

        self.entry_city.delete(0, tk.END)
        self.entry_city.insert(0, r[7] or "")

        self.entry_state.delete(0, tk.END)
        self.entry_state.insert(0, r[8] or "")

        self.entry_pincode.delete(0, tk.END)
        self.entry_pincode.insert(0, r[9] or "")

    # ---------------- Clear ----------------
    def clear_form(self):
        self.customer_id = None
        for e in [
            self.entry_code, self.entry_name, self.entry_phone,
            self.entry_email, self.entry_line,
            self.entry_city, self.entry_state, self.entry_pincode
        ]:
            e.config(state="normal")
            e.delete(0, tk.END)
        self.entry_code.config(state="readonly")
        self.entry_address.delete("1.0", tk.END)

# ✅ Add this function to the END of add_customer.py
def open_add_customer_dialog(parent):
    """
    Standalone function to open add customer dialog and return result
    For use from all other modules
    """
    popup = tk.Toplevel(parent)
    popup.title("➕ Add New Customer")
    popup.transient(parent)
    popup.grab_set()
    
    form = CustomerForm(popup)
    
    result = None
    
    # Override exit button to return result
    original_destroy = popup.destroy
    def on_close():
        nonlocal result
        if form.customer_id:
            result = {
                "customer_id": form.customer_id,
                "customer_name": form.entry_name.get().strip().upper(),
                "customer_code": form.entry_code.get()
            }
        original_destroy()
    
    popup.protocol("WM_DELETE_WINDOW", on_close)
    
    popup.wait_window()
    return result


if __name__ == "__main__":
    root = tk.Tk()
    CustomerForm(root)
    root.mainloop()
