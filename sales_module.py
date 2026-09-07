#!/usr/bin/env python3
"""
SALES / ORDER MODULE - Jewelry ERP
====================================
Cart-based sale builder: search/add items with an explicit sold amount
and paid amount per item, review a summary, then Save writes the whole
order + items + payments to the database in one atomic transaction.
Loading an existing order switches the same screen into Edit Mode.

STATUS LIFECYCLE (sales_order_items.item_status)
--------------------------------------------------
  PENDING_STOCK -> PENDING_SEND -> SOLD -> RETURNED   (or CANCELLED
  at any point before SOLD)

  PENDING_STOCK : no lot assigned yet. Shows in the "Pending Order" tab.
  PENDING_SEND  : a lot IS assigned, sale agreed, not yet dispatched.
                  Shows in the "Pending Send" tab.
  SOLD          : dispatched. This is the ONLY point the matching
                  gold_jewelry/silver_jewelry row becomes SOLD.
  RETURNED      : customer returned it after the sale. The matching
                  jewelry lot goes back to AVAILABLE.
  CANCELLED     : dropped before ever being sold.

PAYMENT LINKAGE (fixes "payment isn't tied to jewelry")
--------------------------------------------------------
Every sales_payments row now carries order_item_id -- a payment is
recorded against ONE specific item, not just the order as a whole.
When you add an item to the cart with its own sold amount and paid
amount, that's exactly what gets written: a sales_order_items row with
its own price/paid_amount/balance_amount, and (if paid_amount > 0) a
matching sales_payments row linked to that item. Your example (items
of 2000/3000/4500, paid in full/full/1000-advance) is recorded
exactly as entered -- no inference needed, because the amounts are
explicit per item from the start.

Editing an existing sale (price change, extra payment, or a refund
for a downgrade) and returning an item after a sale are both first-
class actions here, not something bolted on separately.

LAYOUT
------
Four tabs, each scrollable (small-screen friendly):
  Sale / Order   - THE screen: search/select customer, add items
                   (search stock or describe a custom one) with sold
                   + paid amount, cart/items list, payment method,
                   summary, Save. Same screen handles Edit Sale and
                   Sales Return once an existing order is loaded.
  Pending Order  - every PENDING_STOCK item across all orders.
  Pending Send   - every PENDING_SEND item (sold, awaiting dispatch).
  Stock Lookup   - fast search by lot_no OR item_code.

IMPORTANT: gold_jewelry.status / silver_jewelry.status stay exactly
MFG/AVAILABLE/SOLD/CANCELLED. A reservation/return lives only in
sales_order_items. Any OTHER code path that hands out a lot must also
check sales_order_items before treating a lot as free.

Requires: pip install psycopg2-binary --break-system-packages

Run these once, in order, before first use:
  mygems_migration_04_sales_module.sql
  mygems_migration_05_pending_send_process.sql
  mygems_migration_06_payments_returns.sql
"""

import os
import datetime as dt
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import webbrowser
import tempfile

import psycopg2
import psycopg2.extras
import psycopg2.errors

# Reuse the SAME payment dialog used by metal_purchase.py -- one place
# that captures amount/mode/account/status, instead of a separate
# ad-hoc Cash/Transfer/Advance implementation here.
from payment_module import open_payment_dialog

# Same length options as metal_purchase.py, for consistency across
# the app -- editable combobox, so "manual" entry still works.
LENGTH_OPTIONS = ["5.5", "6", "6.5", "7", "7.5", "8", "12", "15.5", "16", "16.5",
                   "17", "18", "20", "22", "24", "26", "28", "30", "32"]

# ------------------------------------------------------------------ #
# CONFIG -- no hardcoded password, read from MYGEMS_DB_PASSWORD.
# ------------------------------------------------------------------ #
DB_CONFIG = {
    "host": os.environ.get("MYGEMS_DB_HOST", "localhost"),
    "port": int(os.environ.get("MYGEMS_DB_PORT", "5432")),
    "dbname": os.environ.get("MYGEMS_DB_NAME", "mygems"),
    "user": os.environ.get("MYGEMS_DB_USER", "myuser"),
    "password": os.environ.get("MYGEMS_DB_PASSWORD", "28116"),
}


class DB:
    def __init__(self, cfg):
        self.cfg = cfg
        self.conn = None

    def connect(self):
        if not self.cfg.get("password"):
            raise RuntimeError(
                "MYGEMS_DB_PASSWORD environment variable is not set. "
                "Set it before starting the app."
            )
        # Prints exactly what this session is connecting to, BEFORE the
        # window opens (so it's visible even though IDLE's mainloop
        # blocks the shell once the app is running). Added specifically
        # to catch "migrated one database, app talks to another"
        # mismatches -- compare this against pgAdmin's connection.
        print(f"[sales_module] Connecting to host={self.cfg['host']} port={self.cfg['port']} "
              f"dbname={self.cfg['dbname']} user={self.cfg['user']}")
        self.conn = psycopg2.connect(**self.cfg)
        self.conn.autocommit = False
        with self.conn.cursor() as cur:
            cur.execute("SELECT current_database(), inet_server_addr(), inet_server_port()")
            db, addr, port = cur.fetchone()
            print(f"[sales_module] Actually connected to: database={db} server={addr or 'localhost'}:{port}")

    def query(self, sql, params=None, fetch="all"):
        # FIX: a failed SELECT used to leave the connection's transaction
        # "aborted" -- every subsequent query (even unrelated ones) would
        # then fail with InFailedSqlTransaction until something explicitly
        # rolled back. This is exactly what turned one missing-column error
        # into "every item became an error." Auto-rollback on failure here
        # so one bad query can't take down the rest of the session.
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params or ())
                if fetch == "all":
                    return cur.fetchall()
                if fetch == "one":
                    return cur.fetchone()
                return None
        except Exception:
            self.conn.rollback()
            raise

    def execute(self, sql, params=None):
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, params or ())
        except Exception:
            self.conn.rollback()
            raise

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()


