import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import db
from decimal import Decimal

def safe_float(val):
    if isinstance(val, Decimal):
        return float(val)
    try:
        return float(val) if val is not None else 0.0
    except:
        return 0.0

BG = "#f4f6f9"
HEADER = "#2c3e50"
BTN = "#2980b9"

# ---------------- DB HELPERS ----------------

def get_tables(metal):
    return ("GOLD_JEWELRY", "GOLD_ACCOUNT") if metal == "GOLD" else ("SILVER_JEWELRY", "SILVER_ACCOUNT")

def fetch_all(query, params=None):
    return db.fetch_all(query, params or ())

def execute(query, params=None):
    db.execute(query, params or ())

def lot_exists(table, lot):
    r = fetch_all(f"SELECT COUNT(*) FROM {table} WHERE lot_no=%s", (lot,))
    return r[0][0] > 0

def get_per_gram(table, lot):
    r = fetch_all(f"SELECT per_gram FROM {table} WHERE lot_no=%s LIMIT 1", (lot,))
    return safe_float(r[0][0]) if r else 0.0

def get_stock_lots(table):
    r = fetch_all(f"SELECT lot_no FROM {table} WHERE jewelry_type='STOCK'")
    return [x[0] for x in r]

def get_current_lock(account, lot):
    r = fetch_all(f"""
        SELECT lock_type FROM {account}
        WHERE lot_no=%s AND lock_type IS NOT NULL
        ORDER BY txn_date DESC LIMIT 1
    """, (lot,))
    return r[0][0] if r else None

def get_lock_lots(table):
    """Fetch lot_no from jewelry table where jewelry_type = 'LOCK'"""
    r = fetch_all(f"SELECT lot_no FROM {table} WHERE jewelry_type='LOCK'")
    return [x[0] for x in r]


