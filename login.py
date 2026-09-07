import tkinter as tk
from tkinter import messagebox
import bcrypt
from db import get_connection

class LoginForm:
    def __init__(self, root):
        self.root = root
        self.root.title("MYGEMS Login")
        self.root.geometry("350x250")

        tk.Label(root, text="Username").pack(pady=5)
        self.username_entry = tk.Entry(root)
        self.username_entry.pack()

        tk.Label(root, text="Password").pack(pady=5)
        self.password_entry = tk.Entry(root, show="*")
        self.password_entry.pack()

        tk.Button(root, text="Login", command=self.login).pack(pady=20)

    def login(self):
        username = self.username_entry.get()
        password = self.password_entry.get()

        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT user_id, password_hash, role_id
            FROM users
            WHERE username=%s AND is_active=TRUE
        """, (username,))

        user = cur.fetchone()
        cur.close()
        conn.close()

        if not user:
            messagebox.showerror("Error", "Invalid username")
            return

        user_id, password_hash, role_id = user

        if bcrypt.checkpw(password.encode(), password_hash.encode()):
            messagebox.showinfo("Success", "Login successful!")
            print("Logged in User ID:", user_id)
            print("Role ID:", role_id)
            self.root.destroy()
            # Next: open main dashboard
        else:
            messagebox.showerror("Error", "Wrong password")

if __name__ == "__main__":
    root = tk.Tk()
    LoginForm(root)
    root.mainloop()
