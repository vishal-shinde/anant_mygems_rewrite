import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import psycopg2
import re
from datetime import datetime
from reportlab.lib.pagesizes import A4, A5
from reportlab.pdfgen import canvas
import os
import tempfile
import subprocess
import platform

# ================= CONFIGURATION =================
DB_CONFIG = {
    "dbname": "mygems",
    "user": "myuser",
    "password": "28116",
    "host": "localhost",
    "port": "5432"
}

# ======================================================
# APPLICATION FONTS
# ======================================================

TITLE_FONT  = ("Segoe UI", 22, "bold")
HEADER_FONT = ("Segoe UI", 11, "bold")
LABEL_FONT  = ("Segoe UI", 10)
ENTRY_FONT  = ("Leelawadee UI", 10)
BUTTON_FONT = ("Segoe UI", 10, "bold")
GRID_FONT   = ("Leelawadee UI", 10)

# ======================================================
# SUPERVISOR SETTINGS
# ======================================================

SUPERVISOR_PASSWORD = "220824"      # Change later if required
SUPERVISOR_NAME = "ADMIN"

# ======================================================
# GLOBAL HELPER FOR UPPERCASE ENFORCEMENT
# ======================================================
def force_uppercase(event):
    """
    Automatically converts text in any Entry or Combobox widget 
    to upper case on key release, preserving the cursor position.
    """
    widget = event.widget
    if isinstance(widget, (tk.Entry, ttk.Entry)):
        try:
            if str(widget.cget("state")) == "readonly":
                return
        except Exception:
            pass
        
        # Skip control keys to prevent cursor-jumping issues
        if event.keysym in ("Shift_L", "Shift_R", "Control_L", "Control_R", "Caps_Lock", 
                            "Left", "Right", "Up", "Down", "Home", "End", "Tab", "Escape", 
                            "BackSpace", "Delete"):
            return
            
        pos = widget.index(tk.INSERT)
        original = widget.get()
        uppercased = original.upper()
        if original != uppercased:
            widget.delete(0, tk.END)
            widget.insert(0, uppercased)
            widget.icursor(pos)

# =================================================

def get_db_connection():
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        messagebox.showerror("Connection Error", f"Cannot connect to database:\n{e}")
        return None

def verify_supervisor():
    pwd = simpledialog.askstring(
        "Supervisor Approval",
        "Enter Supervisor Password",
        show="*"
    )

    if pwd is None:
        return False

    if pwd == SUPERVISOR_PASSWORD:
        return True

    messagebox.showerror(
        "Access Denied",
        "Invalid Supervisor Password."
    )
    return False

