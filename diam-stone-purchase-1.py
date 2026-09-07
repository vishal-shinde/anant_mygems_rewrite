# diamond_stone_purchase_v3.py
# Diamond & Stone Purchase (DICS) form - Simplified Minimal Database Version
import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import re
import psycopg2
from payment_module import open_payment_dialog
from account_loader import load_accounts

# Establish PostgreSQL connection
conn = psycopg2.connect(
    host="localhost",
    database="mygems",
    user="myuser",
    password="28116"
)
cur = conn.cursor()

# ----------------------------
# Validation helpers
# ----------------------------
def validate_decimal(char, new_value):
    if char == "":
        return True
    return bool(re.match(r"^\d*\.?\d{0,2}$", new_value))

def validate_integer(char, new_value):
    if char == "":
        return True
    return new_value.isdigit()

# ----------------------------
# Main App
# ----------------------------
class DiamondStoneApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Diamond & Stone Purchase (DICS) - Minimal DB Version")
        self.root.geometry("1150x760")

        # Ensure all tables exist
        self._ensure_tables()

        # Get last lot numbers for auto-generation
        self.next_diam_num = self._get_next_lot_number("DIA")
        self.next_stone_num = self._get_next_lot_number("CS")

        # register validation commands
        self._vcmd_dec = (self.root.register(validate_decimal), "%S", "%P")
        self._vcmd_int = (self.root.register(validate_integer), "%S", "%P")

        self.suppliers = load_accounts("stone_purchase")

        # build UI
        self._build_ui()

    # ----------------------------
    # DB Setup and Helpers
    # ----------------------------

    def _ensure_tables(self):
        """Create all required tables with proper columns"""
        try:
            # 1. Master Tables
            cur.execute("""
            CREATE TABLE IF NOT EXISTS attributes_master (
                id SERIAL PRIMARY KEY,
                group_name VARCHAR(50) NOT NULL,
                value_name VARCHAR(100) NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(group_name, value_name)
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS stone_types_master (
                id SERIAL PRIMARY KEY,
                category_name VARCHAR(100) NOT NULL,
                type_name VARCHAR(100) NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(category_name, type_name)
            )
            """)

            # 2. Main Stone Account Table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS stone_account (
                id SERIAL PRIMARY KEY,
                date DATE NOT NULL,
                pur_no VARCHAR(32) NOT NULL,
                stnlot_no VARCHAR(64) NOT NULL UNIQUE,
                stone_type VARCHAR(3) NOT NULL,
                diam_type VARCHAR(50),
                stone_name VARCHAR(100),
                category VARCHAR(50),
                shape VARCHAR(50),
                color VARCHAR(50),
                clarity VARCHAR(50),
                cts NUMERIC(12,3) NOT NULL DEFAULT 0,
                per_ct NUMERIC(12,2) NOT NULL DEFAULT 0,
                total_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
                selling_price NUMERIC(12,2) DEFAULT 0,
                pcs INTEGER DEFAULT 0,
                size VARCHAR(50),
                gia_no VARCHAR(50),
                cert_no VARCHAR(50),
                description TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
            """)

            # 3. Stone Transactions
            cur.execute("""
            CREATE TABLE IF NOT EXISTS stone_transactions (
                id SERIAL PRIMARY KEY,
                date DATE NOT NULL,
                stone_type VARCHAR(3) NOT NULL,
                stnlot_no VARCHAR(64) NOT NULL,
                txn_type VARCHAR(2) NOT NULL,
                lot_no VARCHAR(64),
                weight NUMERIC(12,3) NOT NULL,
                per_ct NUMERIC(12,2) NOT NULL,
                amount NUMERIC(12,2) NOT NULL,
                description TEXT,
                reference_no VARCHAR(64),
                created_at TIMESTAMP DEFAULT NOW()
            )
            """)

            # 4. Transactions Table (used in payment)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                txn_id SERIAL PRIMARY KEY,
                txn_date DATE NOT NULL,
                txn_type VARCHAR(20) NOT NULL,
                purchase_no VARCHAR(32),
                purchase_type VARCHAR(20),
                total_amount NUMERIC(12,2) NOT NULL,
                supplier_id INTEGER,
                payment_status VARCHAR(20),
                payment_mode VARCHAR(20),
                paid_amount NUMERIC(12,2) DEFAULT 0,
                balance_amount NUMERIC(12,2) DEFAULT 0,
                remarks TEXT,
                bill_no VARCHAR(50),
                created_at TIMESTAMP DEFAULT NOW()
            )
            """)

            # 5. Pending Payments Table (This fixes your current error)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS pending_payments (
                pending_id SERIAL PRIMARY KEY,
                txn_id INTEGER REFERENCES transactions(txn_id),
                txn_date DATE NOT NULL,
                purchase_no VARCHAR(32),
                stnlot_no VARCHAR(64),
                txn_type VARCHAR(20),
                account_id INTEGER,
                account_name VARCHAR(100),
                supplier_name VARCHAR(100),
                total_amount NUMERIC(12,2) NOT NULL,
                paid_amount NUMERIC(12,2) DEFAULT 0,
                balance_amount NUMERIC(12,2) DEFAULT 0,
                payment_mode VARCHAR(20),
                payment_status VARCHAR(20),
                remarks TEXT,
                is_settled BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
            """)

            conn.commit()
            self._seed_initial_master_data()
            print("✅ All tables created successfully (including pending_payments with pending_id)")

        except Exception as e:
            conn.rollback()
            print(f"⚠️ Error creating tables: {e}")

            

    def _seed_initial_master_data(self):
        """Seed default values if the master tables are empty"""
        try:
            cur.execute("SELECT COUNT(*) FROM attributes_master")
            if cur.fetchone()[0] == 0:
                defaults = [
                    ('DIAMOND_TYPE', ['NATURAL', 'CVD', 'HTHP']),
                    ('DIAMOND_SHAPE', ['ROUND', 'PRINCESS', 'EMERALD', 'OVAL', 'PEAR', 'CUSHION', 'RADIANT', 'HEART']),
                    ('DIAMOND_COLOR', ['D','E','F','G','H','I','J','K','L','M']),
                    ('DIAMOND_CLARITY', ['IF','VVS1','VVS2','VS1','VS2','SI1','SI2','I1','I2','I3']),
                    ('STONE_CATEGORY', ['PRECIOUS', 'SEMI-PRECIOUS', 'SYNTHETIC']),
                    ('STONE_COLOR', ['RED', 'GREEN', 'BLUE', 'AQUA', 'BLACK', 'BROWN', 'WHITE', 'YELLOW', 'PINK'])
                ]
                for group, values in defaults:
                    for val in values:
                        try:
                            cur.execute("INSERT INTO attributes_master (group_name, value_name) VALUES (%s, %s)", (group, val))
                        except:
                            pass
                conn.commit()
                print("✅ Attributes master data seeded")

            cur.execute("SELECT COUNT(*) FROM stone_types_master")
            if cur.fetchone()[0] == 0:
                stone_defaults = [
                    ('PRECIOUS', ['EMERALD', 'RUBY', 'BLUE-SAPPHIRE', 'REAL-PEARL']),
                    ('SEMI-PRECIOUS', ['AMETHYST','AQUAMARINE','GARNET','OPAL','TOPAZ','TOURMALINE','PERIDOT','MOONSTONE','TANZANITE','CITRINE','ROSE QUARTZ','ONYX','MOP']),
                    ('SYNTHETIC', ['SYN-SAPPHIRE','SYN-DIAMOND','MOISSANITE','CUBIC ZIRCONIA'])
                ]
                for cat, types in stone_defaults:
                    for t in types:
                        try:
                            cur.execute("INSERT INTO stone_types_master (category_name, type_name) VALUES (%s, %s)", (cat, t))
                        except:
                            pass
                conn.commit()
                print("✅ Stone types master data seeded")

            # Add sample supplier if accounts table is empty
            cur.execute("SELECT COUNT(*) FROM accounts WHERE type_id IN (1, 3)")
            if cur.fetchone()[0] == 0:
                cur.execute("""
                    INSERT INTO accounts (short_name, full_name, type_id, contact_info) 
                    VALUES ('SAMPLE-SUP', 'SAMPLE SUPPLIER', 1, 'Default supplier - add more via account management')
                """)
                conn.commit()
                print("✅ Sample supplier added")
                
        except Exception as e:
            conn.rollback()
            print(f"⚠️ Error seeding data: {e}")

    def _get_attributes(self, group_name):
        """Fetch active attributes for a specific group from DB"""
        try:
            cur.execute("SELECT value_name FROM attributes_master WHERE group_name = %s AND is_active = TRUE ORDER BY value_name", (group_name,))
            return [r[0] for r in cur.fetchall()]
        except Exception as e:
            conn.rollback()
            print(f"⚠️ Error loading attributes for {group_name}:", e)
            return []

    def _get_stone_types(self, category_name):
        """Fetch active stone types for a specific category from DB"""
        try:
            cur.execute("SELECT type_name FROM stone_types_master WHERE category_name = %s AND is_active = TRUE ORDER BY type_name", (category_name,))
            return [r[0] for r in cur.fetchall()]
        except Exception as e:
            conn.rollback()
            print(f"⚠️ Error loading stone types for {category_name}:", e)
            return []

    def _get_next_lot_number(self, stone_type):
        """Get next lot number from stone_account table"""
        try:
            prefix = "GD" if stone_type == "DIA" else "GS"
            cur.execute("""
                SELECT stnlot_no FROM stone_account 
                WHERE stone_type = %s AND stnlot_no LIKE %s 
                ORDER BY id DESC LIMIT 1
            """, (stone_type, f"{prefix}-%"))
            row = cur.fetchone()
            if row and row[0]:
                try:
                    num = int(row[0].split("-")[-1])
                    return num + 1
                except:
                    return 570
            return 570
        except Exception as e:
            conn.rollback()
            print(f"⚠️ Error getting next lot number: {e}")
            return 570

    def _get_existing_lots(self):
        """Get existing lot numbers from stone_account"""
        kind = self.kind_var.get()
        stone_type = "DIA" if kind == "DIAMOND" else "CS"
        try:
            cur.execute("SELECT stnlot_no FROM stone_account WHERE stone_type = %s ORDER BY stnlot_no", (stone_type,))
            return [r[0] for r in cur.fetchall() if r[0]]
        except Exception as e:
            conn.rollback()
            print(f"⚠️ Could not load existing lots: {e}")
            return []

    def _lot_exists(self, stnlot_no):
        """Check if STNLOT_NO already exists"""
        try:
            cur.execute("SELECT 1 FROM stone_account WHERE UPPER(stnlot_no) = UPPER(%s) LIMIT 1", 
                       (stnlot_no,))
            return cur.fetchone() is not None
        except Exception as e:
            conn.rollback()
            print(f"⚠️ Error checking lot: {e}")
            return False

    def _load_existing_lot(self, lot_no):
        """Load existing lot details using correct column names (diam_type, stone_type)"""
        try:
            cur.execute("""
                SELECT 
                    COALESCE(diam_type, ''),
                    COALESCE(category, ''),
                    COALESCE(stone_type, ''),
                    COALESCE(shape, ''),
                    COALESCE(color, ''),
                    COALESCE(clarity, ''),
                    COALESCE(cts, 0),
                    COALESCE(per_ct, 0),
                    COALESCE(selling_price, 0),
                    COALESCE(pcs, 0),
                    COALESCE(size, ''),
                    COALESCE(description, ''),
                    COALESCE(gia_no, ''),
                    COALESCE(cert_no, '')
                FROM stone_account 
                WHERE UPPER(stnlot_no) = UPPER(%s)
            """, (lot_no,))
            
            row = cur.fetchone()
            if not row:
                messagebox.showwarning("Not Found", f"Lot {lot_no} not found in database.")
                return False

            kind = self.kind_var.get()
            
            if kind == "DIAMOND":
                self.diam_type_cb.set(row[0])
                self.diam_shape_cb.set(row[3])
                self.diam_color_cb.set(row[4])
                self.diam_clarity_cb.set(row[5])
                
                self.diam_cts_entry.delete(0, tk.END)
                self.diam_cts_entry.insert(0, f"{float(row[6]):.3f}")
                self.diam_perct_entry.delete(0, tk.END)
                self.diam_perct_entry.insert(0, f"{float(row[7]):.2f}")
                self.diam_sell_entry.delete(0, tk.END)
                self.diam_sell_entry.insert(0, f"{float(row[8]):.2f}")
                self.diam_pcs_entry.delete(0, tk.END)
                self.diam_pcs_entry.insert(0, str(row[9] or 0))
                self.diam_size_entry.delete(0, tk.END)
                self.diam_size_entry.insert(0, row[10])
                self.diam_gia_entry.delete(0, tk.END)
                self.diam_gia_entry.insert(0, row[12])
                self.diam_desc_entry.delete(0, tk.END)
                self.diam_desc_entry.insert(0, row[11])

                self._disable_diamond_master_fields()
                self._update_diam_total()

            else:  # STONE
                self.stone_cat_cb.set(row[1])
                self.stone_type_cb.set(row[2])
                self.stone_color_cb.set(row[4])
                self.stone_shape_entry.delete(0, tk.END)
                self.stone_shape_entry.insert(0, row[3])
                
                self.stone_cts_entry.delete(0, tk.END)
                self.stone_cts_entry.insert(0, f"{float(row[6]):.3f}")
                self.stone_perct_entry.delete(0, tk.END)
                self.stone_perct_entry.insert(0, f"{float(row[7]):.2f}")
                self.stone_sell_entry.delete(0, tk.END)
                self.stone_sell_entry.insert(0, f"{float(row[8]):.2f}")
                self.stone_pcs_entry.delete(0, tk.END)
                self.stone_pcs_entry.insert(0, str(row[9] or 0))
                self.stone_size_entry.delete(0, tk.END)
                self.stone_size_entry.insert(0, row[10])
                self.stone_cert_entry.delete(0, tk.END)
                self.stone_cert_entry.insert(0, row[13])
                self.stone_desc_entry.delete(0, tk.END)
                self.stone_desc_entry.insert(0, row[11])

                self._disable_stone_master_fields()
                self._update_stone_total()

            return True

        except Exception as e:
            conn.rollback()
            messagebox.showerror("Load Error", f"Failed to load lot details:\n{str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def _disable_diamond_master_fields(self):
        """Make master attributes read-only"""
        for widget in [self.diam_type_cb, self.diam_shape_cb, self.diam_color_cb, self.diam_clarity_cb]:
            widget.config(state="disabled")
        self.diam_cert_cb.config(state="disabled")

    def _disable_stone_master_fields(self):
        """Make master attributes read-only"""
        for widget in [self.stone_cat_cb, self.stone_type_cb, self.stone_color_cb]:
            widget.config(state="disabled")
        self.stone_shape_entry.config(state="disabled")

    def _enable_all_fields(self):
        """Re-enable all fields when switching to New Lot"""
        for widget in [self.diam_type_cb, self.diam_shape_cb, self.diam_color_cb, 
                      self.diam_clarity_cb, self.diam_cert_cb]:
            widget.config(state="normal")
        for widget in [self.stone_cat_cb, self.stone_type_cb, self.stone_color_cb, self.stone_shape_entry]:
            widget.config(state="normal")

    def _next_purchase_no(self):
        """Generate next purchase number based on date and sequence"""
        try:
            today = datetime.datetime.now().strftime("%Y%m%d")
            cur.execute("""
                SELECT COUNT(DISTINCT pur_no) FROM stone_account 
                WHERE substr(pur_no,1,8) = %s
            """, (today,))
            seq = (cur.fetchone()[0] or 0) + 1
            return f"{today}/{seq:02d}"
        except Exception as e:
            conn.rollback()
            print(f"⚠️ Error generating purchase number: {e}")
            return f"{datetime.datetime.now().strftime('%Y%m%d')}/01"

    def _force_upper(self, event):
        widget = event.widget
        try:
            text = widget.get()
            cursor_pos = widget.index(tk.INSERT)
            widget.delete(0, tk.END)
            widget.insert(0, text.upper())
            widget.icursor(cursor_pos)
        except Exception:
            pass

    def _get_supplier_id(self, supplier_short_name):
        """Get supplier ID from accounts table using short_name"""
        if not supplier_short_name:
            return None
        try:
            cur.execute("""
                SELECT account_id FROM accounts 
                WHERE UPPER(short_name) = UPPER(%s) LIMIT 1
            """, (supplier_short_name,))
            row = cur.fetchone()
            return row[0] if row else None
        except Exception as e:
            conn.rollback()
            print(f"⚠️ Could not fetch supplier ID: {e}")
            return None

    def _on_existing_lot_selected(self, event=None):
        lot = self.existing_lot_cb.get().strip()
        if lot:
            self._load_existing_lot(lot)

    def _get_account_id_by_name(self, account_name):
        """
        Get account_id from accounts table by name.
        Works for bank / cash / supplier since all are in the same table.
        """
        if not account_name:
            return None
        try:
            cur.execute("""
                SELECT account_id FROM accounts 
                WHERE UPPER(short_name) = UPPER(%s) 
                   OR UPPER(full_name) = UPPER(%s)
                LIMIT 1
            """, (account_name, account_name))
            row = cur.fetchone()
            return row[0] if row else None
        except Exception as e:
            conn.rollback()
            print(f"⚠️ Could not fetch account ID for '{account_name}': {e}")
            return None
        
    # ----------------------------
    # UI Build
    # ----------------------------
    def _build_ui(self):
        padx = 8
        pady = 6

        header = tk.Frame(self.root)
        header.pack(fill="x", padx=padx, pady=(pady, 0))

        tk.Label(header, text="Diamond & Stone Purchase (DICS)", font=("Arial", 16, "bold")).pack(side="left")

        header_right = tk.Frame(header)
        header_right.pack(side="right", padx=(0, 20))
        today = datetime.datetime.now().strftime("%d-%m-%Y")
        self.date_label = tk.Label(header_right, text=f"Date: {today}", font=("Arial", 10))
        self.date_label.pack(anchor="e")
        self.purchase_label = tk.Label(header_right, text=f"Purchase No: {self._next_purchase_no()}", fg="red", font=("Arial", 10, "bold"))
        self.purchase_label.pack(anchor="e", pady=(4, 0))

        lot_frame = tk.LabelFrame(self.root, text="Lot Selection", padx=10, pady=6)
        lot_frame.pack(fill="x", padx=padx, pady=(pady, 4))

        self.kind_var = tk.StringVar(value="DIAMOND")
        tk.Radiobutton(lot_frame, text="Diamond", variable=self.kind_var, value="DIAMOND", command=self._on_kind_change).pack(side="left", padx=(2,8))
        tk.Radiobutton(lot_frame, text="Stone", variable=self.kind_var, value="STONE", command=self._on_kind_change).pack(side="left", padx=(0,12))

        self.lot_mode_var = tk.StringVar(value="NEW")
        tk.Radiobutton(lot_frame, text="New Lot", variable=self.lot_mode_var, value="NEW", command=self._on_lot_mode_change).pack(side="left")
        tk.Radiobutton(lot_frame, text="Existing Lot", variable=self.lot_mode_var, value="EXISTING", command=self._on_lot_mode_change).pack(side="left", padx=(6,8))

        tk.Label(lot_frame, text="New Lot:").pack(side="left")
        self.new_lot_entry = tk.Entry(lot_frame, width=18)
        self.new_lot_entry.pack(side="left", padx=(4, 12))

        tk.Label(lot_frame, text="Existing Lot:").pack(side="left")
        self.existing_lot_cb = ttk.Combobox(lot_frame, values=self._get_existing_lots(), width=30, state="readonly")
        self.existing_lot_cb.pack(side="left", padx=4)
        self.existing_lot_cb.bind("<<ComboboxSelected>>", self._on_existing_lot_selected)
        tk.Button(lot_frame, text="🔍", command=self._open_lot_search_popup).pack(side="left", padx=4)
        
        # Button to manage dynamic master data
        tk.Button(lot_frame, text="⚙️ Manage Master", bg="#e0e0e0", command=self._open_master_data_manager).pack(side="right", padx=10)

        main_split = tk.Frame(self.root)
        main_split.pack(fill="x", padx=padx, pady=(0, pady))

        self.diamond_frame = tk.LabelFrame(main_split, text="Diamond", padx=10, pady=8)
        self.diamond_frame.pack(side="left", fill="both", expand=True, padx=(0,6))

        self.stone_frame = tk.LabelFrame(main_split, text="Stone", padx=10, pady=8)
        self.stone_frame.pack(side="left", fill="both", expand=True, padx=(6,0))

        self._build_diamond_fields(self.diamond_frame)
        self._build_stone_fields(self.stone_frame)

        supplier_frame = tk.LabelFrame(self.root, text="Supplier & Payment", padx=8, pady=8)
        supplier_frame.pack(fill="x", padx=padx, pady=(0, pady))

        tk.Label(supplier_frame, text="Supplier:").pack(side="left")

        self.supplier_cb = ttk.Combobox(supplier_frame, values=load_accounts("stone_purchase"), width=50)
        self.supplier_cb.pack(side="left", padx=6)

        
        # Payment button instead of dropdown
        tk.Button(
            supplier_frame, 
            text="💰 Payment Entry", 
            bg="#4CAF50", 
            fg="white",
            font=("Arial", 10, "bold"),
            command=self._open_payment_dialog
        ).pack(side="left", padx=(20, 5))

        # Payment status label
        self.payment_status_label = tk.Label(
            supplier_frame, 
            text="Payment: Not Set", 
            fg="red", 
            font=("Arial", 9, "bold")
        )
        self.payment_status_label.pack(side="left", padx=5)

        btn_frame = tk.Frame(self.root)
        btn_frame.pack(fill="x", padx=padx, pady=(0, pady))
        tk.Button(btn_frame, text="Submit Entry", bg="#4CAF50", fg="white", command=self._on_submit_click).pack(side="left", padx=6)
        tk.Button(btn_frame, text="New Entry", bg="#ffc86b", command=self._clear_form).pack(side="left", padx=6)
        tk.Button(btn_frame, text="Exit", bg="#ff6666", command=self.root.quit).pack(side="right", padx=6)

        self._on_kind_change()
        self._on_lot_mode_change()

        # Store payment details
        self.payment_details = None

        tk.Button(btn_frame, text="📋 View Pending", bg="#FFA500", fg="white",
                  command=self._show_pending_payments).pack(side="left", padx=6)


    # ----------------------------
    # Build sub-frames (DYNAMIC DATA)
    # ----------------------------
    def _build_diamond_fields(self, parent):
        tk.Label(parent, text="Diam Type:").grid(row=0, column=0, sticky="e", padx=5, pady=4)
        self.diam_type_cb = ttk.Combobox(parent, values=self._get_attributes('DIAMOND_TYPE'), width=15)
        self.diam_type_cb.grid(row=0, column=1, sticky="w", padx=5, pady=4)

        tk.Label(parent, text="Shape:").grid(row=0, column=2, sticky="e", padx=5, pady=4)
        self.diam_shape_cb = ttk.Combobox(parent, values=self._get_attributes('DIAMOND_SHAPE'), width=15)
        self.diam_shape_cb.grid(row=0, column=3, sticky="w", padx=5, pady=4)

        tk.Label(parent, text="Color:").grid(row=1, column=0, sticky="e", padx=5, pady=4)
        self.diam_color_cb = ttk.Combobox(parent, values=self._get_attributes('DIAMOND_COLOR'), width=6)
        self.diam_color_cb.grid(row=1, column=1, sticky="w", padx=5, pady=4)

        tk.Label(parent, text="Clarity:").grid(row=1, column=2, sticky="e", padx=5, pady=4)
        self.diam_clarity_cb = ttk.Combobox(parent, values=self._get_attributes('DIAMOND_CLARITY'), width=15)
        self.diam_clarity_cb.grid(row=1, column=3, sticky="w", padx=5, pady=4)

        tk.Label(parent, text="Cts:").grid(row=2, column=0, sticky="e", padx=5, pady=4)
        self.diam_cts_entry = tk.Entry(parent, width=12, validate="key", validatecommand=self._vcmd_dec)
        self.diam_cts_entry.grid(row=2, column=1, sticky="w", padx=5, pady=4)
        self.diam_cts_entry.bind("<KeyRelease>", self._update_diam_total)

        tk.Label(parent, text="Per Ct Price:").grid(row=2, column=2, sticky="e", padx=5, pady=4)
        self.diam_perct_entry = tk.Entry(parent, width=12, validate="key", validatecommand=self._vcmd_dec)
        self.diam_perct_entry.grid(row=2, column=3, sticky="w", padx=5, pady=4)
        self.diam_perct_entry.bind("<KeyRelease>", self._update_diam_total)

        tk.Label(parent, text="Total Amount:").grid(row=3, column=0, sticky="e", padx=5, pady=4)
        self.diam_total_entry = tk.Entry(parent, width=15)
        self.diam_total_entry.grid(row=3, column=1, sticky="w", padx=5, pady=4)

        # >>> NEW: Selling Price field <<<
        tk.Label(parent, text="Selling Price/Ct:").grid(row=3, column=2, sticky="e", padx=5, pady=4)
        self.diam_sell_entry = tk.Entry(parent, width=12, validate="key", validatecommand=self._vcmd_dec)
        self.diam_sell_entry.grid(row=3, column=3, sticky="w", padx=5, pady=4)

        tk.Label(parent, text="Certified?").grid(row=4, column=0, sticky="e", padx=5, pady=4)
        self.diam_cert_cb = ttk.Combobox(parent, values=["YES", "NO"], width=8)
        self.diam_cert_cb.grid(row=4, column=1, sticky="w", padx=5, pady=4)
        self.diam_cert_cb.bind("<<ComboboxSelected>>", self._on_diam_cert_change)

        tk.Label(parent, text="GIA No:").grid(row=4, column=2, sticky="e", padx=5, pady=4)
        self.diam_gia_entry = tk.Entry(parent, width=18)
        self.diam_gia_entry.grid(row=4, column=3, sticky="w", padx=5, pady=4)

        tk.Label(parent, text="PCS:").grid(row=5, column=0, sticky="e", padx=5, pady=4)
        self.diam_pcs_entry = tk.Entry(parent, width=8, validate="key", validatecommand=self._vcmd_int)
        self.diam_pcs_entry.grid(row=5, column=1, sticky="w", padx=5, pady=4)

        tk.Label(parent, text="Size:").grid(row=5, column=2, sticky="e", padx=5, pady=4)
        self.diam_size_entry = tk.Entry(parent, width=15)
        self.diam_size_entry.grid(row=5, column=3, sticky="w", padx=5, pady=4)
        self.diam_size_entry.bind("<KeyRelease>", self._force_upper)

        tk.Label(parent, text="Description:").grid(row=6, column=0, sticky="e", padx=5, pady=4)
        self.diam_desc_entry = tk.Entry(parent, width=50)
        self.diam_desc_entry.grid(row=6, column=1, columnspan=3, sticky="w", padx=5, pady=4)
        self.diam_desc_entry.bind("<KeyRelease>", self._force_upper)

        self.diam_cert_cb.set("NO")
        self.diam_gia_entry.config(state="disabled")

    def _build_stone_fields(self, parent):
        tk.Label(parent, text="Category:").grid(row=0, column=0, sticky="e", padx=5, pady=4)
        self.stone_cat_cb = ttk.Combobox(parent, values=self._get_attributes('STONE_CATEGORY'), width=16)
        self.stone_cat_cb.grid(row=0, column=1, sticky="w", padx=5, pady=4)
        self.stone_cat_cb.bind("<<ComboboxSelected>>", self._on_stone_category_change)

        tk.Label(parent, text="Stone Type:").grid(row=0, column=2, sticky="e", padx=5, pady=4)
        self.stone_type_cb = ttk.Combobox(parent, values=[], width=18)
        self.stone_type_cb.grid(row=0, column=3, sticky="w", padx=5, pady=4)

        tk.Label(parent, text="Color:").grid(row=1, column=0, sticky="e", padx=5, pady=4)
        self.stone_color_cb = ttk.Combobox(parent, values=self._get_attributes('STONE_COLOR'), width=10)
        self.stone_color_cb.grid(row=1, column=1, sticky="w", padx=5, pady=4)

        tk.Label(parent, text="Shape:").grid(row=1, column=2, sticky="e", padx=5, pady=4)
        self.stone_shape_entry = tk.Entry(parent, width=15)
        self.stone_shape_entry.grid(row=1, column=3, sticky="w", padx=5, pady=4)
        self.stone_shape_entry.bind("<KeyRelease>", self._force_upper)

        tk.Label(parent, text="Cts:").grid(row=2, column=0, sticky="e", padx=5, pady=4)
        self.stone_cts_entry = tk.Entry(parent, width=12, validate="key", validatecommand=self._vcmd_dec)
        self.stone_cts_entry.grid(row=2, column=1, sticky="w", padx=5, pady=4)
        self.stone_cts_entry.bind("<KeyRelease>", self._update_stone_total)

        tk.Label(parent, text="Per Ct Price:").grid(row=2, column=2, sticky="e", padx=5, pady=4)
        self.stone_perct_entry = tk.Entry(parent, width=12, validate="key", validatecommand=self._vcmd_dec)
        self.stone_perct_entry.grid(row=2, column=3, sticky="w", padx=5, pady=4)
        self.stone_perct_entry.bind("<KeyRelease>", self._update_stone_total)

        tk.Label(parent, text="Total Amount:").grid(row=3, column=0, sticky="e", padx=5, pady=4)
        self.stone_total_entry = tk.Entry(parent, width=15)
        self.stone_total_entry.grid(row=3, column=1, sticky="w", padx=5, pady=4)

        # >>> NEW: Selling Price field <<<
        tk.Label(parent, text="Selling Price/Ct:").grid(row=3, column=2, sticky="e", padx=5, pady=4)
        self.stone_sell_entry = tk.Entry(parent, width=12, validate="key", validatecommand=self._vcmd_dec)
        self.stone_sell_entry.grid(row=3, column=3, sticky="w", padx=5, pady=4)

        tk.Label(parent, text="Cert No (optional):").grid(row=4, column=0, sticky="e", padx=5, pady=4)
        self.stone_cert_entry = tk.Entry(parent, width=18)
        self.stone_cert_entry.grid(row=4, column=1, sticky="w", padx=5, pady=4)
        self.stone_cert_entry.bind("<KeyRelease>", self._force_upper)

        tk.Label(parent, text="PCS:").grid(row=4, column=2, sticky="e", padx=5, pady=4)
        self.stone_pcs_entry = tk.Entry(parent, width=8, validate="key", validatecommand=self._vcmd_int)
        self.stone_pcs_entry.grid(row=4, column=3, sticky="w", padx=5, pady=4)

        tk.Label(parent, text="Size:").grid(row=5, column=0, sticky="e", padx=5, pady=4)
        self.stone_size_entry = tk.Entry(parent, width=15)
        self.stone_size_entry.grid(row=5, column=1, sticky="w", padx=5, pady=4)
        self.stone_size_entry.bind("<KeyRelease>", self._force_upper)

        tk.Label(parent, text="Description:").grid(row=6, column=0, sticky="e", padx=5, pady=4)
        self.stone_desc_entry = tk.Entry(parent, width=50)
        self.stone_desc_entry.grid(row=6, column=1, columnspan=3, sticky="w", padx=5, pady=4)
        self.stone_desc_entry.bind("<KeyRelease>", self._force_upper)

    # ----------------------------
    # UI event handlers
    # ----------------------------
    def _on_kind_change(self):
        kind = self.kind_var.get()
        if kind == "DIAMOND":
            for child in self.diamond_frame.winfo_children():
                try:
                    child.configure(state="normal")
                except Exception:
                    pass
            for child in self.stone_frame.winfo_children():
                try:
                    child.configure(state="disabled")
                except Exception:
                    pass
        else:
            for child in self.stone_frame.winfo_children():
                try:
                    child.configure(state="normal")
                except Exception:
                    pass
            for child in self.diamond_frame.winfo_children():
                try:
                    child.configure(state="disabled")
                except Exception:
                    pass

        self.existing_lot_cb.config(values=self._get_existing_lots())

    def _on_lot_mode_change(self):
        mode = self.lot_mode_var.get()
        if mode == "NEW":
            self.new_lot_entry.config(state="normal")
            self.existing_lot_cb.set("")
            self.existing_lot_cb.config(state="disabled")
            self._enable_all_fields()
        else:
            self.new_lot_entry.delete(0, tk.END)
            self.new_lot_entry.config(state="disabled")
            self.existing_lot_cb.config(state="readonly")
            # Fields will be disabled after selecting a lot

    def _on_diam_cert_change(self, event=None):
        val = (self.diam_cert_cb.get() or "").upper()
        if val == "YES":
            self.diam_gia_entry.config(state="normal")
        else:
            try:
                self.diam_gia_entry.delete(0, tk.END)
            except:
                pass
            self.diam_gia_entry.config(state="disabled")

    def _on_stone_category_change(self, event=None):
        cat = (self.stone_cat_cb.get() or "").upper()
        types = self._get_stone_types(cat)
        self.stone_type_cb.config(values=types)
        if types:
            self.stone_type_cb.set(types[0])
        else:
            self.stone_type_cb.set("")

    def _update_diam_total(self, event=None):
        try:
            cts = float(self.diam_cts_entry.get() or 0)
            per = float(self.diam_perct_entry.get() or 0)
            total = cts * per
            self.diam_total_entry.delete(0, tk.END)
            self.diam_total_entry.insert(0, f"{total:.2f}")
        except:
            pass

    def _update_stone_total(self, event=None):
        try:
            cts = float(self.stone_cts_entry.get() or 0)
            per = float(self.stone_perct_entry.get() or 0)
            total = cts * per
            self.stone_total_entry.delete(0, tk.END)
            self.stone_total_entry.insert(0, f"{total:.2f}")
        except:
            pass

    
    def _open_payment_dialog(self):
        """Open payment dialog and store payment details"""
        # Get total amount first
        kind = self.kind_var.get()
        
        if kind == "DIAMOND":
            try:
                total_amt = float(self.diam_total_entry.get() or 0)
            except:
                messagebox.showwarning("Missing Amount", "Please enter diamond amount first")
                return
        else:
            try:
                total_amt = float(self.stone_total_entry.get() or 0)
            except:
                messagebox.showwarning("Missing Amount", "Please enter stone amount first")
                return
        
        if total_amt <= 0:
            messagebox.showwarning("Invalid Amount", "Amount must be greater than zero")
            return
        
        # Call payment module
        payment_result = open_payment_dialog(
            self.root, 
            total_amt, 
            txn_type="PURCHASE", 
            module_name="Diamond & Stone Purchase"
        )
        
        if payment_result:
            self.payment_details = payment_result
            
            # Update status label
            mode = payment_result['payment_mode']
            status = payment_result['payment_status']
            account = payment_result.get('account_name', 'N/A')
            
            if mode == "PENDING":
                self.payment_status_label.config(
                    text=f"Payment: PENDING ⏳", 
                    fg="red"
                )
            elif mode == "ADVANCE":
                paid = payment_result['paid_amount']
                balance = payment_result['balance_amount']
                self.payment_status_label.config(
                    text=f"Payment: ADVANCE (Paid: ₹{paid:.2f}, Bal: ₹{balance:.2f}) 📋", 
                    fg="orange"
                )
            else:  # CASH or BANK
                self.payment_status_label.config(
                    text=f"Payment: {mode} - {account} ✅", 
                    fg="green"
                )

    def _open_lot_search_popup(self):
        messagebox.showinfo("Coming Soon", "Lot search will be added in next update")

    # ----------------------------
    # Master Data Manager Popup
    # ----------------------------
    def _open_master_data_manager(self):
        """Opens a popup window to add new master data values"""
        win = tk.Toplevel(self.root)
        win.title("Manage Master Attributes")
        win.geometry("500x380")
        win.transient(self.root)
        win.grab_set()

        tk.Label(win, text="Master Data Manager", font=("Arial", 12, "bold")).pack(pady=15)

        tk.Label(win, text="Select Attribute Group:", font=("Arial", 10)).pack(pady=(5,2))
        groups = [
            'DIAMOND_TYPE', 
            'DIAMOND_SHAPE', 
            'DIAMOND_COLOR', 
            'DIAMOND_CLARITY', 
            'STONE_CATEGORY', 
            'STONE_COLOR', 
            'STONE_TYPE (Category-Based)'
        ]
        group_cb = ttk.Combobox(win, values=groups, state="readonly", width=35)
        group_cb.pack(pady=5)
        group_cb.set(groups[0])

        cat_frame = tk.Frame(win)
        tk.Label(cat_frame, text="Parent Stone Category:").pack(side="left", padx=5)
        parent_cat_cb = ttk.Combobox(cat_frame, values=self._get_attributes('STONE_CATEGORY'), state="readonly", width=20)
        parent_cat_cb.pack(side="left", padx=5)
        
        def on_group_select(e):
            if group_cb.get() == 'STONE_TYPE (Category-Based)':
                cat_frame.pack(pady=10)
                cats = self._get_attributes('STONE_CATEGORY')
                parent_cat_cb['values'] = cats
                if cats:
                    parent_cat_cb.set(cats[0])
            else:
                cat_frame.pack_forget()

        group_cb.bind("<<ComboboxSelected>>", on_group_select)

        tk.Label(win, text="New Value Name:", font=("Arial", 10)).pack(pady=(15,2))
        val_entry = tk.Entry(win, width=40)
        val_entry.pack(pady=5)
        val_entry.bind("<KeyRelease>", self._force_upper)

        info_label = tk.Label(win, text="", fg="green", font=("Arial", 9))
        info_label.pack(pady=5)

        def save_new_attribute():
            grp = group_cb.get()
            val = val_entry.get().strip().upper()
            
            if not val:
                messagebox.showwarning("Warning", "Value cannot be empty", parent=win)
                return

            try:
                if grp == 'STONE_TYPE (Category-Based)':
                    parent_cat = parent_cat_cb.get()
                    if not parent_cat:
                        messagebox.showwarning("Warning", "Please select parent category", parent=win)
                        return
                    cur.execute("INSERT INTO stone_types_master (category_name, type_name) VALUES (%s, %s)", (parent_cat, val))
                    info_text = f"'{val}' added to {parent_cat}"
                else:
                    cur.execute("INSERT INTO attributes_master (group_name, value_name) VALUES (%s, %s)", (grp, val))
                    info_text = f"'{val}' added to {grp}"
                
                conn.commit()
                info_label.config(text=f"✅ {info_text}", fg="green")
                val_entry.delete(0, tk.END)
                self._refresh_all_comboboxes()
                
            except Exception as e:
                conn.rollback()
                if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                    info_label.config(text="⚠️ This value already exists!", fg="red")
                else:
                    info_label.config(text=f"⚠️ Database error: {str(e)[:40]}", fg="red")

        btn_frame = tk.Frame(win)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text="➕ Add Attribute", bg="#4CAF50", fg="white", font=("Arial", 10, "bold"), 
                  command=save_new_attribute, width=15).pack(side="left", padx=10)
        tk.Button(btn_frame, text="Close", command=win.destroy, width=10).pack(side="left", padx=10)

        def view_existing():
            grp = group_cb.get()
            if grp == 'STONE_TYPE (Category-Based)':
                cat = parent_cat_cb.get()
                if not cat:
                    messagebox.showinfo("Info", "Select a category first", parent=win)
                    return
                vals = self._get_stone_types(cat)
                title = f"{cat} Stone Types"
            else:
                vals = self._get_attributes(grp)
                title = grp
            
            msg = "\n".join([f"• {v}" for v in vals]) if vals else "No values found"
            messagebox.showinfo(title, msg, parent=win)

        tk.Button(win, text="👁️ View Existing Values", command=view_existing, bg="#e0e0e0").pack(pady=5)

    def _refresh_all_comboboxes(self):
        """Reloads all combobox lists from DB after adding new master data"""
        self.diam_type_cb['values'] = self._get_attributes('DIAMOND_TYPE')
        self.diam_shape_cb['values'] = self._get_attributes('DIAMOND_SHAPE')
        self.diam_color_cb['values'] = self._get_attributes('DIAMOND_COLOR')
        self.diam_clarity_cb['values'] = self._get_attributes('DIAMOND_CLARITY')
        self.stone_cat_cb['values'] = self._get_attributes('STONE_CATEGORY')
        self.stone_color_cb['values'] = self._get_attributes('STONE_COLOR')
        current_cat = self.stone_cat_cb.get()
        if current_cat:
            self.stone_type_cb['values'] = self._get_stone_types(current_cat)

    def _show_pending_payments(self):
        """Show pending payments for Diamond and Color Stone only"""
        try:
            cur.execute("""
                SELECT 
                    pending_id,
                    COALESCE(txn_date::text, '-'),
                    COALESCE(txn_id::text, '-'),
                    COALESCE(purchase_no, '-'),
                    COALESCE(account_name, '-'),
                    COALESCE(supplier_name, '-'),
                    COALESCE(txn_type, '-'),
                    COALESCE(total_amount, 0),
                    COALESCE(paid_amount, 0),
                    COALESCE(balance_amount, 0),
                    COALESCE(payment_status, '-'),
                    COALESCE(remarks, '-')
                FROM pending_payments
                WHERE balance_amount > 0
                  AND COALESCE(is_settled, FALSE) = FALSE
                ORDER BY txn_date DESC, pending_id DESC
            """)
            rows = cur.fetchall()

        except Exception as e:
            conn.rollback()
            messagebox.showerror("Error", f"Could not fetch pending payments:\n{e}")
            import traceback
            traceback.print_exc()
            return

        if not rows:
            messagebox.showinfo("Pending Payments", "No pending payments found.")
            return

        win = tk.Toplevel(self.root)
        win.title("Pending Diamond / Color Stone Payments")
        win.geometry("1200x550")

        tk.Label(win, text="Pending Payments (Purchase)",
                 font=("Arial", 14, "bold"), fg="darkred").pack(pady=8)

        frame = tk.Frame(win)
        frame.pack(fill="both", expand=True, padx=10, pady=6)

        cols = ("ID", "Date", "Txn ID", "Purchase No", "Account",
                "Supplier", "Txn Type", "Total", "Paid", "Balance",
                "Status", "Remarks")

        tree = ttk.Treeview(frame, columns=cols, show="headings", height=18)

        widths = {"ID": 50, "Date": 90, "Txn ID": 60, "Purchase No": 110,
                  "Account": 140, "Supplier": 140, "Txn Type": 90,
                  "Total": 90, "Paid": 90, "Balance": 90,
                  "Status": 90, "Remarks": 220}

        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=widths.get(c, 100), anchor="center")

        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")

        total_balance = 0
        for r in rows:
            tree.insert("", "end", values=r)
            try:
                total_balance += float(r[9] or 0)
            except:
                pass

        tk.Label(win, text=f"Total Pending Balance: ₹{total_balance:,.2f}",
                 font=("Arial", 12, "bold"), fg="red").pack(pady=8)

        tk.Button(win, text="Close", command=win.destroy,
                  bg="#ff6666", fg="white", width=15).pack(pady=6)

    # ----------------------------
    # Submit flow
    # ----------------------------
    def _on_submit_click(self):
        """Collect form data - Master fields shown but read-only for Existing Lot"""
        kind = self.kind_var.get()
        lot_mode = self.lot_mode_var.get()

        supplier_full = self.supplier_cb.get().strip()
        if not supplier_full:
            messagebox.showwarning("Missing", "Please select a supplier.")
            return

        date_str = self.date_label.cget("text").split(":")[1].strip()
        pur_no = self._next_purchase_no()

        if kind == "DIAMOND":
            diam_type = (self.diam_type_cb.get() or "").strip().upper()
            shape = (self.diam_shape_cb.get() or "").strip().upper()
            color = (self.diam_color_cb.get() or "").strip().upper()
            clarity = (self.diam_clarity_cb.get() or "").strip().upper()
            
            try:
                cts = float(self.diam_cts_entry.get() or 0)
                per_ct = float(self.diam_perct_entry.get() or 0)
                total_amt = float(self.diam_total_entry.get() or 0)
                sell_price = float(self.diam_sell_entry.get() or 0)
                pcs = int(self.diam_pcs_entry.get() or 0)
            except:
                messagebox.showerror("Invalid", "Numeric fields must be valid.")
                return

            cert = (self.diam_cert_cb.get() or "NO").upper()
            gia = (self.diam_gia_entry.get() or "").strip().upper()
            size = (self.diam_size_entry.get() or "").strip().upper()
            desc = (self.diam_desc_entry.get() or "").strip().upper()

            if lot_mode == "NEW":
                lot_text = (self.new_lot_entry.get() or "").strip().upper()
                if not lot_text:
                    lot_text = f"GD-{self.next_diam_num}"
                
                # CHECK IF LOT ALREADY EXISTS
                if self._lot_exists(lot_text):
                    messagebox.showwarning(
                        "Duplicate Lot",
                        f"STNLOT_NO '{lot_text}' ALREADY EXISTS.\n\nPlease give a NEW LOT."
                    )
                    self.new_lot_entry.focus()
                    return
            else:  # EXISTING LOT
                lot_text = (self.existing_lot_cb.get() or "").strip().upper()
                if not lot_text:
                    messagebox.showwarning("Missing", "Please select existing lot.")
                    return
                # Refresh master fields (they will be shown as disabled)
                self._load_existing_lot(lot_text)

            if not self.payment_details:
                messagebox.showwarning("Missing Payment", "Please complete payment entry first")
                return

            summary = (
                f"Type: DIAMOND\n"
                f"Lot: {lot_text} ({lot_mode} LOT)\n"
                f"Supplier: {supplier_full}\n"
                f"Diamond Type: {diam_type} | Shape: {shape} | Color: {color} | Clarity: {clarity}\n"
                f"CTS: {cts} | PCS: {pcs} | Per Ct: {per_ct} | Total: {total_amt}\n"
                f"Selling Price/Ct: {sell_price} | Expected Value: {cts*sell_price:.2f}\n"
                f"Certified: {cert} | GIA: {gia or '-'}\nSize: {size}\nDesc: {desc}"
            )

            data = {
                "lot_text": lot_text, "date": date_str, "pur_no": pur_no, "supplier": supplier_full,
                "sup_code": supplier_full, "cts": cts, "pcs": pcs, "per_ct": per_ct, "total": total_amt,
                "sell_price": sell_price, "cert": cert, "gia": gia, "lot_mode": lot_mode,
                "shape": shape, "color": color, "clarity": clarity, "diam_type": diam_type,
                "size": size, "desc": desc, "purchase_type": "DIAMOND"
            }

            self._show_confirm_and_save(summary, kind, data)

        else:  # STONE
            cat = (self.stone_cat_cb.get() or "").strip().upper()
            stype = (self.stone_type_cb.get() or "").strip().upper()
            shape = (self.stone_shape_entry.get() or "").strip().upper()
            color = (self.stone_color_cb.get() or "").strip().upper()
            cert_no = (self.stone_cert_entry.get() or "").strip().upper()
            
            try:
                cts = float(self.stone_cts_entry.get() or 0)
                per_ct = float(self.stone_perct_entry.get() or 0)
                total_amt = float(self.stone_total_entry.get() or 0)
                sell_price = float(self.stone_sell_entry.get() or 0)
                pcs = int(self.stone_pcs_entry.get() or 0)
            except:
                messagebox.showerror("Invalid", "Numeric fields must be valid.")
                return

            size = (self.stone_size_entry.get() or "").strip().upper()
            desc = (self.stone_desc_entry.get() or "").strip().upper()

            if lot_mode == "NEW":
                lot_text = (self.new_lot_entry.get() or "").strip().upper()
                if not lot_text:
                    lot_text = f"GS-{self.next_stone_num}"
                
                if self._lot_exists(lot_text):
                    messagebox.showwarning(
                        "Duplicate Lot",
                        f"STNLOT_NO '{lot_text}' ALREADY EXISTS.\n\nPlease give a NEW LOT."
                    )
                    self.new_lot_entry.focus()
                    return
            else:  # EXISTING LOT
                lot_text = (self.existing_lot_cb.get() or "").strip().upper()
                if not lot_text:
                    messagebox.showwarning("Missing", "Please select existing lot.")
                    return
                self._load_existing_lot(lot_text)

            if not self.payment_details:
                messagebox.showwarning("Missing Payment", "Please complete payment entry first")
                return

            summary = (
                f"Type: STONE\n"
                f"Lot: {lot_text} ({lot_mode} LOT)\n"
                f"Supplier: {supplier_full}\n"
                f"Category: {cat} | Stone Type: {stype}\n"
                f"Color: {color} | Shape: {shape}\n"
                f"CTS: {cts} | PCS: {pcs} | Per Ct: {per_ct} | Total: {total_amt}\n"
                f"Selling Price/Ct: {sell_price} | Expected Value: {cts*sell_price:.2f}\n"
                f"Cert No: {cert_no or '-'}\nSize: {size}\nDesc: {desc}"
            )

            data = {
                "lot_text": lot_text, "date": date_str, "pur_no": pur_no, "supplier": supplier_full,
                "sup_code": supplier_full, "cts": cts, "pcs": pcs, "per_ct": per_ct, "total": total_amt,
                "sell_price": sell_price, "cert_no": cert_no, "lot_mode": lot_mode,
                "category": cat, "stone_type": stype, "shape": shape, "color": color,
                "size": size, "desc": desc, "purchase_type": "STONE"
            }

            self._show_confirm_and_save(summary, kind, data)

    def _show_confirm_and_save(self, summary_str, kind, data):
        popup = tk.Toplevel(self.root)
        popup.title("Confirm Entry")
        popup.geometry("540x500")  # Increased height
        
        tk.Label(popup, text="Please confirm the entry below:", 
                 font=("Arial", 11, "bold")).pack(anchor="w", padx=8, pady=(8,4))
        
        txt = tk.Text(popup, width=66, height=20)  # Increased height
        txt.pack(padx=8, pady=4)
        
        # Add payment details to summary
        if self.payment_details:
            payment_summary = (
                f"\n{'='*50}\n"
                f"PAYMENT DETAILS:\n"
                f"{'='*50}\n"
                f"Payment Mode: {self.payment_details['payment_mode']}\n"
                f"Status: {self.payment_details['payment_status']}\n"
                f"Account: {self.payment_details.get('account_name', 'N/A')}\n"
                f"Paid Amount: ₹{self.payment_details['paid_amount']:.2f}\n"
                f"Balance: ₹{self.payment_details['balance_amount']:.2f}\n"
                f"Remarks: {self.payment_details.get('remarks', '-')}\n"
            )
            summary_str += payment_summary
        
        txt.insert("1.0", summary_str)
        txt.config(state="disabled")

        def do_save():
            popup.destroy()
            saved = self._save_to_db(kind, data)
            if saved:
                messagebox.showinfo("Saved", f"Entry saved successfully!\nPurchase No: {data['pur_no']}")
                self._clear_form()
            else:
                messagebox.showerror("Error", "Failed to save entry. See console for details.")

        btn_frame = tk.Frame(popup)
        btn_frame.pack(fill="x", pady=8)
        tk.Button(btn_frame, text="✅ Confirm & Save", bg="lightgreen", 
                  font=("Arial", 10, "bold"), command=do_save).pack(side="left", padx=12)
        tk.Button(btn_frame, text="❌ Cancel", command=popup.destroy).pack(side="right", padx=12)

    # ----------------------------
    # SAVE TO DB - SIMPLIFIED VERSION
    # ----------------------------
    def _save_to_db(self, kind, data):
        """Save to stone_account and stone_transactions with correct column names"""
        try:
            # Convert date from DD-MM-YYYY to YYYY-MM-DD
            date_str = data["date"]
            day, month, year = date_str.split("-")
            db_date = f"{year}-{month}-{day}"

            pur_no = data["pur_no"]
            lot_text = data["lot_text"]
            cts = float(data.get("cts", 0))
            per_ct = float(data.get("per_ct", 0))
            total_amt = float(data.get("total", 0))
            sell_price = float(data.get("sell_price", 0))
            pcs = int(data.get("pcs", 0))
            desc = data.get("desc", "")
            supplier_name = data.get("supplier", "")
            sup_code = data.get("sup_code", "")
            
            stone_type = 'DIA' if kind == 'DIAMOND' else 'CS'
            lot_mode = data.get("lot_mode", "NEW")

            # ====================================================
            # 1. Insert or Update stone_account 
            # ====================================================
            if lot_mode == "EXISTING":
                cur.execute("""
                    UPDATE stone_account 
                    SET date = %s,
                        pur_no = %s,
                        cts = cts + %s,
                        per_ct = %s,
                        total_amount = total_amount + %s,
                        selling_price = %s,
                        pcs = pcs + %s,
                        description = %s
                    WHERE UPPER(stnlot_no) = UPPER(%s)
                """, (db_date, pur_no, cts, per_ct, total_amt, sell_price, 
                      pcs, desc, lot_text))
                print(f"✅ Updated existing lot: {lot_text}")
            else:
                # NEW LOT - Use stone_name for detailed type (EMERALD, RUBY etc.)
                cur.execute("""
                    INSERT INTO stone_account 
                    (date, pur_no, stnlot_no, stone_type, diam_type, stone_name, 
                     category, shape, color, clarity, cts, per_ct, total_amount, 
                     selling_price, pcs, size, gia_no, cert_no, description)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                            %s, %s, %s, %s, %s, %s)
                """, (db_date, pur_no, lot_text, stone_type,
                      data.get("diam_type", ""),
                      data.get("stone_type", ""),      # This goes into stone_name column
                      data.get("category", ""),
                      data.get("shape", ""),
                      data.get("color", ""),
                      data.get("clarity", ""),
                      cts, per_ct, total_amt, sell_price, pcs,
                      data.get("size", ""), 
                      data.get("gia", ""), 
                      data.get("cert_no", ""), 
                      desc))
                print(f"✅ New lot saved: {lot_text}")

            # ====================================================
            # 2. Insert CR transaction
            # ====================================================
            txn_desc = desc
            if self.payment_details:
                payment_mode = self.payment_details.get('payment_mode', '')
                payment_account = self.payment_details.get('account_name', '')
                txn_desc = f"{desc} | PAY: {payment_mode} - {payment_account}"
            
            cur.execute("""
                INSERT INTO stone_transactions
                (date, stone_type, stnlot_no, txn_type, weight, per_ct, amount, 
                 description, reference_no)
                VALUES (%s, %s, %s, 'DR', %s, %s, %s, %s, %s)
            """, (db_date, stone_type, lot_text, cts, per_ct, total_amt, txn_desc, pur_no))

            # ====================================================
            # 3. Payment Processing
            # ====================================================
            if self.payment_details:
                pd = self.payment_details
                payment_mode = pd.get('payment_mode')          # CASH / BANK / ADVANCE / PENDING
                payment_status = pd.get('payment_status')       # PAID / PARTIAL / PENDING
                paid_amount = float(pd.get('paid_amount', 0))
                balance_amount = float(pd.get('balance_amount', 0))

                # --- Supplier (WHOM we pay) ---
                supplier_id = self._get_supplier_id(sup_code)

                # --- Bank/Cash account_id (FROM which money leaves) ---
                paid_account_name = pd.get('account_name', '') or ''
                account_id = pd.get('account_id')               # use if module gives id directly
                if not account_id and paid_account_name:
                    account_id = self._get_account_id_by_name(paid_account_name)

                full_remarks = f"{pd.get('remarks','')} | Pur: {pur_no} | Lot: {lot_text}"
                txn_nature = "PURCHASE"

                # Decide txn_type
                if paid_amount > 0:
                    final_txn_type = "CR"        # money actually went out from an account
                else:
                    final_txn_type = "PENDING"

                # --- Safety: a CR (paid) entry MUST have a source account ---
                if final_txn_type == "CR" and not account_id:
                    messagebox.showwarning(
                        "Missing Account",
                        f"Payment of ₹{paid_amount:.2f} was made but the BANK/CASH "
                        f"account could not be identified.\n\n"
                        f"Account name received: '{paid_account_name or 'NONE'}'\n\n"
                        f"Please ensure this account exists in the accounts table."
                    )
                    conn.rollback()
                    return False

                # --- Insert paid (CR) / pending row ---
                cur.execute("""
                    INSERT INTO transactions
                    (txn_date, txn_type, txn_nature, purchase_no, purchase_type,
                     total_amount, supplier_id, account_id,
                     payment_status, payment_mode,
                     paid_amount, balance_amount, remarks, bill_no)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING txn_id
                """, (db_date, final_txn_type, txn_nature, pur_no,
                      data.get("purchase_type", kind), total_amt,
                      supplier_id, account_id,
                      payment_status, payment_mode,
                      paid_amount, balance_amount, full_remarks, pur_no))

                txn_id = cur.fetchone()[0]

                # --- Handle balance (advance payment) ---
                if balance_amount > 0:
                    # Advance: paid part = CR (above), balance = separate PENDING row.
                    # No paying account for pending (no money left yet) -> account_id NULL.
                    if paid_amount > 0:
                        cur.execute("""
                            INSERT INTO transactions
                            (txn_date, txn_type, txn_nature, purchase_no, purchase_type,
                             total_amount, supplier_id, account_id,
                             payment_status, payment_mode,
                             paid_amount, balance_amount, remarks, bill_no)
                            VALUES (%s, 'PENDING', %s, %s, %s, %s, %s, NULL,
                                    'PENDING', 'PENDING', 0, %s, %s, %s)
                        """, (db_date, txn_nature, pur_no,
                              data.get("purchase_type", kind), balance_amount,
                              supplier_id, balance_amount,
                              f"BALANCE PENDING | {full_remarks}", pur_no))

                # Track in pending_payments
                    cur.execute("""
                        INSERT INTO pending_payments
                        (txn_id, txn_date, purchase_no, txn_type, account_id,
                         account_name, total_amount, paid_amount,
                         balance_amount, payment_status, remarks)
                        VALUES (%s, %s, %s, 'PENDING', %s, %s, %s, %s, %s, %s, %s)
                    """, (txn_id, db_date, pur_no, supplier_id, supplier_name,
                          total_amt, paid_amount, balance_amount,
                          payment_status, full_remarks))

            conn.commit()
            print(f"✅ Successfully saved lot: {lot_text}")

            # Refresh UI
            self.next_diam_num = self._get_next_lot_number("DIA")
            self.next_stone_num = self._get_next_lot_number("CS")
            self.purchase_label.config(text=f"Purchase No: {self._next_purchase_no()}")
            self.existing_lot_cb.config(values=self._get_existing_lots())

            return True

        except Exception as e:
            conn.rollback()
            print(f"⚠️ DB Save Error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _clear_form(self, keep_lot=False):
        """Clear all input fields"""
        # Diamond fields
        self.diam_type_cb.set("")
        self.diam_shape_cb.set("")
        self.diam_color_cb.set("")
        self.diam_clarity_cb.set("")
        self.diam_cts_entry.delete(0, tk.END)
        self.diam_perct_entry.delete(0, tk.END)
        self.diam_total_entry.delete(0, tk.END)
        self.diam_cert_cb.set("NO")
        self.diam_gia_entry.delete(0, tk.END)
        self.diam_gia_entry.config(state="disabled")
        self.diam_pcs_entry.delete(0, tk.END)
        self.diam_size_entry.delete(0, tk.END)
        self.diam_desc_entry.delete(0, tk.END)
        self.diam_sell_entry.delete(0, tk.END)


        # Stone fields
        self.stone_cat_cb.set("")
        self.stone_type_cb.set("")
        self.stone_color_cb.set("")
        self.stone_shape_entry.delete(0, tk.END)
        self.stone_cts_entry.delete(0, tk.END)
        self.stone_perct_entry.delete(0, tk.END)
        self.stone_total_entry.delete(0, tk.END)
        self.stone_cert_entry.delete(0, tk.END)
        self.stone_pcs_entry.delete(0, tk.END)
        self.stone_size_entry.delete(0, tk.END)
        self.stone_desc_entry.delete(0, tk.END)
        self.stone_sell_entry.delete(0, tk.END)

        # Supplier
        self.supplier_cb.set("")
        
        # Lot
        if not keep_lot:
            self.new_lot_entry.delete(0, tk.END)
            self.existing_lot_cb.set("")

        # Reset payment
        self.payment_details = None
        self.payment_status_label.config(text="Payment: Not Set", fg="red")

# ----------------------------
# Run
# ----------------------------
def main():
    root = tk.Tk()
    app = DiamondStoneApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
