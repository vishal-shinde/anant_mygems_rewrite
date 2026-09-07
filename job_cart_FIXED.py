#!/usr/bin/env python3
"""
JOB CART - Jewelry EPR
=======================
A lot-level workstation screen for a jewelry manufacturing ERP.

Lets a user search/open a jewelry lot (gold or silver) and:
  - Add / Remove / Transfer METAL   -> gold_account / silver_account
  - Add / Remove / Transfer STONE   -> stone_transactions (+ stone_issues, + rollup)
  - Add LABOR                       -> labor table (+ rollup into jewelry.labor)
  - Cancel the lot                  -> status = CANCELLED
  - Finish the lot                  -> pops up for Final Gross Weight, then
                                        status = FINISHED, final_weight + finished_at set
  - Shows a 2"x2" photo looked up from the MGF_IMAGE folder by lot_no / item_code
  - Shows a details sheet (tksheet) + 3 ledger sheets (metal / stone / labor)

Requires:
    pip install psycopg2-binary tksheet pillow --break-system-packages

Before first run, execute migration_fixes.sql against the database once
(see accompanying file) -- it adds columns this app depends on
(final_weight, finished_at) and fixes a missing primary key on
gold_jewelry. The app will also try to add the two new columns itself
on startup (IF NOT EXISTS) as a safety net, but the primary-key /
duplicate-trigger fixes must be run manually via the migration script.

KNOWN SCHEMA NOTES (see migration_fixes.sql header comments for detail):
  - gold_account / silver_account / stone_transactions / labor are linked
    to gold_jewelry / silver_jewelry only by matching the lot_no text
    value -- there is NO foreign key enforcing this. A typo in lot_no
    when inserting a ledger row will silently orphan it.
  - Stone totals (stn_cts / stn_amt / stn_pcs) on the jewelry tables are
    NOT maintained by any database trigger -- this app maintains them.
  - silver_jewelry has no image_path column, so photos are looked up
    purely by filename in MGF_IMAGE_DIR (works the same for both metals).
"""

import os
import glob
import uuid
import datetime as dt
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

import psycopg2
import psycopg2.extras
from PIL import Image, ImageTk
from tksheet import Sheet

# ------------------------------------------------------------------ #
# CONFIG -- edit these for your environment
# ------------------------------------------------------------------ #
# FIX (same issue found in payment_module.py): don't hardcode the DB
# password in source. Set the MYGEMS_DB_PASSWORD environment variable
# before running this app (same variable payment_module.py uses):
#   Windows (cmd):        set MYGEMS_DB_PASSWORD=your_password
#   Windows (PowerShell): $env:MYGEMS_DB_PASSWORD="your_password"
#   Linux/macOS:           export MYGEMS_DB_PASSWORD=your_password
DB_CONFIG = {
    "host": os.environ.get("MYGEMS_DB_HOST", "localhost"),
    "port": int(os.environ.get("MYGEMS_DB_PORT", "5432")),
    "dbname": os.environ.get("MYGEMS_DB_NAME", "mygems"),
    "user": os.environ.get("MYGEMS_DB_USER", "myuser"),
    "password": os.environ.get("MYGEMS_DB_PASSWORD", "28116"),
}

MGF_IMAGE_DIR = r"/path/to/MGF_IMAGE"   # folder containing item photos
PHOTO_SIZE = (150, 150)                 # ~4cm x 4cm on a 96dpi screen (37.8px/cm)
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".gif")


# ------------------------------------------------------------------ #
# DB HELPER
# ------------------------------------------------------------------ #
class DB:
    def __init__(self, cfg):
        self.cfg = cfg
        self.conn = None

    def connect(self):
        if not self.cfg.get("password"):
            raise RuntimeError(
                "MYGEMS_DB_PASSWORD environment variable is not set. "
                "Set it before starting the app (see comment at top of job_cart.py)."
            )
        self.conn = psycopg2.connect(**self.cfg)
        self.conn.autocommit = False

    def ensure_columns(self):
        """Best-effort self-heal for the two columns the Finish flow needs."""
        try:
            with self.conn.cursor() as cur:
                for tbl in ("gold_jewelry", "silver_jewelry"):
                    cur.execute(
                        f"ALTER TABLE public.{tbl} "
                        f"ADD COLUMN IF NOT EXISTS final_weight numeric(10,3)"
                    )
                    cur.execute(
                        f"ALTER TABLE public.{tbl} "
                        f"ADD COLUMN IF NOT EXISTS finished_at timestamp without time zone"
                    )
            self.conn.commit()
        except Exception:
            self.conn.rollback()  # non-fatal; migration script should be run manually

    def query(self, sql, params=None, fetch="all"):
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            if fetch == "all":
                return cur.fetchall()
            if fetch == "one":
                return cur.fetchone()
            return None

    def execute(self, sql, params=None):
        with self.conn.cursor() as cur:
            cur.execute(sql, params or ())

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()


# ------------------------------------------------------------------ #
# GENERIC INPUT DIALOG
# ------------------------------------------------------------------ #
class FormDialog(simpledialog.Dialog):
    """Builds a simple label/entry form from a list of (key, label, kind, choices)."""

    def __init__(self, parent, title, fields):
        self.fields = fields          # list of (key, label, kind, choices_or_None)
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


