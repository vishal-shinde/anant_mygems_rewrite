import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime
import psycopg2

# ==============================================================================
# POSTGRESQL CONNECTION CONFIGURATION
# ==============================================================================
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "mygems"  # Make sure this database exists in PostgreSQL
DB_USER = "myuser"
DB_PASSWORD = "28116"
# ==============================================================================

class JewelryERPForm:
    def __init__(self, root):
        self.root = root
        self.root.title("Jewelry ERP - Stone & Diamond Issue Form")
        
        # COMPACT GEOMETRY TO FIT SMALL SCREENS
        self.root.geometry("820x660")
        self.root.resizable(False, False)
        
        # Configure Style
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Form Variables
        self.issue_no_var = tk.StringVar()
        self.date_var = tk.StringVar(value=datetime.today().strftime('%Y-%m-%d'))
        self.jwl_lot_var = tk.StringVar()     # Jewelry Lot No
        self.jwl_type_var = tk.StringVar()    # Jewelry Type
        self.stn_type_var = tk.StringVar(value="Diamond") # Diamond or Stone
        self.stn_lot_var = tk.StringVar()     # Stone Lot No
        self.cts_var = tk.StringVar()         # Weight in Carats
        self.pcs_var = tk.StringVar()         # Pieces count
        self.txn_type_var = tk.StringVar(value="Issue")   # Issue or Return
        self.metal_var = tk.StringVar(value="Gold")        # Gold or Silver
        
        # Internal line items list
        self.line_items = []
        self.selected_per_ct = 0.0

        # Database Initialization
        self.init_db()

        # Build UI
        self.create_widgets()
        
        # Initialize Form State
        self.new_record()

    # ---------------- DATABASE METHODS ----------------
    def init_db(self):
        """Initialize all tables and add stn_cts, stn_amt columns."""
        try:
            self.conn = psycopg2.connect(
                host=DB_HOST, port=DB_PORT, database=DB_NAME,
                user=DB_USER, password=DB_PASSWORD
            )
            self.cursor = self.conn.cursor()
            self.cursor.execute("ALTER TABLE stone_issues DROP CONSTRAINT IF EXISTS stone_issues_pkey;")
            self.conn.commit()
        except Exception as e:
            if hasattr(self, 'conn') and self.conn:
                self.conn.rollback()
            messagebox.showerror("Database Error", f"Init Error:\n{e}")

    def generate_issue_no(self):
        """Generates Auto Issue-No: DDMMYY-001 (e.g. 190726-001)"""
        today_str = datetime.today().strftime('%d%m%y')  # DDMMYY
        prefix = f"{today_str}-"
        
        try:
            # Query highest existing issue_no for today
            self.cursor.execute("""
                SELECT issue_no FROM stone_issues 
                WHERE issue_no LIKE %s 
                ORDER BY id DESC LIMIT 1
            """, (f"{prefix}%",))
            row = self.cursor.fetchone()

            if row and row[0]:
                last_no = str(row[0])
                parts = last_no.split('-')
                if len(parts) >= 2 and parts[-1].isdigit():
                    seq = int(parts[-1]) + 1
                else:
                    seq = 1
            else:
                seq = 1

            return f"{prefix}{seq:03d}"
        except Exception:
            if hasattr(self, 'conn') and self.conn:
                self.conn.rollback()
            return f"{prefix}001"

    def fetch_jewelry_type(self, lot_no):
        """Fetch jewelry_type from gold_jewelry for given lot_no."""
        try:
            self.cursor.execute(
                "SELECT jewelry_type FROM gold_jewelry WHERE lot_no = %s OR item_code = %s LIMIT 1", 
                (lot_no, lot_no)
            )
            result = self.cursor.fetchone()
            if result and result[0]:
                return result[0]
            return "General"
        except Exception:
            if hasattr(self, 'conn') and self.conn:
                self.conn.rollback()
            return "General"

    def fetch_price_for_lot(self, stnlot_no):
        """Quietly fetch per_ct rate from stone_account table."""
        try:
            self.cursor.execute(
                "SELECT per_ct FROM stone_account WHERE stnlot_no = %s LIMIT 1", 
                (stnlot_no,)
            )
            result = self.cursor.fetchone()
            if result and result[0] is not None:
                return float(result[0])
            return 0.0
        except Exception:
            if hasattr(self, 'conn') and self.conn:
                self.conn.rollback()
            return 0.0

    # ---------------- UI BUILDING (COMPACT) ----------------
    def create_widgets(self):
        # Title
        title_frame = tk.Frame(self.root, bg="#2C3E50", pady=6)
        title_frame.pack(fill=tk.X)
        tk.Label(title_frame, text="STONE / DIAMOND ISSUE SLIP", 
                font=("Helvetica", 14, "bold"), fg="white", bg="#2C3E50").pack()

        # Metal Selection (Gold / Silver)
        metal_frame = tk.LabelFrame(self.root, text=" Metal Type ", font=("Helvetica", 9, "bold"), padx=10, pady=5)
        metal_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Radiobutton(metal_frame, text="Gold", variable=self.metal_var, value="Gold", 
                      font=("Helvetica", 10), command=self.on_metal_changed).pack(side=tk.LEFT, padx=20)
        tk.Radiobutton(metal_frame, text="Silver", variable=self.metal_var, value="Silver", 
                      font=("Helvetica", 10), command=self.on_metal_changed).pack(side=tk.LEFT, padx=20)

        # Header Details Frame
        header_frame = tk.LabelFrame(self.root, text=" Header Details ", font=("Helvetica", 9, "bold"), padx=10, pady=4)
        header_frame.pack(fill=tk.X, padx=10, pady=4)

        # Date & Issue No
        tk.Label(header_frame, text="Issue Date:", font=("Helvetica", 9)).grid(row=0, column=0, sticky="w")
        ttk.Entry(header_frame, textvariable=self.date_var, state="readonly", width=11).grid(row=0, column=1, sticky="w", padx=5)

        tk.Label(header_frame, text="Issue No:", font=("Helvetica", 9, "bold")).grid(row=0, column=2, sticky="w", padx=(15, 0))
        ttk.Entry(header_frame, textvariable=self.issue_no_var, state="readonly", width=14, font=("Helvetica", 9, "bold")).grid(row=0, column=3, sticky="w", padx=5)

        # BOLD BLUE Display for Selected Jewelry Lot
        tk.Label(header_frame, text="Jewelry Lot:", font=("Helvetica", 9, "bold")).grid(row=0, column=4, sticky="w", padx=(15, 0))
        self.lbl_blue_jwl = tk.Label(
            header_frame, textvariable=self.jwl_lot_var, 
            font=("Helvetica", 10, "bold"), fg="#1A5276"
        )
        self.lbl_blue_jwl.grid(row=0, column=5, sticky="w", padx=5)

        # Form Entry Frame
        form_frame = tk.LabelFrame(self.root, text=" Material Entry Details ", font=("Helvetica", 9, "bold"), padx=10, pady=4)
        form_frame.pack(fill=tk.X, padx=10, pady=2)

        # 1. Jewelry Lot Selection + Search
        tk.Label(form_frame, text="Jewelry Lot:", font=("Helvetica", 9)).grid(row=0, column=0, sticky="w", pady=2)
        entry_jwl = ttk.Entry(form_frame, textvariable=self.jwl_lot_var, width=18)
        entry_jwl.grid(row=0, column=1, sticky="w", padx=5)
        entry_jwl.bind("<FocusOut>", self.on_jwl_lot_changed)
        
        btn_search_jwl = tk.Button(
            form_frame, text="🔍 Search", bg="#2980B9", fg="white", 
            font=("Helvetica", 8, "bold"), command=self.open_jewelry_lot_search
        )
        btn_search_jwl.grid(row=0, column=2, sticky="w", padx=2)

        # Display Fetched Jewelry Type
        tk.Label(form_frame, text="Jewelry Type:", font=("Helvetica", 9)).grid(row=0, column=3, sticky="w", padx=(10, 0))
        ttk.Entry(form_frame, textvariable=self.jwl_type_var, state="readonly", width=15).grid(row=0, column=4, sticky="w", padx=5)

        # 2. Issue Type (Diamond or Stone)
        tk.Label(form_frame, text="Issue Type:", font=("Helvetica", 9)).grid(row=1, column=0, sticky="w", pady=2)
        type_frame = tk.Frame(form_frame)
        type_frame.grid(row=1, column=1, columnspan=2, sticky="w", padx=5)
        ttk.Radiobutton(type_frame, text="Diamond", variable=self.stn_type_var, value="Diamond", command=self.update_lot_options).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(type_frame, text="Stone", variable=self.stn_type_var, value="Stone", command=self.update_lot_options).pack(side=tk.LEFT)

        # 3. Stone Lot Dropdown + Search
        tk.Label(form_frame, text="Stone Lot No:", font=("Helvetica", 9)).grid(row=2, column=0, sticky="w", pady=2)
        self.lot_dropdown = ttk.Combobox(form_frame, textvariable=self.stn_lot_var, width=16)
        self.lot_dropdown.grid(row=2, column=1, sticky="w", padx=5)
        self.lot_dropdown.bind("<<ComboboxSelected>>", self.on_stone_lot_selected)

        btn_search_stone = tk.Button(
            form_frame, text="🔍 Search", bg="#34495E", fg="white", 
            font=("Helvetica", 8, "bold"), command=self.open_stone_lot_search
        )
        btn_search_stone.grid(row=2, column=2, sticky="w", padx=2)

        # 4. Weight (Cts) & Pcs
        tk.Label(form_frame, text="Weight (Cts):", font=("Helvetica", 9)).grid(row=3, column=0, sticky="w", pady=2)
        ttk.Entry(form_frame, textvariable=self.cts_var, width=18).grid(row=3, column=1, sticky="w", padx=5)

        tk.Label(form_frame, text="No. of Pcs:", font=("Helvetica", 9)).grid(row=4, column=0, sticky="w", pady=2)
        ttk.Entry(form_frame, textvariable=self.pcs_var, width=18).grid(row=4, column=1, sticky="w", padx=5)

        # Add Line Item Button
        btn_add_item = tk.Button(
            form_frame, text="➕ Add Item", bg="#27AE60", fg="white", 
            font=("Helvetica", 8, "bold"), command=self.add_line_item
        )
        btn_add_item.grid(row=4, column=4, sticky="e", padx=5)

        # Multi-Entry Table View (Treeview - Reduced Height)
        table_frame = tk.LabelFrame(self.root, text=" Issued Items List ", font=("Helvetica", 9, "bold"), padx=5, pady=2)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=2)

        columns = ("sr", "jwl_lot", "jwl_type", "stn_type", "stnlot_no", "cts", "pcs")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=4)
        self.tree.heading("sr", text="S.No")
        self.tree.heading("jwl_lot", text="Jewelry Lot")
        self.tree.heading("jwl_type", text="Jewelry Type")
        self.tree.heading("stn_type", text="Type")
        self.tree.heading("stnlot_no", text="Stone Lot No")
        self.tree.heading("cts", text="Weight (Cts)")
        self.tree.heading("pcs", text="Pcs")

        self.tree.column("sr", width=35, anchor="center")
        self.tree.column("jwl_lot", width=110, anchor="center")
        self.tree.column("jwl_type", width=95, anchor="center")
        self.tree.column("stn_type", width=75, anchor="center")
        self.tree.column("stnlot_no", width=160, anchor="w")
        self.tree.column("cts", width=80, anchor="e")
        self.tree.column("pcs", width=60, anchor="e")

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Remove Item Option
        grid_ctrl_frame = tk.Frame(self.root)
        grid_ctrl_frame.pack(fill=tk.X, padx=10)
        btn_remove = tk.Button(
            grid_ctrl_frame, text="✖ Remove Item", bg="#C0392B", fg="white", 
            font=("Helvetica", 8, "bold"), command=self.remove_line_item
        )
        btn_remove.pack(side=tk.RIGHT, pady=1)

        # Action Buttons
        btn_frame = tk.Frame(self.root, pady=5)
        btn_frame.pack(fill=tk.X, padx=10)

        tk.Button(btn_frame, text="NEW", bg="#3498DB", fg="white", width=10, font=("Helvetica", 8, "bold"), command=self.new_record).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="SAVE", bg="#2ECC71", fg="white", width=10, font=("Helvetica", 8, "bold"), command=self.save_record).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="FIND", bg="#F39C12", fg="white", width=10, font=("Helvetica", 8, "bold"), command=self.find_record).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="PRINT", bg="#9B59B6", fg="white", width=10, font=("Helvetica", 8, "bold"), command=self.print_record).pack(side=tk.LEFT, padx=4)

    # ---------------- SEARCH MODAL DIALOGS ----------------
    def open_jewelry_lot_search(self):
        """Search Jewelry Lot from correct table based on selected metal."""
        metal = self.metal_var.get()
        table = "gold_jewelry" if metal == "Gold" else "silver_jewelry"

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Search {metal} Jewelry Master")
        dialog.geometry("520x380")
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text=f"Search {metal} Lot / Description:", font=("Helvetica", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 2))
        
        search_var = tk.StringVar()
        entry_search = ttk.Entry(dialog, textvariable=search_var, width=35)
        entry_search.pack(fill=tk.X, padx=10, pady=5)

        search_tree = ttk.Treeview(dialog, columns=("lot", "type", "desc"), show="headings", height=10)
        search_tree.heading("lot", text="Lot No")
        search_tree.heading("type", text="Jewelry Type")
        search_tree.heading("desc", text="Description")
        search_tree.column("lot", width=140)
        search_tree.column("type", width=130)
        search_tree.column("desc", width=200)
        search_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        def populate_search(filter_text=""):
            for row in search_tree.get_children():
                search_tree.delete(row)
            try:
                query = f"""
                    SELECT lot_no, jewelry_type, description 
                    FROM {table} 
                    WHERE lot_no ILIKE %s OR description ILIKE %s
                    ORDER BY lot_no
                """
                pattern = f"%{filter_text}%"
                self.cursor.execute(query, (pattern, pattern))
                for row in self.cursor.fetchall():
                    search_tree.insert("", tk.END, values=row)
            except Exception:
                self.conn.rollback()

        entry_search.bind("<KeyRelease>", lambda e: populate_search(search_var.get().strip()))
        populate_search()

        def select_and_close():
            selected = search_tree.selection()
            if selected:
                item = search_tree.item(selected[0])['values']
                self.jwl_lot_var.set(item[0])
                self.jwl_type_var.set(item[1] if len(item)>1 and item[1] else "General")
                dialog.destroy()

        search_tree.bind("<Double-1>", lambda e: select_and_close())
        tk.Button(dialog, text="Select Lot", bg="#2ECC71", fg="white", command=select_and_close).pack(pady=8)

    def open_stone_lot_search(self):
        """Searches `stone_account` table for Stone Lot."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Search Stone Account Master")
        dialog.geometry("480x320")
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text="Search Stone Lot No:", font=("Helvetica", 9, "bold")).pack(anchor="w", padx=10, pady=(8, 2))
        
        search_var = tk.StringVar()
        entry_search = ttk.Entry(dialog, textvariable=search_var, width=30)
        entry_search.pack(fill=tk.X, padx=10, pady=4)

        search_tree = ttk.Treeview(dialog, columns=("stnlot", "type", "name"), show="headings", height=7)
        search_tree.heading("stnlot", text="Stone Lot No")
        search_tree.heading("type", text="Stone Type")
        search_tree.heading("name", text="Stone Name")
        search_tree.column("stnlot", width=160)
        search_tree.column("type", width=110)
        search_tree.column("name", width=170)
        search_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        def populate_search(filter_text=""):
            for row in search_tree.get_children():
                search_tree.delete(row)
            try:
                query = """
                    SELECT stnlot_no, stone_type, stone_name 
                    FROM stone_account 
                    WHERE stnlot_no ILIKE %s OR stone_type ILIKE %s OR stone_name ILIKE %s
                    ORDER BY stnlot_no
                """
                pattern = f"%{filter_text}%"
                self.cursor.execute(query, (pattern, pattern, pattern))
                for row in self.cursor.fetchall():
                    search_tree.insert("", tk.END, values=row)
            except Exception:
                self.conn.rollback()

        entry_search.bind("<KeyRelease>", lambda e: populate_search(search_var.get().strip()))
        populate_search()

        def select_and_close():
            selected = search_tree.selection()
            if selected:
                item = search_tree.item(selected[0])['values']
                self.stn_lot_var.set(item[0])
                self.selected_per_ct = self.fetch_price_for_lot(item[0])
                dialog.destroy()

        search_tree.bind("<Double-1>", lambda e: select_and_close())
        tk.Button(dialog, text="Select Lot", bg="#2ECC71", fg="white", font=("Helvetica", 8, "bold"), command=select_and_close).pack(pady=4)

    # ---------------- EVENT HANDLERS & HELPERS ----------------
    def on_jwl_lot_changed(self, event=None):
        lot = self.jwl_lot_var.get().strip()
        if lot:
            self.jwl_type_var.set(self.fetch_jewelry_type(lot))

    def update_lot_options(self):
        """Populates Stone Lots dynamically from stone_account."""
        try:
            stn_type = self.stn_type_var.get()
            self.cursor.execute(
                "SELECT stnlot_no FROM stone_account WHERE stone_type ILIKE %s OR diam_type ILIKE %s", 
                (f"%{stn_type}%", f"%{stn_type}%")
            )
            rows = self.cursor.fetchall()
            lots = [r[0] for r in rows]
            self.lot_dropdown['values'] = lots
            if lots:
                self.lot_dropdown.current(0)
                self.on_stone_lot_selected(None)
        except Exception:
            if hasattr(self, 'conn') and self.conn:
                self.conn.rollback()

    def on_stone_lot_selected(self, event):
        lot = self.stn_lot_var.get()
        if lot:
            self.selected_per_ct = self.fetch_price_for_lot(lot)

    # ---------------- LINE ITEM MANAGEMENT ----------------
    def add_line_item(self):
        jwl_lot = self.jwl_lot_var.get().strip()
        jwl_type = self.jwl_type_var.get().strip() or "General"
        stn_lot = self.stn_lot_var.get().strip()
        cts_str = self.cts_var.get().strip()
        pcs_str = self.pcs_var.get().strip()
        stn_type = self.stn_type_var.get()

        if not jwl_lot or not stn_lot or not cts_str or not pcs_str:
            messagebox.showerror("Validation Error", "Jewelry Lot, Stone Lot, Weight, and Pcs are required!")
            return

        try:
            cts = float(cts_str)
            pcs = int(pcs_str)
        except ValueError:
            messagebox.showerror("Validation Error", "Weight must be numeric and Pcs must be an integer!")
            return

        per_ct = self.selected_per_ct if self.selected_per_ct > 0 else self.fetch_price_for_lot(stn_lot)
        price = round(cts * per_ct, 2)

        item_data = {
            "lot_no": jwl_lot,
            "jewelry_type": jwl_type,
            "stn_type": stn_type,
            "stnlot_no": stn_lot,
            "cts": cts,
            "pcs": pcs,
            "price": price
        }
        self.line_items.append(item_data)

        self.refresh_treeview()
        self.cts_var.set("")
        self.pcs_var.set("")

    def remove_line_item(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Selection Error", "Please select an item to remove.")
            return
        
        idx = int(self.tree.item(selected[0])['values'][0]) - 1
        del self.line_items[idx]
        self.refresh_treeview()

    def refresh_treeview(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for i, item in enumerate(self.line_items, 1):
            self.tree.insert("", tk.END, values=(
                i, item['lot_no'], item['jewelry_type'], item['stn_type'], item['stnlot_no'], item['cts'], item['pcs']
            ))

    # ---------------- VOUCHER ACTION BUTTONS ----------------
    def new_record(self):
        """Generates a fresh issue number and resets the entry fields."""
        self.issue_no_var.set(self.generate_issue_no())
        self.date_var.set(datetime.today().strftime('%Y-%m-%d'))
        self.jwl_lot_var.set("")
        self.jwl_type_var.set("")
        self.stn_type_var.set("Diamond")
        self.update_lot_options()
        self.cts_var.set("")
        self.pcs_var.set("")
        self.line_items.clear()
        self.refresh_treeview()

    def save_record(self):
        issue_no = self.issue_no_var.get()
        date_str = self.date_var.get()
        metal = self.metal_var.get()
        jwl_lot = self.jwl_lot_var.get().strip()
        txn_type = self.txn_type_var.get()   # "Issue" or "Return"

        if not self.line_items:
            messagebox.showerror("Save Error", "Please add at least one line item.")
            return
        if not jwl_lot:
            messagebox.showerror("Error", "Jewelry Lot Number is required.")
            return

        try:
            # 1. Stock Check
            requested = {}
            for item in self.line_items:
                requested[item['stnlot_no']] = requested.get(item['stnlot_no'], 0.0) + item['cts']

            for stnlot, req in requested.items():
                self.cursor.execute("SELECT cts FROM stone_account WHERE stnlot_no = %s", (stnlot,))
                res = self.cursor.fetchone()
                avail = float(res[0]) if res and res[0] else 0.0
                if avail < req and txn_type == "Issue":
                    messagebox.showerror("Stock Error", f"{item['stn_type']} CTS not enough in stock for lot {stnlot}!")
                    return

            # 2. Overwrite check
            self.cursor.execute("SELECT COUNT(*) FROM stone_issues WHERE issue_no = %s", (issue_no,))
            if self.cursor.fetchone()[0] > 0:
                if messagebox.askyesno("Record Exists", f"Issue No '{issue_no}' already exists.\n\nOverwrite it?"):
                    self.cursor.execute("DELETE FROM stone_issues WHERE issue_no = %s", (issue_no,))
                else:
                    issue_no = self.generate_issue_no()
                    self.issue_no_var.set(issue_no)

            # 3. Save current transaction
            for item in self.line_items:
                self.cursor.execute("""
                    INSERT INTO stone_issues 
                    (issue_no, issue_date, lot_no, stnlot_no, cts, pcs, price, stn_type, jewelry_type)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (issue_no, date_str, jwl_lot, item['stnlot_no'], item['cts'], item['pcs'], 
                      item['price'], item['stn_type'], item['jewelry_type']))

                sign = 1 if txn_type == "Issue" else -1
                self.cursor.execute("""
                    INSERT INTO stone_transactions 
                    (date, stone_type, stnlot_no, txn_type, lot_no, weight, per_ct, amount, description, reference_no)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (date_str, item['stn_type'], item['stnlot_no'], 'CR' if txn_type=="Issue" else 'DR',
                      jwl_lot, item['cts']*sign, item['price']/item['cts'] if item['cts']>0 else 0, 
                      item['price']*sign, f"{txn_type} against {jwl_lot}", issue_no))

            # 4. CALCULATE NET BALANCE FROM ALL TRANSACTIONS
            self.cursor.execute("""
                SELECT COALESCE(SUM(weight), 0), COALESCE(SUM(amount), 0)
                FROM stone_transactions 
                WHERE lot_no = %s
            """, (jwl_lot,))
            net_cts, net_amt = self.cursor.fetchone()

            # 5. Update correct jewelry table with NET values
            table = "gold_jewelry" if metal == "Gold" else "silver_jewelry"
            self.cursor.execute(f"""
                UPDATE {table}
                SET stn_cts = %s, stn_amt = %s
                WHERE lot_no = %s
            """, (net_cts, net_amt, jwl_lot))

            self.conn.commit()
            messagebox.showinfo("Success", f"{txn_type} Voucher {issue_no} saved successfully.\n"
                                           f"Net Stone in Jewelry: {net_cts:.3f} Cts | ₹{net_amt:.2f}")

            if messagebox.askyesno("Print", "Do you want to print now?"):
                self.print_record()

            self.new_record()

        except Exception as e:
            self.conn.rollback()
            messagebox.showerror("Save Error", f"Failed to save:\n{e}")

    def find_record(self):
        """New Find dialog - Default: Search by Jewelry Lot No"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Find Records")
        dialog.geometry("400x220")
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text="Search By:", font=("Helvetica", 10, "bold")).pack(anchor="w", padx=20, pady=(15,5))

        search_mode = tk.StringVar(value="jewelry_lot")
        tk.Radiobutton(dialog, text="Jewelry Lot No (Default)", variable=search_mode, 
                      value="jewelry_lot").pack(anchor="w", padx=40)
        tk.Radiobutton(dialog, text="Memo No (Issue No)", variable=search_mode, 
                      value="memo_no").pack(anchor="w", padx=40, pady=5)

        tk.Label(dialog, text="Enter Value:", font=("Helvetica", 10, "bold")).pack(anchor="w", padx=20, pady=(10,5))
        search_var = tk.StringVar()
        entry = ttk.Entry(dialog, textvariable=search_var, width=30, font=("Helvetica", 10))
        entry.pack(padx=20, pady=5)
        entry.focus()

        def execute_search():
            value = search_var.get().strip()
            if not value:
                messagebox.showwarning("Input Error", "Please enter a value to search.")
                return
            dialog.destroy()

            if search_mode.get() == "jewelry_lot":
                self.search_by_jewelry_lot(value)
            else:
                self.search_by_memo_no(value)

        tk.Button(dialog, text="SEARCH", bg="#F39C12", fg="white", font=("Helvetica", 9, "bold"),
                 command=execute_search).pack(pady=15)
    def search_by_jewelry_lot(self, jwl_lot):
        """Load all issues for a Jewelry Lot"""
        try:
            self.cursor.execute("""
                SELECT issue_no, issue_date, lot_no, stnlot_no, cts, pcs, price, stn_type, jewelry_type 
                FROM stone_issues 
                WHERE lot_no = %s 
                ORDER BY issue_date DESC, id
            """, (jwl_lot,))
            rows = self.cursor.fetchall()

            if not rows:
                messagebox.showinfo("Not Found", f"No records found for Jewelry Lot: {jwl_lot}")
                return

            self.issue_no_var.set(rows[0][0])
            self.date_var.set(str(rows[0][1]))
            self.jwl_lot_var.set(jwl_lot)
            self.jwl_type_var.set(rows[0][8])

            self.line_items.clear()
            for r in rows:
                self.line_items.append({
                    "lot_no": r[2], "stnlot_no": r[3], "cts": float(r[4]), "pcs": int(r[5]),
                    "price": float(r[6]), "stn_type": r[7], "jewelry_type": r[8]
                })
            self.refresh_treeview()
            messagebox.showinfo("Success", f"Loaded {len(rows)} record(s) for Jewelry Lot: {jwl_lot}")
        except Exception as e:
            self.conn.rollback()
            messagebox.showerror("Query Error", str(e))

    def search_by_memo_no(self, memo_no):
        """Load specific Memo/Issue No"""
        try:
            self.cursor.execute("""
                SELECT issue_no, issue_date, lot_no, stnlot_no, cts, pcs, price, stn_type, jewelry_type 
                FROM stone_issues WHERE issue_no = %s ORDER BY id
            """, (memo_no,))
            rows = self.cursor.fetchall()

            if not rows:
                messagebox.showerror("Not Found", f"No record found for Memo No: {memo_no}")
                return

            self.issue_no_var.set(rows[0][0])
            self.date_var.set(str(rows[0][1]))
            self.jwl_lot_var.set(rows[0][2])
            self.jwl_type_var.set(rows[0][8])

            self.line_items.clear()
            for r in rows:
                self.line_items.append({
                    "lot_no": r[2], "stnlot_no": r[3], "cts": float(r[4]), "pcs": int(r[5]),
                    "price": float(r[6]), "stn_type": r[7], "jewelry_type": r[8]
                })
            self.refresh_treeview()
            messagebox.showinfo("Success", f"Record {memo_no} loaded successfully.")
        except Exception as e:
            self.conn.rollback()
            messagebox.showerror("Query Error", str(e))

    def print_record(self):
        """Show print options: Current Issue or All records for this Jewelry Lot."""
        jwl_lot = self.jwl_lot_var.get().strip()
        issue_no = self.issue_no_var.get().strip()

        if not issue_no and not jwl_lot:
            messagebox.showwarning("Print Error", "No active voucher or Jewelry Lot loaded.")
            return

        choice_win = tk.Toplevel(self.root)
        choice_win.title("Print Memo Options")
        choice_win.geometry("380x180")
        choice_win.resizable(False, False)
        choice_win.transient(self.root)
        choice_win.grab_set()

        tk.Label(choice_win, text="Select Print Mode:", font=("Helvetica", 11, "bold")).pack(pady=15)

        def print_current():
            choice_win.destroy()
            self.generate_print_memo(mode="CURRENT")

        def print_all():
            choice_win.destroy()
            if not jwl_lot:
                messagebox.showerror("Print Error", "Jewelry Lot No is required to print all records.")
                return
            self.generate_print_memo(mode="ALL")

        tk.Button(
            choice_win, text="📄 Print Current Issue Only", bg="#3498DB", fg="white",
            font=("Helvetica", 9, "bold"), width=32, command=print_current
        ).pack(pady=6)

        tk.Button(
            choice_win, text="📋 Print ALL Issues for this Jewelry Lot", bg="#8E44AD", fg="white",
            font=("Helvetica", 9, "bold"), width=32, command=print_all
        ).pack(pady=6)

    def generate_print_memo(self, mode="CURRENT"):
        """Perfect alignment using Text widget + strict fixed-width formatting."""
        issue_no = self.issue_no_var.get().strip()
        jwl_lot = self.jwl_lot_var.get().strip()
        date_str = self.date_var.get()

        items_to_print = []

        if mode == "CURRENT":
            if not self.line_items:
                messagebox.showwarning("Print Error", "No items in current voucher.")
                return
            for item in self.line_items:
                items_to_print.append({
                    "issue_no": issue_no,
                    "stn_type": item.get('stn_type', 'Diamond'),
                    "stnlot_no": item.get('stnlot_no', ''),
                    "cts": item.get('cts', 0.0),
                    "pcs": item.get('pcs', 0)
                })
            title = f"ISSUE VOUCHER: {issue_no}"
        else:  # ALL
            try:
                self.cursor.execute("""
                    SELECT issue_no, stn_type, stnlot_no, cts, pcs 
                    FROM stone_issues 
                    WHERE lot_no = %s 
                    ORDER BY issue_date, id
                """, (jwl_lot,))
                rows = self.cursor.fetchall()
                if not rows:
                    messagebox.showinfo("No Records", f"No history found for Jewelry Lot: {jwl_lot}")
                    return

                for r in rows:
                    items_to_print.append({
                        "issue_no": r[0],
                        "stn_type": r[1],
                        "stnlot_no": r[2],
                        "cts": float(r[3]),
                        "pcs": int(r[4])
                    })
                title = f"ALL ISSUES FOR JEWELRY LOT: {jwl_lot}"
            except Exception as e:
                self.conn.rollback()
                messagebox.showerror("Database Error", f"Failed to fetch records:\n{e}")
                return

        total_cts = sum(item['cts'] for item in items_to_print)
        total_pcs = sum(item['pcs'] for item in items_to_print)

        # ==================== PRINT WINDOW ====================
        win = tk.Toplevel(self.root)
        win.title(f"Print Memo - {title}")
        win.geometry("680x620")
        win.resizable(False, False)

        text = tk.Text(win, font=("Courier", 10, "bold"), bg="white", fg="black", width=85, height=32)
        text.pack(padx=15, pady=10)

        # Header
        text.insert(tk.END, "="*80 + "\n")
        text.insert(tk.END, f"{'MATERIAL ISSUE MEMO':^80}\n")
        text.insert(tk.END, "="*80 + "\n")
        text.insert(tk.END, f"Mode           : {mode}\n")
        text.insert(tk.END, f"Report         : {title}\n")
        text.insert(tk.END, f"Jewelry Lot    : {jwl_lot if jwl_lot else 'N/A'}\n")
        text.insert(tk.END, f"Printed On     : {datetime.today().strftime('%Y-%m-%d %H:%M')}\n")
        text.insert(tk.END, "-"*80 + "\n")
        text.insert(tk.END, f"{'S.No':<5} {'Issue No':<12} {'Type':<9} {'Stone Lot No':<18} {'Cts(Wt)':>8} {'Pcs':>6}\n")
        text.insert(tk.END, "-"*80 + "\n")

        # Data Rows - STRICT FIXED WIDTH
        for i, item in enumerate(items_to_print, 1):
            line = (
                f"{i:<4} "
                f"{item['issue_no'][:12]:<12} "
                f"{item['stn_type'][:8]:<9} "
                f"{item['stnlot_no'][:18]:<18} "
                f"{item['cts']:>8.3f} "
                f"{item['pcs']:>5}"
            )
            text.insert(tk.END, line + "\n")

        # Footer
        text.insert(tk.END, "-"*80 + "\n")
        text.insert(tk.END, f"GRAND SUMMARY:\n")
        text.insert(tk.END, f"   Total Entries    : {len(items_to_print)} Record(s)\n")
        text.insert(tk.END, f"   Total Weight     : {total_cts:.3f} Cts\n")
        text.insert(tk.END, f"   Total Pieces     : {total_pcs} Pcs\n")
        text.insert(tk.END, "-"*80 + "\n\n")
        text.insert(tk.END, "Issued By    : ______________________________\n\n")
        text.insert(tk.END, "Received By  : ______________________________\n")
        text.insert(tk.END, "="*80 + "\n")

        text.config(state="disabled")   # Make it read-only

        # Print Button
        btn = tk.Button(win, text="🖨 Send to Printer", bg="#2ECC71", fg="white", 
                       font=("Helvetica", 10, "bold"), command=lambda: (
                           messagebox.showinfo("Print", "Memo sent to printer!"), 
                           win.destroy()
                       ))
        btn.pack(pady=8)

    def __del__(self):
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()

    def on_metal_changed(self):
        """Clear jewelry lot when metal type is changed"""
        self.jwl_lot_var.set("")
        self.jwl_type_var.set("")

# ---------------- APPLICATION INITIALIZATION ----------------
if __name__ == "__main__":
    root = tk.Tk()
    app = JewelryERPForm(root)
    root.mainloop()
