import tkinter as tk
from tkinter import ttk, messagebox, PanedWindow
from datetime import datetime
import psycopg2
import tksheet

# ========================= CONFIG =========================
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "mygems"
DB_USER = "myuser"
DB_PASSWORD = "28116"
# =========================================================

class MaterialReturnForm:
    def __init__(self, root):
        self.root = root
        self.root.title("Material Return Form")
        self.root.geometry("1100x680")
        
        self.conn = None
        self.cursor = None
        self.init_db()

        self.search_value_var = tk.StringVar()
        self.jwl_lot_var = tk.StringVar()
        self.jwl_type_var = tk.StringVar()
        self.memo_no_var = tk.StringVar(value="---") # Added for Memo Display
        self.detected_metal = None

        self.create_widgets()
        self.search_value_var.trace_add("write", lambda *args: self.search_value_var.set(self.search_value_var.get().upper()))

    def init_db(self):
        try:
            self.conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
            self.cursor = self.conn.cursor()
        except Exception as e:
            messagebox.showerror("Database Error", f"Init failed:\n{e}")

    def create_widgets(self):
        # 1. Header
        header = tk.Frame(self.root, bg="#2C3E50")
        header.pack(fill=tk.X)
        tk.Label(header, text="MATERIAL RETURN FORM", font=("Helvetica", 16, "bold"), bg="#2C3E50", fg="white", pady=8).pack(side=tk.LEFT, padx=20)
        
        # MEMO NO DISPLAY (TOP RIGHT)
        memo_display_frame = tk.Frame(header, bg="#2C3E50")
        memo_display_frame.pack(side=tk.RIGHT, padx=20)
        tk.Label(memo_display_frame, text="RETURN MEMO NO:", font=("Helvetica", 10, "bold"), bg="#2C3E50", fg="#ECF0F1").pack(side=tk.LEFT)
        tk.Label(memo_display_frame, textvariable=self.memo_no_var, font=("Helvetica", 12, "bold"), bg="#2C3E50", fg="#F1C40F").pack(side=tk.LEFT, padx=5)

        # 2. Search Frame
        search_frame = tk.Frame(self.root, padx=15, pady=8)
        search_frame.pack(fill=tk.X)
        
        tk.Label(search_frame, text="Search No:", font=("Helvetica", 10, "bold")).pack(side=tk.LEFT)
        ttk.Entry(search_frame, textvariable=self.search_value_var, width=20).pack(side=tk.LEFT, padx=5)
        
        tk.Button(search_frame, text="🔍 LOAD LOT", bg="#F39C12", fg="white", command=self.search_and_load_all, width=12).pack(side=tk.LEFT, padx=5)
        tk.Button(search_frame, text="📜 VIEW MEMO", bg="#9B59B6", fg="white", command=self.view_memo_history, width=12).pack(side=tk.LEFT, padx=5)

        tk.Label(search_frame, text="  Lot:", font=("Helvetica", 10, "bold")).pack(side=tk.LEFT, padx=(20,0))
        tk.Label(search_frame, textvariable=self.jwl_lot_var, fg="blue", font=("Helvetica", 10, "bold")).pack(side=tk.LEFT)

        # 3. Action Buttons
        btn_frame = tk.Frame(self.root, pady=10, bg="#F0F0F0")
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        tk.Button(btn_frame, text="NEW / RESET", bg="#3498DB", fg="white", width=15, command=self.new_reset).pack(side=tk.LEFT, padx=20)
        tk.Button(btn_frame, text="SAVE RETURN DATA", bg="#27AE60", fg="white", font=("Helvetica", 10, "bold"), width=25, command=self.save_return).pack(side=tk.LEFT)
        tk.Button(btn_frame, text="CLOSE WINDOW", bg="#E74C3C", fg="white", width=15, command=self.root.destroy).pack(side=tk.RIGHT, padx=20)

        # 4. Paned Window
        self.main_pane = PanedWindow(self.root, orient=tk.VERTICAL, sashrelief=tk.RAISED, sashwidth=6)
        self.main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # SECTION A: REFERENCE
        self.ref_lframe = tk.LabelFrame(self.main_pane, text=" 1. REFERENCE VIEW (Lot Balance / Memo History) ", fg="darkblue")
        self.sheet_ref = tksheet.Sheet(self.ref_lframe, header_bg="#34495E", header_fg="white")
        self.sheet_ref.pack(fill=tk.BOTH, expand=True)
        self.sheet_ref.enable_bindings("single_selection", "column_width_resize", "copy", "rc_select")
        self.main_pane.add(self.ref_lframe, height=220)

        # SECTION B: EDITABLE ENTRY
        self.edit_lframe = tk.LabelFrame(self.main_pane, text=" 2. RETURN ENTRY (Type Values Below) ", fg="green")
        self.sheet_edit = tksheet.Sheet(self.edit_lframe, header_bg="#27AE60", header_fg="white")
        self.sheet_edit.pack(fill=tk.BOTH, expand=True)
        self.sheet_edit.enable_bindings("all") 
        self.sheet_edit.extra_bindings([("cell_select", self.force_edit_mode)]) 
        self.main_pane.add(self.edit_lframe, height=180)

        # SECTION C: HISTORY LOG
        self.hist_lframe = tk.LabelFrame(self.main_pane, text=" 3. TRANSACTION LOG (View Only) ", fg="black")
        self.sheet_hist = tksheet.Sheet(self.hist_lframe, header_bg="#2C3E50", header_fg="white")
        self.sheet_hist.pack(fill=tk.BOTH, expand=True)
        self.sheet_hist.enable_bindings("single_selection", "column_width_resize", "copy")
        self.main_pane.add(self.hist_lframe, height=180)

    def force_edit_mode(self, event):
        col = event.column
        row = event.row
        if col in [2, 3]: 
            self.sheet_edit.focus_set()
            self.sheet_edit.create_text_editor(row, col, state="normal")

    def generate_return_memo_id(self):
        """Generates a unique ID based on current time"""
        return f"RET-{datetime.now().strftime('%y%m%d-%H%M%S')}"

    def search_and_load_all(self):
        val = self.search_value_var.get().strip().upper()
        if not val: return

        try:
            # Detect Metal
            self.detected_metal = None
            for tbl in ["gold_jewelry", "silver_jewelry"]:
                self.cursor.execute(f"SELECT jewelry_type FROM {tbl} WHERE lot_no = %s", (val,))
                res = self.cursor.fetchone()
                if res:
                    self.detected_metal = "Gold" if tbl == "gold_jewelry" else "Silver"
                    self.jwl_type_var.set(res[0] or "")
                    break
            
            if not self.detected_metal:
                messagebox.showinfo("Not Found", f"Lot {val} not found.")
                return

            # Set visuals
            self.jwl_lot_var.set(val)
            self.memo_no_var.set(self.generate_return_memo_id()) # Update Memo No on load
            self.ref_lframe.config(text=f" 1. OUTSTANDING BALANCE FOR LOT: {val} ", fg="darkblue")

            # Load Ref Sheet (Balances)
            self.cursor.execute("""
                SELECT stnlot_no, MAX(stn_type),
                       SUM(CASE WHEN (txn_type='Issue' OR txn_type IS NULL) THEN cts ELSE 0 END) - SUM(CASE WHEN txn_type='Return' THEN cts ELSE 0 END) as bal_cts,
                       SUM(CASE WHEN (txn_type='Issue' OR txn_type IS NULL) THEN pcs ELSE 0 END) - SUM(CASE WHEN txn_type='Return' THEN pcs ELSE 0 END) as bal_pcs
                FROM stone_issues WHERE lot_no = %s GROUP BY stnlot_no ORDER BY stnlot_no
            """, (val,))
            rows = self.cursor.fetchall()
            
            ref_data, edit_data = [], []
            for r in rows:
                if r[2] > 0 or r[3] > 0:
                    ref_data.append([r[0], r[1], f"{float(r[2]):.3f}", r[3]])
                    edit_data.append([r[0], r[1], "0.000", "0"])

            self.sheet_ref.headers(["Stone Lot", "Type", "Bal Cts", "Bal Pcs"])
            self.sheet_ref.set_sheet_data(ref_data)
            self.sheet_ref.readonly_columns(columns=[0,1,2,3], readonly=True)

            self.sheet_edit.headers(["Stone Lot", "Type", "Return Cts", "Return Pcs"])
            self.sheet_edit.set_sheet_data(edit_data)
            self.sheet_edit.readonly_columns(columns=[0, 1], readonly=True)

            # Load History
            self.cursor.execute("SELECT issue_date, issue_no, stnlot_no, cts, pcs, txn_type FROM stone_issues WHERE lot_no = %s ORDER BY id DESC", (val,))
            hist = [[str(x[0]), x[1], x[2], f"{float(x[3]):.3f}", x[4], x[5] or "Issue"] for x in self.cursor.fetchall()]
            self.sheet_hist.set_sheet_data(hist)
            self.sheet_hist.headers(["Date", "Memo No", "Stone Lot", "Cts", "Pcs", "Action"])

            self.sheet_ref.refresh(); self.sheet_edit.refresh(); self.sheet_hist.refresh()

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def view_memo_history(self):
        memo_no = self.search_value_var.get().strip().upper()
        if not memo_no: return

        try:
            self.cursor.execute("SELECT lot_no, stnlot_no, stn_type, cts, pcs, txn_type, issue_date FROM stone_issues WHERE issue_no = %s", (memo_no,))
            rows = self.cursor.fetchall()
            if not rows:
                messagebox.showinfo("Not Found", "Memo not found.")
                return

            self.jwl_lot_var.set(f"VIEWING MEMO: {memo_no}")
            self.memo_no_var.set(memo_no) # Show the memo we are looking at
            self.ref_lframe.config(text=f" 1. MEMO DETAILS: {memo_no} (Read-Only) ", fg="#8E44AD")

            memo_data = [[r[1], r[2], f"{float(r[3]):.3f}", r[4], r[5] or "Issue", str(r[6])] for r in rows]
            self.sheet_ref.headers(["Stone Lot", "Type", "Cts", "Pcs", "Action", "Date"])
            self.sheet_ref.set_sheet_data(memo_data)
            self.sheet_ref.readonly_columns(columns=[0,1,2,3,4,5], readonly=True)
            self.sheet_ref.refresh()

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def save_return(self):
        jwl_lot = self.jwl_lot_var.get()
        if "VIEWING" in jwl_lot or not jwl_lot:
            messagebox.showwarning("Save Blocked", "Please search a Jewelry Lot before saving.")
            return

        try:
            data = self.sheet_edit.get_sheet_data()
            today = datetime.now().strftime('%Y-%m-%d')
            memo_id = self.memo_no_var.get()
            
            total_cts, total_pcs, total_amt, count = 0.0, 0, 0.0, 0
            
            for row in data:
                try:
                    # row[0]=StoneLot, row[1]=Type (e.g. Diamond), row[2]=Cts, row[3]=Pcs
                    r_cts = float(row[2]) if row[2] else 0.0
                    r_pcs = int(float(row[3])) if row[3] else 0
                except ValueError:
                    continue

                if r_cts <= 0 and r_pcs <= 0:
                    continue

                # 1. Fetch current price and stone details
                self.cursor.execute("SELECT per_ct FROM stone_account WHERE stnlot_no = %s", (row[0],))
                res = self.cursor.fetchone()
                price = float(res[0]) if res else 0.0
                
                # Variables to ensure no mix-ups
                stn_type_val = str(row[1])      # This should be 'Diamond', 'Ruby', etc.
                stn_lot_val = str(row[0])
                jwl_type_val = str(self.jwl_type_var.get())
                amt = round(r_cts * price, 2)
                description = f"Return from Jwl Lot: {jwl_lot}"

                # --- 2. UPDATE stone_issues (10 Columns) ---
                sql_issues = """
                    INSERT INTO stone_issues 
                    (issue_no, issue_date, lot_no, stnlot_no, cts, pcs, price, stn_type, jewelry_type, txn_type)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                params_issues = (
                    memo_id, today, jwl_lot, stn_lot_val, 
                    r_cts, r_pcs, amt, stn_type_val, 
                    jwl_type_val, 'Return'
                )
                self.cursor.execute(sql_issues, params_issues)

                # --- 3. ADD TO stone_transactions (9 Columns) ---
                # COLUMN MAPPING:
                # 1.txn_date, 2.stone_type, 3.stnlot_no, 4.description, 5.reference_no, 6.weight, 7.txn_type, 8.per_ct, 9.amount
                sql_trans = """
                    INSERT INTO stone_transactions 
                    (date, stone_type, stnlot_no, description, reference_no, weight, txn_type, per_ct, amount, lot_no)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                params_trans = (
                    today,          # 1. txn_date
                    stn_type_val,   # 2. stone_type (Diamond/Stone)
                    stn_lot_val,    # 3. stnlot_no
                    description,    # 4. description
                    memo_id,        # 5. reference_no
                    r_cts,          # 6. weight (cts)
                    'Return',       # 7. txn_type
                    price,          # 8. per_ct
                    amt,            # 9. amount
                    jwl_lot         # 10. jewelry lot no
                )
                self.cursor.execute(sql_trans, params_trans)

                # --- 4. UPDATE stone_account ---
                self.cursor.execute("""
                    UPDATE stone_account 
                    SET cts = cts + %s, pcs = pcs + %s 
                    WHERE stnlot_no = %s
                """, (r_cts, r_pcs, stn_lot_val))
                
                total_cts += r_cts
                total_pcs += r_pcs
                total_amt += amt
                count += 1

            # --- 5. UPDATE Jewelry Table ---
            if count > 0:
                tbl = "gold_jewelry" if self.detected_metal == "Gold" else "silver_jewelry"
                update_query = f"UPDATE {tbl} SET stn_cts=stn_cts-%s, stn_pcs=stn_pcs-%s, stn_amt=stn_amt-%s WHERE lot_no=%s"
                self.cursor.execute(update_query, (total_cts, total_pcs, total_amt, jwl_lot))
                
                self.conn.commit()
                messagebox.showinfo("Success", f"Return Processed Successfully!\nMemo: {memo_id}")
                self.search_and_load_all()
            else:
                messagebox.showwarning("No Data", "Enter Return Cts or Pcs values first.")

        except Exception as e:
            if self.conn: self.conn.rollback()
            messagebox.showerror("Error", f"Transaction Failed: {str(e)}")

    def new_reset(self):
        self.search_value_var.set("")
        self.jwl_lot_var.set("")
        self.memo_no_var.set("---")
        self.sheet_ref.set_sheet_data([]); self.sheet_edit.set_sheet_data([]); self.sheet_hist.set_sheet_data([])
        self.ref_lframe.config(text=" 1. REFERENCE VIEW (Lot Balance / Memo History) ", fg="darkblue")

if __name__ == "__main__":
    root = tk.Tk()
    app = MaterialReturnForm(root)
    root.mainloop()
