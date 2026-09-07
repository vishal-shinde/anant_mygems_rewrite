"""
metal_purchase_unified_v5.py
----------------------------------------
✅ v8 FIXES + SPLIT LOT FEATURE
✅ Dimension/Length now correctly displays & saves to DB
✅ Scrollable main layout (buttons always visible on small screens)
✅ Ring Size (47-69) for rings, Length for chains/bangles
✅ Added "SPLIT LOT" entry type with custom validation, weight per row, and balanced ledger posting.
✅ FIXED: Changed payment_mode from 'NONE (SPLIT)' to 'SPLIT' to prevent varchar(10) database overflow.
"""

import tkinter as tk
from tkinter import ttk, messagebox, Menu
import psycopg2
import datetime
import sys
import os

# Ensure current directory is in sys.path for local module imports
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

# Import reusable modules
from payment_module import open_payment_dialog, get_connection
from entry_type_config import open_entry_type_config, get_all_entry_types, setup_entry_types_table

try:
    from add_customer import open_add_customer_dialog
except ImportError:
    def open_add_customer_dialog(parent):
        messagebox.showwarning("Module Missing", 
            "add_customer.py not found in the same folder.\nPlease ensure the file exists and contains open_add_customer_dialog()")
        return None

# ============================================================
# ✅ METAL CONFIGURATION
# ============================================================
METAL_CONFIG = {
    "GOLD": {
        "title": "Gold Purchase Entry - MYGEMS",
        "jewelry_table": "gold_jewelry",
        "account_table": "gold_account",
        "weight_col": "weight",
        "amount_col": "gold_amount",
        "lot_prefix": "G",
        "purities": ["9K", "14K", "18K", "22K"],
        "metal_types": ["YG", "WG", "RG", "PG"],
        "jewelry_type_map": {
            "CHAIN": "C", "BRACELET": "B", "RING": "R", "EARRING": "E",
            "NECKLACE": "N", "PENDANT": "N", "BANGLE": "B", "SPECTACLES": "S"
        },
        "karat_map": {"9K": "V", "14K": "U", "18K": "X", "22K": "Y"},
        "gold_map": {"YG": "Y", "WG": "W", "PG": "P", "RG": "R"},
        "show_karat": True, "show_metal_type": True,
    },
    "SILVER": {
        "title": "Silver Purchase Entry - MYGEMS",
        "jewelry_table": "silver_jewelry",
        "account_table": "silver_account",
        "weight_col": "weight",
        "amount_col": "silver_amount",
        "lot_prefix": "S",
        "purities": ["925"],
        "metal_types": ["925"],
        "jewelry_type_map": {
            "CHAIN": "C", "BRACELET": "B", "RING": "R", "EARRING": "E",
            "NECKLACE": "N", "PENDANT": "N", "BANGLE": "A", "SPECTACLES": "S"
        },
        "karat_map": {}, "gold_map": {},
        "show_karat": False, "show_metal_type": False,
    }
}

RING_SIZES = [str(i) for i in range(47, 70)]
LENGTH_OPTIONS = ["5.5", "6", "6.5", "7", "7.5", "8", "12", "15.5", "16", "16.5", "17", "18", "20", "22", "24", "26", "28", "30", "32"]


class MetalPurchaseApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MYGEMS - Metal Purchase")
        self.root.geometry("1250x750")

        setup_entry_types_table()
        self.entry_types = get_all_entry_types()
        
        # Inject SPLIT_LOT natively if not present in DB
        if "SPLIT_LOT" not in self.entry_types:
            self.entry_types["SPLIT_LOT"] = {
                "label": "SPLIT LOT",
                "allow_multiple_items": True
            }
        
        self.metal_type = "GOLD"
        self.cfg = METAL_CONFIG[self.metal_type]
        self.conn = get_connection()
        if not self.conn:
            root.destroy()
            return
        self.cur = self.conn.cursor()
        
        self.payment_details = None
        self.customer_settlements = []
        
        self._create_menu_bar()

        # ---------------- METAL HEADER (Combined) ----------------
        self.metal_header_frame = tk.Frame(root, bg="#104e8b")
        self.metal_header_frame.pack(fill="x")

        self.metal_type_header_label = tk.Label(self.metal_header_frame, text="GOLD TYPE", bg="#104e8b", fg="#ffb90f", font=("Arial", 12, "bold"))
        self.metal_type_header_label.pack(side="left", padx=10, pady=4)

        self.header_right = tk.Frame(self.metal_header_frame, bg="#104e8b")
        self.header_right.pack(side="right", padx=10)

        today = datetime.datetime.now().strftime("%d-%m-%Y")
        self.date_label = tk.Label(self.header_right, text=f"Date: {today}", bg="#104e8b", fg="white", font=("Arial", 9, "bold"))
        self.date_label.pack(side="right", padx=10)
        self.purchase_label = tk.Label(self.header_right, text="", bg="#104e8b", fg="white", font=("Arial", 9, "bold"))
        self.purchase_label.pack(side="right", padx=10)
        
        # ---------------- METAL SELECTOR ----------------
        metal_sel_frame = tk.Frame(root, bg="#f0f0f0", pady=4)
        metal_sel_frame.pack(fill="x")
        tk.Label(metal_sel_frame, text="Select Metal:", bg="#f0f0f0", font=("Arial", 10, "bold")).pack(side="left", padx=(10,0))
        self.metal_var = tk.StringVar(value="GOLD")
        tk.Radiobutton(metal_sel_frame, text="Gold", variable=self.metal_var, value="GOLD", bg="#f0f0f0", command=self._on_metal_change).pack(side="left", padx=10)
        tk.Radiobutton(metal_sel_frame, text="Silver", variable=self.metal_var, value="SILVER", bg="#f0f0f0", command=self._on_metal_change).pack(side="left", padx=10)

        # ---------------- ENTRY TYPE SELECTOR (Main UI) ----------------
        self.entry_type_var = tk.StringVar(value="NORMAL")
        self.entry_type_frame = tk.LabelFrame(root, text="Select Entry Type", bg="#f0f0f0")
        self.entry_type_frame.pack(fill="x", pady=5, padx=5)
        
        # Populate Radiobuttons including SPLIT_LOT
        fixed_order = ["NORMAL", "STOCK", "LOCK", "SPLIT_LOT"]
        other_types = [k for k in self.entry_types.keys() if k not in fixed_order]
        
        for type_key in fixed_order + other_types:
            if type_key in self.entry_types:
                tk.Radiobutton(self.entry_type_frame, text=self.entry_types[type_key]["label"], 
                               variable=self.entry_type_var, value=type_key, bg="#f0f0f0").pack(side="left", padx=10, pady=2)

        # ---------------- SCROLLABLE MAIN CONTAINER ----------------
        self.canvas = tk.Canvas(root, highlightthickness=0)
        self.v_scroll = ttk.Scrollbar(root, orient="vertical", command=self.canvas.yview)
        self.main = tk.Frame(self.canvas)

        self.main.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.main, anchor="nw")
        self.canvas.configure(yscrollcommand=self.v_scroll.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.v_scroll.pack(side="right", fill="y")
        
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # ---------------- LOT INFO ----------------
        lot_info_frame = tk.Frame(self.main)
        lot_info_frame.pack(anchor="w", pady=(2, 4))
        self.last_lot_label = tk.Label(lot_info_frame, text="", fg="blue", font=("Arial", 9, "bold"))
        self.last_lot_label.pack(side="left", padx=(10, 20))
        self.new_lot_label = tk.Label(lot_info_frame, text="", fg="green", font=("Arial", 9, "bold"))
        self.new_lot_label.pack(side="left")
        self._refresh_lot_info()
        self._update_purchase_no_label()

        # ---------------- Purchase Type ----------------
        type_frame = tk.LabelFrame(self.main, text="Purchase Type")
        type_frame.pack(fill="x", pady=2)
        self.purchase_type = tk.StringVar(value="New Purchase")
        tk.Radiobutton(type_frame, text="New Purchase", variable=self.purchase_type, value="New Purchase").pack(side="left", padx=10, pady=2)
        tk.Radiobutton(type_frame, text="Existing Lot", variable=self.purchase_type, value="Existing Lot").pack(side="left", padx=10, pady=2)
        self.existing_lot_btn = tk.Button(type_frame, text="🔍 Select Existing", bg="#ffcc88", command=self.open_existing_lot_popup)
        self.existing_lot_btn.pack_forget()
        self.purchase_type.trace_add("write", lambda *_: self._on_type_change())

        # ---------------- Supplier & Bill Details ----------------
        bill_frame = tk.LabelFrame(self.main, text="Supplier/Customer Details")
        bill_frame.pack(fill="x", pady=2)
        tk.Label(bill_frame, text="Supplier/Customer:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        supplier_list = self._load_suppliers_from_db()
        self.supplier_cb = ttk.Combobox(bill_frame, values=supplier_list, width=22, state="readonly")
        self.supplier_cb.grid(row=0, column=1, padx=4, pady=4)

        self.supplier_btn = tk.Button(bill_frame, text="+", width=3,
            command=lambda: self.supplier_cb.config(values=self._load_suppliers_from_db()))
        self.supplier_btn.grid(row=0, column=2, padx=2)

        tk.Label(bill_frame, text="Bill Number:").grid(row=0, column=3, sticky="w", padx=10, pady=4)
        self.bill_no_entry = tk.Entry(bill_frame, width=16)
        self.bill_no_entry.grid(row=0, column=4, padx=4, pady=4)
        self.bill_no_entry.insert(0, f"{datetime.datetime.now().strftime('%d%m%Y')}-1")
        
        # Store button reference to dynamically change color/text for SPLIT_LOT
        self.add_entry_btn = tk.Button(bill_frame, text="➕ Add Entry", bg="#bfefff", font=("Arial", 9, "bold"),
                                       width=16, command=self.open_add_entry_popup)
        self.add_entry_btn.grid(row=0, column=5, padx=15, pady=4)

        self.entry_type_var.trace_add("write", lambda *args: self._on_entry_type_change())
        
        # ---------------- Payment Section ----------------
        pay_frame = tk.LabelFrame(self.main, text="Payment Summary")
        pay_frame.pack(fill="x", pady=2)
        
        self.payment_summary_label = tk.Label(pay_frame, text="No payment details yet", font=("Arial", 9), fg="gray")
        self.payment_summary_label.pack(padx=8, pady=3, anchor="w")
        
        self.payment_btn = tk.Button(pay_frame, text="💰 Set Payment Details", bg="#bfefff", font=("Arial", 9, "bold"), command=self.open_payment_module)
        self.payment_btn.pack(padx=8, pady=3, anchor="w")
        
        self.settlement_label = tk.Label(pay_frame, text="", font=("Arial", 9), fg="purple")
        self.settlement_label.pack(padx=8, pady=1, anchor="w")

        # ---------------- Main Entry Table ----------------
        self._build_tree_columns()

        # ---------------- ACTION BUTTONS ----------------
        action_frame = tk.Frame(self.main)
        action_frame.pack(fill="x", pady=(4, 6))
        tk.Button(action_frame, text="📋 Preview & Submit", bg="green", fg="white", font=("Arial", 9, "bold"), command=self.open_preview).pack(side="left", padx=4)
        tk.Button(action_frame, text="Clear All", bg="red", fg="white", font=("Arial", 9, "bold"), command=self.clear_entries).pack(side="left", padx=4)
        tk.Button(action_frame, text="📝 Edit", bg="#ffc86b", font=("Arial", 9, "bold"), command=self.edit_selected_row).pack(side="left", padx=4)
        tk.Button(action_frame, text="❌ Delete", bg="#ff9999", font=("Arial", 9, "bold"), command=self.delete_selected_row).pack(side="left", padx=4)
        tk.Button(action_frame, text="🔄 New Bill", bg="#87CEFA", font=("Arial", 9, "bold"), command=self.new_bill).pack(side="left", padx=4)

    # ============================================================
    # ✅ MENU BAR
    # ============================================================
    def _create_menu_bar(self):
        menubar = Menu(self.root)
        self.root.config(menu=menubar)
        file_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="📁 File", menu=file_menu)
        file_menu.add_command(label="🔄 New Bill", command=self.new_bill)
        file_menu.add_separator()
        file_menu.add_command(label="🚪 Exit", command=self.root.quit)
        
        settings_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="⚙️ Settings", menu=settings_menu)
        settings_menu.add_command(label="📝 Entry Type Configuration", command=self._open_entry_type_config_and_refresh)
        settings_menu.add_command(label="👤 Add Customer", command=lambda: open_add_customer_dialog(self.root))
        settings_menu.add_separator()
        settings_menu.add_command(label="🔄 Refresh Entry Types", command=self._refresh_entry_types)
        
        help_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="❓ Help", menu=help_menu)
        help_menu.add_command(label="ℹ️ About", command=lambda: messagebox.showinfo("About", "MYGEMS Metal Purchase v8.0"))

    def _rebuild_entry_type_radiobuttons(self):
        for w in self.entry_type_frame.winfo_children():
            w.destroy()

        if "SPLIT_LOT" not in self.entry_types:
            self.entry_types["SPLIT_LOT"] = {"label": "SPLIT LOT", "allow_multiple_items": True}

        fixed_order = ["NORMAL", "STOCK", "LOCK", "SPLIT_LOT"]
        other_types = [k for k in self.entry_types.keys() if k not in fixed_order]

        for type_key in fixed_order + other_types:
            if type_key in self.entry_types:
                tk.Radiobutton(
                    self.entry_type_frame,
                    text=self.entry_types[type_key]["label"],
                    variable=self.entry_type_var,
                    value=type_key,
                    bg="#f0f0f0"
                ).pack(side="left", padx=10, pady=2)

    def _open_entry_type_config_and_refresh(self):
        open_entry_type_config(self.root)
        self._refresh_entry_types()
        if self.entry_type_var.get() not in self.entry_types:
            self.entry_type_var.set("NORMAL")

    def _refresh_entry_types(self):
        self.entry_types = get_all_entry_types()
        self._rebuild_entry_type_radiobuttons()
        messagebox.showinfo("Refreshed", f"Loaded {len(self.entry_types)} entry types")

    # ============================================================
    # ✅ PAYMENT INTEGRATION
    # ============================================================
    def open_payment_module(self):
        items = [self.tree.item(i)["values"] for i in self.tree.get_children()]
        if not items:
            messagebox.showwarning("No Entries", "Add items first before setting payment")
            return
            
        # If splitting lots, bypass manual payments entirely
        if self.entry_type_var.get() == "SPLIT_LOT":
            messagebox.showinfo("No Payment Required", "Splitting lots balances metal accounts automatically. No payment details required.")
            return
            
        total_amount = sum(float(r[8]) for r in items)

        if self.entry_type_var.get() == "BUY_BACK":
            self._open_buyback_payment_choice(total_amount)
        else:
            self.payment_details = open_payment_dialog(
                self.root, total_amount, txn_type=self.metal_type,
                module_name="Metal Purchase")
            if self.payment_details:
                self._update_payment_summary()

    def _open_buyback_payment_choice(self, total_amount):
        popup = tk.Toplevel(self.root)
        popup.title("Buy Back – Payment Method")
        popup.geometry("460x260"); popup.transient(self.root); popup.grab_set()

        tk.Label(popup, text=f"Buy Back Amount: ₹ {total_amount:.2f}",
                 font=("Arial", 13, "bold"), fg="green").pack(pady=15)
        tk.Label(popup, text="Choose how the customer is paid:",
                 font=("Arial", 10)).pack(pady=5)

        def normal():
            popup.destroy()
            self.payment_details = open_payment_dialog(
                self.root, total_amount, txn_type=self.metal_type,
                module_name="Metal Purchase – Buy Back")
            if self.payment_details:
                self._update_payment_summary()

        def adjust():
            popup.destroy()
            self._open_adjustment_dialog(total_amount)

        tk.Button(popup, text="💵 Cash / Bank / Pending Payment",
                  bg="#bfefff", width=35, height=2, command=normal).pack(pady=8)
        tk.Button(popup, text="🔄 Adjustment Against New Purchase",
                  bg="#ffcc88", width=35, height=2, command=adjust).pack(pady=8)

    def _open_adjustment_dialog(self, total_amount):
        """
        Buy-back settlement, now supporting a REAL split between:
          - an amount adjusted against a new purchase lot (adjustment_entries), and
          - a remaining amount paid to the customer via Cash/Bank/Advance/Pending
            (using the same PaymentDialog logic, scoped to just that remainder).
        Previously this was all-or-nothing: either 100% adjustment, or 100%
        cash/bank/pending via the other button. Example this now supports:
        buy-back worth ₹3,000 fully adjusted against a ₹5,000 new purchase,
        with the customer paying the remaining ₹2,000 in cash.
        """
        popup = tk.Toplevel(self.root)
        popup.title("Buy Back – Settlement")
        popup.geometry("620x640"); popup.transient(self.root); popup.grab_set()

        tk.Label(popup, text=f"Buy Back Amount: ₹ {total_amount:.2f}",
                 font=("Arial", 13, "bold"), fg="green").pack(pady=10)

        # ---------------- Adjustment portion ----------------
        adj_frame = tk.LabelFrame(popup, text="Adjust Against New Purchase (optional)", padx=10, pady=10)
        adj_frame.pack(fill="x", padx=15, pady=8)

        tk.Label(adj_frame, text="Adjustment Amount (₹):").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        adj_amt_var = tk.StringVar(value=f"{total_amount:.2f}")
        adj_amt_entry = tk.Entry(adj_frame, textvariable=adj_amt_var, width=15)
        adj_amt_entry.grid(row=0, column=1, padx=5, pady=5)
        tk.Label(adj_frame, text=f"(0 to {total_amount:.2f} — set to 0 for a pure cash/bank/pending buy-back)",
                 fg="gray", font=("Arial", 8)).grid(row=0, column=2, sticky="w", padx=8)

        tk.Label(adj_frame, text="New Purchase Lot No.:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        lot_ent = tk.Entry(adj_frame, width=25)
        lot_ent.grid(row=1, column=1, padx=5, pady=5)

        # ---------------- Remaining summary ----------------
        remaining_lbl = tk.Label(popup, text="", font=("Arial", 11, "bold"), fg="blue")
        remaining_lbl.pack(pady=6)

        # ---------------- Remaining payment portion ----------------
        remain_frame = tk.LabelFrame(popup, text="Remaining Amount — Pay to Customer", padx=10, pady=10)

        remain_mode = tk.StringVar(value="CASH")
        mode_row = tk.Frame(remain_frame); mode_row.pack(fill="x", pady=4)
        for label, val in [("💵 Cash", "CASH"), ("🏦 Bank", "BANK"),
                            ("📋 Advance", "ADVANCE"), ("⏳ Pending", "PENDING")]:
            tk.Radiobutton(mode_row, text=label, variable=remain_mode, value=val,
                           command=lambda: load_remain_accounts()).pack(side="left", padx=6)

        acc_row = tk.Frame(remain_frame); acc_row.pack(fill="x", pady=4)
        tk.Label(acc_row, text="Account:").pack(side="left", padx=5)
        remain_acc_cb = ttk.Combobox(acc_row, width=30, state="readonly")
        remain_acc_cb.pack(side="left", padx=5)

        advance_row = tk.Frame(remain_frame)
        tk.Label(advance_row, text="Advance Paid Now (₹):").pack(side="left", padx=5)
        advance_amt_entry = tk.Entry(advance_row, width=12)
        advance_amt_entry.pack(side="left", padx=5)

        def load_remain_accounts():
            mode = remain_mode.get()
            if mode == "ADVANCE":
                advance_row.pack(fill="x", pady=4)
            else:
                advance_row.pack_forget()
            if mode == "PENDING":
                remain_acc_cb.set(""); remain_acc_cb['values'] = []
                return
            # Advance uses a cash-type account for its "paid now" leg by
            # default, same convention as the main PaymentDialog.
            type_id = 2 if mode in ("CASH", "ADVANCE") else 6
            try:
                self.cur.execute("""
                    SELECT DISTINCT short_name FROM accounts
                    WHERE type_id = %s AND short_name IS NOT NULL ORDER BY short_name
                """, (type_id,))
                accs = [r[0].strip().upper() for r in self.cur.fetchall()]
                remain_acc_cb['values'] = accs
                if accs: remain_acc_cb.set(accs[0])
            except Exception as e:
                print("Account load error:", e); remain_acc_cb['values'] = []

        def recalc(*_):
            try:
                adj_amt = round(float(adj_amt_var.get() or 0), 2)
            except (ValueError, TypeError):
                adj_amt = 0.0
            remaining = round(total_amount - adj_amt, 2)
            remaining_lbl.config(text=f"Remaining to settle with customer: ₹ {max(remaining, 0):.2f}")
            lot_ent.config(state="normal" if adj_amt > 0 else "disabled")
            if remaining > 0.01:
                remain_frame.pack(fill="x", padx=15, pady=8)
                load_remain_accounts()
            else:
                remain_frame.pack_forget()

        adj_amt_var.trace_add("write", recalc)
        recalc()

        tk.Label(popup, text="Remarks:").pack(anchor="w", padx=15)
        rem_ent = tk.Entry(popup, width=60)
        rem_ent.pack(fill="x", padx=15, pady=4)

        def save():
            try:
                adj_amt = round(float(adj_amt_var.get() or 0), 2)
            except (ValueError, TypeError):
                messagebox.showerror("Error", "Invalid adjustment amount"); return
            if adj_amt < 0 or adj_amt > total_amount + 0.01:
                messagebox.showerror("Error", f"Adjustment amount must be between 0 and ₹{total_amount:.2f}"); return

            new_lot = lot_ent.get().strip().upper()
            if adj_amt > 0:
                if not new_lot:
                    messagebox.showwarning("Missing", "Enter the new purchase lot number for the adjusted portion"); return

                # FIX: an adjustment can only be made against a lot that's
                # actually been sold (or is pending dispatch) to a customer
                # — not just any lot sitting in inventory or in this bill.
                # And it must be sold to the SAME customer doing this
                # buy-back, not just any customer. This replaces the old
                # "exists in this bill or in the database" check, which
                # let an adjustment be created against a lot nobody had
                # actually bought yet.
                buyback_customer_name = self.supplier_cb.get().strip().upper()
                try:
                    self.cur.execute(
                        """SELECT c.full_name, soi.item_status
                           FROM sales_order_items soi
                           JOIN sales_orders so ON so.order_id = soi.order_id
                           JOIN customers c ON c.customer_id = so.customer_id
                           WHERE UPPER(soi.lot_no) = %s AND soi.item_status IN ('SOLD', 'PENDING_SEND')
                           LIMIT 1""",
                        (new_lot,)
                    )
                    sale_row = self.cur.fetchone()
                except Exception as e:
                    messagebox.showerror("Error", f"Lot/sale check failed:\n{e}"); return

                if not sale_row:
                    messagebox.showerror(
                        "Invalid Lot",
                        f"'{new_lot}' isn't SOLD or PENDING SEND to any customer.\n"
                        "An adjustment can only be made against a lot that's actually been "
                        "sold (or is pending dispatch) — create that sale in the Sales module first."
                    )
                    return

                sale_customer_name, item_status = sale_row
                if sale_customer_name.strip().upper() != buyback_customer_name:
                    messagebox.showerror(
                        "Customer Mismatch",
                        f"'{new_lot}' is {item_status} to '{sale_customer_name}', not "
                        f"'{self.supplier_cb.get()}'.\nThe adjustment must be against the "
                        f"SAME customer's own purchase."
                    )
                    return

            adj_account_id = None
            if adj_amt > 0:
                adj_account_id = self._get_adjustment_account_id()
                if adj_account_id is None:
                    messagebox.showerror(
                        "Setup Error",
                        "ADJUSTMENT account not found in accounts.\nPlease add an account named 'ADJUSTMENT'."
                    )
                    return

            remaining = round(total_amount - adj_amt, 2)
            remaining_paid = 0.0
            remaining_status = "PAID"
            remaining_account_id = None
            remaining_account_name = None
            mode = None

            if remaining > 0.01:
                mode = remain_mode.get()
                acc = remain_acc_cb.get().strip().upper()

                if mode in ("CASH", "BANK") and not acc:
                    messagebox.showwarning("Missing", "Select an account for the remaining amount"); return

                if mode == "ADVANCE":
                    if not acc:
                        messagebox.showwarning("Missing", "Select an account for the advance"); return
                    try:
                        remaining_paid = round(float(advance_amt_entry.get() or 0), 2)
                    except (ValueError, TypeError):
                        messagebox.showerror("Error", "Invalid advance amount"); return
                    if remaining_paid <= 0:
                        messagebox.showerror("Error", "Advance amount must be greater than 0"); return
                    if remaining_paid > remaining + 0.01:
                        messagebox.showerror("Error", "Advance amount cannot exceed the remaining balance"); return
                elif mode == "PENDING":
                    remaining_paid = 0.0
                else:  # CASH or BANK
                    remaining_paid = remaining

                if mode in ("CASH", "BANK", "ADVANCE") and acc:
                    type_id = 2 if mode in ("CASH", "ADVANCE") else 6
                    try:
                        self.cur.execute(
                            "SELECT account_id FROM accounts WHERE UPPER(short_name)=%s AND type_id=%s LIMIT 1",
                            (acc, type_id)
                        )
                        r = self.cur.fetchone()
                        remaining_account_id = r[0] if r else None
                        remaining_account_name = acc
                    except Exception as e:
                        print("Account ID fetch error:", e)

                remaining_balance = round(remaining - remaining_paid, 2)
                # Same PAID/ADVANCE/PENDING classification as the main
                # PaymentDialog (bug #6 fix applied here too).
                if remaining_balance <= 0.01:
                    remaining_status = "PAID"
                elif remaining_paid > 0:
                    remaining_status = "ADVANCE"
                else:
                    remaining_status = "PENDING"
            else:
                remaining_balance = 0.0

            overall_paid = round(adj_amt + remaining_paid, 2)
            overall_balance = round(total_amount - overall_paid, 2)
            if overall_balance <= 0.01:
                overall_status = "PAID"
            elif overall_paid > 0:
                overall_status = "ADVANCE"
            else:
                overall_status = "PENDING"

            parts = []
            if adj_amt > 0:
                parts.append(f"Adjusted ₹{adj_amt:.2f} against lot {new_lot}")
            if remaining > 0.01:
                acc_note = f" ({remaining_account_name})" if remaining_account_name else ""
                parts.append(f"Remaining ₹{remaining:.2f} via {mode}{acc_note}")
            auto_remarks = "; ".join(parts) if parts else "No amount due"
            user_remarks = rem_ent.get().strip()
            combined_remarks = f"{auto_remarks} | {user_remarks}" if user_remarks else auto_remarks

            if adj_amt > 0 and remaining > 0.01:
                payment_mode = "PARTIAL_ADJUSTMENT"
            elif adj_amt > 0:
                payment_mode = "ADJUSTMENT"
            else:
                payment_mode = mode  # pure cash/bank/advance/pending, no adjustment at all

            self.payment_details = {
                'payment_mode': payment_mode,
                'account_name': 'ADJUSTMENT' if adj_amt > 0 else remaining_account_name,
                'account_id': adj_account_id if adj_amt > 0 else remaining_account_id,
                'secondary_account_id': remaining_account_id if (adj_amt > 0 and remaining > 0.01) else None,
                'paid_amount': overall_paid,
                'balance_amount': overall_balance,
                'total_amount': total_amount,
                'payment_status': overall_status,
                'remarks': combined_remarks,
                'txn_date': datetime.datetime.now().date(),
                'is_adjustment': adj_amt > 0,
                'adjustment_amount': adj_amt,
                'adjusted_lot': new_lot if adj_amt > 0 else None,
            }
            self._update_payment_summary()
            popup.destroy()

        tk.Button(popup, text="✅ Save Settlement", bg="green", fg="white",
                  font=("Arial", 10, "bold"), command=save).pack(pady=15)

    def _get_adjustment_account_id(self):
        try:
            self.cur.execute("""SELECT account_id FROM accounts
                                WHERE UPPER(short_name)='ADJUSTMENT' 
                                   OR UPPER(account_name) LIKE '%ADJUSTMENT%' LIMIT 1""")
            r = self.cur.fetchone()
            return r[0] if r else None
        except Exception as e:
            print("Adjustment a/c lookup err:", e); return None
        
    def _update_payment_summary(self):
        if not self.payment_details:
            self.payment_summary_label.config(text="No payment details yet", fg="gray")
            self.settlement_label.config(text=""); return
        pd = self.payment_details
        text = f"Mode: {pd['payment_mode']} | Account: {pd['account_name'] or 'N/A'} | Paid: ₹ {pd['paid_amount']:.2f} | Balance: ₹ {pd['balance_amount']:.2f} | Status: {pd['payment_status']}"
        colors = {"PAID": "green", "ADVANCE": "orange", "PENDING": "red"}
        self.payment_summary_label.config(text=text, fg=colors.get(pd['payment_status'], "gray"), font=("Arial", 9, "bold"))
        if self.customer_settlements:
            total_settlement = sum(s['amount'] for s in self.customer_settlements)
            self.settlement_label.config(text=f"📌 Customer Settlements: {len(self.customer_settlements)} items = ₹ {total_settlement:.2f}", fg="purple")
        else:
            self.settlement_label.config(text="")

    # ============================================================
    # ✅ UI & METAL SWITCHING
    # ============================================================
    def _on_metal_change(self):
        new_metal = self.metal_var.get().upper()
        if new_metal == self.metal_type: return
        if self.tree.get_children():
            if not messagebox.askyesno("Switch Metal", "Changing metal will clear current entries. Continue?"):
                self.metal_var.set(self.metal_type); return
            self.clear_entries()
        self.metal_type = new_metal
        self.cfg = METAL_CONFIG[self.metal_type]
        self.root.title(self.cfg["title"])
        
        if self.metal_type == "GOLD":
            self.metal_type_header_label.config(text="GOLD PURCHASE", bg="#104e8b", fg="#ffb90f")
            self.metal_header_frame.config(bg="#104e8b")
        else:
            self.metal_type_header_label.config(text="SILVER PURCHASE", bg="#104e8b", fg="white")
            self.metal_header_frame.config(bg="#104e8b")
        
        self._build_tree_columns()
        self._refresh_lot_info()
        self._update_purchase_no_label()
        self.new_bill()

    def _build_tree_columns(self):
        if hasattr(self, 'tree'):
            self.tree.destroy()
            if hasattr(self, 'vsb'): self.vsb.destroy()
            if hasattr(self, 'hsb'): self.hsb.destroy()

        cols = ("Lot", "Code", "ItemType", "Purity", "MetalType", "Dimension", "Weight", "PerGram", "Amount", "Type", "Description")
        self.tree = ttk.Treeview(self.main, columns=cols, show="headings", height=12)
        column_config = {"Lot": 130, "Code": 65, "ItemType": 85, "Purity": 50, "MetalType": 60, "Dimension": 75, "Weight": 75, "PerGram": 75, "Amount": 85, "Type": 65, "Description": 110}
        
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=column_config.get(c, 75), anchor="center" if c != "Description" else "w")
        
        self.tree.pack(fill="both", expand=True, pady=4)
        self.vsb = ttk.Scrollbar(self.main, orient="vertical", command=self.tree.yview)
        self.hsb = ttk.Scrollbar(self.main, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=self.vsb.set, xscrollcommand=self.hsb.set)
        self.vsb.pack(side="right", fill="y")
        self.hsb.pack(side="bottom", fill="x")

    def _refresh_lot_info(self):
        try:
            prefix = self.cfg["lot_prefix"]
            self.cur.execute(f"SELECT lot_no FROM {self.cfg['jewelry_table']} WHERE lot_no LIKE %s", (f"{prefix}%-%",))
            rows = [r[0] for r in self.cur.fetchall() if r[0]]
            if not rows: self.last_lot_num = 0
            else:
                nums = [int(lot.split('-')[-1]) for lot in rows if '-' in lot and lot.split('-')[-1].isdigit()]
                self.last_lot_num = max(nums) if nums else 0
            self.current_lot_number = self.last_lot_num + 1
            self.last_lot_label.config(text=f"Last Lot: {prefix}-{self.last_lot_num}")
            self.new_lot_label.config(text=f"Next Lot: {prefix}-{self.current_lot_number}")
        except Exception as e:
            self.last_lot_label.config(text="Last Lot: -")
            self.new_lot_label.config(text="Next Lot: -")

    def _on_type_change(self):
        if self.purchase_type.get() == "Existing Lot":
            self.existing_lot_btn.pack(side="left", padx=15, pady=2)
        else:
            self.existing_lot_btn.pack_forget()

    def _generate_lot_number(self, item_type, karat=None, metal_type=None):
        item_code = self.cfg["jewelry_type_map"].get(item_type, "X")
        seq = self.current_lot_number
        self.current_lot_number += 1
        self.new_lot_label.config(text=f"Next Lot: {self.cfg['lot_prefix']}-{self.current_lot_number}")
        if self.metal_type == "GOLD":
            k_code = self.cfg["karat_map"].get(karat.upper(), "X") if karat else "X"
            m_code = self.cfg["gold_map"].get(metal_type.upper(), "Y") if metal_type else "Y"
            return f"G{item_code}{k_code}{m_code}-{seq}"
        return f"S{item_code}-{seq}"

    def _get_last_purchase_seq_from_db(self):
        today = datetime.datetime.now().strftime("%Y%m%d")
        try:
            self.cur.execute("SELECT MAX(CAST(SUBSTRING(purchase_no FROM '.*/(\\d+)$') AS INTEGER)) FROM transactions WHERE purchase_no LIKE %s", (f"{today}/%",))
            result = self.cur.fetchone()[0]
            return result if result else 0
        except: return 0

    def _next_purchase_no(self):
        today = datetime.datetime.now().strftime("%Y%m%d")
        seq = getattr(self, '_last_purchase_seq', 0) + 1
        return f"{today}/{seq:02d}"

    def _update_purchase_no_label(self):
        self._last_purchase_seq = self._get_last_purchase_seq_from_db()
        self.purchase_label.config(text=f"Purchase No: {self._next_purchase_no()}")

    def _increment_purchase_seq(self):
        self._last_purchase_seq += 1
        self._update_purchase_no_label()

    def _load_suppliers_from_db(self):

        try:
            self.cur.execute("""
                SELECT DISTINCT a.short_name
                FROM accounts a
                JOIN account_types at
                    ON a.type_id = at.type_id
                JOIN account_sub_types ast
                    ON a.subtype_id = ast.sub_type_id
                WHERE UPPER(at.type_name) = 'SUPPLIER'
                  AND UPPER(ast.sub_type_name) IN ('GOL/SIL')
                  AND a.short_name IS NOT NULL
                ORDER BY a.short_name
            """)

            return [
                r[0].strip().upper()
                for r in self.cur.fetchall()
            ]

        except:
            return []
        
    def _load_customers_from_db(self):
        try:
            self.cur.execute("SELECT DISTINCT short_name FROM accounts WHERE type_id = 3 AND short_name IS NOT NULL ORDER BY short_name")
            return [r[0].strip().upper() for r in self.cur.fetchall()]
        except: return []

    def _on_entry_type_change(self):
        etype = self.entry_type_var.get()
        
        # Adapt UI specifically for SPLIT LOT
        if etype == "SPLIT_LOT":
            self.supplier_cb.set("")
            self.supplier_cb.config(state="disabled")
            self.supplier_btn.config(state="disabled")
            self.add_entry_btn.config(text="Add Split Lot", bg="#ffa07a")
        elif etype == "BUY_BACK":
            self.supplier_cb.config(state="readonly")
            self.supplier_btn.config(state="normal")
            customers = self._load_customers_for_buyback()
            self.supplier_cb.config(values=customers)
            self.supplier_cb.set("")
            self.supplier_btn.config(text="🔍", bg="#ffe680", command=self.open_customer_search_popup)
            self.add_entry_btn.config(text="➕ Add Entry", bg="#bfefff")
        else:
            self.supplier_cb.config(state="readonly")
            self.supplier_btn.config(state="normal")
            self.supplier_cb.config(values=self._load_suppliers_from_db())
            self.supplier_cb.set("")
            self.supplier_btn.config(text="+", bg="SystemButtonFace",
                command=lambda: self.supplier_cb.config(values=self._load_suppliers_from_db()))
            self.add_entry_btn.config(text="➕ Add Entry", bg="#bfefff")

    def _load_customers_for_buyback(self):
        try:
            self.cur.execute("""
                SELECT DISTINCT full_name FROM customers 
                WHERE full_name IS NOT NULL ORDER BY full_name
            """)
            return [r[0].strip().upper() for r in self.cur.fetchall()]
        except Exception as e:
            print("Customer load error:", e)
            return []

    def open_customer_search_popup(self):
        popup = tk.Toplevel(self.root)
        popup.title("🔍 Search Customer")
        popup.geometry("700x500")
        popup.transient(self.root); popup.grab_set()

        top = tk.Frame(popup); top.pack(fill="x", pady=8, padx=10)
        tk.Label(top, text="Search By:", font=("Arial", 10, "bold")).pack(side="left")
        search_by = tk.StringVar(value="full_name")
        tk.Radiobutton(top, text="Name", variable=search_by, value="full_name").pack(side="left", padx=10)
        tk.Radiobutton(top, text="Phone", variable=search_by, value="phone").pack(side="left", padx=10)

        sf = tk.Frame(popup); sf.pack(fill="x", padx=10)
        tk.Label(sf, text="Search:").pack(side="left")
        search_var = tk.StringVar()
        ent = tk.Entry(sf, textvariable=search_var, width=40, font=("Arial", 11))
        ent.pack(side="left", padx=6); ent.focus()

        cols = ("name", "phone", "address")
        tree = ttk.Treeview(popup, columns=cols, show="headings", height=15)
        for c in cols:
            tree.heading(c, text=c.capitalize())
            tree.column(c, width=200, anchor="w")
        tree.pack(fill="both", expand=True, padx=10, pady=8)

        def do_search(*_):
            tree.delete(*tree.get_children())
            txt = search_var.get().strip()
            try:
                if search_by.get() == "full_name":
                    self.cur.execute("""SELECT full_name, phone, address FROM customers 
                                        WHERE UPPER(full_name) LIKE %s ORDER BY full_name LIMIT 200""",
                                     (f"%{txt.upper()}%",))
                else:
                    self.cur.execute("""SELECT full_name, phone, address FROM customers 
                                        WHERE phone LIKE %s ORDER BY full_name LIMIT 200""",
                                     (f"%{txt}%",))
                for r in self.cur.fetchall():
                    tree.insert("", "end", values=r)
            except Exception as e:
                print("Customer search error:", e)

        search_var.trace_add("write", do_search)
        search_by.trace_add("write", do_search)
        do_search()

        def select():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Select", "Pick a customer"); return
            vals = tree.item(sel[0], "values")
            name = vals[0].strip().upper()
            cur_values = list(self.supplier_cb["values"])
            if name not in cur_values:
                cur_values.append(name)
                self.supplier_cb.config(values=cur_values)
            self.supplier_cb.set(name)
            popup.destroy()

        tk.Button(popup, text="✅ Select Customer", bg="green", fg="white",
                  font=("Arial", 10, "bold"), command=select).pack(pady=8)

    # ============================================================
    # ✅ POPUPS & ENTRY MANAGEMENT
    # ============================================================
    def open_existing_lot_popup(self):
        if not self.supplier_cb.get() and self.entry_type_var.get() != "SPLIT_LOT":
            messagebox.showwarning("Missing", "Select Supplier/Customer first"); return
        popup = tk.Toplevel(self.root); popup.title("🔍 Select Existing Lot"); popup.geometry("750x550")
        popup.transient(self.root); popup.grab_set()
        tk.Label(popup, text="Search Lot Number:", font=("Arial", 11, "bold")).pack(pady=(10,4))
        search_type = tk.StringVar(value="NORMAL")
        type_frame = tk.Frame(popup); type_frame.pack(pady=4)
        tk.Radiobutton(type_frame, text="Jewelry", variable=search_type, value="NORMAL").pack(side="left", padx=10)
        tk.Radiobutton(type_frame, text="Stock", variable=search_type, value="STOCK").pack(side="left", padx=10)
        search_var = tk.StringVar()
        search_entry = tk.Entry(popup, textvariable=search_var, font=("Arial",12), width=35); search_entry.pack(pady=4); search_entry.focus()
        list_frame = tk.Frame(popup); list_frame.pack(fill="both", expand=True, padx=10, pady=6)
        vsb = ttk.Scrollbar(list_frame, orient="vertical"); vsb.pack(side="right", fill="y")
        cols = ("lot_no","item_code","jewelry_type","purity","status")
        lot_tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=16)
        for c in cols: lot_tree.heading(c,text=c.capitalize()); lot_tree.column(c,width=100)
        lot_tree.pack(side="left", fill="both", expand=True); lot_tree.configure(yscrollcommand=vsb.set); vsb.configure(command=lot_tree.yview)
        def load_results(txt=""):
            lot_tree.delete(*lot_tree.get_children())
            try:
                if search_type.get() == "NORMAL":
                    self.cur.execute(f"SELECT lot_no, item_code, jewelry_type, purity, status FROM {self.cfg['jewelry_table']} WHERE status='AVAILABLE' AND jewelry_type NOT IN ('STOCK', 'LOCK') AND lot_no ILIKE %s ORDER BY lot_no LIMIT 200", (f"%{txt}%",))
                else:
                    self.cur.execute(f"SELECT lot_no, item_code, jewelry_type, purity, status FROM {self.cfg['jewelry_table']} WHERE status='AVAILABLE' AND jewelry_type = 'STOCK' AND lot_no ILIKE %s ORDER BY lot_no LIMIT 200", (f"%{txt}%",))
                for r in self.cur.fetchall(): lot_tree.insert("", "end", values=r)
            except Exception as e: print("⚠️ Search error:", e)
        def on_select():
            sel = lot_tree.selection()
            if not sel: messagebox.showwarning("Select","Choose a row"); return
            vals = lot_tree.item(sel[0],"values")
            self._add_existing_lot_to_tree(vals); popup.destroy()
        search_var.trace_add("write", lambda *_: load_results(search_var.get()))
        search_type.trace_add("write", lambda *_: load_results(search_var.get()))
        load_results("")
        tk.Button(popup, text="✅ Add Selected", bg="#bfefff", command=on_select).pack(pady=8)

    def _add_existing_lot_to_tree(self, lot_data):
        lot_no, code, jtype, purity, status = lot_data
        conn = get_connection()
        if not conn: return
        cur = conn.cursor()
        try:
            cur.execute(f"SELECT {self.cfg['weight_col']}, per_gram, {self.cfg['amount_col']} FROM {self.cfg['jewelry_table']} WHERE lot_no=%s", (lot_no,))
            res = cur.fetchone()
            cur_wt = res[0] if res else 0; cur_pg = res[1] if res else 0; cur_amt = res[2] if res else 0
        finally: cur.close(); conn.close()
        ask = tk.Toplevel(self.root); ask.title(f"Enter Details — {lot_no}"); ask.geometry("480x380"); ask.transient(self.root); ask.grab_set()
        tk.Label(ask, text=f"Lot: {lot_no}", font=("Arial",11,"bold")).pack(pady=6)
        tk.Label(ask, text=f"Type: {jtype} | Purity: {purity}").pack()
        tk.Label(ask, text=f"Current: {cur_wt:.3f}g @ ₹{cur_pg:.2f} = ₹{cur_amt:.2f}", fg="blue").pack()
        f = tk.Frame(ask); f.pack(pady=10)
        tk.Label(f, text="Weight (gm):").grid(row=0,column=0,sticky="w"); w_ent = tk.Entry(f,width=12); w_ent.grid(row=0,column=1,padx=6)
        tk.Label(f, text="Amount (₹):").grid(row=1,column=0,sticky="w"); a_ent = tk.Entry(f,width=12); a_ent.grid(row=1,column=1,padx=6)
        tk.Label(f, text="Description:").grid(row=2,column=0,sticky="w"); d_ent = tk.Entry(f,width=20); d_ent.grid(row=2,column=1,padx=6)
        def add_it():
            try: w=float(w_ent.get()); a=float(a_ent.get())
            except: messagebox.showerror("Error","Invalid numbers"); return
            pg=round(a/w,2) if w else 0
            # FIX (bug #9): the main tree has exactly 11 columns
            # (Lot, Code, ItemType, Purity, MetalType, Dimension, Weight,
            # PerGram, Amount, Type, Description) in that order. The old
            # code inserted 14 values in a different order, which shoved an
            # empty string into the "Weight" slot and made submit_all()
            # crash with `float("")` every time this flow was used.
            desc_text = d_ent.get().upper()
            if desc_text:
                desc_text = f"{desc_text} (prev: {cur_wt:.3f}g/₹{cur_amt:.2f})"
            else:
                desc_text = f"EXISTING LOT (prev: {cur_wt:.3f}g/₹{cur_amt:.2f})"
            self.tree.insert("", "end", values=(
                lot_no,                                             # Lot
                code.upper(),                                       # Code
                jtype.upper(),                                      # ItemType
                purity,                                              # Purity
                "925" if self.metal_type == "SILVER" else "",       # MetalType
                "0",                                                 # Dimension
                f"{w:.3f}",                                          # Weight
                f"{pg:.2f}",                                         # PerGram
                f"{a:.2f}",                                          # Amount
                "EXISTING",                                          # Type
                desc_text                                            # Description
            ))
            ask.destroy(); messagebox.showinfo("Added",f"{lot_no} added")
        tk.Button(ask, text="✅ Add", bg="green", fg="white", command=add_it).pack(pady=10)

    # ------------------------------------------------------------
    # ✅ SPLIT LOT POPUP ENTRY WINDOW
    # ------------------------------------------------------------
    def open_split_lot_popup(self):
        popup = tk.Toplevel(self.root)
        popup.title("Split Lot Entry")
        popup.geometry("950x650")
        popup.transient(self.root)
        popup.grab_set()
        
        old_lot_var = tk.StringVar(value="None Selected")
        old_wt_var = tk.DoubleVar(value=0.0)
        old_pg_var = tk.DoubleVar(value=0.0)
        old_amt_var = tk.DoubleVar(value=0.0)
        old_code_var = tk.StringVar(value="")
        old_pur_var = tk.StringVar(value="")
        old_mt_var = tk.StringVar(value="")
        old_sup_var = tk.StringVar(value="INTERNAL")
        
        pf = tk.Frame(popup, padx=12, pady=12)
        pf.pack(fill="both", expand=True)
        
        # Search & Select available lot
        search_f = tk.Frame(pf)
        search_f.pack(fill="x", pady=5)
        tk.Label(search_f, text="Select Lot to Split:", font=("Arial", 11, "bold")).pack(side="left", padx=5)
        lbl_selected = tk.Label(search_f, textvariable=old_lot_var, font=("Arial", 11, "bold"), fg="blue")
        lbl_selected.pack(side="left", padx=10)
        
        def open_search():
            s_win = tk.Toplevel(popup)
            s_win.title("🔍 Search Lot to Split")
            s_win.geometry("750x450")
            s_win.transient(popup); s_win.grab_set()
            
            tk.Label(s_win, text="Search Lot No:").pack(pady=5)
            s_var = tk.StringVar()
            s_ent = tk.Entry(s_win, textvariable=s_var, font=("Arial", 11), width=30)
            s_ent.pack(pady=5); s_ent.focus()
            
            cols = ("lot_no", "item_code", "jewelry_type", "purity", "weight", "per_gram", "supplier_name")
            tree = ttk.Treeview(s_win, columns=cols, show="headings", height=12)
            for c in cols: tree.heading(c, text=c.capitalize()); tree.column(c, width=100)
            tree.pack(fill="both", expand=True, padx=10, pady=5)
            
            def do_s(*_):
                tree.delete(*tree.get_children())
                txt = s_var.get().strip()
                try:
                    wt_col = self.cfg["weight_col"]
                    q = f"""SELECT lot_no, item_code, jewelry_type, purity, {wt_col}, per_gram, supplier_name 
                            FROM {self.cfg['jewelry_table']} 
                            WHERE status='AVAILABLE' AND lot_no ILIKE %s ORDER BY lot_no LIMIT 100"""
                    self.cur.execute(q, (f"%{txt}%",))
                    for r in self.cur.fetchall():
                        tree.insert("", "end", values=r)
                except Exception as e: print("Search err:", e)
            
            s_var.trace_add("write", do_s)
            do_s()
            
            def pick():
                sel = tree.selection()
                if not sel: return
                vals = tree.item(sel[0], "values")
                old_lot_var.set(vals[0])
                old_code_var.set(vals[1])
                old_pur_var.set(vals[3])
                old_wt_var.set(float(vals[4]))
                old_pg_var.set(float(vals[5]))
                old_amt_var.set(round(float(vals[4]) * float(vals[5]), 2))
                old_sup_var.set(vals[6] if vals[6] else "INTERNAL")
                old_mt_var.set("YG" if self.metal_type == "GOLD" else "925")
                
                w_ent.config(state="normal"); w_ent.delete(0, tk.END); w_ent.insert(0, str(vals[4])); w_ent.config(state="disabled")
                a_ent.config(state="normal"); a_ent.delete(0, tk.END); a_ent.insert(0, str(old_amt_var.get())); a_ent.config(state="disabled")
                pg_lbl.config(text=str(vals[5]))
                code_ent.config(state="normal"); code_ent.delete(0, tk.END); code_ent.insert(0, str(vals[1])); code_ent.config(state="disabled")
                pur_ent.config(state="normal"); pur_ent.delete(0, tk.END); pur_ent.insert(0, str(vals[3])); pur_ent.config(state="disabled")
                if mt_ent: mt_ent.config(state="normal"); mt_ent.delete(0, tk.END); mt_ent.insert(0, old_mt_var.get()); mt_ent.config(state="disabled")
                
                s_win.destroy()
                
            tk.Button(s_win, text="✅ Select Lot", bg="green", fg="white", font=("Arial", 10, "bold"), command=pick).pack(pady=10)
            
        tk.Button(search_f, text="🔍 Search Lot", bg="#ffe680", font=("Arial", 10, "bold"), command=open_search).pack(side="left", padx=10)
        
        # Disabled fields showing old lot metrics
        top = tk.LabelFrame(pf, text="Original Lot Details (Disabled)")
        top.pack(fill="x", pady=6, padx=5)
        
        tk.Label(top, text="Weight (gm):").grid(row=0, column=0, padx=5, pady=5)
        w_ent = tk.Entry(top, width=12, state="disabled"); w_ent.grid(row=0, column=1, padx=5, pady=5)
        
        tk.Label(top, text="Amount:").grid(row=0, column=2, padx=5, pady=5)
        a_ent = tk.Entry(top, width=14, state="disabled"); a_ent.grid(row=0, column=3, padx=5, pady=5)
        
        tk.Label(top, text="Per Gram:").grid(row=0, column=4, padx=5, pady=5)
        pg_lbl = tk.Label(top, text="0.00", fg="blue", font=("Arial", 10, "bold")); pg_lbl.grid(row=0, column=5, padx=5, pady=5)
        
        tk.Label(top, text="Code:").grid(row=0, column=6, padx=5, pady=5)
        code_ent = tk.Entry(top, width=10, state="disabled"); code_ent.grid(row=0, column=7, padx=5, pady=5)
        
        tk.Label(top, text="Purity:").grid(row=1, column=0, padx=5, pady=5)
        pur_ent = tk.Entry(top, width=12, state="disabled"); pur_ent.grid(row=1, column=1, padx=5, pady=5)
        
        mt_ent = None
        if self.cfg["show_metal_type"]:
            tk.Label(top, text="Metal Type:").grid(row=1, column=2, padx=5, pady=5)
            mt_ent = tk.Entry(top, width=12, state="disabled"); mt_ent.grid(row=1, column=3, padx=5, pady=5)
            
        # Item Rows with separate weight entry
        item_frame = tk.LabelFrame(pf, text="Split Into New Lots (Mention weight for each item)")
        item_frame.pack(fill="both", expand=True, pady=8, padx=5)
        
        itop = tk.Frame(item_frame); itop.pack(fill="x", padx=6, pady=4)
        tk.Button(itop, text="+ Row", bg="#d6ffd6", command=lambda: add_row()).pack(side="left")
        tk.Button(itop, text="- Row", bg="#ffd6d6", command=lambda: rem_row()).pack(side="left", padx=6)
        
        lbl_tot_split = tk.Label(itop, text="Total Split Weight: 0.000 gm", font=("Arial", 10, "bold"), fg="purple")
        lbl_tot_split.pack(side="right", padx=10)
        
        icanvas = tk.Canvas(item_frame); icanvas.pack(side="left", fill="both", expand=True, padx=6, pady=4)
        isb = ttk.Scrollbar(item_frame, orient="vertical", command=icanvas.yview); isb.pack(side="right", fill="y")
        icanvas.configure(yscrollcommand=isb.set)
        
        iinner = tk.Frame(icanvas); icanvas.create_window((0, 0), window=iinner, anchor="nw")
        iinner.bind("<Configure>", lambda e: icanvas.configure(scrollregion=icanvas.bbox("all")))
        
        rows = []
        
        def calc_tot_split(*_):
            tot = 0.0
            for rf, icb, lcb, pce, wte, len_lbl in rows:
                try: tot += float(wte.get() or 0)
                except: pass
            lbl_tot_split.config(text=f"Total Split Weight: {tot:.3f} gm")
            if tot > old_wt_var.get(): lbl_tot_split.config(fg="red")
            else: lbl_tot_split.config(fg="purple")
        
        def add_row():
            rf = tk.Frame(iinner, pady=4); rf.pack(fill="x", padx=6, pady=2)
            tk.Label(rf, text="Item:").pack(side="left")
            icb = ttk.Combobox(rf, values=["Chain","Bracelet","Ring","Earring","Necklace","Pendant","Bangle","Spectacles"], width=12, state="readonly")
            icb.pack(side="left", padx=4)
            
            len_lbl = tk.Label(rf, text="Len:"); len_lbl.pack(side="left", padx=(8, 0))
            lcb = ttk.Combobox(rf, values=LENGTH_OPTIONS, width=6); lcb.pack(side="left", padx=4); lcb.set("18")
            
            tk.Label(rf, text="Pcs:").pack(side="left", padx=(8, 0)); pce = tk.Entry(rf, width=5); pce.pack(side="left", padx=4); pce.insert(0, "1")
            
            # Separate Weight Box for Split items
            tk.Label(rf, text="Weight (gm):", font=("Arial", 9, "bold"), fg="#ff4500").pack(side="left", padx=(10, 2))
            wte = tk.Entry(rf, width=10); wte.pack(side="left", padx=4)
            wte.bind("<KeyRelease>", calc_tot_split)
            
            tk.Button(rf, text="X", fg="red", command=lambda: [rf.destroy(), rows.remove((rf, icb, lcb, pce, wte, len_lbl)), calc_tot_split()]).pack(side="right", padx=10)
            rows.append((rf, icb, lcb, pce, wte, len_lbl))
            
            def update_len(*args):
                if icb.get().strip().upper() == "RING":
                    len_lbl.config(text="Size:"); lcb['values'] = RING_SIZES; lcb.set("55")
                else:
                    len_lbl.config(text="Len:"); lcb['values'] = LENGTH_OPTIONS; lcb.set("18")
            icb.bind("<<ComboboxSelected>>", update_len)
            
        def rem_row():
            if rows:
                rf, icb, lcb, pce, wte, len_lbl = rows.pop()
                rf.destroy(); calc_tot_split()
                
        add_row()
        
        btnf = tk.Frame(pf); btnf.pack(fill="x", pady=10)
        
        def submit_split():
            old_lot = old_lot_var.get().strip()
            if old_lot == "None Selected" or not old_lot:
                messagebox.showwarning("Missing", "Please search and select a lot to split first!"); return
                
            tot_wt = 0.0
            valid_items = []
            for rf, icb, lcb, pce, wte, len_lbl in rows:
                it = icb.get().strip().upper()
                try: pcs = int(pce.get() or 0)
                except: pcs = 0
                try: r_wt = float(wte.get() or 0)
                except: r_wt = 0.0
                
                if it and pcs > 0 and r_wt > 0:
                    tot_wt += r_wt
                    valid_items.append((it, lcb.get().strip(), pcs, r_wt))
                    
            if not valid_items:
                messagebox.showwarning("Missing", "Please enter valid item rows with weights greater than 0"); return
                
            orig_wt = old_wt_var.get()
            
            # VALIDATION: check if total split weight > original lot weight
            if tot_wt > orig_wt:
                messagebox.showerror("Weight Exceeded", 
                    f"Total split weight ({tot_wt:.3f}g) cannot be more than original lot weight ({orig_wt:.3f}g)!\nNo entry will pass.")
                return
                
            pg = old_pg_var.get(); code = old_code_var.get(); pur = old_pur_var.get()
            mt = old_mt_var.get(); orig_sup = old_sup_var.get()
            
            cur_sup_vals = list(self.supplier_cb["values"])
            if orig_sup not in cur_sup_vals:
                cur_sup_vals.append(orig_sup)
                self.supplier_cb.config(values=cur_sup_vals)
            self.supplier_cb.config(state="normal"); self.supplier_cb.set(orig_sup); self.supplier_cb.config(state="disabled")
            
            # ✅ FIXED: Shortened payment_mode to 'SPLIT' (5 chars) to prevent varchar(10) database error
            self.payment_details = {
                'payment_mode': 'SPLIT', 'account_name': 'SPLIT ADJUSTMENT', 'account_id': None,
                'paid_amount': 0.0, 'balance_amount': 0.0, 'total_amount': 0.0,
                'payment_status': 'PAID', 'remarks': f'Split from lot {old_lot}',
                'txn_date': datetime.datetime.now().date(), 'is_adjustment': False
            }
            self._update_payment_summary()
            
            for it, size_str, pcs, r_wt in valid_items:
                wt_per_pc = r_wt / pcs
                amt_per_pc = wt_per_pc * pg
                
                for _ in range(pcs):
                    new_lot = self._generate_lot_number(it, karat=pur if self.metal_type=="GOLD" else None, metal_type=mt if self.metal_type=="GOLD" else None)
                    desc = f"SPLIT FROM {old_lot}"
                    self.tree.insert("", "end", values=(
                        new_lot, code, it, pur, mt, size_str, f"{wt_per_pc:.3f}", f"{pg:.2f}", f"{amt_per_pc:.2f}", "SPLIT_LOT", desc
                    ))
                    
            popup.destroy()
            messagebox.showinfo("Success", "Split entries added to bill.\nClick 'Preview & Submit' to finalize.")
            
        tk.Button(btnf, text="✅ Add Split to Bill", bg="#ffa07a", font=("Arial", 11, "bold"), command=submit_split).pack(side="right", padx=10)
        tk.Button(btnf, text="Cancel", command=popup.destroy).pack(side="right", padx=6)

    def open_add_entry_popup(self):
        # Redirect to customized window if SPLIT LOT selected
        if self.entry_type_var.get() == "SPLIT_LOT":
            self.open_split_lot_popup()
            return
            
        if not self.supplier_cb.get(): 
            messagebox.showwarning("Missing","Select Supplier/Customer first")
            return
        
        popup = tk.Toplevel(self.root)
        popup.title("Add Purchase Entry")
        popup.geometry("900x600")
        popup.transient(self.root)
        popup.grab_set()
        
        pf = tk.Frame(popup, padx=12, pady=12)
        pf.pack(fill="both", expand=True)
        
        current_type = self.entry_type_var.get()
        type_label = self.entry_types.get(current_type, {}).get('label', current_type)
        tk.Label(pf, text=f"Entry Mode: {type_label}", font=("Arial", 12, "bold"), fg="blue").pack(anchor="w", pady=5)

        lot_name_var = tk.StringVar()
        lot_frame = tk.Frame(pf)
        lot_frame.pack(fill="x", pady=5)
        
        if current_type in ("STOCK", "LOCK"):
            tk.Label(lot_frame, text="Lot Number:", font=("Arial", 10)).pack(side="left", padx=5)
            lot_entry = tk.Entry(lot_frame, textvariable=lot_name_var, width=20)
            lot_entry.pack(side="left", padx=5)
            lot_entry.focus()
            lot_name_var.trace_add("write", lambda *args: lot_name_var.set(lot_name_var.get().upper()))

        top = tk.Frame(pf); top.pack(fill="x",pady=6)
        tk.Label(top,text="Weight (gm):").grid(row=0,column=0); w_ent=tk.Entry(top,width=12); w_ent.grid(row=0,column=1,padx=6)
        tk.Label(top,text="Amount:").grid(row=0,column=2); a_ent=tk.Entry(top,width=14); a_ent.grid(row=0,column=3,padx=6)
        tk.Label(top,text="Per Gram:").grid(row=0,column=4); pg_lbl=tk.Label(top,text="0.00",fg="blue"); pg_lbl.grid(row=0,column=5,padx=6)
        tk.Label(top,text="Code:").grid(row=0,column=6); code_ent=tk.Entry(top,width=12); code_ent.grid(row=0,column=7,padx=6)
        
        mid = tk.Frame(pf); mid.pack(fill="x",pady=8)
        tk.Label(mid,text="Purity:").grid(row=0,column=0); pur_cb=ttk.Combobox(mid,values=self.cfg["purities"],width=8,state="readonly"); pur_cb.grid(row=0,column=1,padx=6); pur_cb.set(self.cfg["purities"][0])
        mt_cb = None; col_offset = 2
        if self.cfg["show_metal_type"]:
            tk.Label(mid,text="Metal Type:").grid(row=0,column=col_offset); mt_cb=ttk.Combobox(mid,values=self.cfg["metal_types"],width=8,state="readonly"); mt_cb.grid(row=0,column=col_offset+1,padx=6); mt_cb.set(self.cfg["metal_types"][0]); col_offset += 2
        tk.Label(mid,text="Description:").grid(row=0,column=col_offset); desc_ent=tk.Entry(mid,width=30); desc_ent.grid(row=0,column=col_offset+1,padx=6)
        
        item_frame = tk.LabelFrame(pf,text="Item Rows"); item_frame.pack(fill="both",expand=True,pady=8)
        itop = tk.Frame(item_frame); itop.pack(fill="x",padx=6,pady=4)
        tk.Button(itop,text="+ Row",bg="#d6ffd6",command=lambda:add_row()).pack(side="left")
        tk.Button(itop,text="- Row",bg="#ffd6d6",command=lambda:rem_row()).pack(side="left",padx=6)
        icanvas=tk.Canvas(item_frame); icanvas.pack(side="left",fill="both",expand=True,padx=6,pady=4)
        isb=ttk.Scrollbar(item_frame,orient="vertical",command=icanvas.yview); isb.pack(side="right",fill="y")
        icanvas.configure(yscrollcommand=isb.set)
        iinner=tk.Frame(icanvas); icanvas.create_window((0,0),window=iinner,anchor="nw")
        iinner.bind("<Configure>",lambda e:icanvas.configure(scrollregion=icanvas.bbox("all")))
        rows=[]
        
        def add_row():
            rf=tk.Frame(iinner,pady=3); rf.pack(fill="x",padx=6,pady=2)
            tk.Label(rf,text="Item:").pack(side="left")
            icb=ttk.Combobox(rf,values=["Chain","Bracelet","Ring","Earring","Necklace","Pendant","Bangle","Spectacles"],width=12,state="readonly"); icb.pack(side="left",padx=4)
            len_lbl = tk.Label(rf,text="Len:"); len_lbl.pack(side="left",padx=(8,0))
            lcb=ttk.Combobox(rf,values=LENGTH_OPTIONS,width=6); lcb.pack(side="left",padx=4); lcb.set("18")
            tk.Label(rf,text="Pcs:").pack(side="left",padx=(8,0)); pce=tk.Entry(rf,width=5); pce.pack(side="left",padx=4); pce.insert(0,"1")
            tk.Button(rf,text="X",fg="red",command=lambda:rf.destroy()).pack(side="right")
            rows.append((rf,icb,lcb,pce, len_lbl))
            def update_length_options(*args):
                item = icb.get().strip().upper()
                if item == "RING": len_lbl.config(text="Size:"); lcb['values'] = RING_SIZES; lcb.set("55")
                else: len_lbl.config(text="Len:"); lcb['values'] = LENGTH_OPTIONS; lcb.set("18")
            icb.bind("<<ComboboxSelected>>", update_length_options)
        def rem_row():
            if rows: rows.pop()[0].destroy()
        add_row()
        
        btnf=tk.Frame(pf); btnf.pack(fill="x",pady=10)
        def calc(*_):
            try: w=float(w_ent.get()); a=float(a_ent.get()); pg_lbl.config(text=f"{a/w:.2f}" if w else "0.00")
            except: pg_lbl.config(text="0.00")
        w_ent.bind("<KeyRelease>",calc); a_ent.bind("<KeyRelease>",calc)
        
        def submit():
            if not (pur_cb.get() and code_ent.get()): messagebox.showwarning("Missing","Purity & Code required"); return
            try: w=float(w_ent.get()); a=float(a_ent.get())
            except: messagebox.showerror("Error","Invalid Weight/Amount"); return
            pg=float(pg_lbl.cget("text")); pur=pur_cb.get().strip().upper(); code=code_ent.get().strip().upper()
            desc=desc_ent.get().strip().upper(); mt=mt_cb.get().strip().upper() if mt_cb else ""
            
            dimension = "-" 
            etype = self.entry_type_var.get() 
            type_config = self.entry_types.get(etype, {})
            
            if etype in ("STOCK", "LOCK"):
                lot_name = lot_name_var.get().strip().upper()
                if not lot_name: messagebox.showwarning("Missing", "Enter Lot Number for STOCK/LOCK"); return
                for row in self.tree.get_children():
                    if str(self.tree.item(row)["values"][0]).strip().upper() == lot_name:
                        messagebox.showerror("Duplicate Lot", f"Lot '{lot_name}' already added in this bill"); return
                try:
                    self.cur.execute(f"SELECT 1 FROM {self.cfg['jewelry_table']} WHERE UPPER(lot_no) = %s LIMIT 1", (lot_name,))
                    if self.cur.fetchone(): messagebox.showerror("Duplicate Lot", f"Lot '{lot_name}' already exists in database"); return
                except Exception as e: messagebox.showerror("Error", f"Lot check failed:\n{e}"); return
                stock_lot = lot_name
            else:
                item_type = rows[0][1].get().strip().upper() if rows else "CHAIN"
                stock_lot = self._generate_lot_number(item_type, karat=pur if self.metal_type=="GOLD" else None, metal_type=mt if self.metal_type=="GOLD" else None)
            
            if type_config.get("allow_multiple_items", False) and rows:
                total_units=0; items=[]
                for rf,icb,lcb,pce, len_lbl in rows:
                    it=icb.get().strip().upper(); pcs=int(pce.get() or 0)
                    if not it or pcs<=0: continue
                    size_str = lcb.get().strip()
                    calc_unit = float(size_str) if it != "RING" else 1.0
                    total_units += pcs * calc_unit
                    items.append((it, size_str, calc_unit, pcs))
                if not items: messagebox.showwarning("Missing","Add item rows"); return

                # FIX (bug #20): guard the divisions below — a 0 total weight
                # or 0 total_units used to throw an uncaught ZeroDivisionError
                # and kill the "Add Entry" action with a raw traceback.
                if total_units <= 0:
                    messagebox.showwarning("Missing", "Enter a valid size/quantity for at least one item row"); return
                if w <= 0:
                    messagebox.showwarning("Missing", "Enter a total weight greater than 0"); return

                for it, size_str, calc_unit, pcs in items:
                    for _ in range(pcs):
                        lot_txt=self._generate_lot_number(it, karat=pur if self.metal_type=="GOLD" else None, metal_type=mt if self.metal_type=="GOLD" else None)
                        pwt=(w/total_units)*calc_unit; pamt=(a/w)*pwt
                        self.tree.insert("","end",values=(lot_txt, code, it, pur, mt, size_str, f"{pwt:.3f}", f"{pg:.2f}", f"{pamt:.2f}", "NORMAL", desc))
            else:
                self.tree.insert("", "end", values=(stock_lot, code, etype, pur, mt, dimension, f"{w:.3f}", f"{pg:.2f}", f"{a:.2f}", etype, desc))
            popup.destroy(); messagebox.showinfo("Added","Entry added")
        
        tk.Button(btnf,text="✅ Add to Bill",bg="#bfefff",font=("Arial",10,"bold"),command=submit).pack(side="right",padx=6)
        tk.Button(btnf,text="Cancel",command=popup.destroy).pack(side="right",padx=6)
        w_ent.focus()

    # ============================================================
    # ✅ PREVIEW & SUBMIT
    # ============================================================
    
    def open_preview(self):
        # Fallback payment setup for zero-cost SPLIT transactions
        if self.entry_type_var.get() == "SPLIT_LOT" and not self.payment_details:
            self.payment_details = {
                'payment_mode': 'SPLIT', 'account_name': 'SPLIT ADJUSTMENT', 'account_id': None,
                'paid_amount': 0.0, 'balance_amount': 0.0, 'total_amount': 0.0,
                'payment_status': 'PAID', 'remarks': 'Lot Split Entry',
                'txn_date': datetime.datetime.now().date(), 'is_adjustment': False
            }
            
        if not self.payment_details: 
            messagebox.showwarning("Payment Required", "Please set payment details first")
            return
            
        items = [self.tree.item(i)["values"] for i in self.tree.get_children()]
        if not items: 
            messagebox.showwarning("No Entries", "Add items first")
            return
            
        sup = self.supplier_cb.get()
        bill = self.bill_no_entry.get()
        
        # ✅ FIXED: Summing r[6] (Weight) instead of r[7] (Per Gram)
        tw = sum(float(r[6]) for r in items)
        ta = sum(float(r[8]) for r in items)
        avg = ta / tw if tw > 0 else 0.0
        
        prev = tk.Toplevel(self.root)
        prev.title("Preview")
        prev.geometry("1000x700")
        prev.transient(self.root)
        prev.grab_set()
        
        tk.Label(prev, text="Purchase Bill Preview", font=("Arial", 14, "bold")).pack(pady=10)
        
        sf = tk.LabelFrame(prev, text="Summary")
        sf.pack(fill="x", padx=10, pady=5)
        
        tk.Label(sf, text=f"Supplier/Customer: {sup}").grid(row=0, column=0, sticky="w", padx=10)
        tk.Label(sf, text=f"Bill: {bill}").grid(row=0, column=1, sticky="w", padx=40)
        tk.Label(sf, text=f"Payment: {self.payment_details['payment_mode']}").grid(row=0, column=2, sticky="w", padx=40)
        
        acc = self.payment_details['account_name']
        if acc: 
            tk.Label(sf, text=f"Account: {acc}", fg="purple").grid(row=0, column=3, sticky="w", padx=30)
            
        tk.Label(sf, text=f"Items: {len(items)}", font=("Arial", 10, "bold")).grid(row=1, column=0, sticky="w", padx=10)
        tk.Label(sf, text=f"Weight: {tw:.3f} gm", fg="blue", font=("Arial", 10, "bold")).grid(row=1, column=1, sticky="w", padx=40)
        tk.Label(sf, text=f"Amount: ₹ {ta:.2f}", fg="darkgreen", font=("Arial", 11, "bold")).grid(row=1, column=2, sticky="w", padx=40)
        tk.Label(sf, text=f"Avg: ₹ {avg:.2f}", fg="red", font=("Arial", 10, "bold")).grid(row=1, column=3, sticky="w", padx=30)
        
        if self.customer_settlements:
            csf = tk.LabelFrame(prev, text="Customer Settlements")
            csf.pack(fill="x", padx=10, pady=5)
            for i, cs in enumerate(self.customer_settlements, 1):
                tk.Label(csf, text=f"{i}. {cs['customer']} - {cs['type']} - Lot: {cs['lot']} - ₹{cs['amount']:.2f}", fg="purple").pack(anchor="w", padx=10, pady=2)
                
        cols = ("Lot", "Code", "Type", "Purity", "Dimension", "Weight", "Amount", "PerGram", "EntryType")
        tr = ttk.Treeview(prev, columns=cols, show="headings", height=18)
        for c in cols: 
            tr.heading(c, text=c)
            tr.column(c, width=90, anchor="center")
        tr.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Mapped correctly: 0=Lot, 1=Code, 2=ItemType, 3=Purity, 5=Dim, 6=Weight, 8=Amount, 7=PG, 9=Type
        for r in items: 
            tr.insert("", "end", values=(r[0], r[1], r[2], r[3], r[5], r[6], r[8], r[7], r[9]))
            
        bf = tk.Frame(prev)
        bf.pack(fill="x", pady=10, padx=10)
        
        def submit_all():
            if not messagebox.askyesno("Confirm", "Submit bill?"): 
                return
            self.submit_all()
            prev.destroy()
            
        tk.Button(bf, text="✅ Submit", bg="green", fg="white", font=("Arial", 11, "bold"), command=submit_all).pack(side="right", padx=10)
        tk.Button(bf, text="Back", command=prev.destroy).pack(side="right", padx=6)

    def submit_all(self):
        items = [self.tree.item(i)["values"] for i in self.tree.get_children()]
        pno = self._next_purchase_no()
        sup = self.supplier_cb.get().strip().upper()
        bill = self.bill_no_entry.get().strip().upper()
        if not self.payment_details: messagebox.showerror("Error", "Payment details not found"); return
        pd = self.payment_details
        ta, paid, bal, status, account_id, remarks, txn_date = pd['total_amount'], pd['paid_amount'], pd['balance_amount'], pd['payment_status'], pd['account_id'], pd['remarks'], pd['txn_date']

        # FIX (bug #16): "Set Payment Details" snapshots the total once —
        # nothing stopped items being added/edited/removed afterward, so the
        # payment could be confirmed against a total that no longer matches
        # what's actually in the bill. Re-check before saving (skipped for
        # SPLIT_LOT, whose total is intentionally 0, and for buy-back
        # adjustments, whose total is the buy-back value, not an item sum).
        is_split_entry = (self.entry_type_var.get() == "SPLIT_LOT")
        if not is_split_entry and not pd.get('is_adjustment'):
            current_items_total = round(sum(float(v["values"][8]) for v in
                                             (self.tree.item(i) for i in self.tree.get_children())), 2)
            if abs(current_items_total - round(ta, 2)) > 0.01:
                messagebox.showerror(
                    "Payment Out of Date",
                    f"Items total (₹{current_items_total:.2f}) no longer matches the "
                    f"payment you set (₹{ta:.2f}).\nItems were changed after payment was "
                    f"set — please re-open payment details and confirm again."
                )
                return

        conn = get_connection()
        if not conn: return
        cur = conn.cursor()
        try:
            is_buyback = (self.entry_type_var.get() == "BUY_BACK")

            # FIX (bug #1): transactions.supplier_id used to hold either an
            # accounts.account_id OR a customers.customer_id with no way to
            # tell which — party_type is the discriminator that disambiguates
            # them. Requires the migration in the accompanying SQL file
            # (ALTER TABLE transactions ADD COLUMN party_type ...).
            if is_buyback:
                # FIX: customers table has full_name, not name -- this was
                # never a bug in the original file, it was introduced when
                # party_type was added; the column reference was wrong from
                # the start and only surfaced now that buy-back is being
                # exercised end-to-end.
                cur.execute("""SELECT customer_id FROM customers 
                               WHERE UPPER(full_name)=%s LIMIT 1""", (sup,))
                res = cur.fetchone()
                if not res: raise Exception(f"Customer {sup} not found in customers table")
                sid = res[0]
                party_type = "CUSTOMER"
            else:
                cur.execute("""SELECT account_id FROM accounts 
                               WHERE UPPER(short_name)=%s AND type_id IN (1,3) LIMIT 1""", (sup,))
                res = cur.fetchone()
                # Provide a foolproof default supplier ID if processing internal split
                if not res and self.entry_type_var.get() == "SPLIT_LOT":
                    cur.execute("SELECT account_id FROM accounts WHERE type_id IN (1,3) LIMIT 1")
                    res = cur.fetchone()
                if not res: raise Exception(f"Supplier/Customer {sup} not found in DB")
                sid = res[0]
                party_type = "SUPPLIER"
            
            cur.execute("""INSERT INTO transactions (txn_date, txn_type, purchase_no, purchase_type, 
              total_amount, supplier_id, party_type, payment_status, payment_mode, paid_amount, 
              balance_amount, remarks, bill_no, account_id, secondary_account_id) 
              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING txn_id""", 
              (txn_date, 'PURCHASE', pno, self.metal_type, ta, sid, party_type, status, 
               pd['payment_mode'], paid, bal, remarks, bill, account_id, pd.get('secondary_account_id')))
            txnid = cur.fetchone()[0]

            # FIX (partial buy-back adjustment): previously this always posted
            # the FULL buy-back total (`ta`) to adjustment_entries, which only
            # worked for a 100%-adjustment buy-back. Now it posts the portion
            # the user actually chose to adjust — pd['adjustment_amount'] —
            # so a buy-back can be split between an adjustment against a new
            # lot and a cash/bank/pending payment for the rest.
            if is_buyback and pd.get('is_adjustment'):
                adj_account_id = pd['account_id']
                new_lot       = pd['adjusted_lot']
                adj_amount    = pd.get('adjustment_amount', ta)
                first_lot = str(items[0][0]).strip().upper()

                # FIX (major bug): the adjustment amount was never checked
                # against how much the target sale actually still owes, and
                # the sale's own paid_amount/balance in sales_order_items
                # was never updated at all -- so an item already fully paid
                # (balance = 0) could still have an adjustment posted
                # against it, and even a valid adjustment never showed up
                # as "paid" on the sales side. Both are fixed here: look up
                # the real remaining balance, block anything over it, and
                # apply the adjustment as a real payment on that item.
                cur.execute(
                    """SELECT order_item_id, order_id, price, paid_amount, balance_amount
                       FROM sales_order_items WHERE UPPER(lot_no) = %s
                       AND item_status IN ('SOLD', 'PENDING_SEND') LIMIT 1""",
                    (new_lot,)
                )
                sale_item = cur.fetchone()
                if not sale_item:
                    raise Exception(f"Lot '{new_lot}' is no longer a valid sale to adjust against — try again.")
                sale_order_item_id, sale_order_id, sale_price, sale_paid, sale_balance = sale_item
                sale_balance = float(sale_balance)
                if adj_amount > sale_balance + 0.01:
                    raise Exception(
                        f"Adjustment of ₹{adj_amount:.2f} exceeds lot '{new_lot}''s remaining balance "
                        f"of ₹{sale_balance:.2f} (price ₹{float(sale_price):.2f}, already paid ₹{float(sale_paid):.2f}). "
                        f"Cannot adjust more than what's actually still owed on that sale."
                    )

                cur.execute("""
                    INSERT INTO adjustment_entries
                    (txn_id, txn_date, purchase_no, account_id, lot_no, debit, credit, remarks, party_name)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (txnid, txn_date, pno, adj_account_id, first_lot,
                      0, adj_amount, f"BUY-BACK from {sup}", sup))

                cur.execute("""
                    INSERT INTO adjustment_entries
                    (txn_id, txn_date, purchase_no, account_id, lot_no, debit, credit, remarks, party_name)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (txnid, txn_date, pno, adj_account_id, new_lot,
                      adj_amount, 0, f"ADJ against new lot {new_lot}", sup))

                # Apply the adjustment as a real payment against the sale --
                # this is what was missing entirely before. Mirrors exactly
                # how sales_module.py itself records a payment.
                cur.execute(
                    "UPDATE sales_order_items SET paid_amount = paid_amount + %s, updated_at = now() WHERE order_item_id = %s",
                    (adj_amount, sale_order_item_id)
                )
                cur.execute(
                    "UPDATE sales_orders SET paid_amount = paid_amount + %s, updated_at = now() WHERE order_id = %s",
                    (adj_amount, sale_order_id)
                )
                cur.execute(
                    """SELECT customer_id FROM sales_orders WHERE order_id = %s""", (sale_order_id,)
                )
                sale_customer_id = cur.fetchone()[0]
                cur.execute(
                    "UPDATE customers SET total_paid = total_paid + %s, updated_at = now() WHERE customer_id = %s",
                    (adj_amount, sale_customer_id)
                )
                cur.execute(
                    """INSERT INTO sales_payments
                       (order_id, order_item_id, customer_id, payment_date, amount, payment_mode, payment_type, remarks)
                       VALUES (%s,%s,%s,%s,%s,'ADJUSTMENT','PAYMENT',%s)""",
                    (sale_order_id, sale_order_item_id, sale_customer_id, txn_date, adj_amount,
                     f"Buy-back adjustment from {sup}, purchase {pno}")
                )
            
            # --- LOOP THROUGH ITEMS ---
            for r in items:
                lot, code, jtype, pur, mt = str(r[0]).strip().upper(), str(r[1]).strip().upper(), str(r[2]).strip().upper(), str(r[3]).strip().upper(), str(r[4]).strip().upper()
                dim, wt, pg, amt = str(r[5]).strip(), float(r[6]), float(r[7]), float(r[8])
                entry_type, desc = str(r[9]).strip().upper(), str(r[10]).strip()
                
                # SPLIT LOT LOGIC: Balanced multi-ledger adjustments
                if entry_type == "SPLIT_LOT":
                    old_lot = desc.replace("SPLIT FROM ", "").strip()
                    wt_col = self.cfg["weight_col"]

                    # 1. Deduct split weight from old lot in jewelry table.
                    # FIX (bug #5): FOR UPDATE locks the source lot row for the
                    # rest of this DB transaction so two concurrent splits of
                    # the same lot can't race and lose an update.
                    cur.execute(
                        f"SELECT {wt_col}, status FROM {self.cfg['jewelry_table']} WHERE lot_no = %s FOR UPDATE",
                        (old_lot,)
                    )
                    ores = cur.fetchone()

                    # FIX (bug #4): used to silently continue and still post
                    # CR/DR ledger entries even when the source lot didn't
                    # exist. Now it aborts (and the whole bill rolls back)
                    # instead of leaving orphaned ledger entries.
                    if not ores:
                        raise Exception(
                            f"Split source lot '{old_lot}' not found — cannot split a lot that doesn't exist."
                        )

                    # FIX (per your instruction): a SOLD lot can't be used
                    # for anything, including being split from.
                    if str(ores[1]).strip().upper() == "SOLD":
                        raise Exception(f"Lot '{old_lot}' is SOLD and cannot be split.")

                    cur_old_wt = float(ores[0])
                    new_old_wt = round(cur_old_wt - wt, 3)

                    # FIX (bug #3, per your instruction): block a split that
                    # would take the source lot negative instead of silently
                    # clamping it to 0.
                    if new_old_wt < -0.001:
                        raise Exception(
                            f"Cannot split {wt:.3f}g from lot '{old_lot}' — "
                            f"only {cur_old_wt:.3f}g available in that lot."
                        )

                    if new_old_wt <= 0.001:
                        # FIX (corrected per your latest instruction): a lot
                        # whose full weight has been split out has no
                        # balance left (weight=0, and amount will follow to
                        # 0 automatically via the ledger-recompute trigger,
                        # since amount = weight * per_gram). It can never be
                        # used again, so it's CANCELLED — not a separate
                        # "SPLITED" status. This fits the 4-status workflow
                        # (MFG / AVAILABLE / SOLD / CANCELLED) used across
                        # the app; CANCELLED is already treated as a fully
                        # locked, terminal state everywhere (see job_cart.py).
                        cur.execute(
                            f"UPDATE {self.cfg['jewelry_table']} SET {wt_col} = 0, status = 'CANCELLED' WHERE lot_no = %s",
                            (old_lot,)
                        )
                    else:
                        cur.execute(
                            f"UPDATE {self.cfg['jewelry_table']} SET {wt_col} = %s WHERE lot_no = %s",
                            (new_old_wt, old_lot)
                        )

                    # 2. Insert Credit (CR) posting out for old lot reduction
                    cur.execute(f"""INSERT INTO {self.cfg['account_table']} 
                                (txn_date, purchase_no, lot_no, per_gram, weight, amount, txn_nature, jewelry_code) 
                                VALUES (%s, %s, %s, %s, %s, %s, 'CR', %s)""", 
                                (txn_date, pno, old_lot, pg, wt, amt, code))
                                
                    # 3. Insert new split lot into jewelry table.
                    # FIX: a freshly split-off lot enters production just
                    # like any newly purchased lot — it isn't sellable yet.
                    # Status is MFG, not AVAILABLE (was previously hardcoded
                    # to AVAILABLE here, which would have let an unfinished
                    # lot appear ready for sale).
                    cur.execute(f"""INSERT INTO {self.cfg['jewelry_table']} 
                                (lot_no, purity, purchase_no, jewelry_type, supplier_name, description, status, dimension) 
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""", 
                                (lot, pur, pno, jtype, sup, desc, 'MFG', dim))
                                
                    # 4. Insert Debit (DR) posting in for new split lot
                    cur.execute(f"""INSERT INTO {self.cfg['account_table']} 
                                (txn_date, purchase_no, lot_no, per_gram, weight, amount, txn_nature, jewelry_code) 
                                VALUES (%s, %s, %s, %s, %s, %s, 'DR', %s)""", 
                                (txn_date, pno, lot, pg, wt, amt, code))
                                
                elif entry_type == "EXISTING":
                    # FIX (new bug found while implementing the status
                    # workflow): "Existing Lot" adds weight/amount to a lot
                    # that already exists in the jewelry table. There was no
                    # dedicated branch for this — it fell through to the
                    # generic branch below, which tries to INSERT a fresh
                    # jewelry row and would fail the UNIQUE constraint on
                    # lot_no (or silently do nothing at all if "EXISTING"
                    # isn't a registered entry type). Only post the DR
                    # ledger entry; the existing AFTER-trigger on
                    # gold_account/silver_account recomputes the lot's
                    # weight/amount from full ledger history automatically.
                    cur.execute(
                        f"SELECT status FROM {self.cfg['jewelry_table']} WHERE lot_no = %s",
                        (lot,)
                    )
                    lot_row = cur.fetchone()
                    if not lot_row:
                        raise Exception(
                            f"'Existing Lot' entry references lot '{lot}', which no longer "
                            f"exists in {self.cfg['jewelry_table']} — it may have been split "
                            f"or cancelled since this bill was started."
                        )
                    # FIX (per your instruction): a CANCELLED (zero-balance)
                    # or SOLD lot can never be used again — block adding
                    # more stock to it here, not just at the UI level.
                    if str(lot_row[0]).strip().upper() in ("CANCELLED", "SOLD"):
                        raise Exception(
                            f"Lot '{lot}' is {lot_row[0]} and can't be added to."
                        )
                    cur.execute(f"""INSERT INTO {self.cfg['account_table']} (txn_date, purchase_no, lot_no, per_gram, weight, amount, txn_nature, jewelry_code) VALUES (%s, %s, %s, %s, %s, %s, 'DR', %s)""",
                                (txn_date, pno, lot, pg, wt, amt, code))

                elif entry_type in self.entry_types.keys():
                    # FIX: every newly purchased lot starts in MFG (in
                    # production) — it must be finished via Job Cart before
                    # it's sellable. Was hardcoded to AVAILABLE, which used
                    # to mean "just purchased" under the old 2-status scheme;
                    # under the new 4-status workflow AVAILABLE specifically
                    # means "finished and ready to sell," so a fresh
                    # purchase must never start there.
                    cur.execute(f"""INSERT INTO {self.cfg['jewelry_table']} (lot_no, purity, purchase_no, jewelry_type, supplier_name, description, status, dimension) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""", 
                                (lot, pur, pno, jtype, sup, desc, 'MFG', dim))
                    cur.execute(f"""INSERT INTO {self.cfg['account_table']} (txn_date, purchase_no, lot_no, per_gram, weight, amount, txn_nature, jewelry_code) VALUES (%s, %s, %s, %s, %s, %s, 'DR', %s)""", 
                                (txn_date, pno, lot, pg, wt, amt, code))
            
            if self.customer_settlements:
                for cs in self.customer_settlements:
                    cur.execute("""INSERT INTO customer_settlements (txn_id, customer_name, lot_no, settlement_type, amount, txn_date, purchase_no) VALUES (%s, %s, %s, %s, %s, %s, %s)""", (txnid, cs['customer'], cs['lot'], cs['type'], cs['amount'], txn_date, pno))
            
            # FIX (partial adjustment): the old exclusion "never insert a
            # pending row for an adjustment buy-back" assumed adjustments
            # were always fully settled. That's no longer true — a partial
            # adjustment can still leave a real ADVANCE/PENDING balance on
            # the remaining cash/bank portion, which needs to show up here
            # just like any other unpaid balance. status != "PAID" alone is
            # now the correct check (a full adjustment already computes to
            # status == "PAID", so it's still excluded automatically).
            if status != "PAID":
                    # FIX (bug #7): account_type was never populated, so a
                    # pending row alone couldn't tell you whether it was money
                    # owed TO a supplier or money owed TO a customer (buyback).
                    cur.execute("""INSERT INTO pending_payments (txn_id, account_id, account_type, account_name, bill_no, purchase_no, total_amount, paid_amount, balance_amount, payment_status, txn_type, txn_date, remarks) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", (txnid, sid, party_type, sup, bill, pno, ta, paid, bal, status, "metal purchase", txn_date, remarks))
            
            conn.commit()
            self._increment_purchase_seq()
            self.clear_entries()
            self.payment_details = None
            self._update_payment_summary()
            messagebox.showinfo("Success", f"✅ Bill Saved\n{pno}\nStatus: {status}")
            
        except Exception as e:
            conn.rollback()
            messagebox.showerror("DB Error", str(e))
        finally: cur.close(); conn.close()

    def clear_entries(self):
        self.tree.delete(*self.tree.get_children())
        self.payment_details = None
        self.customer_settlements = []
        self._update_payment_summary()

    def new_bill(self):
        self.clear_entries()
        self.supplier_cb.set("")
        cur = self.bill_no_entry.get().strip()
        seq = int(cur.split('-')[-1]) + 1 if '-' in cur else 1
        self.bill_no_entry.delete(0, tk.END)
        self.bill_no_entry.insert(0, f"{datetime.datetime.now().strftime('%d%m%Y')}-{seq}")
        self._update_purchase_no_label()

    def delete_selected_row(self):
        sel = self.tree.selection()
        if not sel: return
        if messagebox.askyesno("Confirm", "Delete selected row(s)?"):
            for i in sel: self.tree.delete(i)

    def edit_selected_row(self):
        sel = self.tree.selection()
        if not sel or len(sel) > 1: return
        vals = self.tree.item(sel[0], "values")
        win = tk.Toplevel(self.root); win.title("Edit Row"); win.geometry("550x550")
        cols = ("Lot", "Code", "ItemType", "Purity", "MetalType", "Length", "Dimension", "Weight", "Amount", "PerGram", "MetalWeight", "MetalAmount", "Type", "Description")
        ents = {}
        for i, f in enumerate(cols):
            tk.Label(win, text=f).grid(row=i, column=0, sticky="w", padx=6, pady=2)
            e = tk.Entry(win, width=30); e.grid(row=i, column=1, padx=6, pady=2)
            e.insert(0, vals[i]); ents[f] = e
        def save():
            new_vals = [ents[f].get().strip() for f in cols]
            self.tree.item(sel[0], values=new_vals); win.destroy()
        tk.Button(win, text="Save", bg="lightgreen", command=save).grid(row=len(cols), column=0, columnspan=2, pady=10)


if __name__ == "__main__":
    root = tk.Tk()
    app = MetalPurchaseApp(root)
    root.mainloop()