def add_mis_entry(
        module_name,
        transaction_type,
        job_no,
        lot_no,
        old_gold_weight,
        new_gold_weight,
        old_add_gold,
        new_add_gold,
        old_alloy,
        new_alloy,
        old_total_weight,
        new_total_weight,
        remarks=""
):
    conn = get_db_connection()
    if not conn:
        return

    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO mis_entry
            (
                module_name,
                transaction_type,
                job_no,
                lot_no,
                user_name,
                approved_by,
                old_gold_weight,
                new_gold_weight,
                old_add_gold,
                new_add_gold,
                old_alloy_type,
                new_alloy_type,
                old_total_weight,
                new_total_weight,
                remarks
            )
            VALUES
            (
                %s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s,
                %s,%s,%s
            )
        """,
        (
            str(module_name).upper(),
            str(transaction_type).upper(),
            str(job_no).upper(),
            str(lot_no).upper(),
            "CURRENT USER",
            SUPERVISOR_NAME.upper(),
            old_gold_weight,
            new_gold_weight,
            old_add_gold,
            new_add_gold,
            str(old_alloy).upper(),
            str(new_alloy).upper(),
            old_total_weight,
            new_total_weight,
            str(remarks).upper()
        ))
        conn.commit()
    except Exception as e:
        print("MIS Entry Error :", e)
    finally:
        cur.close()
        conn.close()

# ─────────────────────────────────────────────
#  EDITABLE GRID 
# ─────────────────────────────────────────────
class EditableGrid(tk.Frame):
    def __init__(self, parent, columns, **kwargs):
        super().__init__(parent, **kwargs)
        self.columns = columns
        self.rows = []
        self._setup_ui()

    def _setup_ui(self):
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self.scroll_y = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scroll_x = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.inner_frame = tk.Frame(self.canvas)

        self.canvas.configure(yscrollcommand=self.scroll_y.set, xscrollcommand=self.scroll_x.set)
        self.scroll_y.pack(side="right", fill="y")
        self.scroll_x.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.create_window((0, 0), window=self.inner_frame, anchor="nw")
        self.inner_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        for c, col in enumerate(self.columns):
            lbl = tk.Label(self.inner_frame, text=col, bg="#4A90E2", fg="white",
                           font=("Arial", 9, "bold"), relief="ridge", width=12)
            lbl.grid(row=0, column=c, sticky="nsew")
            self.inner_frame.columnconfigure(c, weight=1)
        self.add_row()

    def add_row(self, data=None, text_color="black"):
        row_idx = len(self.rows) + 1
        row_entries = []
        for c, col in enumerate(self.columns):
            val = data[c] if data and c < len(data) else ""
            ent = tk.Entry(self.inner_frame, font=ENTRY_FONT, relief="solid", bd=1, fg=text_color)
            ent.insert(0, str(val).upper() if val is not None else "")
            ent.grid(row=row_idx, column=c, sticky="nsew", padx=1, pady=1)

            if col != "DESCRIPTION":
                ent.config(
                    state="readonly",
                    readonlybackground="#F5F5F5"
                )
            row_entries.append(ent)
        self.rows.append(row_entries)

    def add_multiple_rows(self, count=5):
        for _ in range(count):
            self.add_row()

    def _calc_total(self, row_entries):
        try:
            w = float(row_entries[1].get() or 0)
            a = float(row_entries[2].get() or 0)
            row_entries[4].config(state="normal")
            row_entries[4].delete(0, tk.END)
            row_entries[4].insert(0, f"{w + a:.3f}")
            row_entries[4].config(state="readonly")
        except ValueError:
            pass

    def get_data(self):
        data = []
        for row in self.rows:
            vals = [e.get().strip().upper() for e in row]
            if any(vals):
                data.append(vals)
        return data

    def clear(self):
        for row in self.rows:
            for e in row:
                e.destroy()
        self.rows.clear()
        self.add_row()

    def load_data(self, dataset):
        self.clear()
        for item in dataset:
            if isinstance(item, tuple) and len(item) == 2:
                data, is_valid = item
                color = "black" if is_valid else "red"
                self.add_row(data, text_color=color)
            else:
                self.add_row(item)

# ─────────────────────────────────────────────
#  JOB ASSIGN WINDOW
# ─────────────────────────────────────────────
class JobAssignWindow(tk.Toplevel):

    def __init__(self, master):
        super().__init__(master)
        self.title("JOB ASSIGN MODULE")
        self.geometry("1000x700")
        self.worker_map = {}
        self._setup_ui()
        self._load_workers()
        self._generate_job_no()

    def _setup_ui(self):
        tk.Label(self, text="JOB ASSIGN", font=("Arial", 18, "bold"), bg="#2C3E50", fg="white", pady=10).pack(fill="x")

        toolbar = tk.Frame(self, bg="#ECF0F1", pady=8)
        toolbar.pack(fill="x", padx=10, pady=5)
        for txt in ["NEW", "FIND", "EDIT", "REPEAT ASSIGN", "SAVE", "PRINT"]:
            cmd = getattr(self, f"_{txt.replace(' ', '_').lower()}", None)
            tk.Button(toolbar, text=txt, font=("Arial", 9, "bold"), width=13, command=cmd).pack(side="left", padx=4)

        hdr_frame = tk.Frame(self, pady=5)
        hdr_frame.pack(fill="x", padx=10)
        tk.Label(hdr_frame, text="Date:", font=("Arial", 10)).pack(side="left", padx=5)
        self.ent_date = tk.Entry(hdr_frame, font=("Arial", 10), width=12)
        self.ent_date.pack(side="left", padx=5)
        self.ent_date.insert(0, datetime.now().strftime("%Y-%m-%d"))

        # ---------------- METAL SELECTION ----------------

        tk.Label(
            hdr_frame,
            text="Metal:",
            font= LABEL_FONT
        ).pack(side="left", padx=(20,5))

        self.metal_var = tk.StringVar(value="GOLD")

        tk.Radiobutton(
            hdr_frame,
            text="Gold",
            variable=self.metal_var,
            value="GOLD",
            font=("Arial",9)
        ).pack(side="left")

        tk.Radiobutton(
            hdr_frame,
            text="Silver",
            variable=self.metal_var,
            value="SILVER",
            font=("Arial",9)
        ).pack(side="left")

        tk.Label(hdr_frame, text="Job No:", font=("Arial", 10)).pack(side="right", padx=5)
        self.ent_jobno = tk.Entry(hdr_frame, font=("Arial", 10), width=12, state="readonly", bg="#f0f0f0")
        self.ent_jobno.pack(side="right", padx=5)

        sel_frame = tk.Frame(self, pady=5)
        sel_frame.pack(fill="x", padx=10)
        tk.Label(sel_frame, text="Worker:", font=LABEL_FONT).pack(side="left", padx=5)
        self.cmb_worker = ttk.Combobox(sel_frame, font=("Arial", 10), width=20, state="readonly")
        self.cmb_worker.pack(side="left", padx=5)

        tk.Label(sel_frame, text="Process:", font=("Arial", 10, "bold")).pack(side="left", padx=10)
        self.cmb_process = ttk.Combobox(sel_frame, font=("Arial", 10), width=10, state="readonly",
                                        values=["FILING", "POLISH", "LASER", "SETTING", "REPAIR"])
        self.cmb_process.pack(side="left", padx=5)

        # --- PAPER SIZE SELECTOR ---
        tk.Label(sel_frame, text="Paper Size:", font=("Arial", 10, "bold")).pack(side="left", padx=10)
        self.cmb_paper_size = ttk.Combobox(sel_frame, font=("Arial", 10), width=5, state="readonly", values=["A5", "A4"])
        self.cmb_paper_size.set("A5")
        self.cmb_paper_size.pack(side="left", padx=5)

        detail_frame = tk.LabelFrame(self, text="Get Existing Details", font=("Arial", 10, "bold"), fg="#2980B9", padx=10, pady=10)
        detail_frame.pack(fill="x", padx=10, pady=5)

        f1 = tk.Frame(detail_frame)
        f1.pack(anchor="w", pady=2)
        tk.Label(f1, text="Lot No / Range:", font=("Arial", 9, "bold")).pack(side="left")
        self.ent_lot_input = tk.Entry(f1, width=25, font=("Arial", 9))
        self.ent_lot_input.pack(side="left", padx=5)
        self.ent_lot_input.bind("<Return>", lambda e: self._fetch_by_lot())

        tk.Button(f1, text="Fetch Lots", command=self._fetch_by_lot, font=("Arial", 9, "bold"), bg="#27AE60", fg="white").pack(side="left", padx=5)
        tk.Label(f1, text="Example : 17 or 17-22", font=("Arial", 8), fg="gray").pack(side="left", padx=5)
        f2 = tk.Frame(detail_frame)
        f2.pack(anchor="w", pady=2)
        tk.Label(f2, text="Metal Transfer ID:", font=("Arial", 9)).pack(side="left")
        self.ent_transfer_id = tk.Entry(f2, width=20, font=("Arial", 9))
        self.ent_transfer_id.pack(side="left", padx=5)
        self.ent_transfer_id.bind("<Return>", lambda e: self._fetch_by_transfer())
        tk.Button(f2, text="Fetch by Transfer", command=self._fetch_by_transfer, font=("Arial", 9, "bold"), bg="#8E44AD", fg="white").pack(side="left", padx=5)

        grid_frame = tk.LabelFrame(self, text="Job Details Entry", font=ENTRY_FONT, padx=5, pady=5)
        grid_frame.pack(fill="both", expand=True, padx=10, pady=5)
        cols = ["LOT_NO", "WEIGHT", "ADD_GOLD", "LOCK_TYPE", "TOTAL_WEIGHT", "DESCRIPTION"]
        self.grid = EditableGrid(grid_frame, cols)
        self.grid.pack(fill="both", expand=True)

        btn_frame = tk.Frame(grid_frame)
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="+ Add Empty Row", command=self.grid.add_row, font=("Arial", 9)).pack(side="left", padx=5)
        tk.Button(btn_frame, text="+ Add 5 Rows", command=lambda: self.grid.add_multiple_rows(5), font=("Arial", 9, "bold"), bg="#F39C12", fg="white").pack(side="left", padx=5)
        
    def _load_workers(self):
        conn = get_db_connection()
        if not conn: return
        try:
            cur = conn.cursor()
            cur.execute("SELECT a.account_id, a.account_name FROM accounts a INNER JOIN account_types at ON a.type_id = at.type_id WHERE at.type_name = 'WORKER' AND at.is_active = TRUE ORDER BY a.account_name")
            workers = cur.fetchall()
            self.worker_map = {name.upper(): wid for wid, name in workers}
            self.cmb_worker['values'] = [name.upper() for _, name in workers]
        except Exception as e:
            messagebox.showerror("DB Error", f"Failed to load workers: {e}")
        finally:
            conn.close()

    def _generate_job_no(self):
        conn = get_db_connection()
        if not conn: return
        try:
            cur = conn.cursor()
            cur.execute("SELECT job_no FROM job_transaction WHERE job_no LIKE 'JA-%' ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            next_num = 1
            if row:
                match = re.search(r'JA-(\d+)', row[0])
                if match: next_num = int(match.group(1)) + 1
            self.ent_jobno.config(state="normal")
            self.ent_jobno.delete(0, tk.END)
            self.ent_jobno.insert(0, f"JA-{next_num}")
            self.ent_jobno.config(state="readonly")
        except Exception as e:
            messagebox.showerror("DB Error", f"Failed to generate Job No: {e}")
        finally:
            conn.close()

    def _fetch_by_lot(self):
        raw = self.ent_lot_input.get().strip().upper()

        if not raw:
            messagebox.showwarning(
                "Input",
                "Enter Lot No or Range (Example : 17 or 17-22)"
            )
            return

        range_match = re.match(r'^(\d+)\s*-\s*(\d+)$', raw)

        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2))

            if start > end:
                start, end = end, start

            lot_list = [str(i) for i in range(start, end + 1)]
        else:
            if not raw.isdigit():
                messagebox.showwarning(
                    "Input",
                    "Invalid Lot Number."
                )
                return
            lot_list = [raw]

        self._load_lots_from_db(lot_list)

    def _load_lots_from_db(self, lot_list):
        conn = get_db_connection()
        if not conn:
            return

        try:
            cur = conn.cursor()
            dataset = []
            missing = []
            metal = self.metal_var.get().upper()

            if metal == "GOLD":
                jewelry_table = "gold_jewelry"
                account_table = "gold_account"
                account_id = "gold_txn_id"
            else:
                jewelry_table = "silver_jewelry"
                account_table = "silver_account"
                account_id = "id"

            for number in lot_list:
                cur.execute(f"""
                    SELECT
                        lot_no,
                        weight,
                        description
                    FROM {jewelry_table}
                    WHERE lot_no LIKE %s
                """, (f"%-{number}",))

                jewelry_rows = cur.fetchall()

                if jewelry_rows:
                    for jrow in jewelry_rows:
                        lot_no = jrow[0].upper()
                        total_weight = jrow[1]
                        description = jrow[2].upper() if jrow[2] else ""

                        cur.execute(f"""
                            SELECT lock_type
                            FROM {account_table}
                            WHERE lot_no=%s
                            ORDER BY txn_date DESC,{account_id} DESC
                            LIMIT 1
                        """,(lot_no,))

                        lock = cur.fetchone()
                        lock_type = lock[0].upper() if lock and lock[0] else ""

                        dataset.append([
                            lot_no,          # LOT_NO
                            total_weight,    # WEIGHT
                            "",              # ADD_GOLD
                            lock_type,       # LOCK_TYPE
                            total_weight,    # TOTAL_WEIGHT
                            description      # DESCRIPTION
                        ])
                else:
                    missing.append(number)
                    
            self.grid.load_data(dataset)

            if missing:
                messagebox.showwarning(
                    "Missing Lots",
                    "Lots not found :\n\n" + ", ".join(missing)
                )

        except Exception as e:
            messagebox.showerror(
                "Error",
                str(e)
            )
        finally:
            conn.close()

    def _is_valid_lot(self, lot_no):
        conn = get_db_connection()
        if not conn: return False
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM GOLD_JEWELRY WHERE lot_no = %s", (lot_no.upper(),))
            if cur.fetchone(): return True
            cur.execute("SELECT 1 FROM SILVER_JEWELRY WHERE lot_no = %s", (lot_no.upper(),))
            if cur.fetchone(): return True
            return False
        finally:
            conn.close()

    def _fetch_by_transfer(self):
        tid = self.ent_transfer_id.get().strip().upper()
        if not tid: return
        conn = get_db_connection()
        if not conn: return
        try:
            cur = conn.cursor()
            cur.execute("SELECT lot_no, weight, add_gold, alloy_type, total_weight, description FROM gold_account WHERE description ILIKE %s ORDER BY lot_no", (f'%{tid}%',))
            rows = cur.fetchall()
            if not rows:
                cur.execute("SELECT lot_no, weight, add_gold, alloy_type, total_weight, description FROM job_transaction WHERE description ILIKE %s ORDER BY lot_no", (f'%{tid}%',))
                rows = cur.fetchall()

            if rows:
                dataset = [[r[0].upper(), r[1], r[2], str(r[3]).upper() if r[3] else "", r[4], str(r[5]).upper() if r[5] else ""] for r in rows]
                self.grid.load_data(dataset)
            else:
                messagebox.showinfo("Not Found", f"No records for Transfer ID: {tid}")
        except Exception as e:
            messagebox.showerror("Error", f"Transfer fetch failed: {e}")
        finally:
            conn.close()

    def _new(self):
        self.grid.clear()
        self.cmb_worker.set('')
        self.cmb_process.set('')
        self.ent_lot_input.delete(0, tk.END)
        self.ent_transfer_id.delete(0, tk.END)
        self.ent_date.delete(0, tk.END)
        self.ent_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self._generate_job_no()

    def _save(self):
        job_no = self.ent_jobno.get().strip().upper()
        txn_date = self.ent_date.get().strip().upper()
        worker = self.cmb_worker.get().strip().upper()
        process = self.cmb_process.get().strip().upper()

        if not all([job_no, txn_date, worker, process]):
            messagebox.showwarning("Validation", "Fill Date, Worker, and Process.")
            return
        
        account_id = self.worker_map.get(worker)
        if not account_id:
            messagebox.showerror("Error", "Selected worker not found.")
            return
            
        rows = self.grid.get_data()
        if not rows:
            messagebox.showwarning("Validation", "Grid is empty.")
            return

        invalid_lots = []
        for r in rows:
            lot_name = r[0].upper()
            if not self._is_valid_lot(lot_name):
                invalid_lots.append(lot_name)
                
        if invalid_lots:
            messagebox.showerror("Save Aborted", f"The following lots DO NOT exist in GOLD_JEWELRY or SILVER_JEWELRY:\n\n{', '.join(invalid_lots)}\n\nPlease remove or correct them before saving.")
            return

        conn = get_db_connection()
        if not conn: return
        cur = conn.cursor()
        try:
            cur.execute("SELECT 1 FROM job_transaction WHERE job_no=%s", (job_no,))
            existing_job = cur.fetchone() is not None
            count = 0
            for r in rows:
                lot_no = r[0].upper()
                w = float(r[1] or 0)
                ag = float(r[2] or 0)
                at = r[3].upper()
                tw = float(r[4] or 0)
                desc = r[5].upper()

                if existing_job:
                    cur.execute("UPDATE job_transaction SET weight=%s, add_gold=%s, alloy_type=%s, total_weight=%s, process=%s, txn_type=%s, account_id=%s, account_name=%s, description=%s WHERE job_no=%s AND lot_no=%s",
                                (w, ag, at, tw, process, "ASSIGN", account_id, worker, desc, job_no, lot_no))
                else:
                    cur.execute("INSERT INTO job_transaction (txn_date, job_no, lot_no, weight, add_gold, total_weight, alloy_type, process, rec_weight, txn_type, amount, account_id, account_name, description, status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                                (txn_date, job_no, lot_no, w, ag, tw, at, process, 0, "ASSIGN", 0, account_id, worker, desc, "WITH WORKER"))
                count += 1
            conn.commit()
            messagebox.showinfo("Success", f"Saved {count} entries for Job {job_no}")
            self._new()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("DB Error", f"Save failed: {e}")
        finally:
            cur.close()
            conn.close()

    def _find(self):
        win = tk.Toplevel()
        win.title("Find Job")
        win.geometry("350x170")
        win.resizable(False, False)
        win.grab_set()

        search_type = tk.StringVar(value="JOB")

        tk.Label(win,
                 text="Search By",
                 font=("Segoe UI",10,"bold")
        ).pack(pady=(10,5))

        frm = tk.Frame(win)
        frm.pack()

        tk.Radiobutton(frm,
                       text="Job No",
                       variable=search_type,
                       value="JOB",
                       command=lambda:update_label()
        ).grid(row=0,column=0,padx=10)

        tk.Radiobutton(frm,
                       text="Date",
                       variable=search_type,
                       value="DATE",
                       command=lambda:update_label()
        ).grid(row=0,column=1,padx=10)

        lbl = tk.Label(win,text="Job No")
        lbl.pack(pady=(10,2))

        ent = tk.Entry(win,width=20,font=("Segoe UI",10))
        ent.pack()

        def update_label():
            if search_type.get()=="JOB":
                lbl.config(text="Job No")
            else:
                lbl.config(text="Date (YYYY-MM-DD)")

        def do_search():
            value = ent.get().strip().upper()
            if not value:
                return
            win.destroy()

            if search_type.get()=="JOB":
                self._load_job(value)
            else:
                self._find_by_date(value)

        tk.Button(win,
                  text="Search",
                  width=12,
                  command=do_search
        ).pack(pady=12)
            
    def _find_by_job(self):
        job_no = simpledialog.askstring(
            "Find Job",
            "Enter Job No:"
        )
        if not job_no:
            return
        job_no = job_no.upper()

        conn = get_db_connection()
        if not conn:
            return

        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    txn_date,
                    process,
                    account_name,
                    lot_no,
                    weight,
                    add_gold,
                    alloy_type,
                    total_weight,
                    description
                FROM job_transaction
                WHERE job_no=%s
                ORDER BY id
            """,(job_no,))

            rows = cur.fetchall()
            if not rows:
                messagebox.showerror(
                    "Not Found",
                    f"No records for {job_no}"
                )
                return

            dataset = [[r[3].upper(), r[4], r[5], str(r[6]).upper() if r[6] else "", r[7], str(r[8]).upper() if r[8] else ""] for r in rows]
            self.grid.load_data(dataset)

            self.ent_date.delete(0,tk.END)
            self.ent_date.insert(0,str(rows[0][0]))

            self.cmb_process.set(rows[0][1].upper())

            if rows[0][2]:
                self.cmb_worker.set(rows[0][2].upper())

            self.ent_jobno.config(state="normal")
            self.ent_jobno.delete(0,tk.END)
            self.ent_jobno.insert(0,job_no)
            self.ent_jobno.config(state="readonly")
        finally:
            conn.close()

    def _find_by_date(self, job_date):
        if not job_date:
            return

        conn = get_db_connection()
        if not conn:
            return

        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    job_no,
                    account_name,
                    process,
                    COUNT(*)
                FROM job_transaction
                WHERE txn_date=%s
                GROUP BY
                    job_no,
                    account_name,
                    process
                ORDER BY job_no
            """,(job_date,))

            rows = cur.fetchall()
            if not rows:
                messagebox.showinfo(
                    "No Data",
                    "No Jobs Found."
                )
                return

            self._show_job_list(rows)
        except Exception as e:
            messagebox.showerror(
                "Error",
                str(e)
            )
        finally:
            conn.close()

    def _load_job(self, job_no):
        job_no = job_no.upper()
        conn = get_db_connection()
        if not conn:
            return

        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    txn_date,
                    process,
                    account_name,
                    lot_no,
                    weight,
                    add_gold,
                    alloy_type,
                    total_weight,
                    description
                FROM job_transaction
                WHERE job_no=%s
                ORDER BY id
            """,(job_no,))

            rows = cur.fetchall()
            if not rows:
                messagebox.showerror(
                    "Not Found",
                    f"{job_no} not found."
                )
                return

            dataset=[]
            for r in rows:
                dataset.append([
                    r[3].upper(),                          # lot
                    r[4],                                  # weight
                    r[5],                                  # add gold
                    str(r[6]).upper() if r[6] else "",     # lock/alloy
                    r[7],                                  # total weight
                    str(r[8]).upper() if r[8] else ""      # description
                ])

            self.grid.load_data(dataset)

            self.ent_date.delete(0,tk.END)
            self.ent_date.insert(0,str(rows[0][0]))

            self.cmb_process.set(rows[0][1].upper())
            self.cmb_worker.set(rows[0][2].upper())

            self.ent_jobno.config(state="normal")
            self.ent_jobno.delete(0,tk.END)
            self.ent_jobno.insert(0,job_no)
            self.ent_jobno.config(state="readonly")
        except Exception as e:
            messagebox.showerror("Error",str(e))
        finally:
            conn.close()

    def _show_job_list(self, rows):
        win = tk.Toplevel(self)
        win.title("Jobs")
        win.geometry("500x400")

        lb = tk.Listbox(
            win,
            selectmode=tk.EXTENDED,
            font=("Segoe UI",10)
        )
        lb.pack(fill="both",expand=True,padx=10,pady=10)

        job_map=[]
        for r in rows:
            txt=f"{r[0].upper()}    {r[1].upper()}    {r[2].upper()}    ({r[3]} Lots)"
            lb.insert(tk.END,txt)
            job_map.append(r[0].upper())

        def open_selected():
            sel=lb.curselection()
            if not sel:
                return
            job_no=job_map[sel[0]]
            win.destroy()
            self._load_job(job_no)

        tk.Button(
            win,
            text="Open Selected",
            command=open_selected,
            width=18
        ).pack(pady=5)

    def _edit(self):
        job_no = self.ent_jobno.get().strip().upper()
        worker = self.cmb_worker.get().strip().upper()
        process = self.cmb_process.get().strip().upper()

        if not job_no or not worker:
            messagebox.showwarning("Edit", "Load a Job and Select Worker.")
            return
        account_id = self.worker_map.get(worker)
        conn = get_db_connection()
        if not conn: return
        try:
            cur = conn.cursor()
            cur.execute("UPDATE job_transaction SET account_id=%s, account_name=%s, process=%s WHERE job_no=%s", (account_id, worker, process, job_no))
            conn.commit()
            messagebox.showinfo("Success", f"{job_no} updated.")
        except Exception as e:
            conn.rollback()
            messagebox.showerror("Error", str(e))
        finally:
            cur.close(); conn.close()

    def _repeat_assign(self):
        old_job_no = simpledialog.askstring("Repeat Assign", "Enter Job No to Repeat:")
        if not old_job_no: return
        old_job_no = old_job_no.upper()

        conn = get_db_connection()
        if not conn: return
        try:
            cur = conn.cursor()
            cur.execute("SELECT lot_no, weight, add_gold, alloy_type, total_weight, description FROM job_transaction WHERE job_no = %s ORDER BY id", (old_job_no,))
            rows = cur.fetchall()
            if not rows:
                messagebox.showerror("Error", f"No records for {old_job_no}")
                return
            valid_rows = []
            for row in rows:
                cur.execute("SELECT 1 FROM job_transaction WHERE lot_no=%s AND status='WITH WORKER'", (row[0],))
                if not cur.fetchone():
                    formatted_row = [row[0].upper(), row[1], row[2], str(row[3]).upper() if row[3] else "", row[4], str(row[5]).upper() if row[5] else ""]
                    valid_rows.append(formatted_row)

            if not valid_rows:
                messagebox.showwarning("Already Assigned", "All lots already with workers.")
                return
            self.grid.load_data(valid_rows)
            self._generate_job_no()
            messagebox.showinfo("Success", f"{len(valid_rows)} rows loaded.\nSelect another worker and Save.")
        except Exception as e:
            messagebox.showerror("Error", str(e))
        finally:
            cur.close(); conn.close()

    # ────────── PRINT (A4/A5 Dynamic, 2cm Box, Dynamic Items Max) ──────────
    def _print(self):
        job_no = self.ent_jobno.get().upper()
        worker = self.cmb_worker.get().upper()
        date = self.ent_date.get().upper()
        process = self.cmb_process.get().upper()
        rows = self.grid.get_data()

        if not rows:
            messagebox.showwarning("Print", "No data to print.")
            return

        try:
            paper_size_str = self.cmb_paper_size.get()
            
            # --- DYNAMIC CONFIGURATION BASED ON PAPER SIZE ---
            if paper_size_str == "A4":
                pagesize = A4
                margin = 50
                col_widths = [60, 50, 50, 50, 50, 178, 57] # Total width = 495
                ITEMS_PER_PAGE = 9                         # Comfortably fits 9 items on A4
            else:
                pagesize = A5
                margin = 30
                col_widths = [50, 40, 40, 40, 40, 93, 57]  # Total width = 360
                ITEMS_PER_PAGE = 5                         # Comfortably fits 5 items on A5

            tmp_dir = tempfile.gettempdir()
            pdf_path = os.path.join(tmp_dir, f"{job_no}_AssignBill_{paper_size_str}.pdf")
            c = canvas.Canvas(pdf_path, pagesize=pagesize)
            w, h = pagesize

            BOX_SIZE = 57  # 2cm x 2cm (approx 56.7 points)
            ROW_HEIGHT = 65 
            item_count = 0
            memo_num = 1
            total_wt = 0
            page_wt = 0
            total_items = len(rows)  # Global summary total count

            def draw_header(memo_number):
                c.setFont("Helvetica-Bold", 14 if paper_size_str == "A5" else 16)
                c.drawString(margin, h - margin, "JOB ASSIGNMENT BILL")
                c.setFont("Helvetica-Bold", 10 if paper_size_str == "A5" else 12)
                c.drawString(margin, h - margin - 20, f"JOB NO: {job_no}  |  MEMO-{memo_number}")
                c.setFont("Helvetica", 9 if paper_size_str == "A5" else 10)
                c.drawString(w/2, h - margin - 20, f"DATE: {date}")
                c.drawString(margin, h - margin - 40, f"WORKER: {worker}")
                c.drawString(w/2, h - margin - 40, f"PROCESS: {process}")
                c.line(margin, h - margin - 50, w - margin, h - margin - 50)

                y_pos = h - margin - 70
                col_names = ["Lot No", "Weight", "Add Gold", "Alloy", "Total Wt", "Description", "Sketch (2x2cm)"]
                x_pos = margin
                c.setFont("Helvetica-Bold", 8 if paper_size_str == "A5" else 9)
                for index, cn in enumerate(col_names):
                    c.drawString(x_pos, y_pos, cn.upper())
                    x_pos += col_widths[index]
                c.line(margin, y_pos - 5, w - margin, y_pos - 5)
                return y_pos - 10

            y = draw_header(memo_num)

            for r in rows:
                if item_count == ITEMS_PER_PAGE:
                    # Draw Intermediate Page Footer
                    c.line(margin, y + 10, w - margin, y + 10)
                    c.setFont("Helvetica-Bold", 9)
                    c.drawString(w - margin - 150, y - 10, f"PAGE ITEMS: {item_count}")
                    c.drawString(w - margin - 150, y - 25, f"PAGE WEIGHT: {page_wt:.3f} G")
                    c.drawString(margin, y - 25, "AUTHORIZED SIGNATURE: _________________")
                    
                    c.showPage()
                    memo_num += 1
                    item_count = 0
                    page_wt = 0
                    y = draw_header(memo_num)

                # Draw Row Data
                x = margin
                text_y = y - (ROW_HEIGHT / 2) + 5 
                c.setFont("Helvetica", 8 if paper_size_str == "A5" else 9)
                for i in range(6):
                    val = str(r[i]).upper() if r[i] else ""
                    c.drawString(x, text_y, val)
                    x += col_widths[i]

                # Draw 2x2cm Sketch Box
                box_x = x
                box_y = y - ROW_HEIGHT + 4
                c.rect(box_x, box_y, BOX_SIZE, BOX_SIZE)
                
                # Bottom border for row
                c.line(margin, y - ROW_HEIGHT, w - margin, y - ROW_HEIGHT)

                wt = float(r[4] or 0)
                total_wt += wt
                page_wt += wt
                y -= ROW_HEIGHT
                item_count += 1

            # Final Page Footer (aligns perfectly to the dynamically computed bottom coordinate)
            c.line(margin, y + 10, w - margin, y + 10)
            c.setFont("Helvetica-Bold", 10)
            c.drawString(w - margin - 150, y - 10, f"TOTAL ITEMS: {total_items}")
            c.drawString(w - margin - 150, y - 25, f"TOTAL WEIGHT: {total_wt:.3f} G")
            c.drawString(margin, y - 25, "AUTHORIZED SIGNATURE: _________________")

            c.save()

            if platform.system() == "Darwin": subprocess.call(("open", pdf_path))
            elif platform.system() == "Windows": os.startfile(pdf_path)
            else: subprocess.call(("xdg-open", pdf_path))
        except Exception as e:
            messagebox.showerror("Print Error", str(e))

# ═══════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    
    # ENFORCE UPPER-CASE GLOBALLY: Binds the uppercase validator to all entry widget strokes
    root.bind_class("Entry", "<KeyRelease>", force_uppercase)
    
    app = JobAssignWindow(root)
    def on_close():
        app.destroy()
        root.destroy()
    app.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()
