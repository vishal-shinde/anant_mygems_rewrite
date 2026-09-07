import tkinter as tk
from tkinter import ttk, messagebox
import bcrypt
from db import get_connection


class UserManagement:
    def __init__(self, root):
        self.root = root
        self.root.title("Admin - User Management")
        self.root.geometry("900x520")

        self.selected_user_id = None
        self.role_map = {}

        self.build_ui()
        self.load_roles()
        self.load_users()

    # ---------------- UI ----------------
    def build_ui(self):
        form = tk.Frame(self.root, padx=10, pady=10)
        form.pack(fill="x")

        tk.Label(form, text="Username").grid(row=0, column=0, sticky="w")
        self.entry_username = tk.Entry(form, width=25)
        self.entry_username.grid(row=0, column=1)

        tk.Label(form, text="Password").grid(row=0, column=2, sticky="w")
        self.entry_password = tk.Entry(form, show="*", width=25)
        self.entry_password.grid(row=0, column=3)

        tk.Label(form, text="Full Name").grid(row=1, column=0, sticky="w")
        self.entry_fullname = tk.Entry(form, width=25)
        self.entry_fullname.grid(row=1, column=1)

        tk.Label(form, text="Role").grid(row=1, column=2, sticky="w")
        self.combo_role = ttk.Combobox(form, state="readonly", width=23)
        self.combo_role.grid(row=1, column=3)

        self.var_active = tk.IntVar(value=1)
        tk.Checkbutton(form, text="Active", variable=self.var_active).grid(row=2, column=1, sticky="w")

        btns = tk.Frame(self.root)
        btns.pack(pady=10)

        tk.Button(btns, text="Create", width=12, command=self.create_user).pack(side="left", padx=5)
        tk.Button(btns, text="Update", width=12, command=self.update_user).pack(side="left", padx=5)
        tk.Button(btns, text="Delete", width=12, command=self.delete_user).pack(side="left", padx=5)
        tk.Button(btns, text="Clear", width=12, command=self.clear_form).pack(side="left", padx=5)

        self.tree = ttk.Treeview(
            self.root,
            columns=("id", "username", "name", "role", "active"),
            show="headings"
        )

        for col in self.tree["columns"]:
            self.tree.heading(col, text=col.upper())

        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_row_select)

    # ---------------- DB LOAD ----------------
    def load_roles(self):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT role_id, role_name FROM roles ORDER BY role_id")
        rows = cur.fetchall()
        conn.close()

        self.role_map = {r[1]: r[0] for r in rows}
        self.combo_role["values"] = list(self.role_map.keys())

    def load_users(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT u.user_id, u.username, u.full_name, r.role_name, u.is_active
            FROM users u
            JOIN roles r ON u.role_id = r.role_id
            ORDER BY u.user_id
        """)
        rows = cur.fetchall()
        conn.close()

        for row in rows:
            self.tree.insert("", "end", values=row)

    # ---------------- CRUD ----------------
    def create_user(self):
        username = self.entry_username.get().strip()
        password = self.entry_password.get()
        full_name = self.entry_fullname.get().strip()
        role_name = self.combo_role.get()
        is_active = True if self.var_active.get() == 1 else False

        if not username or not password or not role_name:
            messagebox.showerror("Error", "Username, Password & Role required")
            return

        role_id = self.role_map[role_name]
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO users (username, password_hash, full_name, role_id, is_active)
                VALUES (%s, %s, %s, %s, %s)
            """, (username, password_hash, full_name, role_id, is_active))
            conn.commit()
            messagebox.showinfo("Success", "User created successfully")
            self.load_users()
            self.clear_form()
        except Exception as e:
            messagebox.showerror("Error", str(e))
        finally:
            conn.close()

    def update_user(self):
        if not self.selected_user_id:
            messagebox.showwarning("Select", "Select a user first")
            return

        full_name = self.entry_fullname.get().strip()
        role_id = self.role_map[self.combo_role.get()]
        is_active = True if self.var_active.get() == 1 else False

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE users
            SET full_name=%s,
                role_id=%s,
                is_active=%s
            WHERE user_id=%s
        """, (full_name, role_id, is_active, self.selected_user_id))
        conn.commit()
        conn.close()

        messagebox.showinfo("Updated", "User updated successfully")
        self.load_users()

    def delete_user(self):
        if not self.selected_user_id:
            return

        if not messagebox.askyesno("Confirm", "Delete this user?"):
            return

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE user_id=%s", (self.selected_user_id,))
        conn.commit()
        conn.close()

        self.load_users()
        self.clear_form()

    # ---------------- Helpers ----------------
    def on_row_select(self, _):
        row = self.tree.item(self.tree.focus())["values"]
        if not row:
            return

        self.selected_user_id = row[0]
        self.entry_username.delete(0, tk.END)
        self.entry_username.insert(0, row[1])
        self.entry_fullname.delete(0, tk.END)
        self.entry_fullname.insert(0, row[2])
        self.combo_role.set(row[3])
        self.var_active.set(1 if row[4] else 0)

    def clear_form(self):
        self.selected_user_id = None
        self.entry_username.delete(0, tk.END)
        self.entry_password.delete(0, tk.END)
        self.entry_fullname.delete(0, tk.END)
        self.combo_role.set("")
        self.var_active.set(1)


if __name__ == "__main__":
    root = tk.Tk()
    UserManagement(root)
    root.mainloop()
