import tkinter as tk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry
from datetime import datetime
from decimal import Decimal

from tksheet import Sheet
from db import get_connection as get_db_connection

# Ensure psycopg2 is imported if you use it directly, 
# though we rely on get_db_connection() from your db.py
import psycopg2 

class JobReceiveWindow:

    def __init__(self, root):
        self.root = root
        self.root.title("MYGEMS - Job Receive")
        self.root.state("zoomed")
        self.root.configure(bg="#f2f4f7")

        # ---- MAIN GRID LAYOUT ----
        self.root.grid_rowconfigure(0, weight=0)   # header
        self.root.grid_rowconfigure(1, weight=0)   # search
        self.root.grid_rowconfigure(2, weight=0)   # totals
        self.root.grid_rowconfigure(3, weight=1)   # receive grid (expands)
        self.root.grid_rowconfigure(4, weight=0)   # bottom buttons (fixed)
        self.root.grid_columnconfigure(0, weight=1)

        self.create_variables()
        self.create_header()
        self.create_search_frame()
        self.create_total_frame()
        self.create_receive_frame()
        self.create_bottom_buttons()
        self.change_search_widget()
        self.is_update_mode = False   
        self.btn_edit.config(state="disabled")
        self.btn_update.config(state="disabled")

        self.receive_rows = []
        self.bind_shortcuts()
        self.load_workers()
        self.generate_jr_no()

    # ---------------------------------------------------------
    # VARIABLES
    # ---------------------------------------------------------
    def create_variables(self):
        self.receive_date = tk.StringVar(value=datetime.now().strftime("%d/%m/%Y"))
        self.jr_no = tk.StringVar()
        self.metal = tk.StringVar(value="Gold")
        self.search_type = tk.StringVar(value="JOB")

    # ---------------------------------------------------------
    # HEADER
    # ---------------------------------------------------------
    def create_header(self):
        hdr = tk.Frame(self.root, bg="#0d6efd", height=55)
        hdr.grid(row=0, column=0, sticky="ew")
        tk.Label(hdr, text="JOB RECEIVE", bg="#0d6efd", fg="white", font=("Segoe UI", 18, "bold")).pack(pady=10)

    # ---------------------------------------------------------
    # SEARCH FRAME
    # ---------------------------------------------------------
    def create_search_frame(self):
        frm = tk.LabelFrame(self.root, text="Receive Information", font=("Segoe UI", 10, "bold"), bg="#EEF4FF", padx=10, pady=10)
        frm.grid(row=1, column=0, sticky="ew", padx=10, pady=5)

        tk.Label(frm, text="Receive Date", bg="#EEF4FF").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.dt_receive = DateEntry(frm, width=12, date_pattern="dd-mm-yyyy")
        self.dt_receive.grid(row=0, column=1, padx=5)

        tk.Label(frm, text="JR No", bg="#EEF4FF").grid(row=0, column=2, padx=5)
        tk.Entry(frm, textvariable=self.jr_no, width=15, state="readonly", justify="center", font=("Segoe UI", 10, "bold")).grid(row=0, column=3, padx=5)

        tk.Label(frm, text="Search By", bg="#EEF4FF", font=("Segoe UI", 10, "bold")).grid(row=1, column=0, padx=5, pady=10)

        self.rb_job = tk.Radiobutton(frm, text="JA No", variable=self.search_type, value="JOB", bg="#EEF4FF", command=self.change_search_widget)
        self.rb_job.grid(row=1, column=1, sticky="w")
        self.rb_date = tk.Radiobutton(frm, text="Date", variable=self.search_type, value="DATE", bg="#EEF4FF", command=self.change_search_widget)
        self.rb_date.grid(row=1, column=2, sticky="w")
        self.rb_worker = tk.Radiobutton(frm, text="Worker", variable=self.search_type, value="WORKER", bg="#EEF4FF", command=self.change_search_widget)
        self.rb_worker.grid(row=1, column=3, sticky="w")

        self.search_text = tk.StringVar()
        self.search_text.trace_add("write", lambda *args: self.search_text.set(self.search_text.get().upper()))

        self.ent_job = tk.Entry(frm, textvariable=self.search_text, width=25)
        self.dt_search = DateEntry(frm, width=18, date_pattern="dd-mm-yyyy")
        self.cmb_worker = ttk.Combobox(frm, width=28, state="readonly")
        self.ent_job.grid(row=1, column=4, padx=10)

        tk.Button(frm, text="🔍 Search", bg="#0D6EFD", fg="white", width=12, command=self.search_clicked).grid(row=1, column=5, padx=5)
        tk.Button(frm, text="🆕 New", bg="orange", width=12, command=self.new_receive).grid(row=1, column=6, padx=5)
        # --- ADDITION: Find Job Button ---
        tk.Button(
            frm, text="🔎 Find Job", bg="#6c757d", fg="white", width=12,
            command=self.find_job_clicked
        ).grid(row=1, column=7, padx=5)

        # --- CORRECTION: Increased columnspan from 7 to 8 to cover the new button ---
        tk.Label(
            frm,
            text="Ctrl+F Search   Ctrl+S Save   Ctrl+P Print   Ctrl+N New   Ctrl+E / Esc Exit",
            bg="#EEF4FF", fg="gray", font=("Segoe UI", 8)
        ).grid(row=2, column=0, columnspan=8, pady=(10, 0), sticky="w")

        tk.Label(frm, text="Ctrl+F Search   Ctrl+S Save   Ctrl+P Print   Ctrl+N New   Ctrl+E / Esc Exit", bg="#EEF4FF", fg="gray", font=("Segoe UI", 8)).grid(row=2, column=0, columnspan=7, pady=(10, 0), sticky="w")
        


    def create_total_frame(self):
        frm = tk.LabelFrame(self.root, text="Totals", font=("Segoe UI", 10, "bold"), bg="white")
        frm.grid(row=2, column=0, sticky="ew", padx=10, pady=5)

        self.lbl_issue = tk.Label(frm, text="Issue : 0.000", font=("Segoe UI", 10, "bold"), bg="white")
        self.lbl_issue.grid(row=0, column=0, padx=15, pady=5)
        self.lbl_receive = tk.Label(frm, text="Receive : 0.000", font=("Segoe UI", 10, "bold"), bg="white")
        self.lbl_receive.grid(row=0, column=1, padx=15)
        self.lbl_wastage = tk.Label(frm, text="Wastage : 0.000", font=("Segoe UI", 10, "bold"), bg="white")
        self.lbl_wastage.grid(row=0, column=2, padx=15)
        self.lbl_labor = tk.Label(frm, text="Labor : 0.00", font=("Segoe UI", 10, "bold"), bg="white")
        self.lbl_labor.grid(row=0, column=3, padx=15)

    # ---------------------------------------------------------
    # GENERATE JR-NO
    # ---------------------------------------------------------
    def generate_jr_no(self):
        conn = get_db_connection()
        if not conn: return
        try:
            cur = conn.cursor()
            cur.execute("SELECT MAX(CAST(SUBSTRING(jr_no FROM 4) AS INTEGER)) FROM job_transaction WHERE jr_no IS NOT NULL")
            row = cur.fetchone()
            next_no = 1 if row[0] is None else row[0] + 1
            self.jr_no.set(f"JR-{next_no:06d}")
            cur.close()
        finally:
            conn.close()

    # ---------------------------------------------------------
    # LOAD WORKERS
    # ---------------------------------------------------------
    def load_workers(self):
        conn = get_db_connection()
        if not conn: return
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT a.account_id, a.account_name FROM accounts a
                INNER JOIN account_types at ON a.type_id = at.type_id
                WHERE at.type_name='WORKER' AND at.is_active=TRUE ORDER BY a.account_name
            """)
            workers = cur.fetchall()
            self.worker_map = {name.upper(): wid for wid, name in workers}
            self.cmb_worker["values"] = [name.upper() for _, name in workers]
            cur.close()
        except Exception as e:
            messagebox.showerror("Database Error", str(e))
        finally:
            conn.close()

    # ---------------------------------------------------------
    # RECEIVE GRID (tksheet)
    # ---------------------------------------------------------
    COL_SELECT = 0; COL_JA = 1; COL_LOT = 2; COL_WORKER = 3; COL_PROCESS = 4
    COL_ISSUE = 5; COL_ADD = 6; COL_TOTAL = 7; COL_RECEIVE = 8; COL_LABOR = 9; COL_DESC = 10

    def create_receive_frame(self):
        frm = tk.LabelFrame(self.root, text="Receive Details", font=("Segoe UI", 10, "bold"), bg="white")
        frm.grid(row=3, column=0, sticky="nsew", padx=10, pady=5)
        frm.grid_rowconfigure(1, weight=1)
        frm.grid_columnconfigure(0, weight=1)

        toolbar = tk.Frame(frm, bg="white")
        toolbar.grid(row=0, column=0, sticky="ew")
        self.select_all = tk.BooleanVar(value=True)
        tk.Checkbutton(toolbar, text="Select All", variable=self.select_all, bg="white", font=("Segoe UI", 9, "bold"), command=self.toggle_all_rows).pack(side="left", padx=5, pady=5)

        headers = ["✓", "JA No", "Lot No", "Worker", "Process", "Issue", "Add", "Total", "Receive", "Labor", "Description"]
        col_widths = [60, 90, 100, 160, 100, 80, 80, 80, 90, 80, 250]

        self.sheet = Sheet(frm, headers=headers, data=[], show_row_index=False)
        self.sheet.enable_bindings(("single_select", "row_select", "column_width_resize", "arrowkeys", "edit_cell", "copy", "paste"))
        self.sheet.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        for idx, w in enumerate(col_widths):
            self.sheet.column_width(column=idx, width=w)

        readonly_cols = [c for c in range(len(headers)) if c not in (self.COL_SELECT, self.COL_RECEIVE, self.COL_LABOR)]
        self.sheet.readonly_columns(columns=readonly_cols, readonly=True)
        self.sheet.extra_bindings([("end_edit_cell", self.on_cell_edit)])
        

    # ---------------------------------------------------------
    # BOTTOM BUTTONS
    # ---------------------------------------------------------
    def create_bottom_buttons(self):
        frm = tk.Frame(self.root, bg="#f2f4f7")
        frm.grid(row=4, column=0, sticky="ew", pady=10)

        frm.grid_columnconfigure(0, weight=0)
        frm.grid_columnconfigure(1, weight=0)
        frm.grid_columnconfigure(2, weight=0)
        frm.grid_columnconfigure(3, weight=1)  # spacer
        frm.grid_columnconfigure(4, weight=0)
        frm.grid_columnconfigure(5, weight=0)

        tk.Button(
            frm, text="SAVE (Ctrl+S)", width=15,
            bg="#198754", fg="white", font=("Segoe UI", 10, "bold"),
            command=self.save_receive
        ).grid(row=0, column=0, padx=5)

        # --- ADDITION: EDIT and UPDATE buttons ---
        self.btn_edit = tk.Button(
            frm, text="EDIT", width=10,
            bg="#ffc107", fg="black", font=("Segoe UI", 10, "bold"),
            command=self.enable_edit_mode, state="disabled"
        )
        self.btn_edit.grid(row=0, column=1, padx=5)

        self.btn_update = tk.Button(
            frm, text="UPDATE", width=15,
            bg="#0dcaf0", fg="black", font=("Segoe UI", 10, "bold"),
            command=self.update_receive, state="disabled"
        )
        self.btn_update.grid(row=0, column=2, padx=5)

        tk.Button(
            frm, text="PRINT (Ctrl+P)", width=15,
            bg="#0d6efd", fg="white", font=("Segoe UI", 10, "bold"),
            command=self.print_receive
        ).grid(row=0, column=4, padx=5)

        tk.Button(
            frm, text="EXIT (Ctrl+E)", width=15,
            bg="red", fg="white", font=("Segoe UI", 10, "bold"),
            command=self.exit_window
        ).grid(row=0, column=5, padx=5)

    # ---------------------------------------------------------
    # UTILITY & EVENT METHODS
    # ---------------------------------------------------------
    def new_receive(self):
        self.ent_job.delete(0, "end")
        self.sheet.set_sheet_data([])
        self.receive_rows.clear()
        self.generate_jr_no()
        self.calculate_totals()

    def change_search_widget(self):
        self.ent_job.grid_forget()
        self.dt_search.grid_forget()
        self.cmb_worker.grid_forget()
        mode = self.search_type.get()
        if mode == "JOB":
            self.ent_job.grid(row=1, column=4, padx=10)
            self.ent_job.focus_set()
        elif mode == "DATE":
            self.dt_search.grid(row=1, column=4, padx=10)
        elif mode == "WORKER":
            self.cmb_worker.grid(row=1, column=4, padx=10)

    def bind_shortcuts(self):
        self.root.bind("<Control-s>", lambda e: self.save_receive())
        self.root.bind("<Control-S>", lambda e: self.save_receive())
        self.root.bind("<Control-f>", lambda e: self.search_clicked())
        self.root.bind("<Control-F>", lambda e: self.search_clicked())
        self.root.bind("<Control-n>", lambda e: self.new_receive())
        self.root.bind("<Control-N>", lambda e: self.new_receive())
        self.root.bind("<Control-p>", lambda e: self.print_receive())
        self.root.bind("<Control-P>", lambda e: self.print_receive())
        self.root.bind("<Control-e>", lambda e: self.exit_window())
        self.root.bind("<Control-E>", lambda e: self.exit_window())
        self.root.bind("<Escape>", lambda e: self.exit_window())

    def exit_window(self):
        if messagebox.askyesno("Exit", "Are you sure you want to exit?"):
            self.root.destroy()

    # ---------------------------------------------------------
    # PRINT
    # ---------------------------------------------------------
    def print_receive(self):
        data = self.sheet.get_sheet_data()
        if not data:
            messagebox.showwarning("Warning", "No data to print.")
            return

        selected_rows = [(i, row) for i, row in enumerate(data) if row[self.COL_SELECT]]
        if not selected_rows:
            messagebox.showwarning("Warning", "No rows selected to print.")
            return

        preview = tk.Toplevel(self.root)
        preview.title("Print Preview - Job Receive")
        preview.geometry("800x600")
        txt = tk.Text(preview, font=("Courier New", 10))
        txt.pack(fill="both", expand=True, padx=10, pady=10)

        # FIX: Use self.jr_no instead of self.jr_no_var
        jr_no = self.jr_no.get() 
        receive_date = self.dt_receive.get() # FIX: Get directly from widget

        txt.insert("end", f"{'MYGEMS - JOB RECEIVE SLIP':^90}\n")
        txt.insert("end", "=" * 90 + "\n")
        txt.insert("end", f"JR No : {jr_no:<20} Date : {receive_date}\n")
        txt.insert("end", "-" * 90 + "\n")

        header = f"{'JA No':<10}{'Lot No':<12}{'Worker':<18}{'Process':<12}{'Issue':>10}{'Receive':>10}{'Labor':>10}\n"
        txt.insert("end", header)
        txt.insert("end", "-" * 90 + "\n")

        total_issue = total_receive = total_labor = 0.0
        for i, row in selected_rows:
            issue = float(row[self.COL_TOTAL] or 0)
            receive = float(row[self.COL_RECEIVE] or 0)
            labor = float(row[self.COL_LABOR] or 0)
            total_issue += issue; total_receive += receive; total_labor += labor
            line = f"{row[self.COL_JA]:<10}{row[self.COL_LOT]:<12}{row[self.COL_WORKER]:<18}{row[self.COL_PROCESS]:<12}{issue:>10.3f}{receive:>10.3f}{labor:>10.2f}\n"
            txt.insert("end", line)

        txt.insert("end", "-" * 90 + "\n")
        txt.insert("end", f"{'TOTAL':<52}{total_issue:>10.3f}{total_receive:>10.3f}{total_labor:>10.2f}\n")
        txt.insert("end", f"Wastage : {total_issue - total_receive:.3f}\n")
        txt.insert("end", "=" * 90 + "\n")
        txt.config(state="disabled")

        btnfrm = tk.Frame(preview)
        btnfrm.pack(fill="x", pady=5)
        tk.Button(btnfrm, text="PRINT", bg="#198754", fg="white", width=15, command=lambda: self.send_to_printer(txt)).pack(side="left", padx=10)
        tk.Button(btnfrm, text="CLOSE", bg="#dc3545", fg="white", width=15, command=preview.destroy).pack(side="right", padx=10)

    def send_to_printer(self, txt_widget):
        try:
            content = txt_widget.get("1.0", "end")
            import tempfile, os
            with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8") as f:
                f.write(content)
                temp_path = f.name
            if os.name == "nt": os.startfile(temp_path, "print")
            else: os.system(f"lp '{temp_path}'")
            messagebox.showinfo("Print", "Sent to printer.")
        except Exception as e:
            messagebox.showerror("Print Error", str(e))

    # ---------------------------------------------------------
    # SEARCH & LOAD
    # ---------------------------------------------------------
    def search_clicked(self):
        conn = get_db_connection()
        if not conn: return
        try:
            cur = conn.cursor()
            mode = self.search_type.get()
            
            if mode == "JOB":
                ja_no = self.ent_job.get().strip().upper()
                if not ja_no:
                    messagebox.showwarning("Warning", "Enter JA Number.")
                    return
                # --- CORRECTED QUERY ---
                cur.execute("""
                    SELECT job_no, account_name, txn_date, COUNT(*) 
                    FROM job_transaction 
                    WHERE job_no=%s AND (status != 'RECEIVED' OR status IS NULL)
                    GROUP BY job_no, account_name, txn_date
                """, (ja_no,))

            elif mode == "DATE":
                dt = self.dt_search.get_date()
                # --- CORRECTED QUERY ---
                cur.execute("""
                    SELECT job_no, account_name, txn_date, COUNT(*) 
                    FROM job_transaction 
                    WHERE txn_date=%s AND (status != 'RECEIVED' OR status IS NULL)
                    GROUP BY job_no, account_name, txn_date 
                    ORDER BY job_no
                """, (dt,))

            else:
                worker = self.cmb_worker.get().upper()
                # --- CORRECTED QUERY ---
                cur.execute("""
                    SELECT job_no, account_name, txn_date, COUNT(*) 
                    FROM job_transaction 
                    WHERE account_name=%s AND (status != 'RECEIVED' OR status IS NULL)
                    GROUP BY job_no, account_name, txn_date 
                    ORDER BY txn_date
                """, (worker,))

            rows = cur.fetchall()
            cur.close(); conn.close()
            
            if not rows:
                messagebox.showinfo("Info", "No pending jobs found for this search.")
                return

            self.load_pending_jobs(rows)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def load_pending_jobs(self, rows):
        win = tk.Toplevel(self.root)
        win.title("Pending Job Assignments"); win.geometry("700x450"); win.grab_set()
        columns = ("JA No", "Worker", "Date", "Lots")
        tree = ttk.Treeview(win, columns=columns, show="headings", selectmode="extended")
        for col in columns:
            tree.heading(col, text=col); tree.column(col, width=150, anchor="center")
        for r in rows: tree.insert("", "end", values=r)
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        btnfrm = tk.Frame(win); btnfrm.pack(fill="x", pady=5)
        tk.Button(btnfrm, text="LOAD SELECTED", bg="#198754", fg="white", width=18, command=lambda: self.load_selected_jobs(tree, win)).pack(side="left", padx=10)
        tk.Button(btnfrm, text="CLOSE", bg="#dc3545", fg="white", width=12, command=win.destroy).pack(side="right", padx=10)

    # ---------------------------------------------------------
    # FIND & UPDATE JOB WORKFLOW
    # ---------------------------------------------------------

    def find_job_clicked(self):
        """Searches for ALREADY RECEIVED jobs to update them."""
        conn = get_db_connection()
        if not conn: return
        
        try:
            cur = conn.cursor()
            mode = self.search_type.get()

            if mode == "JOB":
                ja_no = self.ent_job.get().strip().upper()
                if not ja_no:
                    messagebox.showwarning("Warning", "Enter JA Number.")
                    return
                # FIX: Changed txn_date to receive_date
                cur.execute("""
                    SELECT job_no, account_name, receive_date, COUNT(*) 
                    FROM job_transaction 
                    WHERE job_no=%s AND status = 'RECEIVED'
                    GROUP BY job_no, account_name, receive_date
                """, (ja_no,))

            elif mode == "DATE":
                dt = self.dt_search.get_date()
                # FIX: Changed txn_date to receive_date
                cur.execute("""
                    SELECT job_no, account_name, receive_date, COUNT(*) 
                    FROM job_transaction 
                    WHERE receive_date=%s AND status = 'RECEIVED'
                    GROUP BY job_no, account_name, receive_date ORDER BY job_no
                """, (dt,))
            else:
                worker = self.cmb_worker.get().upper()
                # FIX: Changed txn_date to receive_date
                cur.execute("""
                    SELECT job_no, account_name, receive_date, COUNT(*) 
                    FROM job_transaction 
                    WHERE account_name=%s AND status = 'RECEIVED'
                    GROUP BY job_no, account_name, receive_date ORDER BY receive_date
                """, (worker,))

            rows = cur.fetchall()
            cur.close(); conn.close()

            if not rows:
                messagebox.showinfo("Info", "No received jobs found for this search.")
                return

            self.load_received_jobs(rows)

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def load_received_jobs(self, rows):
        """Opens a popup to select which received job to edit, then loads it."""
        win = tk.Toplevel(self.root)
        win.title("Select Received Job to Update"); win.geometry("700x450"); win.grab_set()
        
        columns = ("JA No", "Worker", "Date", "Lots")
        tree = ttk.Treeview(win, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            tree.heading(col, text=col); tree.column(col, width=150, anchor="center")
        for r in rows: tree.insert("", "end", values=r)
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        def load_for_update():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Warning", "Select a Job.")
                return
            
            job_no = tree.item(sel[0])["values"][0]
            win.destroy()

            self.sheet.set_sheet_data([])
            self.receive_rows.clear()
            
            self.is_update_mode = True
            self.btn_edit.config(state="normal")
            
            conn = get_db_connection()
            if not conn: return
            try:
                cur = conn.cursor()
                cur.execute("""
                    SELECT job_no, lot_no, account_name, process, weight, COALESCE(add_gold,0), 
                           COALESCE(total_weight,weight), receive_weight, labor_amount, description
                    FROM job_transaction 
                    WHERE job_no=%s AND status = 'RECEIVED'
                    ORDER BY id
                """, (job_no,))
                
                for row in cur.fetchall():
                    self.add_update_row(row)
                
                cur.close()
                
                # LOCK ALL COLUMNS INITIALLY
                self.sheet.readonly_columns(columns=list(range(11)), readonly=True)
                self.sheet.redraw() # FIX: Force UI to update lock state
                self.calculate_totals()
                
            except Exception as e:
                messagebox.showerror("Error", str(e))
            finally:
                conn.close()

        btnfrm = tk.Frame(win); btnfrm.pack(fill="x", pady=5)
        tk.Button(btnfrm, text="LOAD FOR EDIT", bg="#198754", fg="white", width=18, command=load_for_update).pack(side="left", padx=10)
        tk.Button(btnfrm, text="CLOSE", bg="#dc3545", fg="white", width=12, command=win.destroy).pack(side="right", padx=10)

    def add_update_row(self, row):
        """Adds a row specifically for the Update workflow (includes existing receive/labor)."""
        idx = len(self.receive_rows)
        # row: 0:job, 1:lot, 2:worker, 3:process, 4:issue, 5:add, 6:total, 7:receive, 8:labor, 9:desc
        row_data = [
            True, row[0], row[1], row[2], row[3], 
            f"{float(row[4]):.3f}", f"{float(row[5]):.3f}", f"{float(row[6]):.3f}", 
            f"{float(row[7] or 0):.3f}", f"{float(row[8] or 0):.2f}", row[9] or ""
        ]
        self.sheet.insert_row(row_data, idx=idx)
        self.sheet.create_checkbox(r=idx, c=self.COL_SELECT, checked=True, check_function=self.on_checkbox_toggle)
        
        self.receive_rows.append({
            "job_no": row[0], "lot_no": row[1], "worker": row[2], "process": row[3],
            "issue": float(row[4]), "add_gold": float(row[5]), "total": float(row[6]), 
            "receive": float(row[7] or 0), "labor": float(row[8] or 0), "description": row[9]
        })

    def enable_edit_mode(self):
        """Unlocks the Receive, Labor, and Description columns for editing."""
        if not self.is_update_mode:
            messagebox.showwarning("Warning", "Please use 'Find Job' first.")
            return

        # FIX: Explicitly lock all columns first
        self.sheet.readonly_columns(columns=list(range(11)), readonly=True)
        
        # FIX: Explicitly unlock Checkbox, Receive, Labor, and Description
        self.sheet.readonly_columns(
            columns=[self.COL_SELECT, self.COL_RECEIVE, self.COL_LABOR, self.COL_DESC], 
            readonly=False
        )
        
        # FIX: Force the sheet to redraw and recognize the new editable states
        self.sheet.redraw() 
        
        self.btn_update.config(state="normal")
        messagebox.showinfo("Edit Mode", "You can now edit Receive Weight, Labor, and Description.\nClick UPDATE to save changes.")

    def update_receive(self):
        """Saves the updated Receive/Labor/Description to the database and syncs ALL related tables."""
        if not self.is_update_mode:
            return

        # FIX: Force tksheet to completely commit any open cell edits
        self.root.focus_set()
        self.root.update()
        if hasattr(self.sheet, 'dehighlight_all'):
            self.sheet.dehighlight_all()
        self.root.update()

        conn = get_db_connection()
        if not conn: return
        
        cur = None
        try:
            cur = conn.cursor()
            receive_date = self.dt_receive.get()
            sheet_data = self.sheet.get_sheet_data()

            for r, row_data in enumerate(self.receive_rows):
                if not sheet_data[r][self.COL_SELECT]:
                    continue

                job_no = row_data["job_no"]
                lot_no = row_data["lot_no"]
                worker = row_data["worker"]
                process = row_data["process"]
                description = str(sheet_data[r][self.COL_DESC]).strip()
                
                # FIX: Read directly from sheet_data to bypass any dictionary sync delays
                new_receive_weight = Decimal(str(sheet_data[r][self.COL_RECEIVE] or 0))
                new_labor = Decimal(str(sheet_data[r][self.COL_LABOR] or 0))
                issue_weight = Decimal(str(row_data["total"]))
                
                # DEBUG: Check your Python console to verify the values being processed
                print(f"DEBUG UPDATE: Lot {lot_no} | Receive: {new_receive_weight} | Labor: {new_labor}")
                
                new_wastage = round(issue_weight - new_receive_weight, 3)
                new_wastage_percent = round((new_wastage / issue_weight) * 100, 2) if issue_weight > 0 else Decimal("0")

                # ---------------------------------------------------------
                # 1. Fetch OLD values to calculate Deltas
                # ---------------------------------------------------------
                cur.execute("""
                    SELECT receive_weight, labor_amount, wastage, jr_no, id 
                    FROM job_transaction WHERE job_no=%s AND lot_no=%s
                """, (job_no, lot_no))
                old_data = cur.fetchone()
                if not old_data:
                    raise Exception(f"Job {job_no} Lot {lot_no} not found.")
                
                old_labor = Decimal(str(old_data[1] or 0))
                old_wastage = Decimal(str(old_data[2] or 0))
                old_jr_no_db = old_data[3]
                job_txn_id = old_data[4]
                
                delta_wastage = new_wastage - old_wastage 
                delta_labor = new_labor - old_labor

                # ---------------------------------------------------------
                # 2. Fetch per_gram and jewelry type
                # ---------------------------------------------------------
                cur.execute("SELECT per_gram FROM gold_jewelry WHERE lot_no=%s", (lot_no,))
                gold_row = cur.fetchone()
                if gold_row:
                    jewelry_type = "GOLD"
                    per_gram = Decimal(str(gold_row[0] or 0))
                else:
                    cur.execute("SELECT per_gram FROM silver_jewelry WHERE lot_no=%s", (lot_no,))
                    silver_row = cur.fetchone()
                    if not silver_row:
                        raise Exception(f"Lot {lot_no} not found.")
                    jewelry_type = "SILVER"
                    per_gram = Decimal(str(silver_row[0] or 0))

                delta_amount = round(delta_wastage * per_gram, 2)
                print(f"DEBUG JEWELRY TYPE: lot_no={lot_no!r} jewelry_type={jewelry_type} per_gram={per_gram} delta_wastage={delta_wastage} delta_amount={delta_amount}")

                # ---------------------------------------------------------
                # 3. UPDATE job_transaction (Now correctly includes new_labor)
                # ---------------------------------------------------------
                cur.execute("""
                    UPDATE job_transaction 
                    SET receive_weight=%s, labor_amount=%s, description=%s, 
                        wastage=%s, wastage_percent=%s
                    WHERE job_no=%s AND lot_no=%s
                """, (new_receive_weight, new_labor, description, new_wastage, new_wastage_percent, job_no, lot_no))
                print(f"DEBUG JOB_TRANSACTION UPDATE rowcount={cur.rowcount} new_labor={new_labor} old_labor={old_labor} delta_labor={delta_labor}")

                # ---------------------------------------------------------
                # 4. UPDATE gold_jewelry / silver_jewelry
                # ---------------------------------------------------------
                if jewelry_type == "GOLD":
                    cur.execute("SELECT weight, gold_amount, labor FROM gold_jewelry WHERE lot_no=%s", (lot_no,))
                    j_row = cur.fetchone()
                    curr_weight = Decimal(str(j_row[0] or 0))
                    curr_gold_amt = Decimal(str(j_row[1] or 0))

                    # Labor is a dependent value: recompute it fresh from the labor
                    # table instead of nudging a stored figure by a delta, so edits
                    # (and re-edits) never drift out of sync with the source rows.
                    # Exclude this transaction's own labor row (it hasn't been
                    # written with the new amount yet - that happens in step 7)
                    # and add the new amount being saved right now instead.
                    cur.execute(
                        "SELECT job_no, jr_no, labor_amount, status FROM labor WHERE lot_no=%s ORDER BY date",
                        (lot_no,)
                    )
                    all_labor_rows = cur.fetchall()
                    print(f"DEBUG LABOR ROWS FOR lot_no={lot_no!r}: {all_labor_rows}  (this_job_txn_id={job_txn_id}, this_jr_no={old_jr_no_db!r})")

                    cur.execute(
                        "SELECT COALESCE(SUM(labor_amount),0) FROM labor WHERE lot_no=%s AND NOT (job_no=%s AND jr_no=%s)",
                        (lot_no, job_txn_id, old_jr_no_db)
                    )
                    other_labor_sum = Decimal(str(cur.fetchone()[0] or 0))
                    new_j_labor = other_labor_sum + (new_labor if new_labor > 0 else Decimal("0"))

                    new_j_weight = curr_weight - delta_wastage
                    new_j_gold_amt = curr_gold_amt - delta_amount
                    new_j_total = new_j_gold_amt + new_j_labor
                    
                    cur.execute("""
                        UPDATE gold_jewelry 
                        SET weight=%s, gold_amount=%s, labor=%s, total_cost=%s
                        WHERE lot_no=%s
                    """, (new_j_weight, new_j_gold_amt, new_j_labor, new_j_total, lot_no))
                    print(f"DEBUG GOLD_JEWELRY UPDATE rowcount={cur.rowcount} lot_no={lot_no!r} new_j_labor(recomputed)={new_j_labor} curr_weight={curr_weight} new_j_weight={new_j_weight}")
                else:
                    cur.execute("SELECT weight, silver_amount FROM silver_jewelry WHERE lot_no=%s", (lot_no,))
                    j_row = cur.fetchone()
                    curr_weight = Decimal(str(j_row[0] or 0))
                    curr_silver_amt = Decimal(str(j_row[1] or 0))
                    
                    new_j_weight = curr_weight - delta_wastage
                    new_j_silver_amt = curr_silver_amt - delta_amount
                    
                    cur.execute("""
                        UPDATE silver_jewelry 
                        SET weight=%s, silver_amount=%s
                        WHERE lot_no=%s
                    """, (new_j_weight, new_j_silver_amt, lot_no))

                # ---------------------------------------------------------
                # GET PURITY FOR CURRENT LOT
                # ---------------------------------------------------------

                purity = None

                cur.execute("""
                    SELECT purity
                    FROM gold_jewelry
                    WHERE lot_no=%s
                    LIMIT 1
                """, (lot_no,))

                purity_row = cur.fetchone()

                if purity_row:
                    purity = purity_row[0]

                # ---------------------------------------------------------
                # 5. Handle Wastage Account Entries
                # ---------------------------------------------------------
                if jewelry_type == "GOLD":
                    if new_wastage > 0:
                        new_amount = round(new_wastage * per_gram, 2)
                        cur.execute("SELECT COUNT(*) FROM gold_account WHERE source_job=%s AND lot_no=%s AND entry_type='JOB_WASTAGE'", (job_no, lot_no))
                        if cur.fetchone()[0] > 0:
                            cur.execute("UPDATE gold_account SET weight=%s, amount=%s WHERE source_job=%s AND lot_no=%s AND entry_type='JOB_WASTAGE'", (new_wastage, new_amount, job_no, lot_no))
                            print(f"DEBUG GOLD_ACCOUNT UPDATE rowcount={cur.rowcount} job_no={job_no!r} lot_no={lot_no!r} new_wastage={new_wastage} new_amount={new_amount}")
                        else:
                            cur.execute("""
                                INSERT INTO gold_account (txn_date, purchase_no, lot_no, per_gram, weight, amount, txn_nature, entry_type, source_job, source_worker, source_process)
                                VALUES (%s,%s,%s,%s,%s,%s,'CR','JOB_WASTAGE',%s,%s,%s)
                            """, (receive_date, "", lot_no, per_gram, new_wastage, new_amount, job_no, worker, process))
                            print(f"DEBUG GOLD_ACCOUNT INSERT rowcount={cur.rowcount} job_no={job_no!r} lot_no={lot_no!r} new_wastage={new_wastage} new_amount={new_amount}")
                    else:
                        cur.execute("DELETE FROM gold_account WHERE source_job=%s AND lot_no=%s AND entry_type='JOB_WASTAGE'", (job_no, lot_no))
                        print(f"DEBUG GOLD_ACCOUNT DELETE rowcount={cur.rowcount} job_no={job_no!r} lot_no={lot_no!r} new_wastage={new_wastage}")
                else:
                    if new_wastage > 0:
                        new_amount = round(new_wastage * per_gram, 2)
                        cur.execute("SELECT COUNT(*) FROM silver_account WHERE remarks LIKE %s AND entry_type='JOB_WASTAGE'", (f"{job_no}%",))
                        if cur.fetchone()[0] > 0:
                            cur.execute("UPDATE silver_account SET weight=%s, amount=%s WHERE remarks LIKE %s AND entry_type='JOB_WASTAGE'", (new_wastage, new_amount, f"{job_no}%"))
                        else:
                            cur.execute("""
                                INSERT INTO silver_account (txn_date, txn_no, purchase_no, lot_no, per_gram, weight, amount, txn_nature, entry_type, remarks)
                                VALUES (%s,%s,%s,%s,%s,%s,%s,'CR','JOB_WASTAGE',%s)
                            """, (receive_date, old_jr_no_db, "", lot_no, per_gram, new_wastage, new_amount, f"{job_no} - {worker}"))
                    else:
                        cur.execute("DELETE FROM silver_account WHERE remarks LIKE %s AND entry_type='JOB_WASTAGE'", (f"{job_no}%",))

                # ---------------------------------------------------------
                # 6. Handle worker_metal_recovery
                # ---------------------------------------------------------

                worker_id = self.worker_map.get(worker.upper())

                if not worker_id:
                    raise Exception(
                        f"Worker ID not found for {worker}."
                    )

                # ---------------------------------------------------------
                # GET WORKER WASTAGE MASTER
                # ---------------------------------------------------------

                cur.execute("""
                    SELECT
                        allowed_percent
                    FROM worker_wastage_master
                    WHERE worker_id=%s
                      AND UPPER(TRIM(process))=UPPER(TRIM(%s))
                      AND UPPER(TRIM(metal_type))=UPPER(TRIM(%s))
                      AND (
                            purity IS NULL
                            OR UPPER(TRIM(purity))=UPPER(TRIM(%s))
                          )
                      AND status='ACTIVE'
                      AND effective_from <= %s
                      AND (
                            effective_to IS NULL
                            OR effective_to >= %s
                          )
                    ORDER BY
                        CASE
                            WHEN purity IS NOT NULL
                             AND UPPER(TRIM(purity))=UPPER(TRIM(%s))
                            THEN 0
                            ELSE 1
                        END,
                        effective_from DESC
                    LIMIT 1
                """, (
                    worker_id,
                    process,
                    jewelry_type,
                    purity,
                    receive_date,
                    receive_date,
                    purity
                ))

                wastage_rule = cur.fetchone()

                allowed_percent = Decimal("0.000")

                if wastage_rule:

                    allowed_percent = Decimal(
                        str(wastage_rule[0] or 0)
                    )

                # ---------------------------------------------------------
                # CALCULATE ALLOWED WASTAGE
                # ---------------------------------------------------------

                allowed_wastage = (
                    issue_weight *
                    allowed_percent /
                    Decimal("100")
                )

                allowed_wastage = max(
                    Decimal("0.000"),
                    min(
                        allowed_wastage,
                        new_wastage
                    )
                ).quantize(
                    Decimal("0.001")
                )

                # ---------------------------------------------------------
                # RECOVERABLE WASTAGE
                # ---------------------------------------------------------

                recoverable_wastage = (
                    new_wastage -
                    allowed_wastage
                ).quantize(
                    Decimal("0.001")
                )

                recoverable_wastage = max(
                    Decimal("0.000"),
                    recoverable_wastage
                )

                # ---------------------------------------------------------
                # AMOUNTS
                # ---------------------------------------------------------

                actual_amount = (
                    new_wastage * per_gram
                ).quantize(
                    Decimal("0.01")
                )

                allowed_amount = (
                    allowed_wastage * per_gram
                ).quantize(
                    Decimal("0.01")
                )

                recoverable_amount = (
                    recoverable_wastage * per_gram
                ).quantize(
                    Decimal("0.01")
                )

                # ---------------------------------------------------------
                # PERSIST ALLOWED WASTAGE BACK TO job_transaction
                # (step 3's UPDATE ran before this was calculated, so it
                # never wrote allowed_wastage - do it now.)
                # ---------------------------------------------------------

                cur.execute("""
                    UPDATE job_transaction
                    SET allowed_wastage=%s
                    WHERE job_no=%s AND lot_no=%s
                """, (allowed_wastage, job_no, lot_no))

                cur.execute("SELECT COUNT(*) FROM worker_metal_recovery WHERE job_no=%s AND lot_no=%s", (job_no, lot_no))
                wmr_exists = cur.fetchone()[0] > 0

                if recoverable_wastage > 0:

                    if wmr_exists:
                        cur.execute("""
                            UPDATE worker_metal_recovery
                            SET worker_id=%s, worker_name=%s, gold_type=%s,
                                issue_weight=%s, receive_weight=%s, actual_wastage=%s,
                                allowed_wastage=%s, recoverable_weight=%s,
                                avg_rate=%s, actual_amount=%s, allowed_amount=%s, recoverable_amount=%s,
                                balance_to_recover_weight=%s, balance_to_recover_amount=%s,
                                process=%s, remarks=%s
                            WHERE job_no=%s AND lot_no=%s
                        """, (
                            worker_id, worker, jewelry_type,
                            issue_weight, new_receive_weight, new_wastage,
                            allowed_wastage, recoverable_wastage,
                            per_gram, actual_amount, allowed_amount, recoverable_amount,
                            recoverable_wastage, recoverable_amount,
                            process, description,
                            job_no, lot_no
                        ))
                    else:
                        cur.execute("""
                            INSERT INTO worker_metal_recovery (
                                txn_date, jr_no, job_no, lot_no, worker_id, worker_name, gold_type, 
                                issue_weight, receive_weight, actual_wastage, allowed_wastage, recoverable_weight, 
                                avg_rate, actual_amount, allowed_amount, recoverable_amount,  
                                recovered_gold_weight, recovered_cash_amount, balance_to_recover_weight, balance_to_recover_amount, 
                                status, process, remarks
                            ) VALUES (
                                %s,%s,%s,%s, %s,%s, %s, %s,%s, %s,%s,%s, %s, %s,%s,%s, 0,0, %s,%s, 'PENDING', %s,%s
                            )
                        """, (
                            receive_date, old_jr_no_db, job_no, lot_no, worker_id, worker, jewelry_type, 
                            issue_weight, new_receive_weight, new_wastage, allowed_wastage, recoverable_wastage, 
                            per_gram, actual_amount, allowed_amount, recoverable_amount, 
                            recoverable_wastage, recoverable_amount, process, description
                        ))

                elif wmr_exists:
                    cur.execute("DELETE FROM worker_metal_recovery WHERE job_no=%s AND lot_no=%s", (job_no, lot_no))

                # ---------------------------------------------------------
                # 7. Handle labor table
                # ---------------------------------------------------------
                cur.execute("SELECT COUNT(*) FROM labor WHERE job_no=%s AND jr_no=%s", (job_txn_id, old_jr_no_db))
                labor_exists = cur.fetchone()[0] > 0
                print(f"DEBUG LABOR LOOKUP: job_txn_id={job_txn_id} old_jr_no_db={old_jr_no_db!r} labor_exists={labor_exists}")

                if new_labor > 0:
                    if labor_exists:
                        cur.execute("UPDATE labor SET labor_amount=%s, remarks=%s WHERE job_no=%s AND jr_no=%s",
                                    (new_labor, description, job_txn_id, old_jr_no_db))
                        print(f"DEBUG LABOR UPDATE rowcount={cur.rowcount}")
                        if cur.rowcount == 0:
                            # Safety net: the exists-check said yes but the UPDATE matched nothing
                            # (stale/mismatched jr_no) -> fall back to matching on job_no alone.
                            cur.execute("UPDATE labor SET labor_amount=%s, remarks=%s, jr_no=%s WHERE job_no=%s",
                                        (new_labor, description, old_jr_no_db, job_txn_id))
                            print(f"DEBUG LABOR FALLBACK UPDATE rowcount={cur.rowcount}")
                    else:
                        cur.execute("""
                            INSERT INTO labor (job_no, jr_no, date, lot_no, worker_id, process, labor_amount, status, remarks)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, 'PENDING', %s)
                        """, (job_txn_id, old_jr_no_db, receive_date, lot_no, worker_id, process, new_labor, description))
                        print(f"DEBUG LABOR INSERT rowcount={cur.rowcount}")
                else:
                    if labor_exists:
                        cur.execute("DELETE FROM labor WHERE job_no=%s AND jr_no=%s", (job_txn_id, old_jr_no_db))

                # ---------------------------------------------------------
                # 8. Handle pending_payments
                # ---------------------------------------------------------
                cur.execute("""
                    SELECT COUNT(*), COALESCE(MAX(paid_amount),0) 
                    FROM pending_payments WHERE txn_id=%s AND txn_type='LABOR'
                """, (job_txn_id,))
                pay_count, already_paid = cur.fetchone()
                payment_exists = pay_count > 0
                already_paid = Decimal(str(already_paid or 0))
                new_balance = new_labor - already_paid
                print(f"DEBUG PAYMENT LOOKUP: job_txn_id={job_txn_id} payment_exists={payment_exists} already_paid={already_paid}")

                if new_labor > 0:
                    if payment_exists:
                        cur.execute("""
                            UPDATE pending_payments SET total_amount=%s, balance_amount=%s 
                            WHERE txn_id=%s AND txn_type='LABOR'
                        """, (new_labor, new_balance, job_txn_id))
                        print(f"DEBUG PAYMENT UPDATE rowcount={cur.rowcount}")
                    else:
                        cur.execute("""
                            INSERT INTO pending_payments (
                                txn_date, txn_id, purchase_no, account_id, account_name, account_type,
                                txn_type, bill_no, total_amount, paid_amount, balance_amount, payment_status, remarks
                            ) VALUES (
                                %s, %s, %s, %s, %s, 'WORKER', 'LABOR', %s, %s, 0, %s, 'PENDING', %s
                            )
                        """, (receive_date, job_txn_id, "", worker_id, worker, old_jr_no_db, new_labor, new_labor, lot_no))
                        print(f"DEBUG PAYMENT INSERT rowcount={cur.rowcount}")
                else:
                    if payment_exists:
                        cur.execute("DELETE FROM pending_payments WHERE txn_id=%s AND txn_type='LABOR'", (job_txn_id,))

            # ---------------------------------------------------------
            # COMMIT & CLEANUP
            # ---------------------------------------------------------
            conn.commit()
            messagebox.showinfo("Success", "Job Receive details updated successfully across all tables.")
            
            # Reset to normal mode after update
            self.new_receive() 

        except Exception as e:
            if conn: conn.rollback()
            messagebox.showerror("Update Error", str(e))
        finally:
            if cur: cur.close()
            if conn: conn.close()


    def load_selected_jobs(self, tree, win):
        items = tree.selection()
        if not items:
            messagebox.showwarning("Warning", "Select at least one Job.")
            return

        self.sheet.set_sheet_data([])
        self.receive_rows.clear()
        conn = get_db_connection()
        if not conn: return

        try:
            cur = conn.cursor()
            for item in items:
                job_no = tree.item(item)["values"][0]
                
                # --- CORRECTED QUERY ---
                cur.execute("""
                    SELECT job_no, lot_no, account_name, process, weight, COALESCE(add_gold,0), COALESCE(total_weight,weight), description
                    FROM job_transaction 
                    WHERE job_no=%s AND txn_type='ASSIGN' AND (status != 'RECEIVED' OR status IS NULL)
                    ORDER BY id
                """, (job_no,))
                
                for row in cur.fetchall():
                    self.add_receive_row(row)
            cur.close(); win.destroy()
        except Exception as e:
            messagebox.showerror("Error", str(e))
        finally:
            conn.close()

    def add_receive_row(self, row):
        idx = len(self.receive_rows)
        row_data = [True, row[0], row[1], row[2], row[3], f"{float(row[4]):.3f}", f"{float(row[5]):.3f}", f"{float(row[6]):.3f}", f"{float(row[6]):.3f}", "0.00", row[7] or ""]
        self.sheet.insert_row(row_data, idx=idx)
        self.sheet.create_checkbox(r=idx, c=self.COL_SELECT, checked=True, check_function=self.on_checkbox_toggle)
        
        self.receive_rows.append({
            "job_no": row[0], "lot_no": row[1], "worker": row[2], "process": row[3],
            "issue": float(row[4]), "add_gold": float(row[5]), "total": float(row[6]), "description": row[7],
            # --- FIX: Initialize receive and labor in the dictionary ---
            "receive": float(row[6]), "labor": 0.0  
        })
        self.calculate_totals()

    def on_checkbox_toggle(self, event_data):
        try:
            r = event.row
            c = event.column
        except Exception:
            self.calculate_totals()
            return

        # Force a redraw to ensure the visual checkbox matches the internal data state
        self.sheet.redraw()
        self.calculate_totals()

    def _is_row_selected(self, val):
        """Safely check if a checkbox value is True, handling both bool and string types."""
        if isinstance(val, str):
            return val.lower() in ('true', '1', 'yes')
        return bool(val)

    def calculate_totals(self):
        issue = receive = labor = 0.0
        data = self.sheet.get_sheet_data()
        
        for r, row in enumerate(data):
            # --- CORRECTION: Use the safe boolean checker ---
            if not self._is_row_selected(row[self.COL_SELECT]):
                continue

            issue += self.receive_rows[r]["total"]
            
            try: receive += float(row[self.COL_RECEIVE] or 0)
            except: pass
            try: labor += float(row[self.COL_LABOR] or 0)
            except: pass

        wastage = issue - receive

        self.lbl_issue.config(text=f"Issue : {issue:.3f}")
        self.lbl_receive.config(text=f"Receive : {receive:.3f}")
        self.lbl_wastage.config(text=f"Wastage : {wastage:.3f}")
        self.lbl_labor.config(text=f"Labor : {labor:.2f}")

    def on_cell_edit(self, event=None):
        try:
            r = event.row
            c = event.column
        except Exception:
            self.calculate_totals()
            return

        if c not in (self.COL_RECEIVE, self.COL_LABOR):
            return

        value = str(self.sheet.get_cell_data(r, c)).strip()

        if value == "":
            # --- FIX: Update dictionary if cell is cleared ---
            if c == self.COL_RECEIVE: self.receive_rows[r]["receive"] = 0.0
            elif c == self.COL_LABOR: self.receive_rows[r]["labor"] = 0.0
            self.calculate_totals()
            return

        try:
            num = float(value)
        except Exception:
            messagebox.showwarning("Invalid", "Enter a valid number.")
            self.sheet.set_cell_data(r, c, "0")
            if c == self.COL_RECEIVE: self.receive_rows[r]["receive"] = 0.0
            elif c == self.COL_LABOR: self.receive_rows[r]["labor"] = 0.0
            self.calculate_totals()
            return

        if c == self.COL_RECEIVE:
            total = self.receive_rows[r]["total"]
            if num > total:
                messagebox.showwarning("Invalid Weight", f"Received weight cannot exceed Issued weight ({total:.3f})")
                self.sheet.set_cell_data(r, c, f"{total:.3f}")
                num = total
            # --- FIX: Save validated receive weight to dictionary ---
            self.receive_rows[r]["receive"] = num

        elif c == self.COL_LABOR:
            # --- FIX: Save validated labor amount to dictionary ---
            self.receive_rows[r]["labor"] = num

        self.calculate_totals()

    def toggle_all_rows(self):
        state = self.select_all.get()
        data = self.sheet.get_sheet_data()
        
        for r in range(len(data)):
            self.sheet.set_cell_data(r, self.COL_SELECT, bool(state))

            if state:
                total = self.receive_rows[r]["total"]
                if str(self.sheet.get_cell_data(r, self.COL_RECEIVE)).strip() == "":
                    self.sheet.set_cell_data(r, self.COL_RECEIVE, f"{total:.3f}")
                # --- FIX: Sync dictionary ---
                self.receive_rows[r]["receive"] = total
            else:
                self.sheet.set_cell_data(r, self.COL_RECEIVE, "")
                self.sheet.set_cell_data(r, self.COL_LABOR, "")
                # --- FIX: Sync dictionary ---
                self.receive_rows[r]["receive"] = 0.0
                self.receive_rows[r]["labor"] = 0.0

        self.sheet.redraw()
        self.calculate_totals()

    def calculate_totals(self):
        issue = receive = labor = 0.0
        data = self.sheet.get_sheet_data()
        for r, row in enumerate(data):
            if not row[self.COL_SELECT]: continue
            issue += self.receive_rows[r]["total"]
            try: receive += float(row[self.COL_RECEIVE] or 0)
            except: pass
            try: labor += float(row[self.COL_LABOR] or 0)
            except: pass
        
        self.lbl_issue.config(text=f"Issue : {issue:.3f}")
        self.lbl_receive.config(text=f"Receive : {receive:.3f}")
        self.lbl_wastage.config(text=f"Wastage : {issue - receive:.3f}")
        self.lbl_labor.config(text=f"Labor : {labor:.2f}")

    def validate_before_save(self):
        self.root.focus_set()
        self.root.update()
        
        data = self.sheet.get_sheet_data()
        
        if len(data) == 0:
            messagebox.showwarning("Warning", "No Job Loaded.")
            return False

        selected = False
        for r, row in enumerate(data):
            # --- CORRECTION: Use the safe boolean checker ---
            if not self._is_row_selected(row[self.COL_SELECT]):
                continue

            selected = True
            receive = str(row[self.COL_RECEIVE]).strip()
            if receive == "":
                messagebox.showwarning("Warning", f"Enter Receive Weight for Lot {self.receive_rows[r]['lot_no']}")
                return False
            
            labor = str(row[self.COL_LABOR]).strip()
            if labor == "": 
                self.sheet.set_cell_data(r, self.COL_LABOR, "0")
            
            try: 
                receive_val = float(receive)
            except:
                messagebox.showwarning("Invalid", f"Invalid Receive weight in row {r + 1}")
                return False

            if receive_val > self.receive_rows[r]["total"]:
                messagebox.showwarning("Invalid", f"{self.receive_rows[r]['lot_no']} : Receive Weight cannot exceed Total Weight.")
                return False

        if not selected:
            messagebox.showwarning("Warning", "No Lot Selected.")
            return False
            
        return True

    # ---------------------------------------------------------
    # SAVE RECEIVE CODE (HEAVILY CORRECTED)
    # ---------------------------------------------------------
    def save_receive(self):
        self.root.focus_set()
        self.root.update()

        if not self.validate_before_save():
            return

        conn = get_db_connection()
        if not conn:
            messagebox.showerror("Error", "Database connection failed.")
            return

        cur = None
        try:
            cur = conn.cursor()
            
            # FIX: Fetch date directly from the DateEntry widget
            receive_date = self.dt_receive.get() 
            jr_no = self.jr_no.get().strip() # FIX: Correct variable name

            if not jr_no:
                raise Exception("JR Number not generated.")

            sheet_data = self.sheet.get_sheet_data()

            # ============================================================
            # PROCESS EACH ROW
            # ============================================================
            for r, row_data in enumerate(self.receive_rows):
                
                # Skip unselected rows
                if not sheet_data[r][self.COL_SELECT]:
                    continue

                job_no = row_data["job_no"]
                lot_no = row_data["lot_no"]
                worker = row_data["worker"]
                process = row_data["process"]
                description = row_data["description"]

                # FIX: Fetch editable values from the tksheet data, not the dictionary
                receive_weight = Decimal(str(row_data.get("receive", 0)))
                labor = Decimal(str(row_data.get("labor", 0)))
                labor = Decimal(str(sheet_data[r][self.COL_LABOR] or "0"))
                issue_weight = Decimal(str(row_data["total"]))

                # ---------------------------------------------------------
                # ACTUAL WASTAGE (was never calculated - used below
                # undefined, causing a NameError on every first-time save)
                # ---------------------------------------------------------

                actual_wastage = (
                    issue_weight - receive_weight
                ).quantize(
                    Decimal("0.001")
                )

                if receive_weight > issue_weight:
                    raise Exception(f"{job_no}\n\nReceive Weight cannot be greater than Issue Weight.")

                # FIX: Fetch worker_id from the worker_map
                worker_id = self.worker_map.get(worker.upper())
                if not worker_id:
                    raise Exception(f"Worker ID not found for {worker}")

                # --------------------------------------------------------
                # FIND GOLD / SILVER LOT
                # --------------------------------------------------------
                jewelry_type = None
                cur.execute("SELECT weight, gold_amount, labor, per_gram FROM gold_jewelry WHERE lot_no=%s", (lot_no,))
                jewelry = cur.fetchone()

                if jewelry:
                    jewelry_type = "GOLD"
                    old_weight = Decimal(str(jewelry[0] or 0))
                    old_amount = Decimal(str(jewelry[1] or 0))
                    old_labor = Decimal(str(jewelry[2] or 0))
                    per_gram = Decimal(str(jewelry[3] or 0))
                else:
                    cur.execute("SELECT weight, silver_amount, per_gram FROM silver_jewelry WHERE lot_no=%s", (lot_no,))
                    jewelry = cur.fetchone()
                    if not jewelry:
                        raise Exception(f"Lot {lot_no} not found.")
                    jewelry_type = "SILVER"
                    old_weight = Decimal(str(jewelry[0] or 0))
                    old_amount = Decimal(str(jewelry[1] or 0))
                    old_labor = Decimal("0")
                    per_gram = Decimal(str(jewelry[2] or 0))

                # ============================================================
                # WORKER WASTAGE MASTER LOOKUP
                # Replace the current:
                #
                # allowed_wastage = Decimal("0.000")
                #
                # with this block.
                # ============================================================

                allowed_percent = Decimal("0.000")
                allowed_wastage = Decimal("0.000")

                worker_id = row.get("worker_id")

                if not worker_id:
                    raise Exception(
                        f"Worker ID not found for Job {job_no}."
                    )

                # ------------------------------------------------------------
                # GET ACTIVE WASTAGE RULE
                # ------------------------------------------------------------

                cur.execute("""
                    SELECT
                        allowed_percent
                    FROM worker_wastage_master
                    WHERE worker_id=%s
                      AND UPPER(TRIM(process))=UPPER(TRIM(%s))
                      AND UPPER(TRIM(metal_type))=UPPER(TRIM(%s))
                      AND (
                            purity IS NULL
                            OR UPPER(TRIM(purity))=UPPER(TRIM(%s))
                          )
                      AND status='ACTIVE'
                      AND effective_from <= %s
                      AND (
                            effective_to IS NULL
                            OR effective_to >= %s
                          )
                    ORDER BY
                        CASE
                            WHEN purity IS NOT NULL
                             AND UPPER(TRIM(purity))=UPPER(TRIM(%s))
                            THEN 0
                            ELSE 1
                        END,
                        effective_from DESC
                    LIMIT 1
                """, (
                    worker_id,
                    process,
                    jewelry_type,
                    row.get("purity"),
                    receive_date,
                    receive_date,
                    row.get("purity")
                ))

                wastage_rule = cur.fetchone()

                # ------------------------------------------------------------
                # NO RULE = ZERO ALLOWANCE
                # ------------------------------------------------------------

                if wastage_rule:

                    allowed_percent = Decimal(
                        str(wastage_rule[0] or 0)
                    )

                else:

                    allowed_percent = Decimal("0.000")

                # ------------------------------------------------------------
                # CALCULATE ALLOWED WASTAGE
                # ------------------------------------------------------------

                allowed_wastage = (
                    issue_weight *
                    allowed_percent /
                    Decimal("100")
                )

                allowed_wastage = max(
                    Decimal("0.000"),
                    min(
                        allowed_wastage,
                        actual_wastage
                    )
                )

                allowed_wastage = allowed_wastage.quantize(
                    Decimal("0.001")
                )

                # ------------------------------------------------------------
                # RECOVERABLE WASTAGE
                # ------------------------------------------------------------

                recoverable_wastage = (
                    actual_wastage -
                    allowed_wastage
                )

                recoverable_wastage = max(
                    Decimal("0.000"),
                    recoverable_wastage
                )

                recoverable_wastage = recoverable_wastage.quantize(
                    Decimal("0.001")
                )

                # ------------------------------------------------------------
                # AMOUNTS
                # ------------------------------------------------------------

                actual_amount = (
                    actual_wastage * per_gram
                ).quantize(Decimal("0.01"))

                allowed_amount = (
                    allowed_wastage * per_gram
                ).quantize(Decimal("0.01"))

                recoverable_amount = (
                    recoverable_wastage * per_gram
                ).quantize(Decimal("0.01"))

                # ------------------------------------------------------------
                # WASTAGE PERCENT
                # ------------------------------------------------------------

                if issue_weight > 0:

                    wastage_percent = (
                        actual_wastage /
                        issue_weight *
                        Decimal("100")
                    ).quantize(Decimal("0.01"))

                else:

                    wastage_percent = Decimal("0.00")

                # ========================================================
                # UPDATE JOB TRANSACTION
                # ========================================================
                cur.execute("""
                    UPDATE job_transaction SET jr_no=%s, receive_weight=%s, labor_amount=%s, receive_date=%s, 
                    wastage=%s, wastage_percent=%s, allowed_wastage=%s, transaction_status='COMPLETED', status='RECEIVED'
                    WHERE job_no=%s AND lot_no=%s
                """, (jr_no, receive_weight, labor, receive_date, actual_wastage, wastage_percent, allowed_wastage, job_no, lot_no))

                # ========================================================
                # UPDATE JEWELRY
                # ========================================================
                # Full actual wastage (allowed + recoverable) always comes
                # off the lot's weight/metal value - the metal is physically
                # gone either way. The ALLOWED portion's cash value is not
                # charged to the worker, so it's absorbed into the lot's
                # own labor/production cost instead.
                # ---------------------------------------------------------

                new_weight = (old_weight - actual_wastage).quantize(
                    Decimal("0.001")
                )

                if jewelry_type == "GOLD":

                    new_amount = (old_amount - actual_amount).quantize(
                        Decimal("0.01")
                    )

                    new_labor = (
                        old_labor + labor + allowed_amount
                    ).quantize(
                        Decimal("0.01")
                    )

                    new_total_cost = (new_amount + new_labor).quantize(
                        Decimal("0.01")
                    )

                    cur.execute("UPDATE gold_jewelry SET weight=%s, gold_amount=%s, labor=%s, total_cost=%s WHERE lot_no=%s",
                                (new_weight, new_amount, new_labor, new_total_cost, lot_no))
                else:
                    # silver_jewelry has no labor/total_cost column, so the
                    # allowed-wastage amount can't be folded in the same way
                    # here - only weight/silver_amount are adjusted.
                    new_amount = (old_amount - actual_amount).quantize(
                        Decimal("0.01")
                    )

                    cur.execute("UPDATE silver_jewelry SET weight=%s, silver_amount=%s WHERE lot_no=%s",
                                (new_weight, new_amount, lot_no))

                # ========================================================
                # GOLD / SILVER TRANSACTION
                # ========================================================
                if actual_wastage > 0:
                    if jewelry_type == "GOLD":
                        cur.execute("""
                            INSERT INTO gold_account (txn_date, purchase_no, lot_no, per_gram, weight, amount, txn_nature, entry_type, source_job, source_worker, source_process)
                            VALUES (%s,%s,%s,%s,%s,%s,'CR','JOB_WASTAGE',%s,%s,%s)
                        """, (receive_date, "", lot_no, per_gram, actual_wastage, actual_amount, job_no, worker, process))
                    else:
                        cur.execute("""
                            INSERT INTO silver_account (txn_date, txn_no, purchase_no, lot_no, per_gram, weight, amount, txn_nature, entry_type, remarks)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,'CR','JOB_WASTAGE',%s)
                        """, (receive_date, jr_no, "", lot_no, per_gram, actual_wastage, actual_amount, f"{job_no} - {worker}"))

                # ========================================================
                # PART-3: WORKER METAL RECOVERY (FIXED INDENTATION)
                # ========================================================
                if recoverable_wastage > 0:
                    cur.execute("""
                        INSERT INTO worker_metal_recovery (
                            txn_date, jr_no, job_no, lot_no, worker_id, worker_name, gold_type, 
                            issue_weight, receive_weight, actual_wastage, allowed_wastage, recoverable_weight, 
                            avg_rate, actual_amount, allowed_amount, recoverable_amount,  
                            recovered_gold_weight, recovered_cash_amount, balance_to_recover_weight, balance_to_recover_amount, 
                            status, process, remarks
                        ) VALUES (
                            %s,%s,%s,%s, %s,%s, %s, %s,%s, %s,%s,%s, %s, %s,%s,%s, 0,0, %s,%s, 'PENDING', %s,%s
                        )
                    """, (
                        receive_date, jr_no, job_no, lot_no, worker_id, worker, jewelry_type, 
                        issue_weight, receive_weight, actual_wastage, allowed_wastage, recoverable_wastage, 
                        per_gram, actual_amount, allowed_amount, recoverable_amount, 
                        recoverable_wastage, recoverable_amount, process, description
                    ))

                # ========================================================
                # LABOR ENTRY
                # ========================================================
                if labor > 0:
                    # Fetch the integer ID for the job_transaction
                    cur.execute("""
                        SELECT id FROM job_transaction 
                        WHERE job_no = %s AND lot_no = %s
                    """, (job_no, lot_no))
                    
                    job_txn_id_row = cur.fetchone()
                    if not job_txn_id_row:
                        raise Exception(f"Transaction ID not found for Job {job_no}, Lot {lot_no}")
                    
                    job_txn_id = job_txn_id_row[0]

                    # FIX: Removed 'RETURNING id' because the 'labor' table doesn't have an 'id' column.
                    cur.execute("""
                        INSERT INTO labor (job_no, jr_no, date, lot_no, worker_id, process, labor_amount, status, remarks)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 'PENDING', %s)
                    """, (job_txn_id, jr_no, receive_date, lot_no, worker_id, process, labor, description))

                # ========================================================
                # PENDING PAYMENT
                # ========================================================
                if labor > 0:
                    # FIX: Use 'job_txn_id' for 'txn_id'. 
                    # This satisfies the 'bigint' requirement and links the payment to the job.
                    cur.execute("""
                        INSERT INTO pending_payments (
                            txn_date, txn_id, purchase_no, account_id, account_name, account_type,
                            txn_type, bill_no, total_amount, paid_amount, balance_amount, payment_status, remarks
                        ) VALUES (
                            %s, %s, %s, %s, %s, 'WORKER', 'LABOR', %s, %s, 0, %s, 'PENDING', %s
                        )
                    """, (
                        receive_date, job_txn_id, "", worker_id, worker, jr_no, labor, labor, lot_no
                    ))

            # ========================================================
            # COMMIT & CLEANUP
            # ========================================================
            conn.commit()
            messagebox.showinfo("Success", f"Job Receive Saved Successfully.\n\nJR No : {jr_no}")

            self.receive_rows.clear()
            if hasattr(self, "sheet"):
                self.sheet.set_sheet_data([])
                self.sheet.refresh()

            # FIX: Call correct method name
            self.generate_jr_no() 

            # FIX: Use correct variable name for search text
            if hasattr(self, "search_text"):
                self.search_text.set("")
            if hasattr(self, "ent_job"):
                self.ent_job.focus_set()

        except Exception as e:
            if conn:
                conn.rollback()
            messagebox.showerror("Save Error", str(e))
        finally:
            if cur: cur.close()
            if conn: conn.close()

# =============================================================
if __name__ == "__main__":
    root = tk.Tk()
    JobReceiveWindow(root)
    root.mainloop()