# ---------------- APP ----------------

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Metal Transfer System")
        self.root.geometry("1100x700")
        self.root.configure(bg=BG)

        self.metal = tk.StringVar(value="GOLD")
        self.mode = None
        self.transfer_id = self.generate_transfer_id()
        self.last_prefix = ""
        
        self.build_header()
        self.build_menu_bar()
        self.build_metal_selector()
        self.build_notebook()
        self.build_common_table()
        self.build_bottom_buttons()
        
        # Build inputs inside each tab
        self.build_lot_inputs()
        self.build_stock_inputs()
        self.build_lock_inputs()
        self.build_change_inputs()
        
        self.set_mode("LOT")

        self.edit_transfer_id = None   # non‑None when we loaded a transfer to edit

    def to_upper(self, var):
        var.set(var.get().upper())

    # ---------------- TRANSFER ID AS INTEGER ----------------
    def generate_transfer_id(self):
        """Return integer transfer_id (e.g., 2072601) = next available."""
        try:
            prefix = datetime.now().strftime("%d%m%y")

            # Get all transfer_ids from both metal accounts
            rows = fetch_all("""
                SELECT transfer_id FROM GOLD_ACCOUNT WHERE transfer_id IS NOT NULL
                UNION ALL
                SELECT transfer_id FROM SILVER_ACCOUNT WHERE transfer_id IS NOT NULL
            """)

            max_id = 0
            for (tid_str,) in rows:
                if not tid_str:
                    continue
                # strip any 'MT-' prefix (case‑insensitive)
                cleaned = tid_str.replace('MT-', '').replace('mt-', '')
                try:
                    tid_int = int(cleaned)
                    # only consider IDs from today's prefix
                    if str(tid_int).startswith(prefix) and tid_int > max_id:
                        max_id = tid_int
                except ValueError:
                    pass

            if max_id > 0:
                return max_id + 1
            else:
                return int(prefix + "01")
        except Exception as e:
            print("Error generating transfer ID:", e)
            return int(datetime.now().strftime("%d%m%y") + "01")

    def format_transfer_id(self, tid):
        """Convert integer to display format MT-XXXXXX"""
        return f"MT-{tid}"

    def parse_transfer_id(self, text):
        """Parse 'MT-2072601' or '2072601' to integer 2072601"""
        text = text.strip().upper().replace("MT-", "")
        try:
            return int(text)
        except:
            return None

    # ---------------- HEADER ----------------

    def build_header(self):
        top = tk.Frame(self.root, bg=HEADER)
        top.pack(fill="x")

        tk.Label(top, text="METAL TRANSFER SYSTEM",
                 bg=HEADER, fg="white", font=("Segoe UI", 16, "bold")).pack(side="left", padx=20)

        self.id_label = tk.Label(top, text=f"TRANSFER_ID: {self.format_transfer_id(self.transfer_id)}",
                                 bg=HEADER, fg="white")
        self.id_label.pack(side="right", padx=20)

        tk.Label(top, text=datetime.now().strftime("%d/%m/%Y"),
                 bg=HEADER, fg="white").pack(side="right")

    # ---------------- MENU BAR WITH FIND ----------------
    def build_menu_bar(self):
        menu = tk.Frame(self.root, bg="#34495e")
        menu.pack(fill="x")

        find_lbl = tk.Label(menu, text="FIND TRANSFER", bg="#34495e", fg="white", padx=20, cursor="hand2",
                            font=("Segoe UI", 10, "bold"))
        find_lbl.pack(side="left")
        find_lbl.bind("<Button-1>", lambda e: self.open_find_dialog())

        lbl = tk.Label(menu, text="ADD LOCK LOGIC", bg="#34495e", fg="white", padx=20, cursor="hand2")
        lbl.pack(side="left")
        lbl.bind("<Button-1>", lambda e: self.open_lock_master())

    # --------------- ADD LOCK LOGIC POPUP ----------
    def open_lock_master(self):
        win = tk.Toplevel(self.root)
        win.title("Lock Master")
        win.geometry("700x550")

        metal_var = tk.StringVar(value="GOLD")

        radio_frame = tk.Frame(win)
        radio_frame.pack(pady=10)

        tk.Radiobutton(radio_frame, text="Gold", variable=metal_var, value="GOLD",
                       command=lambda: load_data()).pack(side="left", padx=20)
        tk.Radiobutton(radio_frame, text="Silver", variable=metal_var, value="SILVER",
                       command=lambda: load_data()).pack(side="left", padx=20)

        table_frame = tk.Frame(win)
        table_frame.pack(fill="both", expand=True, padx=10)

        table = ttk.Treeview(table_frame, columns=("lot", "weight", "price"), show="headings", height=10)
        table.heading("lot", text="STOCK LOT")
        table.heading("weight", text="WEIGHT / PC")
        table.heading("price", text="PRICE PER PC")
        table.column("lot", width=150)
        table.column("weight", width=150)
        table.column("price", width=150)
        table.pack(fill="both", expand=True, side="top")

        summary_frame = tk.Frame(win, bg="#ecf0f1", pady=10)
        summary_frame.pack(fill="x", padx=10, pady=5)

        total_weight_label = tk.Label(summary_frame, text="Total Weight: 0.00 g", font=("Arial", 10, "bold"), bg="#ecf0f1")
        total_weight_label.pack(side="left", padx=20)

        total_price_label = tk.Label(summary_frame, text="Total Price: ₹0.00", font=("Arial", 10, "bold"), bg="#ecf0f1")
        total_price_label.pack(side="left", padx=20)

        def load_data():
            table.delete(*table.get_children())
            jewelry, _ = get_tables(metal_var.get())
            lots = fetch_all(f"SELECT lot_no, per_gram FROM {jewelry} WHERE jewelry_type='LOCK'")

            total_weight = 0.0
            total_price = 0.0

            for lot, per_gram in lots:
                per_gram = safe_float(per_gram)
                weight_row = fetch_all("SELECT weight_per_piece FROM LOCK_MASTER WHERE stock_lot=%s", (lot,))
                weight = safe_float(weight_row[0][0]) if weight_row else 0.0
                price = weight * per_gram

                total_weight += weight
                total_price += price

                table.insert("", "end", values=(lot, f"{weight:.3f}", f"₹{price:.2f}"))

            total_weight_label.config(text=f"Total Weight: {total_weight:.3f} g")
            total_price_label.config(text=f"Total Price: ₹{total_price:.2f}")

        load_data()

        def edit():
            item = table.focus()
            if not item:
                messagebox.showwarning("No Selection", "Please select a row to edit.")
                return

            values = table.item(item)["values"]
            lot = values[0]

            edit_win = tk.Toplevel(win)
            edit_win.title(f"Edit Weight for {lot}")
            edit_win.geometry("300x150")

            tk.Label(edit_win, text=f"Stock Lot: {lot}").pack(pady=5)
            tk.Label(edit_win, text="Weight per Piece (g):").pack(pady=5)

            w_entry = tk.Entry(edit_win, width=15)
            current_weight = values[1]
            if isinstance(current_weight, str):
                current_weight = current_weight.replace(' g', '').replace('₹', '').strip()
            w_entry.insert(0, current_weight)
            w_entry.pack(pady=5)

            def save():
                try:
                    w = float(w_entry.get())
                    selected_metal = metal_var.get()

                    exists = fetch_all("SELECT 1 FROM LOCK_MASTER WHERE stock_lot=%s", (lot,))
                    if exists:
                        execute("""
                            UPDATE LOCK_MASTER 
                            SET weight_per_piece=%s, lock_type='DEFAULT', metal=%s 
                            WHERE stock_lot=%s
                        """, (w, selected_metal, lot))
                    else:
                        execute("""
                            INSERT INTO LOCK_MASTER (lock_type, metal, stock_lot, weight_per_piece) 
                            VALUES ('DEFAULT', %s, %s, %s)
                        """, (selected_metal, lot, w))

                    load_data()
                    edit_win.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Invalid weight: {str(e)}")

            tk.Button(edit_win, text="SAVE", bg="green", fg="white", command=save).pack(pady=10)

        tk.Button(win, text="EDIT WEIGHT", bg="#3498db", fg="white", command=edit).pack(pady=10)

    def get_lock_composition(self, jewelry_table, lock_name):
        """Returns (total_weight, total_amount) for given lock type by summing its components."""
        if lock_name == "NONE":
            return 0.0, 0.0

        parts = fetch_all("""
            SELECT lm.weight_per_piece, j.per_gram
            FROM LOCK_MASTER lm
            JOIN {} j ON lm.stock_lot = j.lot_no
            WHERE lm.stock_lot = %s
        """.format(jewelry_table), (lock_name,))

        total_weight = 0.0
        total_amount = 0.0

        for w_pc, per_gram in parts:
            w_pc = safe_float(w_pc)
            per_gram = safe_float(per_gram)
            total_weight += w_pc
            total_amount += w_pc * per_gram

        return total_weight, total_amount

    #----------search lot-----------------------
    
    def open_lot_search(self, target_var, jewelry_type_filter=None, title="Search Lot"):
        """Reusable lot search dialog"""
        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry("680x520")
        win.transient(self.root)
        win.grab_set()
        win.resizable(False, False)

        jewelry_table, account_table = get_tables(self.metal.get())

        tk.Label(win, text=title, font=("Arial", 14, "bold")).pack(pady=8)

        # Search Frame
        search_frame = tk.Frame(win)
        search_frame.pack(fill="x", padx=15, pady=5)

        tk.Label(search_frame, text="Search:").pack(side="left")
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
        search_entry.pack(side="left", padx=5)
        search_entry.focus()

        # Filter by type
        filter_var = tk.StringVar(value=jewelry_type_filter or "ALL")
        ttk.Radiobutton(search_frame, text="All", variable=filter_var, 
                       value="ALL", command=lambda: refresh()).pack(side="right", padx=5)
        ttk.Radiobutton(search_frame, text="STOCK", variable=filter_var, 
                       value="STOCK", command=lambda: refresh()).pack(side="right", padx=5)
        ttk.Radiobutton(search_frame, text="LOCK", variable=filter_var, 
                       value="LOCK", command=lambda: refresh()).pack(side="right", padx=5)

        # Treeview
        columns = ("lot", "type", "per_gram", "current_lock")
        tree = ttk.Treeview(win, columns=columns, show="headings", height=15)
        tree.heading("lot", text="Lot No")
        tree.heading("type", text="Type")
        tree.heading("per_gram", text="Per Gram ₹")
        tree.heading("current_lock", text="Current Lock")
        tree.column("lot", width=160)
        tree.column("type", width=90)
        tree.column("per_gram", width=110)
        tree.column("current_lock", width=130)
        tree.pack(fill="both", expand=True, padx=15, pady=10)

        def refresh():
            tree.delete(*tree.get_children())
            ftype = filter_var.get()
            search_text = f"%{search_var.get().strip().upper()}%"

            where_clause = ""
            params = [search_text]
            if ftype != "ALL":
                where_clause = " AND jewelry_type = %s"
                params.append(ftype)

            query = f"""
                SELECT j.lot_no, j.jewelry_type, j.per_gram,
                       COALESCE((SELECT lock_type FROM {account_table} 
                                 WHERE lot_no = j.lot_no 
                                 ORDER BY txn_date DESC LIMIT 1), 'NONE') as current_lock
                FROM {jewelry_table} j
                WHERE j.lot_no ILIKE %s{where_clause}
                ORDER BY j.lot_no
                LIMIT 500
            """
            rows = fetch_all(query, tuple(params))

            for row in rows:
                tree.insert("", "end", values=(
                    row[0], 
                    row[1], 
                    f"{safe_float(row[2]):.2f}", 
                    row[3]
                ))

        # Live search
        search_var.trace_add("write", lambda *args: refresh())

        def select_lot():
            selected = tree.selection()
            if selected:
                lot_no = tree.item(selected[0])["values"][0]
                target_var.set(lot_no)
                if '-' in str(lot_no):
                    self.last_prefix = str(lot_no).split('-')[0]
                win.destroy()

        # Buttons
        btn_frame = tk.Frame(win)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="SELECT", bg="green", fg="white", width=12,
                  command=select_lot).pack(side="left", padx=10)
        tk.Button(btn_frame, text="CANCEL", bg="#e74c3c", fg="white", width=12,
                  command=win.destroy).pack(side="left", padx=10)

        # Double click support
        tree.bind("<Double-1>", lambda e: select_lot())

        refresh()  # Initial load

    # ---------------- FIND DIALOG WITH PREV/NEXT ----------------
    def open_find_dialog(self):
        """Enhanced Find Transfer dialog with multiple search options and LOAD to main form"""
        win = tk.Toplevel(self.root)
        win.title("Find Transfer")
        win.geometry("1000x620")
        win.transient(self.root)
        win.grab_set()
        win.resizable(True, True)

        # ----------------------------------------------------------------
        # TOP: Search Bar
        # ----------------------------------------------------------------
        search_outer = tk.LabelFrame(win, text=" Search ", font=("Arial", 10, "bold"),
                                      bg="#ecf0f1", pady=8, padx=10)
        search_outer.pack(fill="x", padx=10, pady=8)

        # Search type selector
        search_type = tk.StringVar(value="TRANSFER_ID")

        tk.Radiobutton(search_outer, text="By Transfer ID", variable=search_type,
                       value="TRANSFER_ID", bg="#ecf0f1",
                       command=lambda: toggle_inputs()).grid(row=0, column=0, padx=8)
        tk.Radiobutton(search_outer, text="By Date", variable=search_type,
                       value="DATE", bg="#ecf0f1",
                       command=lambda: toggle_inputs()).grid(row=0, column=1, padx=8)
        tk.Radiobutton(search_outer, text="By Lot No", variable=search_type,
                       value="LOT", bg="#ecf0f1",
                       command=lambda: toggle_inputs()).grid(row=0, column=2, padx=8)

        # --- Transfer ID input ---
        tid_frame = tk.Frame(search_outer, bg="#ecf0f1")
        tid_frame.grid(row=1, column=0, padx=8, pady=5, sticky="w")
        tk.Label(tid_frame, text="Transfer ID:", bg="#ecf0f1").pack(side="left")
        tid_var = tk.StringVar(value=self.format_transfer_id(self.transfer_id))
        tid_entry = ttk.Entry(tid_frame, textvariable=tid_var, width=20, font=("Arial", 10))
        tid_entry.pack(side="left", padx=5)

        # --- Date input ---
        date_frame = tk.Frame(search_outer, bg="#ecf0f1")
        date_frame.grid(row=1, column=1, padx=8, pady=5, sticky="w")
        tk.Label(date_frame, text="Date (DD/MM/YYYY):", bg="#ecf0f1").pack(side="left")
        date_var = tk.StringVar(value=datetime.now().strftime("%d/%m/%Y"))
        date_entry = ttk.Entry(date_frame, textvariable=date_var, width=15, font=("Arial", 10))
        date_entry.pack(side="left", padx=5)

        # --- Lot No input ---
        lot_frame = tk.Frame(search_outer, bg="#ecf0f1")
        lot_frame.grid(row=1, column=2, padx=8, pady=5, sticky="w")
        tk.Label(lot_frame, text="Lot No:", bg="#ecf0f1").pack(side="left")
        lot_var = tk.StringVar()
        lot_entry = ttk.Entry(lot_frame, textvariable=lot_var, width=20, font=("Arial", 10))
        lot_entry.pack(side="left", padx=5)

        def toggle_inputs():
            """Show only relevant input based on search type"""
            stype = search_type.get()
            # Reset border colors
            for entry in [tid_entry, date_entry, lot_entry]:
                entry.config(style="TEntry")

            if stype == "TRANSFER_ID":
                tid_entry.config(state="normal")
                date_entry.config(state="disabled")
                lot_entry.config(state="disabled")
                tid_entry.focus()
            elif stype == "DATE":
                tid_entry.config(state="disabled")
                date_entry.config(state="normal")
                lot_entry.config(state="disabled")
                date_entry.focus()
            elif stype == "LOT":
                tid_entry.config(state="disabled")
                date_entry.config(state="disabled")
                lot_entry.config(state="normal")
                lot_entry.focus()

        toggle_inputs()

        # ----------------------------------------------------------------
        # Navigation buttons + status
        # ----------------------------------------------------------------
        nav_frame = tk.Frame(win, bg="#dfe6e9")
        nav_frame.pack(fill="x", padx=10, pady=2)

        # Current transfer_id being viewed (integer)
        current_tid = tk.IntVar(value=0)

        def do_search():
            """Main search function"""
            stype = search_type.get()
            tree.delete(*tree.get_children())
            info_label.config(text="Searching...")

            if stype == "TRANSFER_ID":
                tid = self.parse_transfer_id(tid_var.get())
                if tid is None:
                    messagebox.showerror("Error", "Invalid Transfer ID format.\nUse MT-XXXXXX or just the number.")
                    return
                _load_by_tid(tid)

            elif stype == "DATE":
                raw_date = date_var.get().strip()
                try:
                    dt = datetime.strptime(raw_date, "%d/%m/%Y")
                    search_date = dt.strftime("%Y-%m-%d")
                except ValueError:
                    messagebox.showerror("Error", "Invalid date format. Use DD/MM/YYYY")
                    return
                _load_by_date(search_date)

            elif stype == "LOT":
                lot = lot_var.get().strip().upper()
                if not lot:
                    messagebox.showerror("Error", "Please enter a Lot No")
                    return
                _load_by_lot(lot)

        def _load_by_tid(tid):
            """Load all debit/credit rows for a given transfer_id (as integer)."""
            tree.delete(*tree.get_children())
            found = False
            tid_str = str(tid)
            mt_tid_str = f"MT-{tid_str}"   # in case older entries have MT- prefix

            for metal in ["GOLD", "SILVER"]:
                _, account = get_tables(metal)
                try:
                    # ----- FULL COLUMN LIST, NO "..." -----
                    rows = fetch_all(f"""
                        SELECT lot_no, txn_nature, weight, per_gram, amount,
                               COALESCE(lock_type, '') as lock_type,
                               transfer_id, txn_date
                        FROM {account}
                        WHERE transfer_id = %s OR transfer_id = %s
                        ORDER BY txn_date, lot_no
                    """, (tid_str, mt_tid_str))

                    for r in rows:
                        found = True
                        tree.insert("", "end", values=(
                            metal,
                            r[0],           # lot_no
                            r[1],           # txn_nature
                            f"{safe_float(r[2]):.3f}",   # weight
                            f"{safe_float(r[3]):.2f}",   # per_gram
                            f"₹{safe_float(r[4]):.2f}",  # amount
                            r[5],           # lock_type
                            self.format_transfer_id(r[6]),  # transfer_id
                            str(r[7])[:19]  # txn_date
                        ))
                except Exception as e:
                    print(f"Error loading {account}: {e}")

            if found:
                current_tid.set(tid)
                tid_var.set(self.format_transfer_id(tid))
                info_label.config(
                    text=f"Showing: {self.format_transfer_id(tid)} | "
                         f"Rows: {len(tree.get_children())}",
                    fg="green"
                )
            else:
                info_label.config(
                    text=f"No entries found for {self.format_transfer_id(tid)}",
                    fg="red"
                )

        def _load_by_date(search_date):
            """Load all transfers made on a specific date"""
            tree.delete(*tree.get_children())
            found_tids = set()

            for metal in ["GOLD", "SILVER"]:
                _, account = get_tables(metal)
                try:
                    rows = fetch_all(f"""
                        SELECT lot_no, txn_nature, weight, per_gram, amount,
                               COALESCE(lock_type, '') as lock_type,
                               transfer_id, txn_date
                        FROM {account}
                        WHERE DATE(txn_date) = %s
                        ORDER BY transfer_id, txn_date, lot_no
                    """, (search_date,))

                    for r in rows:
                        tid_val = r[6]
                        found_tids.add(tid_val)
                        tree.insert("", "end", values=(
                            metal,
                            r[0],
                            r[1],
                            f"{safe_float(r[2]):.3f}",
                            f"{safe_float(r[3]):.2f}",
                            f"₹{safe_float(r[4]):.2f}",
                            r[5],
                            self.format_transfer_id(tid_val) if tid_val else "",
                            str(r[7])[:19]
                        ))
                except Exception as e:
                    print(f"Error loading {account}: {e}")

            count = len(tree.get_children())
            if count > 0:
                info_label.config(
                    text=f"Date: {search_date} | Transfers: {len(found_tids)} | Rows: {count}",
                    fg="green"
                )
            else:
                info_label.config(text=f"No entries found for date {search_date}", fg="red")

        def _load_by_lot(lot):
            """Load all transfers that include a specific lot_no"""
            tree.delete(*tree.get_children())
            found_tids = set()

            for metal in ["GOLD", "SILVER"]:
                _, account = get_tables(metal)
                try:
                    rows = fetch_all(f"""
                        SELECT lot_no, txn_nature, weight, per_gram, amount,
                               COALESCE(lock_type, '') as lock_type,
                               transfer_id, txn_date
                        FROM {account}
                        WHERE lot_no ILIKE %s
                        ORDER BY transfer_id, txn_date, lot_no
                    """, (f"%{lot}%",))

                    for r in rows:
                        tid_val = r[6]
                        found_tids.add(tid_val)
                        tree.insert("", "end", values=(
                            metal,
                            r[0],
                            r[1],
                            f"{safe_float(r[2]):.3f}",
                            f"{safe_float(r[3]):.2f}",
                            f"₹{safe_float(r[4]):.2f}",
                            r[5],
                            self.format_transfer_id(tid_val) if tid_val else "",
                            str(r[7])[:19]
                        ))
                except Exception as e:
                    print(f"Error loading {account}: {e}")

            count = len(tree.get_children())
            if count > 0:
                info_label.config(
                    text=f"Lot: {lot} | Transfers: {len(found_tids)} | Rows: {count}",
                    fg="green"
                )
            else:
                info_label.config(text=f"No entries found for lot: {lot}", fg="red")

        def _get_all_transfer_ids():
            """Return a sorted list of all unique integer transfer IDs (ignoring MT- prefix)."""
            ids = set()
            for metal in ["GOLD", "SILVER"]:
                _, account = get_tables(metal)
                rows = fetch_all(f"SELECT transfer_id FROM {account} WHERE transfer_id IS NOT NULL")
                for (tid_str,) in rows:
                    if not tid_str:
                        continue
                    cleaned = tid_str.strip().upper().replace("MT-", "")
                    try:
                        ids.add(int(cleaned))
                    except ValueError:
                        pass
            return sorted(list(ids))

        def goto_prev():
            """Go to previous existing transfer_id"""
            tid = current_tid.get()
            if tid <= 0:
                tid_val = self.parse_transfer_id(tid_var.get())
                if tid_val:
                    tid = tid_val
                else:
                    return

            all_ids = _get_all_transfer_ids()
            # Find the largest id that is strictly less than tid
            prev_id = None
            for i in all_ids:
                if i < tid:
                    prev_id = i
                else:
                    break
            if prev_id is not None:
                search_type.set("TRANSFER_ID")
                toggle_inputs()
                _load_by_tid(prev_id)
            else:
                messagebox.showinfo("Navigation", "No previous transfer found")

        def goto_next():
            """Go to next existing transfer_id"""
            tid = current_tid.get()
            if tid <= 0:
                tid_val = self.parse_transfer_id(tid_var.get())
                if tid_val:
                    tid = tid_val
                else:
                    return

            all_ids = _get_all_transfer_ids()
            # Find the smallest id that is strictly greater than tid
            next_id = None
            for i in all_ids:
                if i > tid:
                    next_id = i
                    break
            if next_id is not None:
                search_type.set("TRANSFER_ID")
                toggle_inputs()
                _load_by_tid(next_id)
            else:
                messagebox.showinfo("Navigation", "No next transfer found")

        # Navigation row
        tk.Button(nav_frame, text="◀ PREV", bg="#f39c12", fg="white", width=10,
                  font=("Arial", 9, "bold"),
                  command=goto_prev).pack(side="left", padx=5, pady=4)

        tk.Button(nav_frame, text="SEARCH / LOAD", bg=BTN, fg="white", width=16,
                  font=("Arial", 9, "bold"),
                  command=do_search).pack(side="left", padx=5, pady=4)

        tk.Button(nav_frame, text="NEXT ▶", bg="#f39c12", fg="white", width=10,
                  font=("Arial", 9, "bold"),
                  command=goto_next).pack(side="left", padx=5, pady=4)

        # Load to main form button
        tk.Button(nav_frame, text="⬆ LOAD TO MAIN FORM", bg="#8e44ad", fg="white", width=20,
                  font=("Arial", 9, "bold"),
                  command=lambda: load_to_main(win)).pack(side="right", padx=10, pady=4)

        # Status label
        info_label = tk.Label(win, text="Enter search criteria and click SEARCH / LOAD",
                              font=("Arial", 9), fg="#2c3e50", bg=BG, anchor="w")
        info_label.pack(fill="x", padx=12, pady=2)

        # ----------------------------------------------------------------
        # Result Table
        # ----------------------------------------------------------------
        table_frame = tk.Frame(win)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)

        columns = ("metal", "lot", "nature", "weight", "per_gram", "amount", "lock", "transfer_id", "date")
        tree = ttk.Treeview(win, columns=columns, show="headings", height=14)

        tree.heading("metal",       text="Metal")
        tree.heading("lot",         text="Lot No")
        tree.heading("nature",      text="DR/CR")
        tree.heading("weight",      text="Weight")
        tree.heading("per_gram",    text="Per Gram")
        tree.heading("amount",      text="Amount")
        tree.heading("lock",        text="Lock Type")
        tree.heading("transfer_id", text="Transfer ID")
        tree.heading("date",        text="Date & Time")

        tree.column("metal",       width=70,  anchor="center")
        tree.column("lot",         width=150, anchor="center")
        tree.column("nature",      width=60,  anchor="center")
        tree.column("weight",      width=90,  anchor="center")
        tree.column("per_gram",    width=90,  anchor="center")
        tree.column("amount",      width=110, anchor="center")
        tree.column("lock",        width=100, anchor="center")
        tree.column("transfer_id", width=120, anchor="center")
        tree.column("date",        width=160, anchor="center")

        # Scrollbars
        vsb = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(win, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        tree.pack(fill="both", expand=True, padx=10)

        # Row color: DR=light red, CR=light green
        tree.tag_configure("DR", background="#fdecea")
        tree.tag_configure("CR", background="#eafaf1")

        # ----------------------------------------------------------------
        # Summary bar
        # ----------------------------------------------------------------
        summary_frame = tk.Frame(win, bg="#2c3e50", pady=4)
        summary_frame.pack(fill="x", padx=10, pady=4)

        total_dr_label  = tk.Label(summary_frame, text="Total DR: 0.000 g | ₹0.00",
                                   bg="#2c3e50", fg="#e74c3c", font=("Arial", 9, "bold"))
        total_dr_label.pack(side="left", padx=20)

        total_cr_label  = tk.Label(summary_frame, text="Total CR: 0.000 g | ₹0.00",
                                   bg="#2c3e50", fg="#2ecc71", font=("Arial", 9, "bold"))
        total_cr_label.pack(side="left", padx=20)

        row_count_label = tk.Label(summary_frame, text="Rows: 0",
                                   bg="#2c3e50", fg="white", font=("Arial", 9))
        row_count_label.pack(side="right", padx=20)

        def update_summary():
            """Recalculate DR/CR totals from visible rows"""
            dr_wt = dr_amt = cr_wt = cr_amt = 0.0
            for iid in tree.get_children():
                vals = tree.item(iid)["values"]
                nature = str(vals[2]).strip().upper()
                try:
                    wt  = float(str(vals[3]).replace(",", ""))
                    amt = float(str(vals[5]).replace("₹", "").replace(",", ""))
                except:
                    wt = amt = 0.0
                if nature == "DR":
                    dr_wt += wt; dr_amt += amt
                elif nature == "CR":
                    cr_wt += wt; cr_amt += amt

            total_dr_label.config( text=f"Total DR: {dr_wt:.3f} g | ₹{dr_amt:.2f}")
            total_cr_label.config( text=f"Total CR: {cr_wt:.3f} g | ₹{cr_amt:.2f}")
            row_count_label.config(text=f"Rows: {len(tree.get_children())}")

        # Patch _load_by_tid to also color rows and update summary
        original_load_by_tid = _load_by_tid

        def _load_by_tid_colored(tid):
            original_load_by_tid(tid)
            for iid in tree.get_children():
                nature = str(tree.item(iid)["values"][2]).strip().upper()
                tree.item(iid, tags=(nature,))
            update_summary()

        # Override the reference used by do_search and nav buttons
        _load_by_tid = _load_by_tid_colored

        # Also patch date/lot loaders to color + summarize
        def _after_load():
            for iid in tree.get_children():
                nature = str(tree.item(iid)["values"][2]).strip().upper()
                tree.item(iid, tags=(nature,))
            update_summary()

        # Rebind do_search to call _after_load after date/lot loads
        def do_search_enhanced():
            stype = search_type.get()
            tree.delete(*tree.get_children())
            info_label.config(text="Searching...", fg="gray")

            if stype == "TRANSFER_ID":
                tid = self.parse_transfer_id(tid_var.get())
                if tid is None:
                    messagebox.showerror("Error", "Invalid Transfer ID.\nUse MT-XXXXXX or just the number.")
                    return
                _load_by_tid(tid)

            elif stype == "DATE":
                raw_date = date_var.get().strip()
                try:
                    dt = datetime.strptime(raw_date, "%d/%m/%Y")
                    search_date = dt.strftime("%Y-%m-%d")
                except ValueError:
                    messagebox.showerror("Error", "Invalid date format. Use DD/MM/YYYY")
                    return
                _load_by_date(search_date)
                _after_load()

            elif stype == "LOT":
                lot = lot_var.get().strip().upper()
                if not lot:
                    messagebox.showerror("Error", "Please enter a Lot No")
                    return
                _load_by_lot(lot)
                _after_load()

        # Rebind the button
        for widget in nav_frame.winfo_children():
            if isinstance(widget, tk.Button) and "SEARCH" in (widget.cget("text") or ""):
                widget.config(command=do_search_enhanced)
                break

        # ----------------------------------------------------------------
        # LOAD TO MAIN FORM
        # ----------------------------------------------------------------
        def load_to_main(win):
            """
            Load the currently displayed entries back into the main table
            for editing. Groups by transfer_id to reconstruct mode rows.
            """
            rows = tree.get_children()
            if not rows:
                messagebox.showwarning("Empty", "No entries loaded to send to main form.")
                return

            # Confirm: clear current main table entries first
            existing = self.table.get_children()
            if existing:
                confirm = messagebox.askyesno(
                    "Replace Entries",
                    f"Main form has {len(existing)} pending entries.\n"
                    "Loading will REPLACE them. Continue?"
                )
                if not confirm:
                    return
                self.clear_table()

            # Gather all rows grouped by transfer_id
            tid_groups = {}
            for iid in rows:
                vals = tree.item(iid)["values"]
                tid_str = str(vals[7])  # transfer_id column
                if tid_str not in tid_groups:
                    tid_groups[tid_str] = []
                tid_groups[tid_str].append(vals)

            loaded_count = 0
            for tid_str, group_rows in tid_groups.items():
                # Detect mode by inspecting DR/CR pattern and lock_type
                dr_rows = [r for r in group_rows if str(r[2]).strip().upper() == "DR"]
                cr_rows = [r for r in group_rows if str(r[2]).strip().upper() == "CR"]

                for dr in dr_rows:
                    lot_no    = dr[1]
                    nature    = dr[2]
                    weight    = dr[3]
                    per_gram  = dr[4]
                    amount    = dr[5]
                    lock_type = str(dr[6]).strip()
                    tid_disp  = dr[7]

                    # --- Determine mode ---
                    if lock_type and lock_type not in ("", "None"):
                        # This is ADD-LOCK or CHANGE-LOCK
                        # Check if there's a reverse entry (CHANGE-LOCK has both DR and CR for stock lots)
                        # Simplified: if lock_type present on DR → ADD-LOCK
                        mode_label = "ADD-LOCK"
                        price_str  = amount
                        self.table.insert("", "end", values=(
                            mode_label, lot_no, lock_type,
                            str(weight), str(price_str)
                        ))
                    else:
                        # LOT-TO-LOT or STOCK-TO-LOT: find matching CR
                        matched_cr = cr_rows[0] if cr_rows else None
                        to_lot = matched_cr[1] if matched_cr else ""
                        self.table.insert("", "end", values=(
                            "LOT-TO-LOT", lot_no, to_lot,
                            str(weight), ""
                        ))

                    loaded_count += 1

            # Set the transfer_id on main form to match loaded data
            if tid_groups:
                last_tid_str = list(tid_groups.keys())[-1]
                parsed = self.parse_transfer_id(last_tid_str)
                if parsed:
                    self.transfer_id = parsed
                    self.edit_transfer_id = parsed   # mark editing mode

                    # Fetch the original transaction date from any row of this transfer
                    _, account = get_tables(self.metal.get())   # any metal's account works
                    tid_str = str(parsed)
                    mt_tid_str = f"MT-{tid_str}"
                    date_row = fetch_all(f"""
                        SELECT txn_date FROM {account}
                        WHERE transfer_id = %s OR transfer_id = %s LIMIT 1
                    """, (tid_str, mt_tid_str))
                    self.edit_transfer_date = date_row[0][0] if date_row else datetime.now()
                    self.id_label.config(
                        text=f"TRANSFER_ID: {self.format_transfer_id(self.transfer_id)}"
                    )

            messagebox.showinfo(
                "Loaded",
                f"{loaded_count} entries loaded to main form.\n"
                "Edit as needed, then click SAVE AND ASSIGN or SAVE ONLY."
            )
            win.destroy()

        # ----------------------------------------------------------------
        # Keyboard shortcuts
        # ----------------------------------------------------------------
        win.bind("<Return>",   lambda e: do_search_enhanced())
        win.bind("<Left>",     lambda e: goto_prev())
        win.bind("<Right>",    lambda e: goto_next())
        win.bind("<Escape>",   lambda e: win.destroy())

        # Auto-load current transfer
        do_search_enhanced()
        tid_entry.focus()
    
    # ---------------- METAL SELECTOR ----------------

    def build_metal_selector(self):
        frame = tk.Frame(self.root, bg=BG)
        frame.pack(pady=10)

        ttk.Radiobutton(frame, text="Gold", variable=self.metal, value="GOLD",
                        command=self.on_metal_change).grid(row=0, column=0, padx=20)
        ttk.Radiobutton(frame, text="Silver", variable=self.metal, value="SILVER",
                        command=self.on_metal_change).grid(row=0, column=1, padx=20)

    def on_metal_change(self):
        if self.mode:
            self.set_mode(self.mode)

    # ---------------- NOTEBOOK (4 TABS) ----------------

    def build_notebook(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="x", padx=20, pady=5)

        self.tab_lot = tk.Frame(self.notebook, bg=BG)
        self.tab_stock = tk.Frame(self.notebook, bg=BG)
        self.tab_lock = tk.Frame(self.notebook, bg=BG)
        self.tab_change = tk.Frame(self.notebook, bg=BG)

        self.notebook.add(self.tab_lot, text="LOT TO LOT")
        self.notebook.add(self.tab_stock, text="STOCK TO LOT")
        self.notebook.add(self.tab_lock, text="ADD LOCK")
        self.notebook.add(self.tab_change, text="CHANGE LOCK")

        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_change)

    def on_tab_change(self, event):
        index = self.notebook.index("current")
        modes = ["LOT", "STOCK", "LOCK", "CHANGE"]
        self.set_mode(modes[index])

    # ==================== INPUTS INSIDE TABS ====================

    def build_lot_inputs(self):
        """Inputs for LOT TO LOT tab"""
        self.lot_frame = tk.Frame(self.tab_lot, bg="white", bd=2, relief="groove")
        self.lot_frame.pack(fill="x", padx=10, pady=10)

        # From
        tk.Label(self.lot_frame, text="From:", bg="white").grid(row=0, column=0, padx=10, pady=10)
        self.lot_from_var = tk.StringVar()
        self.lot_from_var.trace_add("write", lambda *args: self.to_upper(self.lot_from_var))
        self.lot_from_entry = ttk.Entry(self.lot_frame, textvariable=self.lot_from_var, width=20)
        self.lot_from_entry.grid(row=0, column=1, padx=5)

        tk.Button(self.lot_frame, text="🔍", width=3, bg="#3498db", fg="white",
                  command=lambda: self.open_lot_search(self.lot_from_var, title="Search From Lot")).grid(row=0, column=2)

        # To
        tk.Label(self.lot_frame, text="To:", bg="white").grid(row=0, column=3, padx=10)
        self.lot_to_var = tk.StringVar()
        self.lot_to_var.trace_add("write", lambda *args: self.to_upper(self.lot_to_var))
        self.lot_to_entry = ttk.Entry(self.lot_frame, textvariable=self.lot_to_var, width=20)
        self.lot_to_entry.grid(row=0, column=4, padx=5)

        tk.Button(self.lot_frame, text="🔍", width=3, bg="#3498db", fg="white",
                  command=lambda: self.open_lot_search(self.lot_to_var, title="Search To Lot")).grid(row=0, column=5)

        # Weight
        tk.Label(self.lot_frame, text="Weight:", bg="white").grid(row=0, column=6, padx=10)
        self.lot_weight_entry = ttk.Entry(self.lot_frame, width=12)
        self.lot_weight_entry.grid(row=0, column=7, padx=5)

        # Add button
        tk.Button(self.lot_frame, text="ADD", bg=BTN, fg="white", width=10,
                  command=lambda: self.add_entry()).grid(row=0, column=8, padx=15)

    def build_stock_inputs(self):
        """Inputs for STOCK TO LOT tab"""
        self.stock_frame = tk.Frame(self.tab_stock, bg="white", bd=2, relief="groove")
        self.stock_frame.pack(fill="x", padx=10, pady=10)

        # From (stock lot - combobox)
        tk.Label(self.stock_frame, text="From Stock:", bg="white").grid(row=0, column=0, padx=10, pady=10)
        self.stock_from_var = tk.StringVar()
        self.stock_from_var.trace_add("write", lambda *args: self.to_upper(self.stock_from_var))
        self.stock_from_box = ttk.Combobox(self.stock_frame, textvariable=self.stock_from_var, width=20)
        self.stock_from_box.grid(row=0, column=1, padx=5)

        tk.Button(self.stock_frame, text="🔍", width=3, bg="#3498db", fg="white",
                  command=lambda: self.open_lot_search(self.stock_from_var, 
                          jewelry_type_filter="STOCK", title="Search Stock Lot")).grid(row=0, column=2)

        # To
        tk.Label(self.stock_frame, text="To:", bg="white").grid(row=0, column=3, padx=10)
        self.stock_to_var = tk.StringVar()
        self.stock_to_var.trace_add("write", lambda *args: self.to_upper(self.stock_to_var))
        self.stock_to_entry = ttk.Entry(self.stock_frame, textvariable=self.stock_to_var, width=20)
        self.stock_to_entry.grid(row=0, column=4, padx=5)

        tk.Button(self.stock_frame, text="🔍", width=3, bg="#3498db", fg="white",
                  command=lambda: self.open_lot_search(self.stock_to_var, title="Search To Lot")).grid(row=0, column=5)

        # Weight
        tk.Label(self.stock_frame, text="Weight:", bg="white").grid(row=0, column=6, padx=10)
        self.stock_weight_entry = ttk.Entry(self.stock_frame, width=12)
        self.stock_weight_entry.grid(row=0, column=7, padx=5)

        tk.Button(self.stock_frame, text="ADD", bg=BTN, fg="white", width=10,
                  command=lambda: self.add_entry()).grid(row=0, column=8, padx=15)

    def build_lock_inputs(self):
        """Inputs for ADD LOCK tab"""
        self.lock_frame = tk.Frame(self.tab_lock, bg="white", bd=2, relief="groove")
        self.lock_frame.pack(fill="x", padx=10, pady=10)

        # Lot/Range
        tk.Label(self.lock_frame, text="Lot / Range:", bg="white").grid(row=0, column=0, padx=10, pady=10)
        self.lock_lot_var = tk.StringVar()
        self.lock_lot_var.trace_add("write", lambda *args: self.to_upper(self.lock_lot_var))
        self.lock_lot_entry = ttk.Entry(self.lock_frame, textvariable=self.lock_lot_var, width=20)
        self.lock_lot_entry.grid(row=0, column=1, padx=5)

        tk.Button(self.lock_frame, text="🔍", width=3, bg="#3498db", fg="white",
                  command=lambda: self.open_lot_search(self.lock_lot_var, title="Search Jewelry Lot")).grid(row=0, column=2)

        # Lock type
        tk.Label(self.lock_frame, text="Lock Type:", bg="white").grid(row=0, column=3, padx=10)
        self.lock_type_var = tk.StringVar()
        self.lock_type_box = ttk.Combobox(self.lock_frame, textvariable=self.lock_type_var, width=15)
        self.lock_type_box.grid(row=0, column=4, padx=5)

        tk.Button(self.lock_frame, text="ADD", bg=BTN, fg="white", width=10,
                  command=lambda: self.add_entry()).grid(row=0, column=5, padx=15)

    def build_change_inputs(self):
        """Inputs for CHANGE LOCK tab"""
        self.change_frame = tk.Frame(self.tab_change, bg="white", bd=2, relief="groove")
        self.change_frame.pack(fill="x", padx=10, pady=10)

        # Lot
        tk.Label(self.change_frame, text="Lot:", bg="white").grid(row=0, column=0, padx=10, pady=10)
        self.change_lot_var = tk.StringVar()
        self.change_lot_var.trace_add("write", lambda *args: self.to_upper(self.change_lot_var))
        self.change_lot_entry = ttk.Entry(self.change_frame, textvariable=self.change_lot_var, width=20)
        self.change_lot_entry.grid(row=0, column=1, padx=5)

        tk.Button(self.change_frame, text="🔍", width=3, bg="#3498db", fg="white",
                  command=lambda: self.open_lot_search(self.change_lot_var, title="Search Lot to Change")).grid(row=0, column=2)

        # New Lock
        tk.Label(self.change_frame, text="New Lock:", bg="white").grid(row=0, column=3, padx=10)
        self.change_lock_var = tk.StringVar()
        self.change_lock_box = ttk.Combobox(self.change_frame, textvariable=self.change_lock_var, width=15)
        self.change_lock_box.grid(row=0, column=4, padx=5)

        tk.Button(self.change_frame, text="ADD", bg=BTN, fg="white", width=10,
                  command=lambda: self.add_entry()).grid(row=0, column=5, padx=15)

    # ---------------- COMMON TABLE ----------------
    def build_common_table(self):
        """One common table that persists across tabs"""
        self.table_frame = tk.LabelFrame(self.root, text=" Entries ", bg=BG, font=("Arial", 10, "bold"))
        self.table_frame.pack(fill="both", expand=True, padx=20, pady=5)

        # Common columns: Mode + fields
        self.table = ttk.Treeview(self.table_frame, 
                                   columns=("mode", "field1", "field2", "field3", "field4"),
                                   show="headings", height=10)
        self.table.heading("mode", text="MODE")
        self.table.heading("field1", text="FIELD 1")
        self.table.heading("field2", text="FIELD 2")
        self.table.heading("field3", text="FIELD 3")
        self.table.heading("field4", text="FIELD 4")
        self.table.column("mode", width=100, anchor="center")
        self.table.column("field1", width=180)
        self.table.column("field2", width=180)
        self.table.column("field3", width=150)
        self.table.column("field4", width=150)
        self.table.pack(fill="both", expand=True, padx=5, pady=5)

    # ---------------- BOTTOM BUTTONS ----------------
    def build_bottom_buttons(self):
        btn_frame = tk.Frame(self.root, bg=BG)
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="SAVE AND ASSIGN", bg="#27ae60", fg="white", 
                  font=("Segoe UI", 10, "bold"), width=18,
                  command=self.save_and_assign).pack(side="left", padx=5)
        # NEW: SAVE ONLY button
        tk.Button(btn_frame, text="SAVE ONLY", bg="#16a085", fg="white", 
                  font=("Segoe UI", 10, "bold"), width=12,
                  command=self.save_only).pack(side="left", padx=5)
        tk.Button(btn_frame, text="EDIT", bg="#f39c12", fg="white", width=10,
                  command=self.edit_selected).pack(side="left", padx=5)
        tk.Button(btn_frame, text="DELETE", bg="#e74c3c", fg="white", width=10,
                  command=self.delete_selected).pack(side="left", padx=5)
        tk.Button(btn_frame, text="CLEAR ALL", bg="#7f8c8d", fg="white", width=10,
                  command=self.clear_table).pack(side="left", padx=5)
        tk.Button(btn_frame, text="EXIT", bg="#34495e", fg="white", width=10,
                  command=self.root.quit).pack(side="left", padx=5)

    # ---------------- MODE LOGIC ----------------

    def set_mode(self, mode):
        self.mode = mode
        jewelry, _ = get_tables(self.metal.get())

        # Populate lock comboboxes based on DB
        lock_lots = get_lock_lots(jewelry)
        if hasattr(self, 'lock_type_box'):
            self.lock_type_box['values'] = lock_lots
        if hasattr(self, 'change_lock_box'):
            self.change_lock_box['values'] = lock_lots
        
        # Populate stock combobox
        if hasattr(self, 'stock_from_box'):
            self.stock_from_box['values'] = get_stock_lots(jewelry)

    # ---------------- FIXED LOT RANGE PARSER (NO PREFIX REQUIRED) ----------------
    def parse_lot_range(self, lot_input):
        """
        Parse single lot or range:
        - Full prefixed range: CGVY-21-25 → generates CGVY-21 to CGVY-25
        - Number-only range: 17-20 → automatically pulls ALL matching lots from DB (any prefix)
        - Single lot: returns the lot directly
        """
        if not lot_input:
            return []
        
        lot_input = lot_input.strip().upper()
        
        # Case 1: Single lot (no dash)
        if '-' not in lot_input:
            return [lot_input]
        
        parts = lot_input.split('-')
        
        # Case 2: PREFIX-START-END (e.g., CGVY-21-25)
        if len(parts) == 3:
            prefix, start_str, end_str = parts
            try:
                start = int(start_str)
                end = int(end_str)
                if start > end:
                    start, end = end, start
                padding = len(start_str)
                self.last_prefix = prefix
                return [f"{prefix}-{str(i).zfill(padding)}" for i in range(start, end + 1)]
            except ValueError:
                return [lot_input]
        
        # Case 3: Number-only range (e.g., 17-20) - PULL MATCHING LOTS DIRECTLY FROM DB
        elif len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            try:
                start = int(parts[0])
                end = int(parts[1])
                if start > end:
                    start, end = end, start

                # Get current metal's jewelry table
                jewelry_table, _ = get_tables(self.metal.get())

                # Safe query to find all lots with numeric suffix in range, no prefix required
                # Handles non-numeric suffixes safely without cast errors
                query = f"""
                    SELECT lot_no FROM {jewelry_table}
                    WHERE CASE 
                        WHEN POSITION('-' IN lot_no) > 0 THEN 
                            CASE 
                                WHEN SPLIT_PART(lot_no, '-', LENGTH(lot_no) - LENGTH(REPLACE(lot_no, '-', '')) + 1) ~ '^[0-9]+$'
                                THEN SPLIT_PART(lot_no, '-', LENGTH(lot_no) - LENGTH(REPLACE(lot_no, '-', '')) + 1)::integer
                                ELSE NULL
                            END
                        ELSE 
                            CASE WHEN lot_no ~ '^[0-9]+$' THEN lot_no::integer ELSE NULL END
                    END BETWEEN %s AND %s
                    ORDER BY lot_no
                """
                lots = [row[0] for row in fetch_all(query, (start, end))]

                if not lots:
                    messagebox.showinfo("No Lots Found", 
                        f"No lots found in number range {start}-{end} for {self.metal.get()}")
                    return []

                # Remember prefix from first found lot for convenience
                if lots and '-' in lots[0]:
                    self.last_prefix = lots[0].split('-')[0]

                return lots
                
            except ValueError:
                return [lot_input]
        
        return [lot_input]

    # ---------------- ADD ENTRY ----------------

    def add_entry(self):
        jewelry, account = get_tables(self.metal.get())

        # Get values from current tab's inputs
        if self.mode == "LOT":
            f = self.lot_from_var.get().strip()
            t = self.lot_to_var.get().strip()
            w = self.lot_weight_entry.get().strip()
            lock = ""
        elif self.mode == "STOCK":
            f = self.stock_from_var.get().strip()
            t = self.stock_to_var.get().strip()
            w = self.stock_weight_entry.get().strip()
            lock = ""
        elif self.mode == "LOCK":
            f = ""
            t = self.lock_lot_var.get().strip()
            w = ""
            lock = self.lock_type_var.get().strip()
        elif self.mode == "CHANGE":
            f = self.change_lot_var.get().strip()
            t = ""
            w = ""
            lock = self.change_lock_var.get().strip()
        else:
            return

        if self.mode in ["LOT", "STOCK"]:
            if not f or not t or not w:
                messagebox.showerror("Error", "All fields required")
                return
            if f == t:
                messagebox.showerror("Error", "From and To cannot be same")
                return

            try:
                w = float(w)
                if w <= 0:
                    raise ValueError
            except:
                messagebox.showerror("Error", "Invalid Weight")
                return

            if not lot_exists(jewelry, f):
                messagebox.showerror("Error", f"Invalid From Lot: {f}")
                return
            if not lot_exists(jewelry, t):
                messagebox.showerror("Error", f"Invalid To Lot: {t}")
                return

            if '-' in f:
                self.last_prefix = f.split('-')[0]

            # Set correct label based on which tab you added the entry from
            mode_label = "LOT-TO-LOT" if self.mode == "LOT" else "STOCK-TO-LOT"
            self.table.insert("", "end", values=(mode_label, f, t, f"{w:.3f}", ""))
        elif self.mode == "LOCK":
            lot_input = t
            lock = self.lock_type_var.get().strip()

            if not lot_input or not lock:
                messagebox.showerror("Error", "Lot/Range + Lock required")
                return

            lots_to_process = self.parse_lot_range(lot_input)
            if not lots_to_process:
                return

            added_count = 0
            for lot in lots_to_process:
                if not lot_exists(jewelry, lot):
                    messagebox.showwarning("Invalid Lot", f"Lot {lot} does not exist in database.")
                    continue

                old_lock = get_current_lock(account, lot)
                if old_lock and old_lock != "NONE":
                    choice = messagebox.askyesnocancel(
                        "Lock Exists",
                        f"Lot {lot} already has lock: {old_lock}\n\n"
                        "YES = Force Add\nNO = Skip this lot\nCANCEL = Stop process"
                    )
                    if choice is None:
                        return
                    elif choice is False:
                        continue

                parts = fetch_all("SELECT stock_lot, weight_per_piece FROM LOCK_MASTER WHERE stock_lot=%s", (lock,))
                if not parts:
                    messagebox.showerror("Error", f"No lock composition defined for {lock}")
                    return

                total_weight = 0.0
                total_price = 0.0
                for stock_lot, w_pc in parts:
                    w_pc = safe_float(w_pc)
                    per_gram = get_per_gram(jewelry, stock_lot)
                    total_weight += w_pc
                    total_price += w_pc * per_gram

                self.table.insert("", "end", values=("ADD-LOCK", lot, lock, f"{total_weight:.3f}", f"₹{total_price:.2f}"))
                added_count += 1

            if added_count > 0:
                messagebox.showinfo("Success", f"Added {added_count} lot(s) with lock {lock}")
            
            self.lock_lot_var.set("")
            self.lock_type_var.set("")
            return

        elif self.mode == "CHANGE":
            lot = f
            new_lock = lock
            if not lot or not new_lock:
                messagebox.showerror("Error", "Lot + New Lock required")
                return
            if not lot_exists(jewelry, lot):
                messagebox.showerror("Error", f"Invalid Lot: {lot}")
                return

            old_lock = get_current_lock(account, lot)
            if not old_lock:
                old_lock = "NONE"
            if old_lock == new_lock:
                messagebox.showerror("Error", "New lock same as old lock")
                return

            parts = fetch_all("SELECT 1 FROM LOCK_MASTER WHERE stock_lot=%s", (new_lock,))
            if not parts:
                messagebox.showerror("Error", f"Lock composition not defined for: {new_lock}")
                return

            self.table.insert("", "end", values=("CHANGE-LOCK", lot, old_lock, new_lock, ""))

        # Clear current tab's inputs
        if self.mode == "LOT":
            self.lot_from_var.set("")
            self.lot_to_var.set("")
            self.lot_weight_entry.delete(0, tk.END)
        elif self.mode == "STOCK":
            self.stock_from_var.set("")
            self.stock_to_var.set("")
            self.stock_weight_entry.delete(0, tk.END)
        elif self.mode == "CHANGE":
            self.change_lot_var.set("")
            self.change_lock_var.set("")

    # ---------------- EDIT SELECTED ----------------

    def edit_selected(self):
        selected = self.table.focus()
        if not selected:
            messagebox.showwarning("Warning", "No row selected to edit.")
            return

        values = self.table.item(selected)["values"]
        mode = values[0]  # LOT-TO-LOT, ADD-LOCK, CHANGE-LOCK

        edit_win = tk.Toplevel(self.root)
        edit_win.title("Edit Entry")
        edit_win.geometry("400x350")

        entries = []

        if mode in ["LOT-TO-LOT", "STOCK-TO-LOT"]:
            tk.Label(edit_win, text="From Lot:").pack(pady=5)
            from_ent = tk.Entry(edit_win)
            from_ent.insert(0, values[1])
            from_ent.pack()
            entries.append(from_ent)

            tk.Label(edit_win, text="To Lot:").pack(pady=5)
            to_ent = tk.Entry(edit_win)
            to_ent.insert(0, values[2])
            to_ent.pack()
            entries.append(to_ent)

            tk.Label(edit_win, text="Weight:").pack(pady=5)
            weight_ent = tk.Entry(edit_win)
            weight_ent.insert(0, values[3])
            weight_ent.pack()
            entries.append(weight_ent)

            def save_edit():
                try:
                    f = from_ent.get().strip()
                    t = to_ent.get().strip()
                    w = float(weight_ent.get().strip())
                    if not f or not t or w <= 0:
                        raise Exception("Invalid values")
                    jewelry, _ = get_tables(self.metal.get())
                    if not lot_exists(jewelry, f) or not lot_exists(jewelry, t):
                        raise Exception("Invalid lot")
                    self.table.item(selected, values=(mode, f, t, f"{w:.3f}", ""))
                    edit_win.destroy()
                except Exception as e:
                    messagebox.showerror("Error", str(e))

        elif mode == "ADD-LOCK":
            tk.Label(edit_win, text="Lot No:").pack(pady=5)
            lot_ent = tk.Entry(edit_win)
            lot_ent.insert(0, values[1])
            lot_ent.pack()
            entries.append(lot_ent)

            tk.Label(edit_win, text="Lock Type:").pack(pady=5)
            lock_ent = ttk.Combobox(edit_win)
            jewelry, _ = get_tables(self.metal.get())
            lock_ent['values'] = get_lock_lots(jewelry)
            lock_ent.set(values[2])
            lock_ent.pack()
            entries.append(lock_ent)

            def save_edit():
                try:
                    lot = lot_ent.get().strip()
                    new_lock = lock_ent.get().strip()
                    if not lot or not new_lock:
                        raise Exception("Required")
                    
                    # Recalculate
                    jewelry, _ = get_tables(self.metal.get())
                    parts = fetch_all("SELECT stock_lot, weight_per_piece FROM LOCK_MASTER WHERE stock_lot=%s", (new_lock,))
                    if not parts:
                        raise Exception(f"No lock composition for {new_lock}")
                    
                    total_weight = 0.0
                    total_price = 0.0
                    for stock_lot, w_pc in parts:
                        w_pc = safe_float(w_pc)
                        per_gram = get_per_gram(jewelry, stock_lot)
                        total_weight += w_pc
                        total_price += w_pc * per_gram
                    
                    self.table.item(selected, values=("ADD-LOCK", lot, new_lock, f"{total_weight:.3f}", f"₹{total_price:.2f}"))
                    edit_win.destroy()
                except Exception as e:
                    messagebox.showerror("Error", str(e))

        elif mode == "CHANGE-LOCK":
            tk.Label(edit_win, text="Lot No:").pack(pady=5)
            lot_ent = tk.Entry(edit_win)
            lot_ent.insert(0, values[1])
            lot_ent.pack()
            entries.append(lot_ent)

            tk.Label(edit_win, text=f"Old Lock: {values[2]}").pack(pady=5)

            tk.Label(edit_win, text="New Lock:").pack(pady=5)
            lock_ent = ttk.Combobox(edit_win)
            jewelry, _ = get_tables(self.metal.get())
            lock_ent['values'] = get_lock_lots(jewelry)
            lock_ent.set(values[3])
            lock_ent.pack()
            entries.append(lock_ent)

            def save_edit():
                try:
                    lot = lot_ent.get().strip()
                    new_lock = lock_ent.get().strip()
                    if not lot or not new_lock:
                        raise Exception("Required")
                    if values[2] == new_lock:
                        raise Exception("Same lock")
                    self.table.item(selected, values=("CHANGE-LOCK", lot, values[2], new_lock, ""))
                    edit_win.destroy()
                except Exception as e:
                    messagebox.showerror("Error", str(e))

        tk.Button(edit_win, text="SAVE CHANGES", bg="green", fg="white", command=save_edit).pack(pady=20)

    # ---------------- DELETE SELECTED ----------------

    def delete_selected(self):
        selected = self.table.selection()
        if not selected:
            messagebox.showwarning("Warning", "No row selected to delete.")
            return

        for item in selected:
            self.table.delete(item)

    # ---------------- NEW: SAVE ONLY METHOD ----------------
    def save_only(self):
        """Save entries to database only, handling edits correctly."""
        try:
            rows = self.table.get_children()
            if not rows:
                messagebox.showerror("Error", "No entries to save")
                return

            if self.edit_transfer_id is not None:
                # Editing an existing transfer
                confirm = messagebox.askyesno(
                    "Update Transfer",
                    f"Transfer {self.format_transfer_id(self.edit_transfer_id)} is loaded for editing.\n"
                    "All previous entries of this transfer will be REPLACED with your changes.\n"
                    "The transaction ID and original date will be preserved.\nContinue?"
                )
                if not confirm:
                    return

                # Delete the old entries of this transfer
                self._delete_existing_transfer(self.edit_transfer_id)

                # Re-insert with the same transfer_id and original date
                self._save_to_db(
                    rows,
                    transfer_id_override=self.edit_transfer_id,
                    txn_date_override=self.edit_transfer_date
                )
                messagebox.showinfo("Success", f"Transfer {self.format_transfer_id(self.edit_transfer_id)} updated.")
            else:
                # Brand‑new transfer
                self._save_to_db(rows)
                count = len(rows)
                messagebox.showinfo("Success", f"{count} entries saved successfully!")

            # Reset table and editing flags, generate a fresh transfer ID for next use
            self.clear_table()
            self.edit_transfer_id = None
            self.edit_transfer_date = None
            self.transfer_id = self.generate_transfer_id()
            self.id_label.config(text=f"TRANSFER_ID: {self.format_transfer_id(self.transfer_id)}")

        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    # ---------------- SAVE AND ASSIGN ----------------
    def save_and_assign(self):
        """Save all entries to DB and pass to JobAssignWindow, handling edits correctly."""
        try:
            rows = self.table.get_children()
            if not rows:
                messagebox.showerror("Error", "No entries to save")
                return

            if self.edit_transfer_id is not None:
                confirm = messagebox.askyesno(
                    "Update Transfer",
                    f"Transfer {self.format_transfer_id(self.edit_transfer_id)} is loaded for editing.\n"
                    "All previous entries of this transfer will be REPLACED with your changes.\n"
                    "The transaction ID and original date will be preserved.\nContinue?"
                )
                if not confirm:
                    return

                self._delete_existing_transfer(self.edit_transfer_id)
                self._save_to_db(
                    rows,
                    transfer_id_override=self.edit_transfer_id,
                    txn_date_override=self.edit_transfer_date
                )
            else:
                self._save_to_db(rows)

            # Prepare data for job assignment (if any)
            job_data = self._prepare_job_data(rows)
            if job_data:
                try:
                    from JOB_TRANSACTION import JobAssignWindow
                    job_win = JobAssignWindow()
                    job_win.grid.load_data(job_data)
                except ImportError:
                    messagebox.showwarning("Job Module Not Found", 
                        "Entries saved to DB, but JOB_TRANSACTION.py is not available.")
                except Exception as e:
                    messagebox.showerror("Job Assign Error", str(e))

            messagebox.showinfo("Success", "Entries saved and assigned successfully")
            self.clear_table()
            self.edit_transfer_id = None
            self.edit_transfer_date = None
            self.transfer_id = self.generate_transfer_id()
            self.id_label.config(text=f"TRANSFER_ID: {self.format_transfer_id(self.transfer_id)}")

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _save_to_db(self, rows, transfer_id_override=None, txn_date_override=None):
        """Save rows. If overrides are given, they replace the current transfer_id and date."""
        jewelry, account = get_tables(self.metal.get())
        now = txn_date_override if txn_date_override is not None else datetime.now().replace(microsecond=0)
        tid = transfer_id_override if transfer_id_override is not None else self.transfer_id

        for row in rows:
            values = self.table.item(row)["values"]
            mode = values[0]

            if mode in ("LOT-TO-LOT", "STOCK-TO-LOT"):
                lot1, lot2, weight = values[1], values[2], float(values[3])
                if weight <= 0:
                    raise Exception("Invalid weight")
                per = get_per_gram(jewelry, lot1)
                if per == 0:
                    raise Exception(f"Per Gram not found for Lot {lot1}")
                amt = weight * per

                execute(f"""INSERT INTO {account}
                (lot_no, txn_nature, weight, per_gram, amount, txn_date, transfer_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                        (lot1, "DR", weight, per, amt, now, tid))

                execute(f"""INSERT INTO {account}
                (lot_no, txn_nature, weight, per_gram, amount, txn_date, transfer_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                        (lot2, "CR", weight, per, amt, now, tid))

            elif mode == "ADD-LOCK":
                lot, lock, weight_str, price_str = values[1], values[2], values[3], values[4]
                weight = float(weight_str)
                
                parts = fetch_all("SELECT stock_lot, weight_per_piece FROM LOCK_MASTER WHERE stock_lot=%s", (lock,))
                if not parts:
                    raise Exception(f"No lock logic for {lock}")

                total_weight = 0
                total_amount = 0

                for stock_lot, w in parts:
                    w = safe_float(w)
                    per = safe_float(get_per_gram(jewelry, stock_lot))
                    total_weight += w
                    total_amount += w * per

                    execute(f"""INSERT INTO {account}
                    (lot_no, txn_nature, weight, per_gram, amount, txn_date, transfer_id)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                            (stock_lot, "CR", w, per, w * per, now, tid))

                per_jewel = total_amount / total_weight if total_weight else 0
                execute(f"""INSERT INTO {account}
                (lot_no, txn_nature, weight, per_gram, amount, lock_type, txn_date, transfer_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (lot, "DR", total_weight, per_jewel, total_amount, lock, now, tid))

            elif mode == "CHANGE-LOCK":
                lot, old_lock, new_lock = values[1], values[2], values[3]
                
                new_weight, new_amount = self.get_lock_composition(jewelry, new_lock)
                if new_weight <= 0:
                    raise Exception(f"Lock '{new_lock}' has no defined composition")

                if old_lock == "NONE":
                    confirm = messagebox.askyesno(
                        "No Existing Lock",
                        f"Lot {lot} has no current lock.\nApply {new_lock} as new lock?"
                    )
                    if not confirm:
                        continue

                    parts_new = fetch_all("""
                        SELECT stock_lot, weight_per_piece
                        FROM LOCK_MASTER
                        WHERE stock_lot = %s
                    """, (new_lock,))

                    for stock_lot, w_pc in parts_new:
                        w_pc = safe_float(w_pc)
                        per_gram = get_per_gram(jewelry, stock_lot)
                        amount = w_pc * per_gram
                        execute(f"""INSERT INTO {account}
                        (lot_no, txn_nature, weight, per_gram, amount, lock_type, txn_date, transfer_id)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                                (stock_lot, "CR", w_pc, per_gram, amount, new_lock, now, tid))

                    per_jewel = new_amount / new_weight if new_weight > 0 else 0
                    execute(f"""INSERT INTO {account}
                    (lot_no, txn_nature, weight, per_gram, amount, lock_type, txn_date, transfer_id)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                            (lot, "DR", new_weight, per_jewel, new_amount, new_lock, now, tid))
                else:
                    old_weight, old_amount = self.get_lock_composition(jewelry, old_lock)
                    
                    parts_old = fetch_all("""
                        SELECT stock_lot, weight_per_piece
                        FROM LOCK_MASTER
                        WHERE stock_lot = %s
                    """, (old_lock,))

                    for stock_lot, w_pc in parts_old:
                        w_pc = safe_float(w_pc)
                        per_gram = get_per_gram(jewelry, stock_lot)
                        amount = w_pc * per_gram
                        execute(f"""INSERT INTO {account}
                        (lot_no, txn_nature, weight, per_gram, amount, lock_type, txn_date, transfer_id)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                                (stock_lot, "DR", w_pc, per_gram, amount, old_lock, now, tid))

                    parts_new = fetch_all("""
                        SELECT stock_lot, weight_per_piece
                        FROM LOCK_MASTER
                        WHERE stock_lot = %s
                    """, (new_lock,))

                    for stock_lot, w_pc in parts_new:
                        w_pc = safe_float(w_pc)
                        per_gram = get_per_gram(jewelry, stock_lot)
                        amount = w_pc * per_gram
                        execute(f"""INSERT INTO {account}
                        (lot_no, txn_nature, weight, per_gram, amount, lock_type, txn_date, transfer_id)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                                (stock_lot, "CR", w_pc, per_gram, amount, new_lock, now, tid))

                    per_jewel = new_amount / new_weight if new_weight > 0 else 0
                    execute(f"""INSERT INTO {account}
                    (lot_no, txn_nature, weight, per_gram, amount, lock_type, txn_date, transfer_id)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                            (lot, "DR", new_weight, per_jewel, new_amount, new_lock, now, tid))

    def _prepare_job_data(self, rows):
        """Prepare data for JobAssignWindow"""
        dataset = []
        for row in rows:
            values = self.table.item(row)["values"]
            mode = values[0]

            if mode == "ADD-LOCK":
                lot, lock, weight_str, price_str = values[1], values[2], values[3], values[4]
                weight = float(weight_str)
                jewelry, _ = get_tables(self.metal.get())
                r = fetch_all(f"SELECT weight FROM {jewelry} WHERE lot_no=%s", (lot,))
                item_weight = safe_float(r[0][0]) if r else 0
                total_weight = item_weight + weight
                dataset.append([lot, item_weight, weight, "", total_weight, f"ADD {lock}"])
            elif mode == "CHANGE-LOCK":
                lot, old_lock, new_lock = values[1], values[2], values[3]
                dataset.append([lot, 0, 0, "", 0, f"CHANGE {old_lock} → {new_lock}"])
        return dataset

    # ---------------- UTILS ----------------

    def clear_table(self):
        for i in self.table.get_children():
            self.table.delete(i)

    def _delete_existing_transfer(self, transfer_id):
        """Delete all rows with this transfer_id from both GOLD_ACCOUNT and SILVER_ACCOUNT."""
        tid_str = str(transfer_id)
        mt_tid_str = f"MT-{tid_str}"
        for metal in ["GOLD", "SILVER"]:
            _, account = get_tables(metal)
            execute(f"DELETE FROM {account} WHERE transfer_id = %s OR transfer_id = %s",
                    (tid_str, mt_tid_str))
# ---------------- RUN ----------------

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
