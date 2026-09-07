import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk
import os
import psycopg2

DB_CONFIG = {
    "host": "localhost",
    "dbname": "mygems",
    "user": "myuser",
    "password": "28116"
}


class EmployeeForm:

    def __init__(self, root):

        self.root = root
        self.root.title("Employee Management")
        self.root.geometry("720x650")
        self.root.resizable(False, False)

        self.current_code = None
        self.roles = []

        self.photo_path = None
        self.photo_image = None
        
        bg = "#f4f6fb"
        primary = "#2C7BE5"

        root.configure(bg=bg)

        title = tk.Label(
            root,
            text="Employee Management System",
            font=("Segoe UI", 18, "bold"),
            bg=bg,
            fg=primary
        )
        title.pack(pady=15)

        form = tk.Frame(root, bg="white", bd=1, relief="solid")
        form.pack(padx=20, pady=10, fill="both")

        form.grid_columnconfigure(0, weight=1)
        form.grid_columnconfigure(1, weight=0)

        left_form = tk.Frame(form, bg="white")
        left_form.grid(row=0, column=0, padx=10, pady=10, sticky="n")

        right_form = tk.Frame(form, bg="white")
        right_form.grid(row=0, column=1, padx=20, pady=10, sticky="n")

        # LEFT SIDE (EMPLOYEE DETAILS)

        self._row(left_form, 0, "Employee Code", readonly=True)
        self._row(left_form, 1, "Full Name")
        self._row(left_form, 2, "Nickname")
        self._row(left_form, 3, "Basic Salary")

        tk.Label(left_form, text="Role", bg="white").grid(row=4, column=0, sticky="e", pady=6)
        self.role_cb = ttk.Combobox(left_form, state="readonly", width=30)
        self.role_cb.grid(row=4, column=1, pady=6)

        self._row(left_form, 5, "Phone")
        self._row(left_form, 6, "Line ID")
        self._row(left_form, 7, "SSID")
        self._row(left_form, 8, "Email")

        tk.Label(left_form, text="Address", bg="white").grid(row=9, column=0, sticky="e", pady=6)

        self.address = tk.Text(left_form, width=32, height=3)
        self.address.grid(row=9, column=1, pady=6)

        # RIGHT SIDE (PHOTO)

        tk.Label(
            right_form,
            text="Employee Photo",
            bg="white",
            font=("Segoe UI", 10, "bold")
        ).pack(pady=5)

        photo_frame = tk.Frame(right_form, width=120, height=120, bg="#ddd")
        photo_frame.pack(pady=5)
        photo_frame.pack_propagate(False)

        self.photo_label = tk.Label(photo_frame, bg="#eee")
        self.photo_label.pack(fill="both", expand=True)
        
        tk.Button(
            right_form,
            text="Select Photo",
            command=self.select_photo,
            width=15
        ).pack(pady=5)

        
        btn_frame = tk.Frame(root, bg=bg)
        btn_frame.pack(pady=20)

        self.button(btn_frame, "Save", "#28a745", self.save_employee)
        self.button(btn_frame, "Search", "#17a2b8", self.search_popup)
        self.button(btn_frame, "Delete", "#dc3545", self.delete_employee)
        self.button(btn_frame, "Clear", "#ffc107", self.clear_form)
        self.button(btn_frame, "Exit", "#6c757d", root.destroy)

        self.load_roles()

    def button(self, frame, text, color, cmd):

        tk.Button(
            frame,
            text=text,
            width=10,
            bg=color,
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            command=cmd
        ).pack(side="left", padx=6)

    def _row(self, parent, r, label, readonly=False):

        tk.Label(parent, text=label, bg="white").grid(row=r, column=0, sticky="e", pady=6, padx=5)

        e = tk.Entry(parent, width=32, state="readonly" if readonly else "normal")

        e.grid(row=r, column=1, pady=6, padx=5)

        setattr(self, label.replace(" ", "_").lower(), e)

    def connect(self):
        return psycopg2.connect(**DB_CONFIG)

    def generate_employee_code(self, cur):
        cur.execute("SELECT generate_employee_code()")
        return cur.fetchone()[0]

    def load_roles(self):

        conn = self.connect()
        cur = conn.cursor()

        cur.execute("SELECT role_name FROM roles ORDER BY role_name")

        self.roles = [r[0] for r in cur.fetchall()]

        conn.close()

        self.role_cb["values"] = self.roles

        if self.roles:
            self.role_cb.current(0)

    def select_photo(self):

        file_path = filedialog.askopenfilename(
            title="Select Employee Photo",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.gif")]
        )

        if file_path:
            self.photo_path = file_path

            img = Image.open(file_path)

            # Resize image properly
            img = img.resize((180, 180), Image.LANCZOS)

            self.photo_image = ImageTk.PhotoImage(img)

            self.photo_label.config(image=self.photo_image, text="")
            
    def save_employee(self):

        role = self.role_cb.get().strip()
        salary = self.basic_salary.get().strip()

        if not role:
            messagebox.showerror("Error", "Role must be selected")
            return

        if not salary:
            messagebox.showerror("Error", "Salary must be entered")
            return

        data = (
            self.full_name.get().strip(),
            self.nickname.get().strip(),
            role,
            self.phone.get().strip(),
            self.line_id.get().strip(),
            self.ssid.get().strip(),
            self.email.get().strip(),
            self.address.get("1.0", "end").strip(),
            self.photo_path
        )

        if not data[0]:
            messagebox.showerror("Missing", "Employee name required")
            return

        conn = self.connect()
        cur = conn.cursor()

        try:

            if self.current_code:

                cur.execute("""
                    UPDATE employees
                    SET full_name=%s,nickname=%s,role=%s,phone=%s,
                        line_id=%s,ssid=%s,email=%s,address=%s,photo_path=%s
                    WHERE emp_code=%s
                """, (*data, self.current_code))

                cur.execute("SELECT employee_id FROM employees WHERE emp_code=%s",(self.current_code,))
                emp_id = cur.fetchone()[0]

            else:

                code = self.generate_employee_code(cur)

                cur.execute("""
                    INSERT INTO employees
                    (emp_code,full_name,nickname,role,phone,line_id,ssid,email,address,photo_path)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (code, *data))

                self.employee_code.config(state="normal")
                self.employee_code.insert(0, code)
                self.employee_code.config(state="readonly")

                cur.execute("SELECT employee_id FROM employees WHERE emp_code=%s",(code,))
                emp_id = cur.fetchone()[0]

            # check latest salary
            cur.execute("""
            SELECT basic_salary
            FROM employee_salary_history
            WHERE employee_id=%s
            ORDER BY effective_from DESC
            LIMIT 1
            """,(emp_id,))

            last_salary = cur.fetchone()

            if not last_salary or float(last_salary[0]) != float(salary):

                cur.execute("""
                INSERT INTO employee_salary_history
                (employee_id,basic_salary,effective_from,increment_reason)
                VALUES (%s,%s,CURRENT_DATE,'Salary Update')
                """,(emp_id,salary))

            conn.commit()

            messagebox.showinfo("Success", "Employee saved successfully")

            self.clear_form()

        except Exception as e:

            conn.rollback()

            messagebox.showerror("Database Error", str(e))

        finally:
            conn.close()

    def search_popup(self):

        popup = tk.Toplevel(self.root)

        popup.title("Search Employee")

        popup.geometry("480x320")

        tk.Label(popup, text="Search Employee").pack(pady=10)

        search_var = tk.StringVar()

        entry = tk.Entry(popup, textvariable=search_var, width=40)

        entry.pack()

        lb = tk.Listbox(popup, width=60)

        lb.pack(pady=10)

        conn = self.connect()

        cur = conn.cursor()

        cur.execute("""
        SELECT emp_code,full_name,nickname,phone
        FROM employees
        ORDER BY full_name
        """)

        rows = cur.fetchall()

        conn.close()

        def refresh(*_):

            lb.delete(0, tk.END)

            key = search_var.get().lower()

            for code, name, nick, phone in rows:

                text = f"{name} ({code})"

                blob = f"{name} {nick or ''} {phone or ''}".lower()

                if key in blob:
                    lb.insert(tk.END, text)

        search_var.trace_add("write", refresh)

        refresh()

        def load_selected():

            if not lb.curselection():
                return

            selected = lb.get(lb.curselection()[0])

            code = selected.split("(")[-1].replace(")", "").strip()

            popup.destroy()

            self.load_employee(code)

        tk.Button(popup, text="Load", command=load_selected).pack()

    def load_employee(self, code):

        conn = self.connect()

        cur = conn.cursor()

        cur.execute("""
        SELECT 
        e.emp_code,
        e.full_name,
        e.nickname,
        e.role,
        e.phone,
        e.line_id,
        e.ssid,
        e.email,
        e.address,
        e.photo_path,
        s.basic_salary
        FROM employees e
        LEFT JOIN employee_salary_history s
        ON e.employee_id = s.employee_id
        WHERE e.emp_code=%s
        ORDER BY s.effective_from DESC
        LIMIT 1
        """,(code,))

        r = cur.fetchone()

        conn.close()

        if not r:
            return

        self.clear_form()

        self.current_code = r[0]

        self.employee_code.config(state="normal")
        self.employee_code.insert(0, r[0])
        self.employee_code.config(state="readonly")

        self.full_name.insert(0, r[1])
        self.nickname.insert(0, r[2] or "")
        self.role_cb.set(r[3])
        self.phone.insert(0, r[4] or "")
        self.line_id.insert(0, r[5] or "")
        self.ssid.insert(0, r[6] or "")
        self.email.insert(0, r[7] or "")
        self.address.insert("1.0", r[8] or "")
        self.photo_path = r[9]

        if self.photo_path and os.path.exists(self.photo_path):

            frame_size = 110

            img = Image.open(self.photo_path)

            img.thumbnail((frame_size, frame_size), Image.LANCZOS)

            # Create square background
            bg = Image.new("RGB", (frame_size, frame_size), (240,240,240))

            x = (frame_size - img.width) // 2
            y = (frame_size - img.height) // 2

            bg.paste(img, (x, y))

            self.photo_image = ImageTk.PhotoImage(bg)

            self.photo_label.config(image=self.photo_image, text="")

        else:
            self.photo_label.config(image="", text="No Photo")

        self.basic_salary.delete(0, tk.END)

        if r[10]:
            self.basic_salary.insert(0, r[10])
              
    
    def delete_employee(self):

        if not self.current_code:
            return

        if not messagebox.askyesno("Confirm", "Delete employee?"):
            return

        conn = self.connect()

        cur = conn.cursor()

        cur.execute("DELETE FROM employees WHERE emp_code=%s", (self.current_code,))

        conn.commit()

        conn.close()

        self.clear_form()

    def clear_form(self):

        for f in [self.full_name, self.nickname, self.phone,
                  self.line_id, self.ssid, self.email,
                  self.basic_salary]:
            f.delete(0, tk.END)

        self.address.delete("1.0", tk.END)

        if self.roles:
            self.role_cb.current(0)

        self.employee_code.config(state="normal")
        self.employee_code.delete(0, tk.END)
        self.employee_code.config(state="readonly")
        self.photo_label.config(image="", text="No Photo")
        self.photo_path = None

        self.current_code = None


if __name__ == "__main__":

    root = tk.Tk()

    EmployeeForm(root)

    root.mainloop()