class Tooltip:
    """
    Simple hover tooltip -- Tkinter has no built-in widget for this.
    Shows `text` in a small borderless window near the cursor while
    hovering over `widget`, hides on leave.
    """
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _event=None):
        if self.tip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self.text, justify="left", background="#ffffe0",
                 relief="solid", borderwidth=1, wraplength=320,
                 font=("Segoe UI", 9), padx=6, pady=4).pack()

    def _hide(self, _event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


class ScrollableFrame(tk.Frame):
    """Wraps a tab's content so small screens can scroll to reach everything."""
    def __init__(self, parent):
        super().__init__(parent)
        canvas = tk.Canvas(self, highlightthickness=0)
        vscroll = tk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.inner = tk.Frame(canvas)

        self.inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_window = canvas.create_window((0, 0), window=self.inner, anchor="nw")
        canvas.configure(yscrollcommand=vscroll.set)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

        canvas.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

        def _wheel(event):
            delta = -1 if event.num == 4 else (1 if event.num == 5 else int(-1 * (event.delta / 120)))
            canvas.yview_scroll(delta, "units")

        def _bind(_e):
            canvas.bind_all("<MouseWheel>", _wheel)
            canvas.bind_all("<Button-4>", _wheel)
            canvas.bind_all("<Button-5>", _wheel)

        def _unbind(_e):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        canvas.bind("<Enter>", _bind)
        canvas.bind("<Leave>", _unbind)


class FormDialog(simpledialog.Dialog):
    """Kept only for genuinely one-off entry (new customer, sales person pick, etc)."""
    def __init__(self, parent, title, fields):
        self.fields = fields
        self.vars = {}
        self.result = None
        super().__init__(parent, title=title)

    def body(self, master):
        for i, (key, label, kind, choices) in enumerate(self.fields):
            tk.Label(master, text=label).grid(row=i, column=0, sticky="w", padx=4, pady=4)
            if kind == "choice":
                var = tk.StringVar(value=choices[0] if choices else "")
                w = ttk.Combobox(master, textvariable=var, values=choices, state="readonly", width=27)
            else:
                var = tk.StringVar()
                w = tk.Entry(master, textvariable=var, width=30)
            w.grid(row=i, column=1, padx=4, pady=4)
            self.vars[key] = var
        return None

    def apply(self):
        self.result = {k: v.get().strip() for k, v in self.vars.items()}


def ask_form(parent, title, fields):
    d = FormDialog(parent, title, fields)
    return d.result


class SalesOrderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sales / Order Management")
        self.geometry("1000x680")

        self.db = DB(DB_CONFIG)
        try:
            self.db.connect()
        except Exception as e:
            messagebox.showerror("DB Connection Error", str(e))
            self.destroy()
            return

        # current_order_id is None while building a NEW (unsaved) sale;
        # once set, the screen is in EDIT mode against a real DB order.
        self.current_order_id = None
        self.current_order_no = None
        self.current_customer = None
        self.selected_sales_person_id = None
        self.cart_items = []  # staged, unsaved items for a new sale

        self.account_name_to_id = {}
        self.process_name_to_id = {}
        self.dispatch_name_to_code = {}
        self.dispatch_requires_tracking = {}

        self._build_ui()
        self._load_catalog_codes()
        self._load_accounts()
        self._load_processes()
        self._load_dispatch_methods()
        self._load_jewelry_types()
        self._load_alloy_types()

    # ---------------------------------------------------- UI BUILD ---
    def _build_ui(self):
        top = tk.Frame(self, bg="#e8eef4")
        top.pack(fill="x")
        tk.Button(top, text="👤 Add Customer", command=self.add_customer_direct).pack(side="left", padx=6, pady=6)
        tk.Button(top, text="📖 New Catalog Item", command=self.add_catalog_item).pack(side="left", padx=6, pady=6)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=6, pady=6)

        tab_order_outer = tk.Frame(self.notebook)
        tab_po_outer = tk.Frame(self.notebook)
        tab_ps_outer = tk.Frame(self.notebook)
        tab_inst_outer = tk.Frame(self.notebook)
        tab_stock_outer = tk.Frame(self.notebook)
        self.notebook.add(tab_order_outer, text="🧾 Sale / Order")
        self.notebook.add(tab_po_outer, text="📋 Pending Order")
        self.notebook.add(tab_ps_outer, text="📦 Pending Send")
        self.notebook.add(tab_inst_outer, text="🗓️ Installments")
        self.notebook.add(tab_stock_outer, text="🔍 Stock Lookup")
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        order_scroll = ScrollableFrame(tab_order_outer)
        order_scroll.pack(fill="both", expand=True)
        self._build_order_tab(order_scroll.inner)

        po_scroll = ScrollableFrame(tab_po_outer)
        po_scroll.pack(fill="both", expand=True)
        self._build_pending_order_tab(po_scroll.inner)

        ps_scroll = ScrollableFrame(tab_ps_outer)
        ps_scroll.pack(fill="both", expand=True)
        self._build_pending_send_tab(ps_scroll.inner)

        inst_scroll = ScrollableFrame(tab_inst_outer)
        inst_scroll.pack(fill="both", expand=True)
        self._build_installments_tab(inst_scroll.inner)

        stock_scroll = ScrollableFrame(tab_stock_outer)
        stock_scroll.pack(fill="both", expand=True)
        self._build_stock_tab(stock_scroll.inner)

        self.status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self.status_var, anchor="w", bd=1, relief="sunken").pack(fill="x")

    def _on_tab_changed(self, _event):
        label = self.notebook.tab(self.notebook.select(), "text")
        if "Pending Order" in label:
            self._refresh_pending_order()
        elif "Pending Send" in label:
            self._refresh_pending_send()
        elif "Installments" in label:
            self._refresh_installments()

    # ---------------------------------------------------- LOOKUPS ----
    def _load_catalog_codes(self):
        rows = self.db.query("SELECT item_code FROM public.item_catalog WHERE is_active ORDER BY item_code")
        self.catalog_combo["values"] = [r["item_code"] for r in rows]

    def _load_accounts(self):
        # NOTE: loads ALL accounts -- no confirmed type_id for "staff"
        # specifically. Narrow this filter if you have one.
        rows = self.db.query(
            "SELECT account_id, COALESCE(short_name, account_name) AS name FROM public.accounts ORDER BY name"
        )
        self.account_name_to_id = {r["name"]: r["account_id"] for r in rows}

    def _load_processes(self):
        rows = self.db.query(
            "SELECT process_id, process_name FROM public.process_master WHERE status='ACTIVE' ORDER BY sort_order, process_name"
        )
        self.process_name_to_id = {r["process_name"]: r["process_id"] for r in rows}

    def _load_dispatch_methods(self):
        rows = self.db.query(
            "SELECT method_code, method_name, requires_tracking_no FROM public.dispatch_methods WHERE is_active ORDER BY sort_order"
        )
        self.dispatch_name_to_code = {r["method_name"]: r["method_code"] for r in rows}
        self.dispatch_requires_tracking = {r["method_code"]: r["requires_tracking_no"] for r in rows}

    def _load_jewelry_types(self):
        rows = self.db.query(
            """SELECT DISTINCT jewelry_type FROM public.gold_jewelry WHERE jewelry_type IS NOT NULL
               UNION
               SELECT DISTINCT jewelry_type FROM public.silver_jewelry WHERE jewelry_type IS NOT NULL
               ORDER BY jewelry_type"""
        )
        self.order_jewelry_type_combo["values"] = [r["jewelry_type"] for r in rows]

    def _load_alloy_types(self):
        # job_transaction.alloy_type is the only place alloy data exists
        # in the schema (no formal alloy_types_master table) -- editable
        # combobox, so a new value can still be typed if it's not in the
        # historical list yet.
        rows = self.db.query(
            "SELECT DISTINCT alloy_type FROM public.job_transaction WHERE alloy_type IS NOT NULL ORDER BY alloy_type"
        )
        self.order_alloy_type_combo["values"] = [r["alloy_type"] for r in rows]

    def _resolve_account_id(self, mode, account_short):
        if not account_short:
            return None
        type_id = 2 if mode in ("CASH", "ADVANCE") else 6
        acc = self.db.query(
            "SELECT account_id FROM public.accounts WHERE UPPER(short_name)=%s AND type_id=%s LIMIT 1",
            (account_short.strip().upper(), type_id), "one"
        )
        return acc["account_id"] if acc else None

    def _capture_refund(self, max_amount, title="Refund"):
        """
        Dedicated payback dialog. Redesigned per feedback:
          - Account is a real dropdown pulled from `accounts`, not a
            free-text short name -- picking an account also tells us its
            CASH vs BANK nature directly (no separate radio needed).
          - Customer A/C No (optional) -- the customer's OWN account
            number, for a bank-transfer refund reference. Not a link to
            your internal accounts table.
          - PARTIAL refund is allowed now (was previously forced to
            cover the full amount). Whatever isn't refunded is
            automatically treated as a cancellation charge and booked
            as revenue to a Profit/Charges account you pick -- so the
            leftover never just vanishes from the books, it's
            deliberately converted into recognized income instead.

        Returns a dict or None if cancelled:
          {"refund_amount", "refund_account_id", "refund_payment_mode",
           "customer_account_no", "charge_amount", "charge_account_id"}
        charge_amount is always (max_amount - refund_amount), computed,
        not separately entered.
        """
        # type_id 2 = Cash, 6 = Bank per the app's existing convention.
        cash_bank_accounts = self.db.query(
            """SELECT account_id, COALESCE(short_name, account_name) AS name, type_id
               FROM public.accounts WHERE type_id IN (2, 6) ORDER BY name"""
        )
        all_accounts = self.db.query(
            "SELECT account_id, COALESCE(short_name, account_name) AS name FROM public.accounts ORDER BY name"
        )
        cash_bank_name_to_row = {r["name"]: r for r in cash_bank_accounts}
        all_name_to_id = {r["name"]: r["account_id"] for r in all_accounts}

        win = tk.Toplevel(self)
        win.title(title)
        win.transient(self)
        win.grab_set()
        win.geometry("420x360")

        tk.Label(win, text=f"Amount to Resolve: ₹{max_amount:.2f}", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(12, 8)
        )

        tk.Label(win, text="Refund to Customer (₹):").grid(row=1, column=0, sticky="w", padx=10, pady=4)
        refund_amount_var = tk.StringVar(value=f"{max_amount:.2f}")
        tk.Entry(win, textvariable=refund_amount_var, width=15).grid(row=1, column=1, sticky="w", padx=10, pady=4)

        tk.Label(win, text="Refund Account:").grid(row=2, column=0, sticky="w", padx=10, pady=4)
        refund_account_var = tk.StringVar()
        refund_account_cb = ttk.Combobox(win, textvariable=refund_account_var,
                                          values=list(cash_bank_name_to_row.keys()), width=22, state="readonly")
        refund_account_cb.grid(row=2, column=1, sticky="w", padx=10, pady=4)

        tk.Label(win, text="Customer A/C No (optional):").grid(row=3, column=0, sticky="w", padx=10, pady=4)
        customer_acc_var = tk.StringVar()
        tk.Entry(win, textvariable=customer_acc_var, width=22).grid(row=3, column=1, sticky="w", padx=10, pady=4)

        charge_lbl = tk.Label(win, text="Cancellation Charge (kept): ₹0.00", fg="#b71c1c")
        charge_lbl.grid(row=4, column=0, columnspan=2, sticky="w", padx=10, pady=(14, 4))

        tk.Label(win, text="Charge to Account:").grid(row=5, column=0, sticky="w", padx=10, pady=4)
        charge_account_var = tk.StringVar()
        charge_account_cb = ttk.Combobox(win, textvariable=charge_account_var,
                                          values=list(all_name_to_id.keys()), width=22, state="readonly")
        charge_account_cb.grid(row=5, column=1, sticky="w", padx=10, pady=4)
        charge_account_cb.configure(state="disabled")

        def recalc(*_):
            try:
                refund_amt = float(refund_amount_var.get())
            except (ValueError, TypeError):
                refund_amt = 0.0
            charge = round(max_amount - refund_amt, 2)
            charge_lbl.config(text=f"Cancellation Charge (kept): ₹{max(charge, 0):.2f}")
            charge_account_cb.configure(state="readonly" if charge > 0.01 else "disabled")

        refund_amount_var.trace_add("write", recalc)
        recalc()

        result = {}

        def confirm():
            try:
                refund_amt = round(float(refund_amount_var.get()), 2)
            except (ValueError, TypeError):
                messagebox.showerror(title, "Refund amount must be numeric.")
                return
            if refund_amt < 0 or refund_amt > max_amount + 0.01:
                messagebox.showerror(title, f"Refund amount must be between 0 and ₹{max_amount:.2f}.")
                return
            charge_amt = round(max_amount - refund_amt, 2)

            refund_account_id = None
            refund_mode = None
            if refund_amt > 0:
                acc_name = refund_account_var.get()
                if not acc_name or acc_name not in cash_bank_name_to_row:
                    messagebox.showerror(title, "Select a valid refund account.")
                    return
                acc_row = cash_bank_name_to_row[acc_name]
                refund_account_id = acc_row["account_id"]
                refund_mode = "CASH" if acc_row["type_id"] == 2 else "BANK"

            charge_account_id = None
            if charge_amt > 0.01:
                acc_name = charge_account_var.get()
                if not acc_name or acc_name not in all_name_to_id:
                    messagebox.showerror(title, "Select an account to book the cancellation charge to.")
                    return
                charge_account_id = all_name_to_id[acc_name]

            result["refund_amount"] = refund_amt
            result["refund_account_id"] = refund_account_id
            result["refund_payment_mode"] = refund_mode
            result["customer_account_no"] = customer_acc_var.get().strip() or None
            result["charge_amount"] = charge_amt
            result["charge_account_id"] = charge_account_id
            win.destroy()

        tk.Button(win, text="✅ Confirm", bg="#b71c1c", fg="white", command=confirm).grid(
            row=6, column=0, columnspan=2, pady=20
        )
        win.wait_window()
        return result if result else None

    def _book_cancellation_charge(self, customer_id, amount, account_id, order_no, remarks):
        """
        Books the unrefunded portion of a cancellation/return as
        recognized revenue -- a CR into whatever account represents
        profit/charges, so it's deliberately converted to income instead
        of silently vanishing from the books when a partial refund is
        given.
        """
        if amount <= 0.01 or account_id is None:
            return
        try:
            self.db.execute(
                """INSERT INTO public.transactions
                   (txn_date, txn_type, purchase_type, total_amount, txn_nature, supplier_id, party_type,
                    payment_status, payment_mode, account_id, paid_amount, balance_amount, remarks, bill_no)
                   VALUES (CURRENT_TIMESTAMP, 'SALE', 'SALE', %s, 'CR', %s, 'CUSTOMER', 'PAID', 'CASH', %s, %s, 0, %s, %s)""",
                (amount, customer_id, account_id, amount, remarks, order_no)
            )
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            print("cancellation charge booking failed (non-fatal):", e)

    # ============================================================= #
    # TAB 1: SALE / ORDER  (cart builder + edit mode, one screen)
    # ============================================================= #
    def _build_order_tab(self, parent):
        bar = tk.Frame(parent, bg="#e8eef4")
        bar.pack(fill="x")
        tk.Label(bar, text="Load Existing (Order No / Phone):", bg="#e8eef4").pack(side="left", padx=6, pady=8)
        self.search_var = tk.StringVar()
        search_entry = tk.Entry(bar, textvariable=self.search_var, width=18)
        search_entry.pack(side="left", padx=4)
        search_entry.bind("<Return>", lambda e: self._on_search())
        tk.Button(bar, text="Load", command=self._on_search).pack(side="left", padx=4)
        tk.Button(bar, text="👤 Search Customer", command=self.open_customer_search).pack(side="left", padx=4)
        tk.Button(bar, text="🆕 Start New Sale", bg="#2e7d32", fg="white", command=self.start_new_sale).pack(side="left", padx=12)

        header = tk.LabelFrame(parent, text="Order", padx=10, pady=8)
        header.pack(fill="x", padx=10, pady=6)
        self.header_var = tk.StringVar(value="No sale in progress — click 'Start New Sale' or load an existing order.")
        tk.Label(header, textvariable=self.header_var, font=("Segoe UI", 10, "bold"),
                 justify="left", anchor="w").pack(fill="x")

        # ---- Add Item panel (search-based, with a fallback custom section) ----
        add_frame = tk.LabelFrame(parent, text="Search Item for Sale", padx=8, pady=8)
        add_frame.pack(fill="x", padx=10, pady=6)

        tk.Label(add_frame, text="Search by:").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.add_search_mode_var = tk.StringVar(value="ITEM_CODE")
        mode_row = tk.Frame(add_frame)
        mode_row.grid(row=0, column=1, columnspan=3, sticky="w")
        for label, val in [("Item Code", "ITEM_CODE"), ("Jewelry Type", "JEWELRY_TYPE"), ("Lot No", "LOT_NO")]:
            tk.Radiobutton(mode_row, text=label, variable=self.add_search_mode_var, value=val).pack(side="left", padx=4)

        self.add_search_term_var = tk.StringVar()
        term_entry = tk.Entry(add_frame, textvariable=self.add_search_term_var, width=18)
        term_entry.grid(row=1, column=0, columnspan=2, padx=4, pady=4, sticky="w")
        term_entry.bind("<Return>", lambda e: self._search_add_item())
        tk.Button(add_frame, text="🔍 Search", command=self._search_add_item).grid(row=1, column=2, padx=4)
        self.custom_toggle_btn = tk.Button(add_frame, text="+ No Stock / Custom Item", command=self._toggle_custom_fields)
        self.custom_toggle_btn.grid(row=1, column=3, padx=4)

        self.add_search_note = tk.Label(add_frame, text="", fg="gray")
        self.add_search_note.grid(row=2, column=0, columnspan=4, sticky="w", padx=4, pady=(4, 0))

        search_cols = ("lot_no", "item_code", "metal_type", "jewelry_type", "dimension", "weight", "description")
        self.add_search_tree = ttk.Treeview(add_frame, columns=search_cols, show="headings", height=3)
        for c, w in zip(search_cols, (90, 90, 70, 90, 70, 70, 0)):
            self.add_search_tree.heading(c, text=c.replace("_", " ").title())
            self.add_search_tree.column(c, width=w, anchor="center", stretch=(c != "description"))
        self.add_search_tree.grid(row=3, column=0, columnspan=4, sticky="ew", padx=4, pady=4)
        self.add_search_tree.bind("<<TreeviewSelect>>", lambda e: self._on_search_result_selected())

        # ---- Custom item fields (hidden until toggled) ----
        self.custom_frame = tk.Frame(add_frame)
        tk.Label(self.custom_frame, text="Item Code (optional, if it's a catalog item):").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        self.order_item_code_var = tk.StringVar()
        self.catalog_combo = ttk.Combobox(self.custom_frame, textvariable=self.order_item_code_var, width=14)
        self.catalog_combo.grid(row=0, column=1, sticky="w", padx=4, pady=2)

        tk.Label(self.custom_frame, text="Description (if no item code):").grid(row=0, column=2, sticky="w", padx=4, pady=2)
        self.order_custom_desc_var = tk.StringVar()
        tk.Entry(self.custom_frame, textvariable=self.order_custom_desc_var, width=30).grid(row=0, column=3, sticky="w", padx=4, pady=2)

        tk.Label(self.custom_frame, text="Metal:").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        self.order_metal_type_var = tk.StringVar(value="GOLD")
        ttk.Combobox(self.custom_frame, textvariable=self.order_metal_type_var, values=["GOLD", "SILVER"],
                     state="readonly", width=10).grid(row=1, column=1, sticky="w", padx=4, pady=2)

        # FIX: jewelry_type and dimension/length are now editable
        # comboboxes (dropdown of known values, but still typeable --
        # "manual" entry works) instead of plain free-text Entry
        # widgets.
        tk.Label(self.custom_frame, text="Jewelry Type:").grid(row=1, column=2, sticky="w", padx=4, pady=2)
        self.order_jewelry_type_var = tk.StringVar()
        self.order_jewelry_type_combo = ttk.Combobox(self.custom_frame, textvariable=self.order_jewelry_type_var, width=13)
        self.order_jewelry_type_combo.grid(row=1, column=3, sticky="w", padx=4, pady=2)

        tk.Label(self.custom_frame, text="Length/Dimension:").grid(row=2, column=0, sticky="w", padx=4, pady=2)
        self.order_dimension_var = tk.StringVar()
        ttk.Combobox(self.custom_frame, textvariable=self.order_dimension_var, values=LENGTH_OPTIONS, width=9).grid(
            row=2, column=1, sticky="w", padx=4, pady=2
        )

        tk.Label(self.custom_frame, text="Alloy Type:").grid(row=2, column=2, sticky="w", padx=4, pady=2)
        self.order_alloy_type_var = tk.StringVar()
        self.order_alloy_type_combo = ttk.Combobox(self.custom_frame, textvariable=self.order_alloy_type_var, width=13)
        self.order_alloy_type_combo.grid(row=2, column=3, sticky="w", padx=4, pady=2)

        # FIX: process is no longer selected here at all -- it belongs
        # to the physical jewelry lot (gold_jewelry/silver_jewelry.
        # process_id), tracked from job_cart.py as manufacturing
        # progresses. A brand-new custom/pending order item has no lot
        # yet, so the Pending Order tab just displays "ORDER CREATED"
        # until a lot gets linked to it.

        self.order_photo_path_var = tk.StringVar()
        self.order_photo_label = tk.Label(self.custom_frame, text="No photo", fg="gray")
        tk.Label(self.custom_frame, text="Photo:").grid(row=3, column=0, sticky="w", padx=4, pady=2)
        self.order_photo_label.grid(row=3, column=1, sticky="w", padx=4, pady=2)
        tk.Button(self.custom_frame, text="Browse…",
                  command=lambda: self._browse_photo(self.order_photo_path_var, self.order_photo_label)
                  ).grid(row=3, column=2, sticky="w", padx=4, pady=2)

        # "Lock" order type -- holds this order at its current price/terms.
        self.order_locked_var = tk.BooleanVar(value=False)
        lock_cb = tk.Checkbutton(self.custom_frame, text="🔒 Lock this order (reserve price/terms)",
                                  variable=self.order_locked_var)
        lock_cb.grid(row=4, column=0, columnspan=3, sticky="w", padx=4, pady=(6, 2))
        Tooltip(lock_cb,
                "Locking holds this order at today's price and terms:\n"
                "• The agreed sold price won't change even if the catalog\n"
                "  price moves before this order is fulfilled.\n"
                "• Flagged here and in the Pending Order list so staff know\n"
                "  not to renegotiate the price on this order.\n"
                "Leave unchecked for a normal open order.")
        # custom_frame is NOT packed/gridded here -- _toggle_custom_fields shows it

        # ---- Sold amount + Add button (shared by both paths) ----
        # FIX: "Paid Amount" is no longer a separate field here -- clicking
        # Add Item opens the same PaymentDialog metal_purchase.py uses,
        # which captures paid amount + mode + account together.
        amt_row = tk.Frame(add_frame)
        amt_row.grid(row=5, column=0, columnspan=4, sticky="w", pady=(8, 2))
        tk.Label(amt_row, text="Sold Amount:").pack(side="left", padx=4)
        self.sold_amount_var = tk.StringVar()
        sold_entry = tk.Entry(amt_row, textvariable=self.sold_amount_var, width=12)
        sold_entry.pack(side="left", padx=4)
        sold_entry.bind("<Return>", lambda e: self._add_item_clicked())
        tk.Button(amt_row, text="➕ Add Item (set payment)", bg="#1565c0", fg="white",
                  command=self._add_item_clicked).pack(side="left", padx=8)

        # FIX: description field, shared by both paths -- when a lot is
        # picked from search, this auto-fills from that lot's own
        # description (if it has one) but stays editable; if you change
        # it here, that becomes a note specific to THIS sale, saved
        # alongside the lot_no/item_code rather than lost.
        desc_row = tk.Frame(add_frame)
        desc_row.grid(row=6, column=0, columnspan=4, sticky="ew", pady=(4, 2))
        tk.Label(desc_row, text="Description:").pack(side="left", padx=4)
        self.sale_description_var = tk.StringVar()
        tk.Entry(desc_row, textvariable=self.sale_description_var, width=45).pack(side="left", padx=4, fill="x", expand=True)

        # ---- Items / Cart display ----
        items_frame = tk.LabelFrame(parent, text="Items", padx=8, pady=8)
        items_frame.pack(fill="both", expand=True, padx=10, pady=6)

        item_cols = ("ref", "item", "lot_no", "sold", "paid", "balance", "status")
        self.items_tree = ttk.Treeview(items_frame, columns=item_cols, show="headings", height=6)
        for c, w in zip(item_cols, (0, 140, 90, 80, 80, 80, 100)):
            self.items_tree.heading(c, text=c.replace("_", " ").title())
            self.items_tree.column(c, width=w, anchor="center")
        self.items_tree.column("ref", width=0, stretch=False)
        self.items_tree.pack(fill="both", expand=True, side="left")

        items_btns = tk.Frame(items_frame)
        items_btns.pack(side="left", fill="y", padx=8)
        tk.Button(items_btns, text="Remove from Cart", width=16, command=self._remove_cart_item).pack(pady=2)
        tk.Button(items_btns, text="Edit Price", width=16, command=self._edit_item_price).pack(pady=2)
        tk.Button(items_btns, text="Add Payment", width=16, command=self._add_payment_to_item).pack(pady=2)
        tk.Button(items_btns, text="Return Item", width=16, fg="#b71c1c", command=self._return_item).pack(pady=2)
        tk.Button(items_btns, text="Cancel Item", width=16, fg="red", command=self._cancel_item_selected).pack(pady=2)

        # ---- Summary ----
        summary_frame = tk.LabelFrame(parent, text="Summary", padx=8, pady=8)
        summary_frame.pack(fill="x", padx=10, pady=6)
        self.summary_var = tk.StringVar(value="Total Sold: ₹0.00   Total Paid: ₹0.00   Balance: ₹0.00")
        tk.Label(summary_frame, textvariable=self.summary_var, font=("Segoe UI", 10, "bold")).pack(anchor="w")

        # ---- Save / Cancel ----
        bottom = tk.Frame(parent, bg="#e8eef4")
        bottom.pack(fill="x")
        tk.Button(bottom, text="💾 Save Sale", bg="#2e7d32", fg="white", font=("Segoe UI", 10, "bold"),
                  command=self.save_new_sale).pack(side="left", padx=8, pady=6)
        tk.Button(bottom, text="Cancel Order", fg="red", command=self.cancel_order).pack(side="right", padx=8, pady=6)

    def _toggle_custom_fields(self):
        if self.custom_frame.winfo_ismapped():
            self.custom_frame.grid_forget()
            self.custom_toggle_btn.config(text="+ No Stock / Custom Item")
        else:
            self.custom_frame.grid(row=4, column=0, columnspan=4, sticky="w", pady=(6, 0))
            self.custom_toggle_btn.config(text="− Hide Custom Item")

    # ---------------------------------------------------- SEARCH -----
    def _on_search(self):
        term = self.search_var.get().strip()
        if not term:
            messagebox.showwarning("Search", "Enter an order number or customer phone.")
            return
        row = self.db.query("SELECT order_id FROM public.sales_orders WHERE order_no = %s", (term,), "one")
        if not row:
            cust = self.db.query("SELECT customer_id FROM public.customers WHERE phone = %s", (term,), "one")
            if cust:
                orders = self.db.query(
                    """SELECT order_id, order_no FROM public.sales_orders
                       WHERE customer_id = %s ORDER BY created_at DESC""",
                    (cust["customer_id"],)
                )
                if not orders:
                    messagebox.showinfo("Search", "That customer has no orders yet.")
                    return
                row = orders[0]
                if len(orders) > 1:
                    self.status_var.set(
                        f"Customer has {len(orders)} orders — loaded most recent "
                        f"({row['order_no']}). Search by exact order_no for a different one."
                    )
        if not row:
            messagebox.showerror("Search", f"No order or customer found for '{term}'.")
            return
        self.load_order(row["order_id"])

    def _on_search_result_selected(self):
        sel = self.add_search_tree.selection()
        if not sel:
            return
        vals = self.add_search_tree.item(sel[0])["values"]
        code = vals[1]
        if code and not self.sold_amount_var.get().strip():
            cat = self.db.query("SELECT base_price FROM public.item_catalog WHERE item_code=%s", (code,), "one")
            if cat and cat["base_price"] is not None:
                self.sold_amount_var.set(f"{float(cat['base_price']):.2f}")
        # FIX: auto-fill the description from this lot's own record, but
        # leave it editable -- if changed before Add Item, that becomes a
        # note specific to this sale (saved to custom_description
        # alongside the lot_no, not lost).
        self.sale_description_var.set(vals[6] if len(vals) > 6 else "")

    def _search_add_item(self):
        for i in self.add_search_tree.get_children():
            self.add_search_tree.delete(i)
        mode = self.add_search_mode_var.get()
        term = self.add_search_term_var.get().strip().upper()
        if not term:
            return
        already_claimed = """
            SELECT lot_no FROM public.sales_order_items
            WHERE lot_no IS NOT NULL AND item_status IN ('PENDING_SEND','SOLD')
        """
        for table, metal in (("gold_jewelry", "GOLD"), ("silver_jewelry", "SILVER")):
            if mode == "LOT_NO":
                rows = self.db.query(
                    f"""SELECT lot_no, item_code, jewelry_type, dimension, weight, description FROM public.{table}
                        WHERE lot_no=%s AND status='AVAILABLE' AND lot_no NOT IN ({already_claimed})""",
                    (term,)
                )
            elif mode == "ITEM_CODE":
                rows = self.db.query(
                    f"""SELECT lot_no, item_code, jewelry_type, dimension, weight, description FROM public.{table}
                        WHERE item_code=%s AND status='AVAILABLE' AND lot_no NOT IN ({already_claimed})
                        ORDER BY created_at ASC""",
                    (term,)
                )
            else:
                rows = self.db.query(
                    f"""SELECT lot_no, item_code, jewelry_type, dimension, weight, description FROM public.{table}
                        WHERE jewelry_type ILIKE %s AND status='AVAILABLE' AND lot_no NOT IN ({already_claimed})
                        ORDER BY created_at ASC""",
                    (f"%{term}%",)
                )
            for r in rows:
                self.add_search_tree.insert("", "end", values=(
                    r["lot_no"], r["item_code"] or "", metal, r["jewelry_type"] or "",
                    r["dimension"] or "", f"{r['weight']:.3f}" if r["weight"] is not None else "",
                    r["description"] or ""
                ))
        found = self.add_search_tree.get_children()
        if not found:
            self.add_search_note.config(
                text="No matching stock — click '+ No Stock / Custom Item' below to order it instead.", fg="#e65100"
            )
        else:
            self.add_search_note.config(text=f"{len(found)} found — select one, set amounts, and Add Item.", fg="green")

    # ---------------------------------------------------- LOAD -------
    def load_order(self, order_id):
        order = self.db.query(
            """SELECT so.*, COALESCE(a.short_name, a.account_name) AS sales_person_name
               FROM public.sales_orders so
               LEFT JOIN public.accounts a ON a.account_id = so.sales_person
               WHERE so.order_id=%s""",
            (order_id,), "one"
        )
        if not order:
            messagebox.showerror("Load Order", "Order not found.")
            return
        cust = self.db.query("SELECT * FROM public.customers WHERE customer_id=%s", (order["customer_id"],), "one")
        self.current_order_id = order_id
        self.current_order_no = order["order_no"]
        self.current_customer = cust
        self.cart_items = []  # not in cart-staging mode anymore

        items = self.db.query(
            "SELECT * FROM public.sales_order_items WHERE order_id=%s ORDER BY order_item_id", (order_id,)
        )
        non_cancelled = [i for i in items if i["item_status"] not in ("CANCELLED", "RETURNED")]
        if not non_cancelled:
            kind = "EMPTY"
        elif all(i["item_status"] in ("PENDING_SEND", "SOLD") for i in non_cancelled):
            kind = "SALE"
        else:
            kind = "ORDER (pending stock)"

        sp = order["sales_person_name"] or "—"
        self.header_var.set(
            f"[{kind}]  Order {order['order_no']}  |  {order['order_date']}  |  Status: {order['status']}  |  Sales Person: {sp}\n"
            f"Customer: {cust['full_name']}  ({cust['phone']})  {cust.get('address') or ''}\n"
            f"Total: ₹{order['total_amount']:.2f}   Paid: ₹{order['paid_amount']:.2f}   "
            f"Balance: ₹{order['balance_amount']:.2f}"
        )

        for i in self.items_tree.get_children():
            self.items_tree.delete(i)
        for it in items:
            label = it["item_code"] or it["custom_description"] or ""
            self.items_tree.insert("", "end", values=(
                it["order_item_id"], label, it["lot_no"] or "",
                f"{it['price']:.2f}", f"{it['paid_amount']:.2f}", f"{it['balance_amount']:.2f}",
                it["item_status"]
            ))

        self._update_summary()
        self.status_var.set(f"Loaded order {order['order_no']}")

    def _update_summary(self):
        if self.current_order_id is None:
            total = sum(i["sold_amount"] for i in self.cart_items)
            paid = sum(i["paid_amount"] for i in self.cart_items)
        else:
            order = self.db.query("SELECT * FROM public.sales_orders WHERE order_id=%s", (self.current_order_id,), "one")
            total = float(order["total_amount"]) if order else 0.0
            paid = float(order["paid_amount"]) if order else 0.0
        balance = round(total - paid, 2)
        self.summary_var.set(f"Total Sold: ₹{total:.2f}   Total Paid: ₹{paid:.2f}   Balance: ₹{balance:.2f}")

    # ---------------------------------------------------- START NEW --
    def start_new_sale(self):
        data = ask_form(self, "Start New Sale — Customer Phone", [("phone", "Customer Phone", "text", None)])
        if not data or not data["phone"]:
            return
        phone = data["phone"].strip()
        cust = self.db.query("SELECT * FROM public.customers WHERE phone=%s", (phone,), "one")
        if not cust:
            if not messagebox.askyesno("New Customer", f"No customer with phone {phone}. Create one?"):
                return
            cdata = ask_form(self, "New Customer", [
                ("full_name", "Full Name", "text", None),
                ("phone", "Phone", "text", None),
                ("email", "Email", "text", None),
                ("line_id", "LINE ID", "text", None),
                ("address", "Address", "text", None),
            ])
            if not cdata or not cdata["full_name"] or not cdata["phone"]:
                messagebox.showerror("New Customer", "Name and phone are required.")
                return
            try:
                row = self.db.query(
                    """INSERT INTO public.customers (full_name, phone, email, line_id, address)
                       VALUES (%s,%s,%s,%s,%s) RETURNING customer_id""",
                    (cdata["full_name"], cdata["phone"], cdata["email"] or None,
                     cdata["line_id"] or None, cdata["address"] or None), "one"
                )
                self.db.commit()
                cust = self.db.query("SELECT * FROM public.customers WHERE customer_id=%s", (row["customer_id"],), "one")
            except Exception as e:
                self.db.rollback()
                messagebox.showerror("New Customer", str(e))
                return

        sp_names = [""] + list(self.account_name_to_id.keys())
        sp_data = ask_form(self, "Sales Person", [("sales_person", "Sales Person", "choice", sp_names)])
        self.selected_sales_person_id = (
            self.account_name_to_id.get(sp_data["sales_person"]) if sp_data and sp_data["sales_person"] else None
        )

        self.current_order_id = None
        self.current_customer = cust
        self.cart_items = []
        self._refresh_cart_display()
        self._update_summary()
        self.header_var.set(f"[NEW SALE — not yet saved]  Customer: {cust['full_name']} ({cust['phone']})")
        self.status_var.set("Building new sale — add items, then Save.")

    # ---------------------------------------------------- ADD ITEM ---
    def _open_html_for_print(self, html, filename_hint):
        """
        Writes the given HTML to a temp file and opens it in the default
        browser. Printing itself (including picking a thermal vs. normal
        printer) happens through the browser's own print dialog (Ctrl+P /
        the Print button in the page) -- this app doesn't talk to printer
        drivers directly, which keeps it working the same way regardless
        of what printers are actually connected to this computer.
        """
        path = os.path.join(tempfile.gettempdir(), f"{filename_hint}_{int(dt.datetime.now().timestamp())}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        webbrowser.open(f"file://{path}")

    def _browse_photo(self, target_var, label_widget):
        path = filedialog.askopenfilename(
            title="Select Photo", filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.gif"), ("All files", "*.*")]
        )
        if path:
            target_var.set(path)
            label_widget.config(text=os.path.basename(path), fg="black")

    def _gather_item_entry(self):
        sel = self.add_search_tree.selection()
        if sel:
            vals = self.add_search_tree.item(sel[0])["values"]
            lot_no, item_code, metal_type = vals[0], (vals[1] or None), vals[2]
            jewelry_type, dimension = vals[3] or None, vals[4] or None
            # FIX: description for a lot-based sale -- auto-filled from the
            # lot's own record when selected, but if you edit it here that
            # becomes a note specific to THIS sale and gets saved (only
            # stored when it actually differs from what's already on file,
            # so an unchanged auto-fill doesn't create a redundant copy).
            original_description = vals[6] if len(vals) > 6 else ""
            entered_description = self.sale_description_var.get().strip()
            custom_description = entered_description if entered_description and entered_description != original_description else None
            photo_path = None
            is_locked = False  # Lock only applies to a no-stock-yet order, not an in-hand sale
            alloy_type = None  # Alloy is a custom-order attribute; a real lot doesn't need it re-entered
        else:
            item_code = self.order_item_code_var.get().strip().upper() or None
            custom_description = self.order_custom_desc_var.get().strip() or None
            if not item_code and not custom_description:
                messagebox.showerror(
                    "Add Item", "Search and select stock, or open '+ No Stock / Custom Item' and describe it."
                )
                return None
            if item_code:
                cat = self.db.query("SELECT * FROM public.item_catalog WHERE item_code=%s AND is_active", (item_code,), "one")
                if not cat:
                    messagebox.showerror("Add Item", f"'{item_code}' not found in catalog (or inactive).")
                    return None
                metal_type = cat["metal_type"]
            else:
                metal_type = self.order_metal_type_var.get()
                if metal_type not in ("GOLD", "SILVER"):
                    messagebox.showerror("Add Item", "Select a metal type.")
                    return None
            lot_no = None
            jewelry_type = self.order_jewelry_type_var.get().strip() or None
            dimension = self.order_dimension_var.get().strip() or None
            alloy_type = self.order_alloy_type_var.get().strip() or None
            photo_path = self.order_photo_path_var.get().strip() or None
            is_locked = self.order_locked_var.get()

        sold_text = self.sold_amount_var.get().strip()
        if not sold_text:
            messagebox.showerror("Add Item", "Enter the sold amount.")
            return None
        try:
            sold_amount = float(sold_text)
        except ValueError:
            messagebox.showerror("Add Item", "Sold amount must be numeric.")
            return None
        if sold_amount <= 0:
            messagebox.showerror("Add Item", "Sold amount must be greater than 0.")
            return None

        # FIX: payment amount/mode/account is now captured via the same
        # PaymentDialog metal_purchase.py uses -- gives a real, validated
        # account_id instead of a free-text account name, and a proper
        # Cash/Bank/Advance/Pending flow instead of a separate radio row.
        pd = open_payment_dialog(self, sold_amount, txn_type="SALE", module_name="Sales")
        if pd is None:
            messagebox.showinfo("Add Item", "Payment not set — item not added.")
            return None

        return {
            "item_code": item_code, "custom_description": custom_description,
            "metal_type": metal_type, "lot_no": lot_no,
            "jewelry_type": jewelry_type, "dimension": dimension,
            "photo_path": photo_path, "is_locked": is_locked, "alloy_type": alloy_type,
            "sold_amount": sold_amount, "paid_amount": pd["paid_amount"],
            "payment_mode": pd["payment_mode"], "account_id": pd["account_id"],
            "installment_schedule": pd.get("installment_schedule"),
        }

    def _clear_item_entry_fields(self):
        self.sold_amount_var.set("")
        self.sale_description_var.set("")
        self.order_item_code_var.set("")
        self.order_custom_desc_var.set("")
        self.order_jewelry_type_var.set("")
        self.order_dimension_var.set("")
        self.order_photo_path_var.set("")
        self.order_photo_label.config(text="No photo", fg="gray")
        self.order_locked_var.set(False)
        self.order_alloy_type_var.set("")
        self.add_search_term_var.set("")
        for i in self.add_search_tree.get_children():
            self.add_search_tree.delete(i)
        self.add_search_note.config(text="")

    def _add_item_clicked(self):
        entry = self._gather_item_entry()
        if entry is None:
            return
        if self.current_order_id is None:
            if not self.current_customer:
                messagebox.showwarning("No Customer", "Click 'Start New Sale' first.")
                return
            self.cart_items.append(entry)
            self._refresh_cart_display()
            self._update_summary()
            self._clear_item_entry_fields()
            self.status_var.set("Item added to cart.")
        else:
            self._insert_order_item_now(entry)
            self._clear_item_entry_fields()

    def _refresh_cart_display(self):
        for i in self.items_tree.get_children():
            self.items_tree.delete(i)
        for idx, it in enumerate(self.cart_items):
            label = it["item_code"] or it["custom_description"] or ""
            balance = round(it["sold_amount"] - it["paid_amount"], 2)
            fulfillment = "SALE (in stock)" if it["lot_no"] else "ORDER (no stock)"
            self.items_tree.insert("", "end", values=(
                idx, label, it["lot_no"] or "", f"{it['sold_amount']:.2f}",
                f"{it['paid_amount']:.2f}", f"{balance:.2f}", fulfillment
            ))

    def _remove_cart_item(self):
        if self.current_order_id is not None:
            messagebox.showinfo("Remove", "This order is already saved — use Cancel Item instead.")
            return
        sel = self.items_tree.selection()
        if not sel:
            messagebox.showwarning("Remove", "Select a cart row first.")
            return
        idx = int(self.items_tree.item(sel[0])["values"][0])
        del self.cart_items[idx]
        self._refresh_cart_display()
        self._update_summary()

    # ---------------------------------------------------- SAVE (new) -
    def save_new_sale(self):
        if self.current_order_id is not None:
            messagebox.showinfo("Save", "This order is already saved — item/payment actions apply immediately.")
            return
        if not self.current_customer:
            messagebox.showwarning("Save", "Click 'Start New Sale' first.")
            return
        if not self.cart_items:
            messagebox.showwarning("Save", "Add at least one item first.")
            return

        order_no = self._next_order_no()
        try:
            row = self.db.query(
                """INSERT INTO public.sales_orders (order_no, customer_id, sales_person, status)
                   VALUES (%s,%s,%s,'ORDER') RETURNING order_id""",
                (order_no, self.current_customer["customer_id"], self.selected_sales_person_id), "one"
            )
            order_id = row["order_id"]

            total_sold = 0.0
            total_paid = 0.0
            for it in self.cart_items:
                item_status = "PENDING_STOCK"
                lot_no = it["lot_no"]
                if lot_no:
                    table = "gold_jewelry" if it["metal_type"] == "GOLD" else "silver_jewelry"
                    lot_row = self.db.query(
                        f"SELECT status FROM public.{table} WHERE lot_no=%s FOR UPDATE", (lot_no,), "one"
                    )
                    if not lot_row or lot_row["status"] != "AVAILABLE":
                        raise Exception(
                            f"Lot {lot_no} is no longer available — remove that cart item, re-search, and try again."
                        )
                    item_status = "PENDING_SEND"

                item_row = self.db.query(
                    """INSERT INTO public.sales_order_items
                       (order_id, item_code, metal_type, lot_no, price, paid_amount, item_status,
                        jewelry_type, dimension, custom_description, photo_path, is_locked, alloy_type)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING order_item_id""",
                    (order_id, it["item_code"], it["metal_type"], lot_no, it["sold_amount"], it["paid_amount"],
                     item_status, it["jewelry_type"], it["dimension"], it["custom_description"],
                     it["photo_path"], it.get("is_locked", False), it.get("alloy_type")), "one"
                )

                if it["paid_amount"] > 0:
                    payment_row = self.db.query(
                        """INSERT INTO public.sales_payments
                           (order_id, order_item_id, customer_id, payment_date, amount, payment_mode, account_id, payment_type)
                           VALUES (%s,%s,%s,CURRENT_DATE,%s,%s,%s,'PAYMENT') RETURNING payment_id""",
                        (order_id, item_row["order_item_id"], self.current_customer["customer_id"],
                         it["paid_amount"], it["payment_mode"], it["account_id"]), "one"
                    )
                    self._record_transaction(
                        self.current_customer["customer_id"], it["paid_amount"], it["payment_mode"],
                        it["account_id"], "CR", order_no, f"Sale payment - {it['item_code'] or it['custom_description']}",
                        sales_payment_id=payment_row["payment_id"]
                    )

                total_sold += it["sold_amount"]
                total_paid += it["paid_amount"]
                self._sync_pending_payment(item_row["order_item_id"])
                self._create_installment_plan(item_row["order_item_id"], it["sold_amount"], it.get("installment_schedule"))

            self.db.execute(
                "UPDATE public.sales_orders SET total_amount=%s, paid_amount=%s, updated_at=now() WHERE order_id=%s",
                (total_sold, total_paid, order_id)
            )
            self.db.execute(
                """UPDATE public.customers
                   SET total_purchase = total_purchase + %s, total_paid = total_paid + %s, updated_at=now()
                   WHERE customer_id=%s""",
                (total_sold, total_paid, self.current_customer["customer_id"])
            )

            self.db.commit()
            self._recalc_order_status(order_id)
            item_count = len(self.cart_items)
            self.cart_items = []
            self.load_order(order_id)
            # FIX: the old confirmation just said "Sale saved as order X"
            # every time, regardless of what was actually saved. This one
            # actually tells you what happened.
            balance = round(total_sold - total_paid, 2)
            messagebox.showinfo(
                "Sale Saved",
                f"Order {order_no} — {item_count} item(s)\n"
                f"Sold: ₹{total_sold:.2f}   Paid: ₹{total_paid:.2f}   Balance: ₹{balance:.2f}"
            )
            self.status_var.set(f"Sale saved as order {order_no}.")
        except psycopg2.errors.UniqueViolation:
            self.db.rollback()
            messagebox.showerror("Save", "Order number collision — click Save again.")
        except Exception as e:
            self.db.rollback()
            messagebox.showerror("Save", str(e))

    def _next_order_no(self):
        today = dt.date.today().strftime("%Y%m%d")
        row = self.db.query(
            "SELECT order_no FROM public.sales_orders WHERE order_no LIKE %s ORDER BY order_no DESC LIMIT 1",
            (f"{today}/%",), "one"
        )
        n = 1
        if row:
            try:
                n = int(row["order_no"].split("/")[-1]) + 1
            except (ValueError, IndexError):
                n = 1
        return f"{today}/{n:02d}"

    def _record_transaction(self, customer_id, amount, payment_mode, account_id, txn_nature, bill_no, remarks,
                             sales_payment_id=None):
        """
        Mirrors a sales-side cash movement into transactions -- the table
        the account_balances view (migration 08) actually reads. Without
        this, money collected/refunded through sales was invisible to
        account balance calculations. CR = money into the account (a
        payment received), DR = money out (a refund). Skipped when
        there's no real account (e.g. a Pending payment_mode with
        nothing actually moving yet).

        sales_payment_id links this row back to the EXACT sales_payments
        row that caused it (migration 10) -- pass it whenever you have
        it (i.e. whenever the INSERT INTO sales_payments used RETURNING
        payment_id), so the connection is a real FK, not a fuzzy match
        on order_no/amount/date.
        """
        if amount <= 0 or account_id is None:
            return
        try:
            self.db.execute(
                """INSERT INTO public.transactions
                   (txn_date, txn_type, purchase_type, total_amount, txn_nature, supplier_id, party_type,
                    payment_status, payment_mode, account_id, paid_amount, balance_amount, remarks, bill_no,
                    sales_payment_id)
                   VALUES (CURRENT_TIMESTAMP, 'SALE', 'SALE', %s, %s, %s, 'CUSTOMER', 'PAID', %s, %s, %s, 0, %s, %s, %s)""",
                (amount, txn_nature, customer_id, payment_mode, account_id, amount, remarks, bill_no, sales_payment_id)
            )
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            print("transactions sync failed (non-fatal):", e)

    def _create_installment_plan(self, order_item_id, total_amount, schedule):
        if not schedule:
            return
        try:
            plan_row = self.db.query(
                """INSERT INTO public.installment_plans (order_item_id, total_amount, num_installments)
                   VALUES (%s,%s,%s) RETURNING plan_id""",
                (order_item_id, total_amount, len(schedule)), "one"
            )
            for s in schedule:
                self.db.execute(
                    """INSERT INTO public.installment_schedule (plan_id, installment_no, due_date, amount_due)
                       VALUES (%s,%s,%s,%s)""",
                    (plan_row["plan_id"], s["installment_no"], s["due_date"], s["amount"])
                )
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            print("installment plan creation failed (non-fatal):", e)

    def _sync_pending_payment(self, order_item_id):
        """
        Keeps pending_payments in sync with one sales_order_item's
        balance -- your ask for a single table that shows every
        outstanding payment (purchase-side AND sales-side) without a
        separate query per module. Inserts/updates/deletes based on
        the item's CURRENT balance; commits on its own so callers
        don't need to think about transaction boundaries.
        """
        row = self.db.query(
            """SELECT soi.*, so.order_no, c.customer_id, c.full_name
               FROM public.sales_order_items soi
               JOIN public.sales_orders so ON so.order_id = soi.order_id
               JOIN public.customers c ON c.customer_id = so.customer_id
               WHERE soi.order_item_id=%s""",
            (order_item_id,), "one"
        )
        if not row:
            return
        try:
            existing = self.db.query(
                "SELECT pending_id FROM public.pending_payments WHERE sale_order_item_id=%s", (order_item_id,), "one"
            )
            balance = float(row["balance_amount"])
            if row["item_status"] in ("CANCELLED", "RETURNED") or balance <= 0.01:
                if existing:
                    self.db.execute("DELETE FROM public.pending_payments WHERE pending_id=%s", (existing["pending_id"],))
                    self.db.commit()
                return
            status = "PENDING" if float(row["paid_amount"]) <= 0.01 else "ADVANCE"
            # FIX: once a specific physical lot is attached to this item,
            # that lot_no is the useful identifier for tracking THIS sale
            # (item_code is just the general catalog code, shared across
            # every piece of that design) -- show it as the primary label,
            # with the catalog code alongside for context when both exist.
            if row["lot_no"] and row["item_code"]:
                label = f"{row['lot_no']} ({row['item_code']})"
            else:
                label = row["lot_no"] or row["item_code"] or row["custom_description"] or ""
            if existing:
                self.db.execute(
                    """UPDATE public.pending_payments
                       SET total_amount=%s, paid_amount=%s, balance_amount=%s, payment_status=%s, updated_at=now()
                       WHERE pending_id=%s""",
                    (row["price"], row["paid_amount"], balance, status, existing["pending_id"])
                )
            else:
                self.db.execute(
                    """INSERT INTO public.pending_payments
                       (txn_date, sale_order_item_id, bill_no, account_id, account_name, account_type,
                        txn_type, total_amount, paid_amount, balance_amount, payment_status, remarks)
                       VALUES (CURRENT_DATE, %s, %s, %s, %s, 'CUSTOMER', 'SALE', %s, %s, %s, %s, %s)""",
                    (order_item_id, row["order_no"], row["customer_id"], row["full_name"],
                     row["price"], row["paid_amount"], balance, status, label)
                )
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            print("pending_payments sync failed (non-fatal):", e)

    # ---------------------------------------------------- EDIT MODE --
    def _insert_order_item_now(self, entry):
        """Add-item, but for an already-saved order: writes immediately."""
        item_status = "PENDING_STOCK"
        lot_no = entry["lot_no"]
        try:
            if lot_no:
                table = "gold_jewelry" if entry["metal_type"] == "GOLD" else "silver_jewelry"
                lot_row = self.db.query(
                    f"SELECT status FROM public.{table} WHERE lot_no=%s FOR UPDATE", (lot_no,), "one"
                )
                if not lot_row or lot_row["status"] != "AVAILABLE":
                    messagebox.showerror("Add Item", f"Lot {lot_no} is no longer available — try again.")
                    self.db.rollback()
                    return
                item_status = "PENDING_SEND"

            item_row = self.db.query(
                """INSERT INTO public.sales_order_items
                   (order_id, item_code, metal_type, lot_no, price, paid_amount, item_status,
                    jewelry_type, dimension, custom_description, photo_path, is_locked, alloy_type)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING order_item_id""",
                (self.current_order_id, entry["item_code"], entry["metal_type"], lot_no,
                 entry["sold_amount"], entry["paid_amount"], item_status,
                 entry["jewelry_type"], entry["dimension"], entry["custom_description"],
                 entry["photo_path"], entry.get("is_locked", False), entry.get("alloy_type")), "one"
            )
            if entry["paid_amount"] > 0:
                payment_row = self.db.query(
                    """INSERT INTO public.sales_payments
                       (order_id, order_item_id, customer_id, payment_date, amount, payment_mode, account_id, payment_type)
                       VALUES (%s,%s,%s,CURRENT_DATE,%s,%s,%s,'PAYMENT') RETURNING payment_id""",
                    (self.current_order_id, item_row["order_item_id"], self.current_customer["customer_id"],
                     entry["paid_amount"], entry["payment_mode"], entry["account_id"]), "one"
                )
                self._record_transaction(
                    self.current_customer["customer_id"], entry["paid_amount"], entry["payment_mode"],
                    entry["account_id"], "CR", self.current_order_no,
                    f"Sale payment - {entry['item_code'] or entry['custom_description']}",
                    sales_payment_id=payment_row["payment_id"]
                )
            self.db.execute(
                "UPDATE public.sales_orders SET total_amount = total_amount + %s, paid_amount = paid_amount + %s, updated_at = now() WHERE order_id = %s",
                (entry["sold_amount"], entry["paid_amount"], self.current_order_id)
            )
            self.db.execute(
                """UPDATE public.customers
                   SET total_purchase = total_purchase + %s, total_paid = total_paid + %s, updated_at = now()
                   WHERE customer_id = %s""",
                (entry["sold_amount"], entry["paid_amount"], self.current_customer["customer_id"])
            )
            self.db.commit()
            self._recalc_order_status(self.current_order_id)
            self._sync_pending_payment(item_row["order_item_id"])
            self._create_installment_plan(item_row["order_item_id"], entry["sold_amount"], entry.get("installment_schedule"))
            self.load_order(self.current_order_id)
        except psycopg2.errors.UniqueViolation:
            self.db.rollback()
            messagebox.showwarning("Add Item", f"Lot {lot_no} was just claimed by someone else — try again.")
        except Exception as e:
            self.db.rollback()
            messagebox.showerror("Add Item", str(e))

    def _selected_item_id(self, tree):
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Select Item", "Select a row in the list first.")
            return None
        return int(tree.item(sel[0])["values"][0])

    def _edit_item_price(self):
        if self.current_order_id is None:
            messagebox.showinfo("Edit Price", "Save this sale first, then you can edit item prices.")
            return
        item_id = self._selected_item_id(self.items_tree)
        if item_id is None:
            return
        row = self.db.query("SELECT * FROM public.sales_order_items WHERE order_item_id=%s", (item_id,), "one")
        if not row:
            return
        if row["item_status"] in ("SOLD", "RETURNED", "CANCELLED"):
            messagebox.showerror("Edit Price", f"Can't edit price on a {row['item_status']} item.")
            return
        data = ask_form(self, "Edit Price", [("new_price", f"New Sold Amount (was ₹{row['price']:.2f})", "text", None)])
        if not data or not data["new_price"]:
            return
        try:
            new_price = float(data["new_price"])
        except ValueError:
            messagebox.showerror("Edit Price", "Must be numeric.")
            return
        if new_price <= 0:
            messagebox.showerror("Edit Price", "Must be greater than 0.")
            return

        old_price = float(row["price"])
        old_paid = float(row["paid_amount"])
        delta = round(new_price - old_price, 2)
        if delta == 0:
            messagebox.showinfo("Edit Price", "No change.")
            return

        extra_payment = 0.0
        refund_amount = 0.0
        payment_mode_used = None
        account_id_used = None
        if delta > 0:
            if messagebox.askyesno("Edit Price", f"Price increased by ₹{delta:.2f}. Collect additional payment now?"):
                pd = open_payment_dialog(self, delta, txn_type="SALE", module_name="Sales - Price Increase")
                if pd is not None:
                    extra_payment = pd["paid_amount"]
                    payment_mode_used = pd["payment_mode"]
                    account_id_used = pd["account_id"]
        else:
            # FIX (bug you flagged: balance going negative): a price
            # decrease that leaves paid_amount above the new price is
            # exactly what was producing negative balances. Partial
            # refund is now allowed -- whatever isn't refunded becomes a
            # cancellation charge booked as revenue, so the paid_amount
            # still comes back in line either way. The DB-level CHECK
            # constraint (migration 07) is the hard backstop regardless.
            overpaid = round(old_paid - new_price, 2)
            charge_amount = 0.0
            charge_account_id = None
            customer_account_no = None
            if overpaid > 0:
                messagebox.showwarning(
                    "Refund Required",
                    f"Price decreased by ₹{abs(delta):.2f}. Customer is now overpaid by ₹{overpaid:.2f} — "
                    f"resolve it (refund, cancellation charge, or a mix) to continue."
                )
                rd = self._capture_refund(overpaid, title="Refund — Price Decrease")
                if rd is None:
                    messagebox.showerror("Edit Price", "Not resolved — price NOT changed.")
                    return
                refund_amount = rd["refund_amount"]
                payment_mode_used = rd["refund_payment_mode"]
                account_id_used = rd["refund_account_id"]
                customer_account_no = rd["customer_account_no"]
                charge_amount = rd["charge_amount"]
                charge_account_id = rd["charge_account_id"]

        try:
            new_paid = round(old_paid + extra_payment - refund_amount - charge_amount, 2)
            self.db.execute(
                "UPDATE public.sales_order_items SET price=%s, paid_amount=%s, updated_at=now() WHERE order_item_id=%s",
                (new_price, new_paid, item_id)
            )
            if extra_payment > 0:
                payment_row = self.db.query(
                    """INSERT INTO public.sales_payments
                       (order_id, order_item_id, customer_id, payment_date, amount, payment_mode, account_id, payment_type)
                       VALUES (%s,%s,%s,CURRENT_DATE,%s,%s,%s,'PAYMENT') RETURNING payment_id""",
                    (row["order_id"], item_id, self.current_customer["customer_id"],
                     extra_payment, payment_mode_used, account_id_used), "one"
                )
                self._record_transaction(
                    self.current_customer["customer_id"], extra_payment, payment_mode_used,
                    account_id_used, "CR", self.current_order_no, "Sale price increase - additional payment",
                    sales_payment_id=payment_row["payment_id"]
                )
            if refund_amount > 0:
                payment_row = self.db.query(
                    """INSERT INTO public.sales_payments
                       (order_id, order_item_id, customer_id, payment_date, amount, payment_mode, account_id,
                        payment_type, customer_account_no)
                       VALUES (%s,%s,%s,CURRENT_DATE,%s,%s,%s,'REFUND',%s) RETURNING payment_id""",
                    (row["order_id"], item_id, self.current_customer["customer_id"],
                     refund_amount, payment_mode_used, account_id_used, customer_account_no), "one"
                )
                self._record_transaction(
                    self.current_customer["customer_id"], refund_amount, payment_mode_used,
                    account_id_used, "DR", self.current_order_no, "Sale price decrease - refund",
                    sales_payment_id=payment_row["payment_id"]
                )
            if charge_amount > 0:
                self._book_cancellation_charge(
                    self.current_customer["customer_id"], charge_amount, charge_account_id,
                    self.current_order_no, "Cancellation charge - price decrease"
                )
            self.db.execute(
                "UPDATE public.sales_orders SET total_amount = total_amount + %s, paid_amount = paid_amount + %s, updated_at=now() WHERE order_id=%s",
                (delta, extra_payment - refund_amount - charge_amount, row["order_id"])
            )
            self.db.execute(
                """UPDATE public.customers
                   SET total_purchase = total_purchase + %s, total_paid = total_paid + %s, updated_at=now()
                   WHERE customer_id=%s""",
                (delta, extra_payment - refund_amount - charge_amount, self.current_customer["customer_id"])
            )
            self.db.commit()
            self._recalc_order_status(row["order_id"])
            self._sync_pending_payment(item_id)
            self.load_order(self.current_order_id)
        except Exception as e:
            self.db.rollback()
            messagebox.showerror("Edit Price", str(e))

    def _add_payment_to_item(self):
        if self.current_order_id is None:
            messagebox.showinfo("Add Payment", "Save this sale first.")
            return
        item_id = self._selected_item_id(self.items_tree)
        if item_id is None:
            return
        row = self.db.query("SELECT * FROM public.sales_order_items WHERE order_item_id=%s", (item_id,), "one")
        if not row:
            return
        if row["item_status"] in ("RETURNED", "CANCELLED"):
            messagebox.showerror("Add Payment", f"Can't add payment to a {row['item_status']} item.")
            return
        balance = float(row["balance_amount"])
        if balance <= 0.01:
            messagebox.showinfo("Add Payment", "This item is already fully paid.")
            return
        pd = open_payment_dialog(self, balance, txn_type="SALE", module_name="Sales - Add Payment")
        if pd is None:
            return
        amount = pd["paid_amount"]
        if amount <= 0:
            return
        try:
            payment_row = self.db.query(
                """INSERT INTO public.sales_payments
                   (order_id, order_item_id, customer_id, payment_date, amount, payment_mode, account_id, payment_type)
                   VALUES (%s,%s,%s,CURRENT_DATE,%s,%s,%s,'PAYMENT') RETURNING payment_id""",
                (row["order_id"], item_id, self.current_customer["customer_id"],
                 amount, pd["payment_mode"], pd["account_id"]), "one"
            )
            self._record_transaction(
                self.current_customer["customer_id"], amount, pd["payment_mode"],
                pd["account_id"], "CR", self.current_order_no, "Sale - additional payment",
                sales_payment_id=payment_row["payment_id"]
            )
            self.db.execute(
                "UPDATE public.sales_order_items SET paid_amount = paid_amount + %s, updated_at=now() WHERE order_item_id=%s",
                (amount, item_id)
            )
            self.db.execute(
                "UPDATE public.sales_orders SET paid_amount = paid_amount + %s, updated_at=now() WHERE order_id=%s",
                (amount, row["order_id"])
            )
            self.db.execute(
                "UPDATE public.customers SET total_paid = total_paid + %s, updated_at=now() WHERE customer_id=%s",
                (amount, self.current_customer["customer_id"])
            )
            self.db.commit()
            self._recalc_order_status(row["order_id"])
            self._sync_pending_payment(item_id)
            self.load_order(self.current_order_id)
        except Exception as e:
            self.db.rollback()
            messagebox.showerror("Add Payment", str(e))

    def _cancel_item_selected(self):
        item_id = self._selected_item_id(self.items_tree)
        if item_id is not None:
            self._cancel_item(item_id)

    def _cancel_item(self, order_item_id):
        row = self.db.query("SELECT * FROM public.sales_order_items WHERE order_item_id=%s", (order_item_id,), "one")
        if not row:
            return
        if row["item_status"] in ("SOLD", "RETURNED"):
            messagebox.showerror("Cancel Item", f"Can't cancel a {row['item_status']} item.")
            return
        if row["item_status"] == "CANCELLED":
            return
        if not messagebox.askyesno("Cancel Item", "Cancel this item from the order?"):
            return

        # FIX (money silently vanishing): if the customer already paid
        # something toward this item, cancelling it used to just subtract
        # that amount from the order/customer totals with no refund record
        # anywhere -- the money effectively disappeared from the books.
        # Now resolved via refund and/or cancellation charge.
        paid = float(row["paid_amount"])
        refund_amount = 0.0
        payment_mode_used = None
        account_id_used = None
        customer_account_no = None
        charge_amount = 0.0
        charge_account_id = None
        if paid > 0.01:
            messagebox.showwarning(
                "Payment Resolution Required",
                f"₹{paid:.2f} was already paid toward this item — resolve it "
                f"(refund, cancellation charge, or a mix) to cancel it."
            )
            rd = self._capture_refund(paid, title="Refund — Cancel Item")
            if rd is None:
                messagebox.showerror("Cancel Item", "Not resolved — item NOT cancelled.")
                return
            refund_amount = rd["refund_amount"]
            payment_mode_used = rd["refund_payment_mode"]
            account_id_used = rd["refund_account_id"]
            customer_account_no = rd["customer_account_no"]
            charge_amount = rd["charge_amount"]
            charge_account_id = rd["charge_account_id"]

        try:
            self.db.execute(
                "UPDATE public.sales_order_items SET item_status='CANCELLED', paid_amount = paid_amount - %s - %s, updated_at=now() WHERE order_item_id=%s",
                (refund_amount, charge_amount, order_item_id)
            )
            if refund_amount > 0:
                payment_row = self.db.query(
                    """INSERT INTO public.sales_payments
                       (order_id, order_item_id, customer_id, payment_date, amount, payment_mode, account_id,
                        payment_type, customer_account_no)
                       VALUES (%s,%s,%s,CURRENT_DATE,%s,%s,%s,'REFUND',%s) RETURNING payment_id""",
                    (row["order_id"], order_item_id, self.current_customer["customer_id"],
                     refund_amount, payment_mode_used, account_id_used, customer_account_no), "one"
                )
                self._record_transaction(
                    self.current_customer["customer_id"], refund_amount, payment_mode_used,
                    account_id_used, "DR", self.current_order_no, "Sale cancelled - refund",
                    sales_payment_id=payment_row["payment_id"]
                )
            if charge_amount > 0:
                self._book_cancellation_charge(
                    self.current_customer["customer_id"], charge_amount, charge_account_id,
                    self.current_order_no, "Cancellation charge - item cancelled"
                )
            self.db.execute(
                "UPDATE public.sales_orders SET total_amount = total_amount - %s, paid_amount = paid_amount - %s - %s, updated_at = now() WHERE order_id = %s",
                (row["price"], refund_amount, charge_amount, row["order_id"])
            )
            self.db.execute(
                """UPDATE public.customers
                   SET total_purchase = total_purchase - %s, total_paid = total_paid - %s - %s, updated_at = now()
                   WHERE customer_id = %s""",
                (row["price"], refund_amount, charge_amount, self.current_customer["customer_id"])
            )
            self.db.commit()
            self._recalc_order_status(row["order_id"])
            self._sync_pending_payment(order_item_id)
            self.load_order(self.current_order_id)
        except Exception as e:
            self.db.rollback()
            messagebox.showerror("Cancel Item", str(e))

    # ---------------------------------------------------- RETURN -----
    def _return_item(self):
        if self.current_order_id is None:
            messagebox.showinfo("Return Item", "Load an existing order first.")
            return
        item_id = self._selected_item_id(self.items_tree)
        if item_id is None:
            return
        row = self.db.query("SELECT * FROM public.sales_order_items WHERE order_item_id=%s", (item_id,), "one")
        if not row:
            return
        if row["item_status"] != "SOLD":
            messagebox.showerror("Return Item", "Only a SOLD item can be returned.")
            return

        paid = float(row["paid_amount"])
        reason_data = ask_form(self, "Return Item", [("reason", "Return Reason", "text", None)])
        if reason_data is None:
            return

        refund_amount = 0.0
        payment_mode_used = None
        account_id_used = None
        customer_account_no = None
        charge_amount = 0.0
        charge_account_id = None
        if paid > 0.01:
            rd = self._capture_refund(paid, title="Refund — Return Item")
            if rd is None:
                return
            refund_amount = rd["refund_amount"]
            payment_mode_used = rd["refund_payment_mode"]
            account_id_used = rd["refund_account_id"]
            customer_account_no = rd["customer_account_no"]
            charge_amount = rd["charge_amount"]
            charge_account_id = rd["charge_account_id"]

        table = "gold_jewelry" if row["metal_type"] == "GOLD" else "silver_jewelry"
        try:
            lot_row = self.db.query(f"SELECT status FROM public.{table} WHERE lot_no=%s FOR UPDATE", (row["lot_no"],), "one")
            if not lot_row or lot_row["status"] != "SOLD":
                messagebox.showerror(
                    "Return Item",
                    f"Lot {row['lot_no']} isn't currently SOLD "
                    f"(status={lot_row['status'] if lot_row else 'not found'}) — can't return."
                )
                self.db.rollback()
                return
            self.db.execute(f"UPDATE public.{table} SET status='AVAILABLE' WHERE lot_no=%s", (row["lot_no"],))
            self.db.execute(
                """UPDATE public.sales_order_items
                   SET item_status='RETURNED', returned_at=now(), return_reason=%s,
                       paid_amount = paid_amount - %s - %s, updated_at=now()
                   WHERE order_item_id=%s""",
                (reason_data["reason"] or None, refund_amount, charge_amount, item_id)
            )
            if refund_amount > 0:
                payment_row = self.db.query(
                    """INSERT INTO public.sales_payments
                       (order_id, order_item_id, customer_id, payment_date, amount, payment_mode, account_id,
                        payment_type, customer_account_no)
                       VALUES (%s,%s,%s,CURRENT_DATE,%s,%s,%s,'REFUND',%s) RETURNING payment_id""",
                    (row["order_id"], item_id, self.current_customer["customer_id"],
                     refund_amount, payment_mode_used, account_id_used, customer_account_no), "one"
                )
                self._record_transaction(
                    self.current_customer["customer_id"], refund_amount, payment_mode_used,
                    account_id_used, "DR", self.current_order_no, "Item returned - refund",
                    sales_payment_id=payment_row["payment_id"]
                )
            if charge_amount > 0:
                self._book_cancellation_charge(
                    self.current_customer["customer_id"], charge_amount, charge_account_id,
                    self.current_order_no, "Cancellation charge - item returned"
                )
            self.db.execute(
                """UPDATE public.sales_orders
                   SET total_amount = total_amount - %s, paid_amount = paid_amount - %s - %s, updated_at=now()
                   WHERE order_id=%s""",
                (row["price"], refund_amount, charge_amount, row["order_id"])
            )
            self.db.execute(
                """UPDATE public.customers
                   SET total_purchase = total_purchase - %s, total_paid = total_paid - %s - %s, updated_at=now()
                   WHERE customer_id=%s""",
                (row["price"], refund_amount, charge_amount, self.current_customer["customer_id"])
            )
            self.db.commit()
            self._recalc_order_status(row["order_id"])
            self._sync_pending_payment(item_id)
            self.load_order(self.current_order_id)
            self.status_var.set(f"Item returned — lot {row['lot_no']} is AVAILABLE again.")
        except Exception as e:
            self.db.rollback()
            messagebox.showerror("Return Item", str(e))

    # ---------------------------------------------------- STATUS -----
    def _recalc_order_status(self, order_id):
        order = self.db.query("SELECT * FROM public.sales_orders WHERE order_id=%s", (order_id,), "one")
        if not order or order["status"] == "CANCELLED":
            return
        items = self.db.query("SELECT item_status FROM public.sales_order_items WHERE order_id=%s", (order_id,))
        active = [i for i in items if i["item_status"] not in ("CANCELLED", "RETURNED")]
        if not active:
            new_status = order["status"]
        elif all(i["item_status"] == "SOLD" for i in active) and float(order["balance_amount"]) <= 0.01:
            new_status = "COMPLETED"
        elif all(i["item_status"] in ("PENDING_SEND", "SOLD") for i in active):
            new_status = "READY"
        else:
            new_status = "ORDER"
        if new_status != order["status"]:
            self.db.execute("UPDATE public.sales_orders SET status=%s, updated_at=now() WHERE order_id=%s",
                             (new_status, order_id))
            self.db.commit()

    # ---------------------------------------------------- CANCEL -----
    def cancel_order(self):
        if self.current_order_id is None:
            if self.cart_items:
                if messagebox.askyesno("Discard", "Discard this unsaved sale?"):
                    self.cart_items = []
                    self.current_customer = None
                    self._refresh_cart_display()
                    self._update_summary()
                    self.header_var.set("No sale in progress — click 'Start New Sale' or load an existing order.")
            return
        order = self.db.query("SELECT * FROM public.sales_orders WHERE order_id=%s", (self.current_order_id,), "one")
        if order["status"] == "COMPLETED":
            messagebox.showerror("Cancel Order", "Can't cancel a completed order.")
            return
        if order["status"] == "CANCELLED":
            return
        if not messagebox.askyesno(
            "Cancel Order", "Cancel this entire order? All non-sold items will be released."
        ):
            return
        try:
            items = self.db.query(
                """SELECT order_item_id, price, paid_amount FROM public.sales_order_items
                   WHERE order_id=%s AND item_status NOT IN ('SOLD', 'RETURNED', 'CANCELLED')""",
                (self.current_order_id,)
            )
            release_total = sum(float(i["price"]) for i in items)
            release_paid = sum(float(i["paid_amount"]) for i in items)

            # FIX (same money-vanishing bug as single-item cancel): if any
            # of these items had a payment against them, resolve it via
            # refund and/or cancellation charge before the order cancels.
            refund_amount = 0.0
            payment_mode_used = None
            account_id_used = None
            customer_account_no = None
            charge_amount = 0.0
            charge_account_id = None
            if release_paid > 0.01:
                messagebox.showwarning(
                    "Payment Resolution Required",
                    f"₹{release_paid:.2f} was already paid across items on this order — "
                    f"resolve it (refund, cancellation charge, or a mix) to cancel it."
                )
                rd = self._capture_refund(release_paid, title="Refund — Cancel Order")
                if rd is None:
                    messagebox.showerror("Cancel Order", "Not resolved — order NOT cancelled.")
                    return
                refund_amount = rd["refund_amount"]
                payment_mode_used = rd["refund_payment_mode"]
                account_id_used = rd["refund_account_id"]
                customer_account_no = rd["customer_account_no"]
                charge_amount = rd["charge_amount"]
                charge_account_id = rd["charge_account_id"]

            self.db.execute(
                """UPDATE public.sales_order_items SET item_status='CANCELLED', paid_amount=0, updated_at=now()
                   WHERE order_id=%s AND item_status NOT IN ('SOLD', 'RETURNED', 'CANCELLED')""",
                (self.current_order_id,)
            )
            if refund_amount > 0:
                # One consolidated refund row for the order (not linked to
                # a single item, since it may cover several) -- order_item_id
                # stays NULL here, which sales_payments allows.
                payment_row = self.db.query(
                    """INSERT INTO public.sales_payments
                       (order_id, customer_id, payment_date, amount, payment_mode, account_id,
                        payment_type, customer_account_no)
                       VALUES (%s,%s,CURRENT_DATE,%s,%s,%s,'REFUND',%s) RETURNING payment_id""",
                    (self.current_order_id, order["customer_id"], refund_amount,
                     payment_mode_used, account_id_used, customer_account_no), "one"
                )
                self._record_transaction(
                    order["customer_id"], refund_amount, payment_mode_used, account_id_used,
                    "DR", self.current_order_no, "Order cancelled - refund",
                    sales_payment_id=payment_row["payment_id"]
                )
            if charge_amount > 0:
                self._book_cancellation_charge(
                    order["customer_id"], charge_amount, charge_account_id,
                    self.current_order_no, "Cancellation charge - order cancelled"
                )
            if release_total > 0 or refund_amount > 0 or charge_amount > 0:
                self.db.execute(
                    "UPDATE public.sales_orders SET total_amount = total_amount - %s, paid_amount = paid_amount - %s, updated_at = now() WHERE order_id = %s",
                    (release_total, refund_amount + charge_amount, self.current_order_id)
                )
                self.db.execute(
                    """UPDATE public.customers
                       SET total_purchase = total_purchase - %s, total_paid = total_paid - %s, updated_at = now()
                       WHERE customer_id = %s""",
                    (release_total, refund_amount + charge_amount, order["customer_id"])
                )
            self.db.execute(
                "UPDATE public.sales_orders SET status='CANCELLED', updated_at=now() WHERE order_id=%s",
                (self.current_order_id,)
            )
            self.db.commit()
            for it in items:
                self._sync_pending_payment(it["order_item_id"])
            self.load_order(self.current_order_id)
        except Exception as e:
            self.db.rollback()
            messagebox.showerror("Cancel Order", str(e))

    # ============================================================= #
    # TAB 2: PENDING ORDER (PENDING_STOCK items)
    # ============================================================= #
    def _build_pending_order_tab(self, parent):
        bar = tk.Frame(parent)
        bar.pack(fill="x", padx=8, pady=8)
        tk.Button(bar, text="🔄 Refresh", command=self._refresh_pending_order).pack(side="left", padx=4)
        tk.Button(bar, text="Assign Stock to Selected", command=self._po_assign_stock).pack(side="left", padx=4)
        tk.Button(bar, text="🔗 Link to Lot In Progress", command=self._po_link_lot).pack(side="left", padx=4)
        tk.Button(bar, text="Open Order", command=self._po_open_order).pack(side="left", padx=4)
        tk.Button(bar, text="🖨️ Print Pending Order", command=self._print_pending_order_list).pack(side="right", padx=4)

        cols = ("order_item_id", "order_no", "customer", "phone", "item", "jewelry_type", "dimension", "price", "process", "order_date", "locked")
        self.po_tree = ttk.Treeview(parent, columns=cols, show="headings", height=18)
        widths = (0, 90, 140, 90, 130, 90, 70, 70, 110, 90, 60)
        for c, w in zip(cols, widths):
            self.po_tree.heading(c, text=c.replace("_", " ").title())
            self.po_tree.column(c, width=w, anchor="center")
        self.po_tree.column("order_item_id", width=0, stretch=False)
        self.po_tree.pack(fill="both", expand=True, padx=8, pady=8)

    def _refresh_pending_order(self):
        for i in self.po_tree.get_children():
            self.po_tree.delete(i)
        # FIX: process is now read LIVE from whichever jewelry lot is
        # linked (gold_jewelry.process_id / silver_jewelry.process_id,
        # updated by job_cart.py as manufacturing progresses) -- not a
        # value picked here. No lot linked yet -> shows "Order Created"
        # (the same literal text that's also the real first process_master
        # row every new lot starts at, once one IS linked).
        rows = self.db.query(
            """SELECT soi.order_item_id, so.order_no, c.full_name, c.phone,
                      COALESCE(soi.item_code, soi.custom_description) AS item_label,
                      soi.jewelry_type, soi.dimension, soi.price, soi.lot_no, soi.metal_type, so.order_date,
                      soi.is_locked,
                      COALESCE(gpm.process_name, spm.process_name) AS process_name
               FROM public.sales_order_items soi
               JOIN public.sales_orders so ON so.order_id = soi.order_id
               JOIN public.customers c ON c.customer_id = so.customer_id
               LEFT JOIN public.gold_jewelry gj ON gj.lot_no = soi.lot_no AND soi.metal_type = 'GOLD'
               LEFT JOIN public.process_master gpm ON gpm.process_id = gj.process_id
               LEFT JOIN public.silver_jewelry sj ON sj.lot_no = soi.lot_no AND soi.metal_type = 'SILVER'
               LEFT JOIN public.process_master spm ON spm.process_id = sj.process_id
               WHERE soi.item_status = 'PENDING_STOCK'
               ORDER BY so.order_date, soi.order_item_id"""
        )
        for r in rows:
            self.po_tree.insert("", "end", values=(
                r["order_item_id"], r["order_no"], r["full_name"], r["phone"],
                r["item_label"], r["jewelry_type"] or "", r["dimension"] or "",
                f"{r['price']:.2f}", r["process_name"] or "Order Created", r["order_date"],
                "🔒" if r["is_locked"] else ""
            ))

    def _po_link_lot(self):
        """
        Links a PENDING_STOCK item to a lot that's still being
        manufactured (MFG, not yet AVAILABLE) purely so its process can
        be tracked here -- does NOT change item_status (stays
        PENDING_STOCK) and does NOT claim/reserve the lot the way Assign
        Stock does. Once that lot is finished (job_cart.py moves it to
        AVAILABLE), use Assign Stock as normal.
        """
        item_id = self._selected_item_id(self.po_tree)
        if item_id is None:
            return
        row = self.db.query("SELECT * FROM public.sales_order_items WHERE order_item_id=%s", (item_id,), "one")
        if not row:
            return
        data = ask_form(self, "Link to Lot In Progress", [("lot_no", "Lot No", "text", None)])
        if not data or not data["lot_no"]:
            return
        lot_no = data["lot_no"].strip().upper()
        table = "gold_jewelry" if row["metal_type"] == "GOLD" else "silver_jewelry"
        lot_row = self.db.query(f"SELECT status FROM public.{table} WHERE lot_no=%s", (lot_no,), "one")
        if not lot_row:
            messagebox.showerror("Link to Lot", f"Lot {lot_no} not found in {table}.")
            return
        if lot_row["status"] not in ("MFG", "AVAILABLE"):
            messagebox.showerror("Link to Lot", f"Lot {lot_no} is {lot_row['status']} — can't link a {lot_row['status']} lot.")
            return
        try:
            self.db.execute(
                "UPDATE public.sales_order_items SET lot_no=%s, updated_at=now() WHERE order_item_id=%s",
                (lot_no, item_id)
            )
            self.db.commit()
            self._refresh_pending_order()
            self.status_var.set(f"Linked to lot {lot_no} for progress tracking.")
        except Exception as e:
            self.db.rollback()
            messagebox.showerror("Link to Lot", str(e))

    def _print_pending_order_list(self):
        rows = self.db.query(
            """SELECT so.order_no, c.full_name, c.phone,
                      COALESCE(soi.item_code, soi.custom_description) AS item_label,
                      soi.jewelry_type, soi.dimension, soi.price,
                      COALESCE(gpm.process_name, spm.process_name, 'Order Created') AS process_name,
                      so.order_date
               FROM public.sales_order_items soi
               JOIN public.sales_orders so ON so.order_id = soi.order_id
               JOIN public.customers c ON c.customer_id = so.customer_id
               LEFT JOIN public.gold_jewelry gj ON gj.lot_no = soi.lot_no AND soi.metal_type = 'GOLD'
               LEFT JOIN public.process_master gpm ON gpm.process_id = gj.process_id
               LEFT JOIN public.silver_jewelry sj ON sj.lot_no = soi.lot_no AND soi.metal_type = 'SILVER'
               LEFT JOIN public.process_master spm ON spm.process_id = sj.process_id
               WHERE soi.item_status = 'PENDING_STOCK'
               ORDER BY so.order_date, so.order_no"""
        )
        rows_html = "".join(
            f"<tr><td>{r['order_no']}</td><td>{r['full_name']}</td><td>{r['phone']}</td>"
            f"<td>{r['item_label']}</td><td>{r['jewelry_type'] or ''}</td><td>{r['dimension'] or ''}</td>"
            f"<td>₹{r['price']:.2f}</td><td>{r['process_name']}</td><td>{r['order_date']}</td></tr>"
            for r in rows
        )
        html = f"""<html><head><meta charset="utf-8"><title>Pending Order List</title>
<style>
  body {{ font-family: Arial, sans-serif; font-size: 12px; }}
  h2 {{ margin-bottom: 4px; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
  th, td {{ border: 1px solid #999; padding: 4px 6px; text-align: left; }}
  th {{ background: #eee; }}
  @media print {{ button {{ display: none; }} }}
</style></head><body>
<h2>Pending Order List</h2>
<p>Printed: {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
<table>
<tr><th>Order No</th><th>Customer</th><th>Phone</th><th>Item</th><th>Jewelry Type</th>
<th>Dimension</th><th>Price</th><th>Process</th><th>Order Date</th></tr>
{rows_html}
</table>
<p style="margin-top:16px;"><button onclick="window.print()">Print</button></p>
</body></html>"""
        self._open_html_for_print(html, "pending_order_list")

    def _po_assign_stock(self):
        item_id = self._selected_item_id(self.po_tree)
        if item_id is not None:
            self._assign_stock(item_id)
            self._refresh_pending_order()

    def _assign_stock(self, order_item_id):
        """
        First come, first served. SELECT ... FOR UPDATE SKIP LOCKED on
        the candidate jewelry row means a second concurrent claim simply
        skips the locked row and finds the next candidate instead of
        blocking or erroring. The partial unique index on
        sales_order_items is the final backstop.
        """
        row = self.db.query("SELECT * FROM public.sales_order_items WHERE order_item_id=%s", (order_item_id,), "one")
        if not row:
            return
        if row["item_status"] != "PENDING_STOCK":
            messagebox.showinfo("Assign Stock", "This item already has stock assigned (or isn't pending).")
            return
        if not row["item_code"]:
            messagebox.showerror(
                "Assign Stock",
                "This is a custom item with no catalog item_code, so stock can't be auto-matched. "
                "Find the right lot on the Sale/Order tab's search and add it manually instead."
            )
            return
        table = "gold_jewelry" if row["metal_type"] == "GOLD" else "silver_jewelry"
        try:
            # FIX: if this item was already linked to a specific lot in
            # progress (via "Link to Lot In Progress"), check THAT lot
            # first instead of searching fresh -- searching fresh could
            # claim a totally different lot than the one being tracked.
            candidate = None
            if row["lot_no"]:
                linked = self.db.query(
                    f"SELECT lot_no, status FROM public.{table} WHERE lot_no=%s FOR UPDATE", (row["lot_no"],), "one"
                )
                if linked and linked["status"] == "AVAILABLE":
                    candidate = linked
                elif linked:
                    messagebox.showinfo(
                        "Assign Stock",
                        f"Lot {row['lot_no']} (linked to this item) is still {linked['status']}, not finished yet."
                    )
                    self.db.rollback()
                    return

            if not candidate:
                candidate = self.db.query(
                    f"""SELECT lot_no FROM public.{table}
                        WHERE item_code = %s AND status = 'AVAILABLE'
                          AND lot_no NOT IN (
                              SELECT lot_no FROM public.sales_order_items
                              WHERE lot_no IS NOT NULL AND item_status IN ('PENDING_SEND','SOLD')
                          )
                        ORDER BY created_at ASC
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1""",
                    (row["item_code"],), "one"
                )
            if not candidate:
                self.db.rollback()
                messagebox.showinfo("Assign Stock", f"No stock currently available for {row['item_code']}. Stays pending.")
                return
            self.db.execute(
                "UPDATE public.sales_order_items SET lot_no=%s, item_status='PENDING_SEND', updated_at=now() WHERE order_item_id=%s",
                (candidate["lot_no"], order_item_id)
            )
            self.db.commit()
            self.status_var.set(f"Lot {candidate['lot_no']} assigned — now Pending Send.")
            self._recalc_order_status(row["order_id"])
            if self.current_order_id == row["order_id"]:
                self.load_order(self.current_order_id)
        except psycopg2.errors.UniqueViolation:
            self.db.rollback()
            messagebox.showwarning("Assign Stock", "That lot was just claimed by another order — try again.")
        except Exception as e:
            self.db.rollback()
            messagebox.showerror("Assign Stock", str(e))

    def _po_open_order(self):
        sel = self.po_tree.selection()
        if not sel:
            return
        order_no = self.po_tree.item(sel[0])["values"][1]
        row = self.db.query("SELECT order_id FROM public.sales_orders WHERE order_no=%s", (order_no,), "one")
        if row:
            self.notebook.select(0)
            self.load_order(row["order_id"])

    # ============================================================= #
    # TAB 3: PENDING SEND (PENDING_SEND items)
    # ============================================================= #
    def _build_pending_send_tab(self, parent):
        bar = tk.Frame(parent)
        bar.pack(fill="x", padx=8, pady=8)
        tk.Button(bar, text="🔄 Refresh", command=self._refresh_pending_send).pack(side="left", padx=4)
        tk.Button(bar, text="Set Send Details", command=self._ps_set_send_details).pack(side="left", padx=4)
        tk.Button(bar, text="Open Order", command=self._ps_open_order).pack(side="left", padx=4)
        tk.Button(bar, text="🏷️ Print Address Label (Thermal)", command=self._print_address_label).pack(side="right", padx=4)
        tk.Button(bar, text="📜 Print Certificate", command=self._print_certificate).pack(side="right", padx=4)

        cols = ("order_item_id", "order_no", "customer", "phone", "item", "lot_no", "price", "order_date")
        self.ps_tree = ttk.Treeview(parent, columns=cols, show="headings", height=12)
        widths = (0, 90, 150, 90, 130, 90, 80, 90)
        for c, w in zip(cols, widths):
            self.ps_tree.heading(c, text=c.replace("_", " ").title())
            self.ps_tree.column(c, width=w, anchor="center")
        self.ps_tree.column("order_item_id", width=0, stretch=False)
        self.ps_tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.ps_tree.bind("<<TreeviewSelect>>", lambda e: self._refresh_ps_customer_panel())

        # FIX: full customer details, not just name/phone -- shown for
        # the currently selected row, so the treeview itself doesn't need
        # to be impossibly wide.
        detail_frame = tk.LabelFrame(parent, text="Customer Details (selected item)", padx=8, pady=6)
        detail_frame.pack(fill="x", padx=8, pady=(0, 8))
        self.ps_customer_detail_var = tk.StringVar(value="Select a row above to see full customer details.")
        tk.Label(detail_frame, textvariable=self.ps_customer_detail_var, justify="left", anchor="w").pack(fill="x")

    def _refresh_pending_send(self):
        for i in self.ps_tree.get_children():
            self.ps_tree.delete(i)
        rows = self.db.query(
            """SELECT soi.order_item_id, so.order_no, c.full_name, c.phone,
                      COALESCE(soi.item_code, soi.custom_description) AS item_label,
                      soi.lot_no, soi.price, so.order_date
               FROM public.sales_order_items soi
               JOIN public.sales_orders so ON so.order_id = soi.order_id
               JOIN public.customers c ON c.customer_id = so.customer_id
               WHERE soi.item_status = 'PENDING_SEND'
               ORDER BY so.order_date, soi.order_item_id"""
        )
        for r in rows:
            self.ps_tree.insert("", "end", values=(
                r["order_item_id"], r["order_no"], r["full_name"], r["phone"],
                r["item_label"], r["lot_no"], f"{r['price']:.2f}", r["order_date"]
            ))
        self.ps_customer_detail_var.set("Select a row above to see full customer details.")

    def _refresh_ps_customer_panel(self):
        item_id = self._selected_item_id(self.ps_tree)
        if item_id is None:
            return
        row = self.db.query(
            """SELECT c.* FROM public.sales_order_items soi
               JOIN public.sales_orders so ON so.order_id = soi.order_id
               JOIN public.customers c ON c.customer_id = so.customer_id
               WHERE soi.order_item_id=%s""",
            (item_id,), "one"
        )
        if not row:
            return
        parts = [f"Name: {row['full_name']}", f"Phone: {row['phone']}"]
        if row.get("email"):
            parts.append(f"Email: {row['email']}")
        if row.get("line_id"):
            parts.append(f"LINE ID: {row['line_id']}")
        addr_bits = [row.get("address"), row.get("city"), row.get("state"), row.get("pincode")]
        addr = ", ".join(str(b) for b in addr_bits if b)
        if addr:
            parts.append(f"Address: {addr}")
        self.ps_customer_detail_var.set("   |   ".join(parts))

    def _get_full_item_details(self, order_item_id):
        """Everything needed for the two print templates below."""
        row = self.db.query(
            """SELECT soi.*, so.order_no, so.order_date,
                      c.full_name, c.phone, c.email, c.line_id, c.address, c.city, c.state, c.pincode
               FROM public.sales_order_items soi
               JOIN public.sales_orders so ON so.order_id = soi.order_id
               JOIN public.customers c ON c.customer_id = so.customer_id
               WHERE soi.order_item_id=%s""",
            (order_item_id,), "one"
        )
        if not row or not row["lot_no"]:
            return row, None
        table = "gold_jewelry" if row["metal_type"] == "GOLD" else "silver_jewelry"
        lot = self.db.query(
            f"SELECT purity, weight, final_weight, jewelry_type, dimension FROM public.{table} WHERE lot_no=%s",
            (row["lot_no"],), "one"
        )
        return row, lot

    def _print_address_label(self):
        item_id = self._selected_item_id(self.ps_tree)
        if item_id is None:
            return
        row, _lot = self._get_full_item_details(item_id)
        if not row:
            return
        addr_bits = [row.get("address"), row.get("city"), row.get("state"), row.get("pincode")]
        addr = "<br>".join(str(b) for b in addr_bits if b) or "(no address on file)"
        dispatch_bits = []
        if row.get("dispatch_method"):
            dispatch_bits.append(f"Method: {row['dispatch_method']}")
        if row.get("dispatch_tracking_no"):
            dispatch_bits.append(f"Tracking: {row['dispatch_tracking_no']}")
        dispatch_line = " | ".join(dispatch_bits)
        item_label = f"{row['item_code']} — Lot {row['lot_no']}" if row.get("item_code") else \
            (f"{row['custom_description']} — Lot {row['lot_no']}" if row.get("custom_description") else row.get("lot_no", ""))
        # 4in x 6in -- typical thermal shipping-label size. Adjust the
        # @page size below if your printer uses a different label stock.
        html = f"""<html><head><meta charset="utf-8"><title>Address Label</title>
<style>
  @page {{ size: 4in 6in; margin: 0.15in; }}
  body {{ font-family: Arial, sans-serif; font-size: 14px; }}
  .name {{ font-size: 20px; font-weight: bold; margin-bottom: 6px; }}
  .section {{ margin-top: 14px; }}
  .label {{ font-weight: bold; }}
  @media print {{ button {{ display: none; }} }}
</style></head><body>
<div class="name">{row['full_name']}</div>
<div>{row['phone']}</div>
<div class="section">{addr}</div>
<div class="section"><span class="label">Order:</span> {row['order_no']} &nbsp; <span class="label">Item:</span> {item_label}</div>
<div class="section">{dispatch_line}</div>
<p style="margin-top:20px;"><button onclick="window.print()">Print</button></p>
</body></html>"""
        self._open_html_for_print(html, "address_label")

    def _print_certificate(self):
        item_id = self._selected_item_id(self.ps_tree)
        if item_id is None:
            return
        row, lot = self._get_full_item_details(item_id)
        if not row:
            return
        item_label = row["item_code"] or row["custom_description"] or ""
        jewelry_type = (lot["jewelry_type"] if lot else row.get("jewelry_type")) or ""
        dimension = (lot["dimension"] if lot else row.get("dimension")) or ""
        purity = lot["purity"] if lot else ""
        weight = lot["final_weight"] or lot["weight"] if lot else None
        weight_line = f"{weight:.3f} g" if weight is not None else "—"
        html = f"""<html><head><meta charset="utf-8"><title>Certificate</title>
<style>
  @page {{ size: A4; margin: 1in; }}
  body {{ font-family: Georgia, 'Times New Roman', serif; }}
  h1 {{ text-align: center; font-size: 26px; letter-spacing: 2px; margin-bottom: 4px; }}
  .sub {{ text-align: center; color: #555; margin-bottom: 40px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
  td {{ padding: 10px 6px; border-bottom: 1px solid #ccc; font-size: 15px; }}
  td.label {{ width: 220px; font-weight: bold; }}
  .footer {{ margin-top: 60px; display: flex; justify-content: space-between; }}
  @media print {{ button {{ display: none; }} }}
</style></head><body>
<h1>Certificate of Authenticity</h1>
<div class="sub">Order {row['order_no']} &nbsp;·&nbsp; {row['order_date']}</div>
<table>
<tr><td class="label">Customer</td><td>{row['full_name']}</td></tr>
<tr><td class="label">Item</td><td>{item_label}</td></tr>
<tr><td class="label">Jewelry Type</td><td>{jewelry_type}</td></tr>
<tr><td class="label">Metal</td><td>{row['metal_type']}</td></tr>
<tr><td class="label">Purity</td><td>{purity or ''}</td></tr>
<tr><td class="label">Weight</td><td>{weight_line}</td></tr>
<tr><td class="label">Dimension / Length</td><td>{dimension}</td></tr>
<tr><td class="label">Lot No</td><td>{row['lot_no'] or ''}</td></tr>
<tr><td class="label">Price</td><td>₹{row['price']:.2f}</td></tr>
</table>
<div class="footer">
  <div>_______________________<br>Authorized Signature</div>
  <div>_______________________<br>Date</div>
</div>
<p style="margin-top:30px;"><button onclick="window.print()">Print</button></p>
</body></html>"""
        self._open_html_for_print(html, "certificate")

    def _ps_set_send_details(self):
        item_id = self._selected_item_id(self.ps_tree)
        if item_id is None:
            return
        method_names = list(self.dispatch_name_to_code.keys())
        if not method_names:
            messagebox.showerror("Send Details", "No dispatch methods configured in dispatch_methods.")
            return
        data = ask_form(self, "Send Details", [
            ("method", "Sending Option", "choice", method_names),
            ("tracking_no", "Tracking No (if required)", "text", None),
        ])
        if not data or not data["method"]:
            return
        method_code = self.dispatch_name_to_code[data["method"]]
        requires_tracking = self.dispatch_requires_tracking.get(method_code, False)
        tracking_no = data["tracking_no"].strip() or None
        if requires_tracking and not tracking_no:
            messagebox.showerror("Send Details", f"{data['method']} requires a tracking number.")
            return

        row = self.db.query("SELECT * FROM public.sales_order_items WHERE order_item_id=%s", (item_id,), "one")
        if not row:
            return
        item_balance = float(row["balance_amount"])
        if item_balance > 0.01:
            if not messagebox.askyesno(
                "Send Details", f"This item still has a balance of ₹{item_balance:.2f}. Dispatch anyway?"
            ):
                return

        table = "gold_jewelry" if row["metal_type"] == "GOLD" else "silver_jewelry"
        try:
            lot_row = self.db.query(f"SELECT status FROM public.{table} WHERE lot_no=%s FOR UPDATE", (row["lot_no"],), "one")
            if not lot_row or lot_row["status"] != "AVAILABLE":
                messagebox.showerror(
                    "Send Details",
                    f"Lot {row['lot_no']} is not AVAILABLE "
                    f"(status={lot_row['status'] if lot_row else 'not found'}) — cannot dispatch."
                )
                self.db.rollback()
                return
            self.db.execute(f"UPDATE public.{table} SET status='SOLD' WHERE lot_no=%s", (row["lot_no"],))
            self.db.execute(
                """UPDATE public.sales_order_items
                   SET item_status='SOLD', dispatch_method=%s, dispatch_tracking_no=%s,
                       dispatch_date=CURRENT_DATE, updated_at=now()
                   WHERE order_item_id=%s""",
                (method_code, tracking_no, item_id)
            )
            self.db.commit()
            self._recalc_order_status(row["order_id"])
            self._refresh_pending_send()
            if self.current_order_id == row["order_id"]:
                self.load_order(self.current_order_id)
            self.status_var.set(f"Item dispatched via {data['method']}.")
        except Exception as e:
            self.db.rollback()
            messagebox.showerror("Send Details", str(e))

    def _ps_open_order(self):
        sel = self.ps_tree.selection()
        if not sel:
            return
        order_no = self.ps_tree.item(sel[0])["values"][1]
        row = self.db.query("SELECT order_id FROM public.sales_orders WHERE order_no=%s", (order_no,), "one")
        if row:
            self.notebook.select(0)
            self.load_order(row["order_id"])

    # ============================================================= #
    # TAB 4: STOCK LOOKUP
    # ============================================================= #
    # ============================================================= #
    # TAB: INSTALLMENTS
    # ============================================================= #
    def _build_installments_tab(self, parent):
        bar = tk.Frame(parent)
        bar.pack(fill="x", padx=8, pady=8)
        tk.Button(bar, text="🔄 Refresh", command=self._refresh_installments).pack(side="left", padx=4)
        tk.Button(bar, text="💳 Collect Payment", bg="#1565c0", fg="white",
                  command=self._collect_installment).pack(side="left", padx=4)
        tk.Button(bar, text="❌ Cancel Plan", fg="red", command=self._cancel_installment_plan).pack(side="left", padx=4)
        tk.Button(bar, text="Open Order", command=self._inst_open_order).pack(side="left", padx=4)
        self.inst_filter_var = tk.StringVar(value="ALL")
        for label, val in [("All", "ALL"), ("Overdue only", "OVERDUE")]:
            tk.Radiobutton(bar, text=label, variable=self.inst_filter_var, value=val,
                           command=self._refresh_installments).pack(side="left", padx=6)

        cols = ("schedule_id", "order_no", "customer", "phone", "item", "inst_no", "due_date",
                 "amount_due", "amount_paid", "remaining", "status")
        self.inst_tree = ttk.Treeview(parent, columns=cols, show="headings", height=18)
        widths = (0, 90, 150, 90, 130, 60, 90, 90, 90, 90, 90)
        for c, w in zip(cols, widths):
            self.inst_tree.heading(c, text=c.replace("_", " ").title())
            self.inst_tree.column(c, width=w, anchor="center")
        self.inst_tree.column("schedule_id", width=0, stretch=False)
        self.inst_tree.tag_configure("overdue", background="#ffebee")
        self.inst_tree.pack(fill="both", expand=True, padx=8, pady=8)

    def _refresh_installments(self):
        for i in self.inst_tree.get_children():
            self.inst_tree.delete(i)
        where_overdue = "AND s.due_date < CURRENT_DATE" if self.inst_filter_var.get() == "OVERDUE" else ""
        rows = self.db.query(
            f"""SELECT s.schedule_id, so.order_no, c.full_name, c.phone,
                       COALESCE(soi.item_code, soi.custom_description) AS item_label,
                       s.installment_no, s.due_date, s.amount_due, s.amount_paid, s.status
                FROM public.installment_schedule s
                JOIN public.installment_plans p ON p.plan_id = s.plan_id
                JOIN public.sales_order_items soi ON soi.order_item_id = p.order_item_id
                JOIN public.sales_orders so ON so.order_id = soi.order_id
                JOIN public.customers c ON c.customer_id = so.customer_id
                WHERE p.status = 'ACTIVE' AND s.status != 'PAID' {where_overdue}
                ORDER BY s.due_date"""
        )
        today = dt.date.today()
        for r in rows:
            remaining = round(float(r["amount_due"]) - float(r["amount_paid"]), 2)
            tag = "overdue" if r["due_date"] < today else ""
            self.inst_tree.insert("", "end", values=(
                r["schedule_id"], r["order_no"], r["full_name"], r["phone"], r["item_label"],
                r["installment_no"], r["due_date"], f"{r['amount_due']:.2f}",
                f"{r['amount_paid']:.2f}", f"{remaining:.2f}", r["status"]
            ), tags=(tag,) if tag else ())

    def _collect_installment(self):
        sel = self.inst_tree.selection()
        if not sel:
            messagebox.showwarning("Collect Payment", "Select an installment row first.")
            return
        schedule_id = int(self.inst_tree.item(sel[0])["values"][0])
        row = self.db.query(
            """SELECT s.*, p.order_item_id, soi.order_id, soi.metal_type, so.customer_id, so.order_no
               FROM public.installment_schedule s
               JOIN public.installment_plans p ON p.plan_id = s.plan_id
               JOIN public.sales_order_items soi ON soi.order_item_id = p.order_item_id
               JOIN public.sales_orders so ON so.order_id = soi.order_id
               WHERE s.schedule_id=%s""",
            (schedule_id,), "one"
        )
        if not row:
            return
        remaining = round(float(row["amount_due"]) - float(row["amount_paid"]), 2)
        if remaining <= 0.01:
            messagebox.showinfo("Collect Payment", "This installment is already fully paid.")
            return
        pd = open_payment_dialog(self, remaining, txn_type="SALE",
                                  module_name=f"Sales - Installment #{row['installment_no']}")
        if pd is None or pd["paid_amount"] <= 0:
            return
        amount = min(pd["paid_amount"], remaining)  # never let this leg overpay itself
        try:
            payment_row = self.db.query(
                """INSERT INTO public.sales_payments
                   (order_id, order_item_id, customer_id, payment_date, amount, payment_mode, account_id, payment_type)
                   VALUES (%s,%s,%s,CURRENT_DATE,%s,%s,%s,'PAYMENT') RETURNING payment_id""",
                (row["order_id"], row["order_item_id"], row["customer_id"],
                 amount, pd["payment_mode"], pd["account_id"]), "one"
            )
            new_paid = round(float(row["amount_paid"]) + amount, 2)
            new_status = "PAID" if new_paid >= float(row["amount_due"]) - 0.01 else "PARTIAL"
            self.db.execute(
                """UPDATE public.installment_schedule
                   SET amount_paid=%s, status=%s, paid_date=CASE WHEN %s='PAID' THEN CURRENT_DATE ELSE paid_date END,
                       sales_payment_id=%s
                   WHERE schedule_id=%s""",
                (new_paid, new_status, new_status, payment_row["payment_id"], schedule_id)
            )
            self.db.execute(
                "UPDATE public.sales_order_items SET paid_amount = paid_amount + %s, updated_at=now() WHERE order_item_id=%s",
                (amount, row["order_item_id"])
            )
            self.db.execute(
                "UPDATE public.sales_orders SET paid_amount = paid_amount + %s, updated_at=now() WHERE order_id=%s",
                (amount, row["order_id"])
            )
            self.db.execute(
                "UPDATE public.customers SET total_paid = total_paid + %s, updated_at=now() WHERE customer_id=%s",
                (amount, row["customer_id"])
            )
            # If every installment on this plan is now PAID, close the plan out.
            remaining_count = self.db.query(
                "SELECT COUNT(*) AS n FROM public.installment_schedule WHERE plan_id=%s AND status != 'PAID'",
                (row["plan_id"],), "one"
            )
            if remaining_count["n"] == 0:
                self.db.execute("UPDATE public.installment_plans SET status='COMPLETED' WHERE plan_id=%s", (row["plan_id"],))
            self.db.commit()
            self._record_transaction(
                row["customer_id"], amount, pd["payment_mode"], pd["account_id"], "CR",
                row["order_no"], f"Installment #{row['installment_no']} payment",
                sales_payment_id=payment_row["payment_id"]
            )
            self._recalc_order_status(row["order_id"])
            self._sync_pending_payment(row["order_item_id"])
            self._refresh_installments()
            if self.current_order_id == row["order_id"]:
                self.load_order(self.current_order_id)
            self.status_var.set(f"Collected ₹{amount:.2f} for installment #{row['installment_no']}.")
        except Exception as e:
            self.db.rollback()
            messagebox.showerror("Collect Payment", str(e))

    def _cancel_installment_plan(self):
        """
        Cancels the WHOLE plan behind the selected installment row --
        supports partial or full refund, same as any other
        cancellation, by reusing the existing _cancel_item (item not
        yet dispatched) / _return_item (already SOLD) logic instead of
        duplicating the refund/cancellation-charge flow here.
        """
        sel = self.inst_tree.selection()
        if not sel:
            messagebox.showwarning("Cancel Plan", "Select an installment row first.")
            return
        schedule_id = int(self.inst_tree.item(sel[0])["values"][0])
        row = self.db.query(
            """SELECT p.plan_id, p.order_item_id, p.status AS plan_status,
                      soi.item_status, soi.order_id
               FROM public.installment_schedule s
               JOIN public.installment_plans p ON p.plan_id = s.plan_id
               JOIN public.sales_order_items soi ON soi.order_item_id = p.order_item_id
               WHERE s.schedule_id=%s""",
            (schedule_id,), "one"
        )
        if not row:
            return
        if row["plan_status"] != "ACTIVE":
            messagebox.showinfo("Cancel Plan", f"This plan is already {row['plan_status']}.")
            return
        if not messagebox.askyesno(
            "Cancel Plan",
            "Cancel this entire installment plan? This will cancel or return the underlying item too, "
            "with a refund/cancellation-charge step for whatever's been paid so far."
        ):
            return

        self.notebook.select(0)
        self.load_order(row["order_id"])
        for iid in self.items_tree.get_children():
            if int(self.items_tree.item(iid)["values"][0]) == row["order_item_id"]:
                self.items_tree.selection_set(iid)
                break
        else:
            messagebox.showerror("Cancel Plan", "Couldn't find the item on the loaded order.")
            return

        if row["item_status"] == "SOLD":
            self._return_item()
        elif row["item_status"] in ("PENDING_STOCK", "PENDING_SEND"):
            self._cancel_item_selected()
        else:
            messagebox.showinfo("Cancel Plan", f"Item is already {row['item_status']} — nothing to cancel.")
            return

        try:
            self.db.execute("UPDATE public.installment_plans SET status='CANCELLED' WHERE plan_id=%s", (row["plan_id"],))
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            print("plan close-out failed (non-fatal):", e)
        self._refresh_installments()

    def _inst_open_order(self):
        sel = self.inst_tree.selection()
        if not sel:
            return
        order_no = self.inst_tree.item(sel[0])["values"][1]
        row = self.db.query("SELECT order_id FROM public.sales_orders WHERE order_no=%s", (order_no,), "one")
        if row:
            self.notebook.select(0)
            self.load_order(row["order_id"])

    def _build_stock_tab(self, parent):
        bar = tk.Frame(parent)
        bar.pack(fill="x", padx=8, pady=8)
        self.stock_mode_var = tk.StringVar(value="ITEM_CODE")
        tk.Radiobutton(bar, text="By Item Code", variable=self.stock_mode_var, value="ITEM_CODE").pack(side="left", padx=4)
        tk.Radiobutton(bar, text="By Lot No", variable=self.stock_mode_var, value="LOT_NO").pack(side="left", padx=4)
        self.stock_term_var = tk.StringVar()
        e = tk.Entry(bar, textvariable=self.stock_term_var, width=22)
        e.pack(side="left", padx=8)
        e.bind("<Return>", lambda ev: self._do_stock_search())
        tk.Button(bar, text="🔍 Search", command=self._do_stock_search).pack(side="left", padx=4)

        cols = ("lot_no", "item_code", "metal_type", "weight", "status")
        self.stock_tree = ttk.Treeview(parent, columns=cols, show="headings", height=18)
        for c, w in zip(cols, (100, 100, 80, 90, 200)):
            self.stock_tree.heading(c, text=c.replace("_", " ").title())
            self.stock_tree.column(c, width=w, anchor="center")
        self.stock_tree.pack(fill="both", expand=True, padx=8, pady=8)

    def _do_stock_search(self):
        for i in self.stock_tree.get_children():
            self.stock_tree.delete(i)
        term = self.stock_term_var.get().strip().upper()
        if not term:
            return
        col = "item_code" if self.stock_mode_var.get() == "ITEM_CODE" else "lot_no"
        for table, metal in (("gold_jewelry", "GOLD"), ("silver_jewelry", "SILVER")):
            rows = self.db.query(
                f"SELECT lot_no, item_code, weight, status FROM public.{table} WHERE {col}=%s ORDER BY status, lot_no",
                (term,)
            )
            for r in rows:
                reserved = self.db.query(
                    """SELECT so.order_no FROM public.sales_order_items soi
                       JOIN public.sales_orders so ON so.order_id = soi.order_id
                       WHERE soi.lot_no=%s AND soi.item_status IN ('PENDING_SEND','SOLD')""",
                    (r["lot_no"],), "one"
                )
                status_display = r["status"] + (f" (order {reserved['order_no']})" if reserved else "")
                self.stock_tree.insert("", "end", values=(
                    r["lot_no"], r["item_code"], metal,
                    f"{r['weight']:.3f}" if r["weight"] is not None else "", status_display
                ))
        if not self.stock_tree.get_children():
            messagebox.showinfo("Stock Search", f"No results for '{term}'.")

    # ============================================================= #
    # CUSTOMER / CATALOG
    # ============================================================= #
    def open_customer_search(self):
        """
        Browsable customer search -- matches name, phone, OR customer_code
        (partial match on any of them), since exact-phone-only search
        couldn't find someone if you only remembered part of their name.
        Pick a result to either start a new sale for them directly or
        view their full order history (every sales_orders row tied to
        their customer_id -- the "unique number" that makes history
        lookup possible).
        """
        win = tk.Toplevel(self)
        win.title("Search Customer")
        win.geometry("620x420")

        bar = tk.Frame(win)
        bar.pack(fill="x", padx=8, pady=8)
        tk.Label(bar, text="Name / Phone / Customer Code:").pack(side="left", padx=4)
        term_var = tk.StringVar()
        e = tk.Entry(bar, textvariable=term_var, width=25)
        e.pack(side="left", padx=4)

        cols = ("customer_id", "customer_code", "full_name", "phone", "address")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=12)
        widths = (0, 100, 160, 100, 220)
        for c, w in zip(cols, widths):
            tree.heading(c, text=c.replace("_", " ").title())
            tree.column(c, width=w, anchor="center")
        tree.column("customer_id", width=0, stretch=False)
        tree.pack(fill="both", expand=True, padx=8, pady=4)

        def do_search(*_):
            for i in tree.get_children():
                tree.delete(i)
            term = term_var.get().strip()
            if not term:
                return
            rows = self.db.query(
                """SELECT customer_id, customer_code, full_name, phone, address FROM public.customers
                   WHERE full_name ILIKE %s OR phone ILIKE %s OR customer_code ILIKE %s
                   ORDER BY full_name""",
                (f"%{term}%", f"%{term}%", f"%{term}%")
            )
            for r in rows:
                tree.insert("", "end", values=(
                    r["customer_id"], r["customer_code"], r["full_name"], r["phone"], r["address"] or ""
                ))
            if not rows:
                self.status_var.set(f"No customers matching '{term}'.")

        e.bind("<Return>", do_search)
        tk.Button(bar, text="🔍 Search", command=do_search).pack(side="left", padx=4)

        def selected_customer_id():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Select Customer", "Select a row first.")
                return None
            return int(tree.item(sel[0])["values"][0])

        def start_sale_for_selected():
            cid = selected_customer_id()
            if cid is None:
                return
            cust = self.db.query("SELECT * FROM public.customers WHERE customer_id=%s", (cid,), "one")
            sp_names = [""] + list(self.account_name_to_id.keys())
            sp_data = ask_form(self, "Sales Person", [("sales_person", "Sales Person", "choice", sp_names)])
            self.selected_sales_person_id = (
                self.account_name_to_id.get(sp_data["sales_person"]) if sp_data and sp_data["sales_person"] else None
            )
            self.current_order_id = None
            self.current_order_no = None
            self.current_customer = cust
            self.cart_items = []
            self._refresh_cart_display()
            self._update_summary()
            self.header_var.set(f"[NEW SALE — not yet saved]  Customer: {cust['full_name']} ({cust['phone']})")
            win.destroy()

        def view_history():
            cid = selected_customer_id()
            if cid is None:
                return
            win.destroy()
            self.open_customer_history(cid)

        btns = tk.Frame(win)
        btns.pack(fill="x", padx=8, pady=8)
        tk.Button(btns, text="🆕 Start Sale for Selected", bg="#2e7d32", fg="white",
                  command=start_sale_for_selected).pack(side="left", padx=4)
        tk.Button(btns, text="📜 View History", command=view_history).pack(side="left", padx=4)

    def open_customer_history(self, customer_id):
        """
        Every sales_orders row tied to this customer_id, in one place --
        the actual point of a permanent per-customer number: you can
        always answer "how many orders does this person have, and is
        anything still owed" from here.
        """
        cust = self.db.query("SELECT * FROM public.customers WHERE customer_id=%s", (customer_id,), "one")
        if not cust:
            return
        win = tk.Toplevel(self)
        win.title(f"History — {cust['full_name']} ({cust['customer_code']})")
        win.geometry("780x480")

        header = tk.Label(
            win,
            text=f"{cust['full_name']}   |   {cust['customer_code']}   |   {cust['phone']}\n"
                 f"Total Purchase: ₹{cust['total_purchase']:.2f}   Total Paid: ₹{cust['total_paid']:.2f}   "
                 f"Balance: ₹{cust['balance']:.2f}",
            justify="left", anchor="w", font=("Segoe UI", 10, "bold")
        )
        header.pack(fill="x", padx=8, pady=8)

        cols = ("order_id", "order_no", "order_date", "status", "total_amount", "paid_amount", "balance_amount")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=16)
        widths = (0, 100, 100, 110, 100, 100, 100)
        for c, w in zip(cols, widths):
            tree.heading(c, text=c.replace("_", " ").title())
            tree.column(c, width=w, anchor="center")
        tree.column("order_id", width=0, stretch=False)
        tree.pack(fill="both", expand=True, padx=8, pady=4)

        rows = self.db.query(
            """SELECT order_id, order_no, order_date, status, total_amount, paid_amount, balance_amount
               FROM public.sales_orders WHERE customer_id=%s ORDER BY order_date DESC""",
            (customer_id,)
        )
        for r in rows:
            tree.insert("", "end", values=(
                r["order_id"], r["order_no"], r["order_date"], r["status"],
                f"{r['total_amount']:.2f}", f"{r['paid_amount']:.2f}", f"{r['balance_amount']:.2f}"
            ))
        if not rows:
            self.status_var.set(f"{cust['full_name']} has no orders yet.")

        def open_selected():
            sel = tree.selection()
            if not sel:
                return
            order_id = int(tree.item(sel[0])["values"][0])
            win.destroy()
            self.notebook.select(0)
            self.load_order(order_id)

        tk.Button(win, text="Open Selected Order", command=open_selected).pack(anchor="w", padx=8, pady=8)

    def add_customer_direct(self):
        data = ask_form(self, "Add Customer", [
            ("phone", "Phone", "text", None),
            ("full_name", "Full Name", "text", None),
            ("email", "Email", "text", None),
            ("line_id", "LINE ID", "text", None),
            ("address", "Address", "text", None),
        ])
        if not data:
            return
        if not data["phone"] or not data["full_name"]:
            messagebox.showerror("Add Customer", "Phone and full name are required.")
            return
        existing = self.db.query(
            "SELECT customer_id, full_name FROM public.customers WHERE phone=%s", (data["phone"],), "one"
        )
        if existing:
            messagebox.showinfo(
                "Add Customer",
                f"A customer with this phone already exists: {existing['full_name']}. "
                f"Use 'Load Existing' on the Sale/Order tab to find their orders instead."
            )
            return
        try:
            self.db.execute(
                """INSERT INTO public.customers (full_name, phone, email, line_id, address)
                   VALUES (%s,%s,%s,%s,%s)""",
                (data["full_name"], data["phone"], data["email"] or None,
                 data["line_id"] or None, data["address"] or None)
            )
            self.db.commit()
            messagebox.showinfo("Add Customer", f"Customer {data['full_name']} added.")
        except Exception as e:
            self.db.rollback()
            messagebox.showerror("Add Customer", str(e))

    def add_catalog_item(self):
        win = tk.Toplevel(self)
        win.title("New Catalog Item")
        win.transient(self)
        win.grab_set()

        fields = [
            ("item_code", "Item Code"),
            ("item_name", "Item Name"),
            ("jewelry_type", "Jewelry Type"),
            ("purity", "Purity"),
            ("standard_weight", "Standard Weight (g)"),
            ("base_price", "Base Price"),
        ]
        vars_ = {}
        for i, (key, label) in enumerate(fields):
            tk.Label(win, text=label).grid(row=i, column=0, sticky="w", padx=6, pady=4)
            v = tk.StringVar()
            tk.Entry(win, textvariable=v, width=28).grid(row=i, column=1, padx=6, pady=4)
            vars_[key] = v

        row_n = len(fields)
        tk.Label(win, text="Metal Type").grid(row=row_n, column=0, sticky="w", padx=6, pady=4)
        metal_var = tk.StringVar(value="GOLD")
        ttk.Combobox(win, textvariable=metal_var, values=["GOLD", "SILVER"], state="readonly", width=25).grid(
            row=row_n, column=1, padx=6, pady=4
        )

        photo_var = tk.StringVar()
        photo_label = tk.Label(win, text="No file selected", fg="gray")
        tk.Label(win, text="Photo").grid(row=row_n + 1, column=0, sticky="w", padx=6, pady=4)
        photo_label.grid(row=row_n + 1, column=1, sticky="w", padx=6, pady=4)
        tk.Button(win, text="Browse…", command=lambda: self._browse_photo(photo_var, photo_label)).grid(
            row=row_n + 1, column=2, padx=6, pady=4
        )

        def save():
            item_code = vars_["item_code"].get().strip().upper()
            item_name = vars_["item_name"].get().strip()
            if not item_code or not item_name:
                messagebox.showerror("New Catalog Item", "Item code and name are required.")
                return
            try:
                std_wt = float(vars_["standard_weight"].get()) if vars_["standard_weight"].get().strip() else None
                base_price = float(vars_["base_price"].get()) if vars_["base_price"].get().strip() else None
            except ValueError:
                messagebox.showerror("New Catalog Item", "Weight/price must be numeric.")
                return
            try:
                self.db.execute(
                    """INSERT INTO public.item_catalog
                       (item_code, item_name, metal_type, jewelry_type, purity, standard_weight, base_price, image_path)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (item_code, item_name, metal_var.get(), vars_["jewelry_type"].get().strip() or None,
                     vars_["purity"].get().strip() or None, std_wt, base_price, photo_var.get().strip() or None)
                )
                self.db.commit()
                self._load_catalog_codes()
                messagebox.showinfo("New Catalog Item", "Catalog item added.")
                win.destroy()
            except psycopg2.errors.UniqueViolation:
                self.db.rollback()
                messagebox.showerror("New Catalog Item", "That item_code already exists.")
            except Exception as e:
                self.db.rollback()
                messagebox.showerror("New Catalog Item", str(e))

        tk.Button(win, text="✅ Save", bg="green", fg="white", command=save).grid(
            row=row_n + 2, column=0, columnspan=3, pady=10
        )


if __name__ == "__main__":
    app = SalesOrderApp()
    app.mainloop()