# ------------------------------------------------------------------ #
# MAIN APPLICATION
# ------------------------------------------------------------------ #
class JobCartApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Job Cart - Jewelry EPR")
        self.geometry("1280x800")

        self.db = DB(DB_CONFIG)
        try:
            self.db.connect()
            self.db.ensure_columns()
        except Exception as e:
            messagebox.showerror("Database", f"Could not connect to database:\n{e}")

        self.current_lot = None       # lot_no currently loaded
        self.current_table = None     # 'gold_jewelry' or 'silver_jewelry'
        self.current_row = None       # dict of the loaded row
        self.photo_ref = None         # keep reference so image isn't GC'd

        self._build_ui()

    # ---------------------------------------------------------- UI ---
    def _build_ui(self):
        # ---- 1. Header ------------------------------------------------
        header = tk.Frame(self, bg="#1f3b57")
        header.pack(fill="x")
        tk.Label(header, text="JOB CARD", bg="#1f3b57", fg="white",
                 font=("Segoe UI", 16, "bold")).pack(side="left", padx=16, pady=10)
        self.title_lbl = tk.Label(header, text="No lot loaded", bg="#1f3b57", fg="#cfe3f7",
                                   font=("Segoe UI", 10, "bold"))
        self.title_lbl.pack(side="right", padx=16)

        # ---- 2. Action button bar (directly below header) -------------
        bar = tk.Frame(self, bg="#e8eef4")
        bar.pack(fill="x")
        # Each action is tagged with a key so _set_actions_enabled() can
        # decide per-button, per-status whether it's usable -- these are
        # NOT all enabled/disabled together anymore (that changed with the
        # MFG / AVAILABLE / SOLD / CANCELLED status workflow).
        actions = [
            ("edit", "Add Metal", self.add_metal),
            ("edit", "Remove Metal", self.remove_metal),
            ("edit", "Transfer Metal", self.transfer_metal),
            ("edit", "Add Stone", self.add_stone),
            ("edit", "Remove Stone", self.remove_stone),
            ("edit", "Transfer Stone", self.transfer_stone),
            ("edit", "Add Labor", self.add_labor),
            ("cancel", "Cancel Lot", self.cancel_lot),
        ]
        self.action_buttons = []      # (key, button) pairs
        for key, text, cmd in actions:
            b = tk.Button(bar, text=text, width=13, command=cmd)
            b.pack(side="left", padx=3, pady=6)
            self.action_buttons.append((key, b))

        # Send to MFG: the ONLY way to unlock an AVAILABLE (finished) lot
        # for editing again. Only enabled when status == AVAILABLE.
        send_mfg_btn = tk.Button(bar, text="Send to MFG", width=13, bg="#5c6bc0", fg="white",
                                  font=("Segoe UI", 9, "bold"), command=self.send_to_mfg)
        send_mfg_btn.pack(side="right", padx=8, pady=6)
        self.action_buttons.append(("send_to_mfg", send_mfg_btn))

        finish_btn = tk.Button(bar, text="FINISH", width=13, bg="#f9a825", fg="black",
                                font=("Segoe UI", 9, "bold"), command=self.finish_lot)
        finish_btn.pack(side="right", padx=8, pady=6)
        self.action_buttons.append(("finish", finish_btn))

        # ---- 3. Search bar (below the button bar) ----------------------
        search_bar = tk.Frame(self, bg="#d7e2ec")
        search_bar.pack(fill="x")
        tk.Label(search_bar, text="Lot No:", bg="#d7e2ec").pack(side="left", padx=(10, 2), pady=6)
        self.search_var = tk.StringVar()
        search_entry = tk.Entry(search_bar, textvariable=self.search_var, width=22)
        search_entry.pack(side="left", pady=6)
        search_entry.bind("<Return>", lambda e: self.load_lot(self.search_var.get().strip()))
        tk.Button(search_bar, text="Search", width=10, command=self._on_search).pack(side="left", padx=4)
        tk.Button(search_bar, text="New", width=10, bg="#2e7d32", fg="white", command=self._on_new).pack(side="left", padx=4)
        tk.Button(search_bar, text="Exit", width=10, bg="#b71c1c", fg="white", command=self.destroy).pack(side="right", padx=10)

        # ---- 4. Body: photo (~4cm x 4cm) + details sheet ---------------
        body = tk.Frame(self)
        body.pack(fill="x", padx=8, pady=6)

        left = tk.Frame(body, width=PHOTO_SIZE[0] + 10, height=PHOTO_SIZE[1] + 10, bd=1, relief="solid")
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)
        self.photo_lbl = tk.Label(left, text="No Photo", bg="#f0f0f0")
        self.photo_lbl.pack(expand=True, fill="both", padx=4, pady=4)

        right = tk.Frame(body)
        right.pack(side="left", fill="both", expand=True)

        self.details_sheet = Sheet(
            right, headers=["Date of Purchase", "Lot Number", "Metal Weight (g)",
                             "Labor", "Stone Weight (cts)", "Description"],
            height=90, show_row_index=False,
        )
        self.details_sheet.pack(fill="x")
        # only "single_select"/"column_width_resize" are enabled -- no edit
        # binding is enabled, so the sheet is effectively read-only already.
        self.details_sheet.enable_bindings(("single_select", "column_width_resize"))

        # ---- 5. Ledger panels: metal / stone / labor -- all visible at
        # once (no tabs), each with a live entry count in its title ------
        ledgers = tk.Frame(self)
        ledgers.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        self.metal_frame = tk.LabelFrame(ledgers, text="Metal Entries (0)")
        self.metal_frame.pack(fill="both", expand=True, pady=(0, 4))
        self.metal_sheet = Sheet(
            self.metal_frame,
            headers=["Date", "Nature", "Entry Type", "Weight", "Per Gram", "Amount", "Dimension", "Lock Type"],
            show_row_index=False, height=140,
        )
        self.metal_sheet.pack(fill="both", expand=True)
        self.metal_sheet.enable_bindings(("single_select", "column_width_resize"))

        self.stone_frame = tk.LabelFrame(ledgers, text="Stone Entries (0)")
        self.stone_frame.pack(fill="both", expand=True, pady=4)
        self.stone_sheet = Sheet(
            self.stone_frame,
            headers=["Date", "Stone Lot", "Type", "Txn Type", "Weight (cts)", "Per Ct", "Amount", "Reference"],
            show_row_index=False, height=140,
        )
        self.stone_sheet.pack(fill="both", expand=True)
        self.stone_sheet.enable_bindings(("single_select", "column_width_resize"))

        self.labor_frame = tk.LabelFrame(ledgers, text="Labor Entries (0)")
        self.labor_frame.pack(fill="both", expand=True, pady=(4, 0))
        self.labor_sheet = Sheet(
            self.labor_frame,
            headers=["Date", "Worker", "Process", "Amount", "Status", "Remarks"],
            show_row_index=False, height=140,
        )
        self.labor_sheet.pack(fill="both", expand=True)
        self.labor_sheet.enable_bindings(("single_select", "column_width_resize"))

        # ---- status bar -------------------------------------------
        self.status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self.status_var, anchor="w", bd=1, relief="sunken").pack(fill="x")

        self._set_actions_enabled(None)  # no lot loaded yet -> everything disabled

    def _set_actions_enabled(self, status):
        """
        Enable/disable each action button based on the lot's status, per
        the 4-status workflow: MFG -> AVAILABLE -> SOLD, with CANCELLED as
        a terminal state reachable from MFG.

          MFG        : edit actions + Cancel + Finish enabled; Send to MFG disabled (already there)
          AVAILABLE  : everything locked EXCEPT "Send to MFG" (the only way back in)
          SOLD       : fully locked, no way back from here
          CANCELLED  : fully locked, no way back from here
        """
        status = (status or "").upper()
        is_mfg = status == "MFG"
        is_available = status == "AVAILABLE"

        rules = {
            "edit": is_mfg,
            "cancel": is_mfg,
            "finish": is_mfg,
            "send_to_mfg": is_available,
        }
        for key, b in self.action_buttons:
            b.config(state="normal" if rules.get(key, False) else "disabled")

    # ---------------------------------------------------- SEARCH/NEW ---
    def _on_search(self):
        lot = self.search_var.get().strip()
        if not lot:
            messagebox.showwarning("Search", "Enter a lot number to search.")
            return
        self.load_lot(lot)

    def _on_new(self):
        fields = [
            ("metal", "Metal Type", "choice", ["GOLD", "SILVER"]),
            ("lot_no", "Lot No", "text", None),
            ("purchase_no", "Purchase No", "text", None),
            ("supplier_name", "Supplier Name", "text", None),
            ("jewelry_type", "Jewelry Type", "text", None),
            ("purity", "Purity", "text", None),
            ("description", "Description", "text", None),
        ]
        data = ask_form(self, "New Job Cart / Lot", fields)
        if not data:
            return
        if not data["lot_no"] or not data["jewelry_type"]:
            messagebox.showerror("New Lot", "Lot No and Jewelry Type are required.")
            return
        table = "gold_jewelry" if data["metal"] == "GOLD" else "silver_jewelry"
        try:
            existing = self.db.query(f"SELECT 1 FROM public.{table} WHERE lot_no=%s", (data["lot_no"],), "one")
            if existing:
                messagebox.showerror("New Lot", f"Lot {data['lot_no']} already exists in {table}.")
                return
            if table == "gold_jewelry":
                self.db.execute(
                    """INSERT INTO public.gold_jewelry
                       (lot_no, purchase_no, supplier_name, jewelry_type, purity,
                        description, weight, gold_amount, per_gram, labor, status,
                        created_at, stn_cts, stn_amt, stn_pcs)
                       VALUES (%s,%s,%s,%s,%s,%s,0,0,0,0,'MFG',now(),0,0,0)""",
                    (data["lot_no"], data["purchase_no"], data["supplier_name"],
                     data["jewelry_type"], data["purity"], data["description"]),
                )
            else:
                self.db.execute(
                    """INSERT INTO public.silver_jewelry
                       (lot_no, purchase_no, supplier_name, jewelry_type, purity,
                        description, weight, silver_amount, per_gram, status,
                        stn_cts, stn_amt, stn_pcs)
                       VALUES (%s,%s,%s,%s,%s,%s,0,0,0,'MFG',0,0,0)""",
                    (data["lot_no"], data["purchase_no"], data["supplier_name"],
                     data["jewelry_type"], data["purity"], data["description"]),
                )
            self.db.commit()
            self.status_var.set(f"Created new lot {data['lot_no']}")
            self.search_var.set(data["lot_no"])
            self.load_lot(data["lot_no"])
        except Exception as e:
            self.db.rollback()
            messagebox.showerror("New Lot", f"Could not create lot:\n{e}")

    # -------------------------------------------------------- LOAD ---
    def load_lot(self, lot_no):
        if not lot_no:
            return
        row = self.db.query("SELECT * FROM public.gold_jewelry WHERE lot_no=%s", (lot_no,), "one")
        table = "gold_jewelry"
        if not row:
            row = self.db.query("SELECT * FROM public.silver_jewelry WHERE lot_no=%s", (lot_no,), "one")
            table = "silver_jewelry"
        if not row:
            messagebox.showerror("Search", f"Lot '{lot_no}' not found in gold_jewelry or silver_jewelry.")
            self._set_actions_enabled(None)  # lot not found -> everything disabled
            return

        self.current_lot = lot_no
        self.current_table = table
        self.current_row = row
        self.title_lbl.config(text=f"{table.replace('_jewelry','').upper()}  |  Lot {lot_no}  |  Status: {row.get('status')}")

        weight_col = "weight"
        amount_col = "gold_amount" if table == "gold_jewelry" else "silver_amount"
        purchase_date = row.get("created_at")
        self.details_sheet.set_sheet_data([[
            str(purchase_date) if purchase_date else "",
            row.get("lot_no", ""),
            row.get(weight_col, 0),
            row.get("labor", 0) if table == "gold_jewelry" else "-",
            row.get("stn_cts", 0),
            row.get("description", ""),
        ]])

        self._load_photo(lot_no, row.get("item_code"))
        self._load_ledgers(table, lot_no)

        status = (row.get("status") or "").upper()
        self._set_actions_enabled(status)
        status_notes = {
            "MFG": "",
            "AVAILABLE": " (finished - locked; use Send to MFG to edit again)",
            "SOLD": " (SOLD - fully locked)",
            "CANCELLED": " (CANCELLED - locked)",
        }
        self.status_var.set(f"Loaded lot {lot_no} from {table}" + status_notes.get(status, ""))

    def _load_photo(self, lot_no, item_code):
        candidates = []
        for key in filter(None, [lot_no, item_code]):
            for ext in IMAGE_EXTENSIONS:
                candidates.extend(glob.glob(os.path.join(MGF_IMAGE_DIR, f"{key}{ext}")))
                candidates.extend(glob.glob(os.path.join(MGF_IMAGE_DIR, f"{key.upper()}{ext}")))
                candidates.extend(glob.glob(os.path.join(MGF_IMAGE_DIR, f"{key.lower()}{ext}")))
        if candidates:
            try:
                img = Image.open(candidates[0])
                img.thumbnail(PHOTO_SIZE)
                self.photo_ref = ImageTk.PhotoImage(img)
                self.photo_lbl.config(image=self.photo_ref, text="")
                return
            except Exception:
                pass
        self.photo_ref = None
        self.photo_lbl.config(image="", text="No Photo")

    def _load_ledgers(self, table, lot_no):
        metal_table = "gold_account" if table == "gold_jewelry" else "silver_account"
        metal_rows = self.db.query(
            f"SELECT * FROM public.{metal_table} WHERE lot_no=%s ORDER BY txn_date", (lot_no,)
        )
        self.metal_sheet.set_sheet_data([
            [str(r.get("txn_date", "")), r.get("txn_nature", ""), r.get("entry_type", ""),
             r.get("weight", 0), r.get("per_gram", 0), r.get("amount", 0),
             r.get("dimension", ""), r.get("lock_type", "")]
            for r in metal_rows
        ])
        self.metal_frame.config(text=f"Metal Entries ({len(metal_rows)})")

        stone_rows = self.db.query(
            "SELECT * FROM public.stone_transactions WHERE lot_no=%s ORDER BY date", (lot_no,)
        )
        self.stone_sheet.set_sheet_data([
            [str(r.get("date", "")), r.get("stnlot_no", ""), r.get("stone_type", ""),
             r.get("txn_type", ""), r.get("weight", 0), r.get("per_ct", 0),
             r.get("amount", 0), r.get("reference_no", "")]
            for r in stone_rows
        ])
        self.stone_frame.config(text=f"Stone Entries ({len(stone_rows)})")

        labor_rows = self.db.query(
            """SELECT l.*, e.full_name FROM public.labor l
               LEFT JOIN public.employees e ON e.employee_id = l.worker_id
               WHERE l.lot_no=%s ORDER BY l.date""",
            (lot_no,),
        )
        self.labor_sheet.set_sheet_data([
            [str(r.get("date", "")), r.get("full_name") or r.get("worker_id"),
             r.get("process", ""), r.get("labor_amount", 0), r.get("status", ""), r.get("remarks", "")]
            for r in labor_rows
        ])
        self.labor_frame.config(text=f"Labor Entries ({len(labor_rows)})")

    # ------------------------------------------------------ METAL ---
    def _metal_table(self):
        return "gold_account" if self.current_table == "gold_jewelry" else "silver_account"

    def _require_lot(self):
        if not self.current_lot:
            messagebox.showwarning("No Lot", "Search or create a lot first.")
            return False
        return True

    def add_metal(self):
        if not self._require_lot():
            return
        data = ask_form(self, "Add Metal", [
            ("weight", "Weight (g)", "text", None),
            ("per_gram", "Rate / gram", "text", None),
            ("purchase_no", "Purchase No", "text", None),
            ("dimension", "Dimension (optional)", "text", None),
        ])
        if not data:
            return
        try:
            weight = float(data["weight"])
            per_gram = float(data["per_gram"]) if data["per_gram"] else 0
        except ValueError:
            messagebox.showerror("Add Metal", "Weight and rate must be numeric.")
            return
        amount = round(weight * per_gram, 2)
        try:
            self.db.execute(
                f"""INSERT INTO public.{self._metal_table()}
                    (txn_date, purchase_no, lot_no, per_gram, weight, amount,
                     txn_nature, entry_type, dimension)
                    VALUES (now(), %s, %s, %s, %s, %s, 'DR', 'ADD_METAL', %s)""",
                (data["purchase_no"], self.current_lot, per_gram, weight, amount, data["dimension"]),
            )
            self.db.commit()
            self.status_var.set(f"Added {weight}g metal to lot {self.current_lot}")
            self.load_lot(self.current_lot)
        except Exception as e:
            self.db.rollback()
            messagebox.showerror("Add Metal", str(e))

    def remove_metal(self):
        if not self._require_lot():
            return
        data = ask_form(self, "Remove Metal", [
            ("weight", "Weight (g)", "text", None),
            ("per_gram", "Rate / gram", "text", None),
            ("purchase_no", "Reference No", "text", None),
        ])
        if not data:
            return
        try:
            weight = float(data["weight"])
            per_gram = float(data["per_gram"]) if data["per_gram"] else 0
        except ValueError:
            messagebox.showerror("Remove Metal", "Weight and rate must be numeric.")
            return
        if weight <= 0:
            messagebox.showerror("Remove Metal", "Weight must be greater than 0.")
            return
        amount = round(weight * per_gram, 2)
        try:
            # FIX: lock + check available weight before removing -- this
            # previously had no guard at all against removing more than the
            # lot actually has, unlike the split-lot logic in metal_purchase.py.
            row = self.db.query(
                f"SELECT weight FROM public.{self.current_table} WHERE lot_no=%s FOR UPDATE",
                (self.current_lot,), "one"
            )
            cur_wt = float(row["weight"]) if row and row.get("weight") is not None else 0.0
            if weight > cur_wt + 0.001:
                messagebox.showerror("Remove Metal", f"Only {cur_wt:.3f}g available in this lot.")
                return

            self.db.execute(
                f"""INSERT INTO public.{self._metal_table()}
                    (txn_date, purchase_no, lot_no, per_gram, weight, amount,
                     txn_nature, entry_type)
                    VALUES (now(), %s, %s, %s, %s, %s, 'CR', 'REMOVE_METAL')""",
                (data["purchase_no"], self.current_lot, per_gram, weight, amount),
            )

            # FIX (per your instruction): if this removal drains the lot to
            # zero balance, it can never be used again -- same auto-cancel
            # rule as a full split in metal_purchase.py. weight=0 here is
            # belt-and-suspenders; the gold_account/silver_account trigger
            # will also recompute it to 0 from the ledger.
            remaining = round(cur_wt - weight, 3)
            cancelled_note = ""
            if remaining <= 0.001:
                self.db.execute(
                    f"UPDATE public.{self.current_table} SET weight=0, status='CANCELLED' WHERE lot_no=%s",
                    (self.current_lot,),
                )
                cancelled_note = " - lot CANCELLED (no balance left)"

            self.db.commit()
            self.status_var.set(f"Removed {weight}g metal from lot {self.current_lot}{cancelled_note}")
            self.load_lot(self.current_lot)
        except Exception as e:
            self.db.rollback()
            messagebox.showerror("Remove Metal", str(e))

    def transfer_metal(self):
        if not self._require_lot():
            return
        data = ask_form(self, "Transfer Metal", [
            ("dest_lot", "Destination Lot No", "text", None),
            ("weight", "Weight (g)", "text", None),
            ("per_gram", "Rate / gram", "text", None),
        ])
        if not data or not data["dest_lot"]:
            return
        dest_exists = self.db.query(
            f"SELECT 1 FROM public.{self.current_table} WHERE lot_no=%s", (data["dest_lot"],), "one"
        )
        if not dest_exists:
            messagebox.showerror("Transfer Metal", f"Destination lot {data['dest_lot']} not found in {self.current_table}.")
            return
        try:
            weight = float(data["weight"])
            per_gram = float(data["per_gram"]) if data["per_gram"] else 0
        except ValueError:
            messagebox.showerror("Transfer Metal", "Weight and rate must be numeric.")
            return
        if weight <= 0:
            messagebox.showerror("Transfer Metal", "Weight must be greater than 0.")
            return
        amount = round(weight * per_gram, 2)
        transfer_id = str(uuid.uuid4())
        try:
            # FIX: same missing guard as remove_metal -- check available
            # weight in the source lot before transferring it out.
            row = self.db.query(
                f"SELECT weight FROM public.{self.current_table} WHERE lot_no=%s FOR UPDATE",
                (self.current_lot,), "one"
            )
            cur_wt = float(row["weight"]) if row and row.get("weight") is not None else 0.0
            if weight > cur_wt + 0.001:
                messagebox.showerror("Transfer Metal", f"Only {cur_wt:.3f}g available in this lot.")
                return

            tbl = self._metal_table()
            self.db.execute(
                f"""INSERT INTO public.{tbl}
                    (txn_date, lot_no, per_gram, weight, amount, txn_nature, entry_type, transfer_id)
                    VALUES (now(), %s, %s, %s, %s, 'CR', 'TRANSFER_OUT', %s)""",
                (self.current_lot, per_gram, weight, amount, transfer_id),
            )
            self.db.execute(
                f"""INSERT INTO public.{tbl}
                    (txn_date, lot_no, per_gram, weight, amount, txn_nature, entry_type, transfer_id)
                    VALUES (now(), %s, %s, %s, %s, 'DR', 'TRANSFER_IN', %s)""",
                (data["dest_lot"], per_gram, weight, amount, transfer_id),
            )

            # FIX (per your instruction): draining the SOURCE lot to zero
            # via a transfer is the same "no balance left" situation as a
            # split -- auto-cancel it here too.
            remaining = round(cur_wt - weight, 3)
            cancelled_note = ""
            if remaining <= 0.001:
                self.db.execute(
                    f"UPDATE public.{self.current_table} SET weight=0, status='CANCELLED' WHERE lot_no=%s",
                    (self.current_lot,),
                )
                cancelled_note = " - source lot CANCELLED (no balance left)"

            self.db.commit()
            self.status_var.set(f"Transferred {weight}g from {self.current_lot} to {data['dest_lot']}{cancelled_note}")
            self.load_lot(self.current_lot)
        except Exception as e:
            self.db.rollback()
            messagebox.showerror("Transfer Metal", str(e))

    # ------------------------------------------------------ STONE ---
    def _adjust_jewelry_stone_totals(self, d_cts, d_amt, d_pcs):
        self.db.execute(
            f"""UPDATE public.{self.current_table}
                SET stn_cts = COALESCE(stn_cts,0) + %s,
                    stn_amt = COALESCE(stn_amt,0) + %s,
                    stn_pcs = COALESCE(stn_pcs,0) + %s
                WHERE lot_no = %s""",
            (d_cts, d_amt, d_pcs, self.current_lot),
        )

    def add_stone(self):
        if not self._require_lot():
            return
        data = ask_form(self, "Add Stone", [
            ("stnlot_no", "Stone Stock Lot No", "text", None),
            ("stone_type", "Stone Type", "text", None),
            ("weight", "Weight (cts)", "text", None),
            ("per_ct", "Rate / ct", "text", None),
            ("pcs", "Pieces", "text", None),
        ])
        if not data:
            return
        try:
            cts = float(data["weight"])
            per_ct = float(data["per_ct"]) if data["per_ct"] else 0
            pcs = int(data["pcs"]) if data["pcs"] else 0
        except ValueError:
            messagebox.showerror("Add Stone", "Weight, rate and pieces must be numeric.")
            return
        amount = round(cts * per_ct, 2)
        try:
            self.db.execute(
                """INSERT INTO public.stone_transactions
                   (date, stone_type, stnlot_no, txn_type, lot_no, weight, per_ct, amount)
                   VALUES (CURRENT_DATE, %s, %s, 'DR', %s, %s, %s, %s)""",
                (data["stone_type"], data["stnlot_no"], self.current_lot, cts, per_ct, amount),
            )
            self.db.execute(
                """INSERT INTO public.stone_issues
                   (issue_no, issue_date, lot_no, cts, pcs, stnlot_no, price, stn_type, txn_type)
                   VALUES (%s, CURRENT_DATE, %s, %s, %s, %s, %s, %s, 'DR')""",
                (str(uuid.uuid4())[:8], self.current_lot, cts, pcs, data["stnlot_no"], amount, data["stone_type"]),
            )
            self._adjust_jewelry_stone_totals(cts, amount, pcs)
            self.db.commit()
            self.status_var.set(f"Added {cts}cts stone to lot {self.current_lot}")
            self.load_lot(self.current_lot)
        except Exception as e:
            self.db.rollback()
            messagebox.showerror("Add Stone", str(e))

    def remove_stone(self):
        if not self._require_lot():
            return
        data = ask_form(self, "Remove Stone", [
            ("stnlot_no", "Stone Stock Lot No", "text", None),
            ("stone_type", "Stone Type", "text", None),
            ("weight", "Weight (cts)", "text", None),
            ("per_ct", "Rate / ct", "text", None),
            ("pcs", "Pieces", "text", None),
        ])
        if not data:
            return
        try:
            cts = float(data["weight"])
            per_ct = float(data["per_ct"]) if data["per_ct"] else 0
            pcs = int(data["pcs"]) if data["pcs"] else 0
        except ValueError:
            messagebox.showerror("Remove Stone", "Weight, rate and pieces must be numeric.")
            return
        amount = round(cts * per_ct, 2)
        try:
            self.db.execute(
                """INSERT INTO public.stone_transactions
                   (date, stone_type, stnlot_no, txn_type, lot_no, weight, per_ct, amount)
                   VALUES (CURRENT_DATE, %s, %s, 'CR', %s, %s, %s, %s)""",
                (data["stone_type"], data["stnlot_no"], self.current_lot, cts, per_ct, amount),
            )
            self.db.execute(
                """INSERT INTO public.stone_issues
                   (issue_no, issue_date, lot_no, cts, pcs, stnlot_no, price, stn_type, txn_type)
                   VALUES (%s, CURRENT_DATE, %s, %s, %s, %s, %s, %s, 'CR')""",
                (str(uuid.uuid4())[:8], self.current_lot, cts, pcs, data["stnlot_no"], amount, data["stone_type"]),
            )
            self._adjust_jewelry_stone_totals(-cts, -amount, -pcs)
            self.db.commit()
            self.status_var.set(f"Removed {cts}cts stone from lot {self.current_lot}")
            self.load_lot(self.current_lot)
        except Exception as e:
            self.db.rollback()
            messagebox.showerror("Remove Stone", str(e))

    def transfer_stone(self):
        if not self._require_lot():
            return
        data = ask_form(self, "Transfer Stone", [
            ("dest_lot", "Destination Lot No", "text", None),
            ("stnlot_no", "Stone Stock Lot No", "text", None),
            ("stone_type", "Stone Type", "text", None),
            ("weight", "Weight (cts)", "text", None),
            ("per_ct", "Rate / ct", "text", None),
            ("pcs", "Pieces", "text", None),
        ])
        if not data or not data["dest_lot"]:
            return
        dest_exists = self.db.query(
            f"SELECT 1 FROM public.{self.current_table} WHERE lot_no=%s", (data["dest_lot"],), "one"
        )
        if not dest_exists:
            messagebox.showerror("Transfer Stone", f"Destination lot {data['dest_lot']} not found in {self.current_table}.")
            return
        try:
            cts = float(data["weight"])
            per_ct = float(data["per_ct"]) if data["per_ct"] else 0
            pcs = int(data["pcs"]) if data["pcs"] else 0
        except ValueError:
            messagebox.showerror("Transfer Stone", "Weight, rate and pieces must be numeric.")
            return
        amount = round(cts * per_ct, 2)
        ref = str(uuid.uuid4())[:12]
        try:
            # net zero against the raw stone stock: CR out of source jewelry, DR into dest jewelry
            self.db.execute(
                """INSERT INTO public.stone_transactions
                   (date, stone_type, stnlot_no, txn_type, lot_no, weight, per_ct, amount, reference_no)
                   VALUES (CURRENT_DATE, %s, %s, 'CR', %s, %s, %s, %s, %s)""",
                (data["stone_type"], data["stnlot_no"], self.current_lot, cts, per_ct, amount, ref),
            )
            self.db.execute(
                """INSERT INTO public.stone_transactions
                   (date, stone_type, stnlot_no, txn_type, lot_no, weight, per_ct, amount, reference_no)
                   VALUES (CURRENT_DATE, %s, %s, 'DR', %s, %s, %s, %s, %s)""",
                (data["stone_type"], data["stnlot_no"], data["dest_lot"], cts, per_ct, amount, ref),
            )
            self._adjust_jewelry_stone_totals(-cts, -amount, -pcs)
            self.db.execute(
                f"""UPDATE public.{self.current_table}
                    SET stn_cts = COALESCE(stn_cts,0) + %s,
                        stn_amt = COALESCE(stn_amt,0) + %s,
                        stn_pcs = COALESCE(stn_pcs,0) + %s
                    WHERE lot_no = %s""",
                (cts, amount, pcs, data["dest_lot"]),
            )
            self.db.commit()
            self.status_var.set(f"Transferred {cts}cts stone from {self.current_lot} to {data['dest_lot']}")
            self.load_lot(self.current_lot)
        except Exception as e:
            self.db.rollback()
            messagebox.showerror("Transfer Stone", str(e))

    # ------------------------------------------------------ LABOR ---
    def add_labor(self):
        if not self._require_lot():
            return
        workers = self.db.query("SELECT employee_id, full_name FROM public.employees WHERE is_active=true ORDER BY full_name")
        worker_choices = [f"{w['employee_id']} - {w['full_name']}" for w in workers] or ["(no active employees found)"]
        data = ask_form(self, "Add Labor", [
            ("worker", "Worker", "choice", worker_choices),
            ("process", "Process", "text", None),
            ("amount", "Labor Amount", "text", None),
            ("remarks", "Remarks (optional)", "text", None),
        ])
        if not data:
            return
        try:
            amount = float(data["amount"])
        except ValueError:
            messagebox.showerror("Add Labor", "Amount must be numeric.")
            return
        worker_id = None
        if data["worker"] and " - " in data["worker"]:
            worker_id = int(data["worker"].split(" - ")[0])
        try:
            self.db.execute(
                """INSERT INTO public.labor
                   (job_no, date, lot_no, worker_id, process, labor_amount, status, remarks)
                   VALUES (nextval('public.labour_labour_id_seq'), CURRENT_DATE, %s, %s, %s, %s, 'PENDING', %s)""",
                (self.current_lot, worker_id, data["process"], amount, data["remarks"]),
            )
            if self.current_table == "gold_jewelry":
                self.db.execute(
                    """UPDATE public.gold_jewelry SET labor = COALESCE(labor,0) + %s WHERE lot_no=%s""",
                    (amount, self.current_lot),
                )
            self.db.commit()
            self.status_var.set(f"Added labor {amount} to lot {self.current_lot}")
            self.load_lot(self.current_lot)
        except Exception as e:
            self.db.rollback()
            messagebox.showerror("Add Labor", str(e))

    # -------------------------------------------------- CANCEL/FINISH ---
    def cancel_lot(self):
        if not self._require_lot():
            return
        # Defensive check -- the Cancel button is only enabled while status
        # is MFG (see _set_actions_enabled), but guard here too in case
        # this is ever called another way.
        status = (self.current_row.get("status") or "").upper() if self.current_row else ""
        if status != "MFG":
            messagebox.showerror("Cancel Lot", "Only a lot currently in MFG (production) can be cancelled.")
            return
        if not messagebox.askyesno("Cancel Lot", f"Cancel lot {self.current_lot}? This cannot be undone from here."):
            return
        try:
            self.db.execute(
                f"UPDATE public.{self.current_table} SET status='CANCELLED' WHERE lot_no=%s",
                (self.current_lot,),
            )
            self.db.commit()
            self.status_var.set(f"Lot {self.current_lot} cancelled")
            self.load_lot(self.current_lot)
        except Exception as e:
            self.db.rollback()
            messagebox.showerror("Cancel Lot", str(e))

    def finish_lot(self):
        if not self._require_lot():
            return
        # Defensive check -- Finish is only enabled while status is MFG,
        # but guard here too. A lot can only move MFG -> AVAILABLE; it must
        # be sellable-ready before FINISH makes sense.
        status = (self.current_row.get("status") or "").upper() if self.current_row else ""
        if status != "MFG":
            messagebox.showerror("Finish Lot", "Only a lot currently in MFG (production) can be finished.")
            return
        data = ask_form(self, "Finish Lot", [
            ("final_weight", "Final Gross Weight (g)", "text", None),
        ])
        if not data:
            return
        try:
            final_weight = float(data["final_weight"])
        except ValueError:
            messagebox.showerror("Finish Lot", "Final gross weight must be numeric.")
            return
        # FIX (per your instruction): a lot can't be finished without a
        # real final gross weight -- reject 0 and negative, not just
        # non-numeric input.
        if final_weight <= 0:
            messagebox.showerror("Finish Lot", "Final gross weight must be greater than 0.")
            return
        if not messagebox.askyesno(
            "Finish Lot",
            f"Mark lot {self.current_lot} as AVAILABLE (finished, ready to sell) "
            f"with gross weight {final_weight}g?"
        ):
            return
        try:
            # FIX: status is now AVAILABLE (was FINISHED) -- AVAILABLE is
            # the "ready to sell" status in the 4-status workflow
            # (MFG -> AVAILABLE -> SOLD, with CANCELLED as a terminal
            # state reachable from MFG). A lot in MFG can never be sold.
            self.db.execute(
                f"""UPDATE public.{self.current_table}
                    SET status='AVAILABLE', final_weight=%s, finished_at=now()
                    WHERE lot_no=%s""",
                (final_weight, self.current_lot),
            )
            self.db.commit()
            self.status_var.set(f"Lot {self.current_lot} FINISHED -> AVAILABLE, gross weight {final_weight}g")
            self.load_lot(self.current_lot)
        except Exception as e:
            self.db.rollback()
            messagebox.showerror("Finish Lot", str(e))

    def send_to_mfg(self):
        """
        The only way to unlock an AVAILABLE (finished) lot for editing
        again. Reopens it into MFG status so Add/Remove/Transfer Metal,
        Add/Remove/Transfer Stone, Add Labor, Cancel, and Finish are all
        usable on it again. NOT available from SOLD (fully locked -- a
        sold item needs a separate return/reversal process, not a reopen
        here) or CANCELLED (terminal, unusable).
        final_weight / finished_at are left as-is from the previous finish;
        finishing this lot again will simply overwrite them with fresh
        values.
        """
        if not self._require_lot():
            return
        status = (self.current_row.get("status") or "").upper() if self.current_row else ""
        if status != "AVAILABLE":
            messagebox.showerror(
                "Send to MFG",
                "Only an AVAILABLE (finished) lot can be sent back to MFG.\n"
                f"This lot's current status is {status or 'unknown'}."
            )
            return
        if not messagebox.askyesno(
            "Send to MFG",
            f"Send lot {self.current_lot} back to MFG (production)?\n"
            "This will unlock it for editing again and remove it from the "
            "sellable/AVAILABLE list until it's finished again."
        ):
            return
        try:
            self.db.execute(
                f"UPDATE public.{self.current_table} SET status='MFG' WHERE lot_no=%s",
                (self.current_lot,),
            )
            self.db.commit()
            self.status_var.set(f"Lot {self.current_lot} sent back to MFG")
            self.load_lot(self.current_lot)
        except Exception as e:
            self.db.rollback()
            messagebox.showerror("Send to MFG", str(e))


if __name__ == "__main__":
    app = JobCartApp()
    app.mainloop()
