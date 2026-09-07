import tkinter as tk
from tkinter import ttk, messagebox
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime
from contextlib import closing

import psycopg2
import psycopg2.extras

from db import get_connection


# If your stone_account table stores current balance, keep True.
# If balance is calculated only from stone_transaction, set False.
UPDATE_STONE_ACCOUNT_BALANCE = True

# If True, To Lot per cts price will be updated using weighted average.
UPDATE_TO_LOT_AVG_PRICE = True

CHECK_FROM_LOT_AVAILABLE_WEIGHT = True

WEIGHT_Q = Decimal("0.001")
MONEY_Q = Decimal("0.01")
RATE_Q = Decimal("0.01")


def to_decimal(value, default="0"):
    if value is None:
        if default is None:
            return None
        return Decimal(str(default))

    if isinstance(value, Decimal):
        return value

    return Decimal(str(value))


def parse_weight(weight_text):
    text = str(weight_text).strip()

    if not text:
        raise ValueError("Please enter weight.")

    try:
        weight = Decimal(text)
    except InvalidOperation:
        raise ValueError("Weight must be a valid number.")

    if weight <= 0:
        raise ValueError("Weight must be greater than zero.")

    weight = weight.quantize(WEIGHT_Q, rounding=ROUND_HALF_UP)

    if weight <= 0:
        raise ValueError("Weight is too small. Minimum allowed is 0.001.")

    return weight


def fmt_num(value, places=2):
    if value is None:
        return ""

    try:
        d = to_decimal(value)
        return f"{d:,.{places}f}"
    except Exception:
        return str(value)


class StoneDB:
    def connect(self):
        return get_connection()
    
    def generate_reference_no(self, cur, trans_date):
        date_str = trans_date.strftime("%Y%m%d")
        prefix = f"TR{date_str}/"

        cur.execute(
            """
            SELECT reference_no
            FROM stone_transactions
            WHERE reference_no LIKE %s
            ORDER BY reference_no DESC
            LIMIT 1
            """,
            (prefix + "%",)
        )

        row = cur.fetchone()

        if row and row["reference_no"]:
            last_ref = row["reference_no"]
            last_no = int(last_ref.split("/")[-1])
            next_no = last_no + 1
        else:
            next_no = 1

        return f"{prefix}{next_no:02d}"

    def search_lots(self, search_text=""):
        search_text = str(search_text or "").strip()

        sql = """
            SELECT 
                stnlot_no::text AS lot_no,
                cts AS weight,
                per_ct AS per_cts_price
            FROM stone_account
            WHERE (%s = '' OR stnlot_no::text ILIKE %s)
            ORDER BY stnlot_no
            LIMIT 100
        """

        with closing(self.connect()) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (search_text, f"%{search_text}%"))
                return cur.fetchall()

    def get_lot(self, lot_no):
        lot_no = str(lot_no or "").strip()

        if not lot_no:
            return None

        sql = """
            SELECT 
                stnlot_no::text AS lot_no,
                cts AS weight,
                per_ct AS per_cts_price
            FROM stone_account
            WHERE LOWER(stnlot_no::text) = LOWER(%s)
            LIMIT 1
        """

        with closing(self.connect()) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                now = datetime.now()
                reference_no = self.generate_reference_no(cur, now)
                cur.execute(sql, (lot_no,))
                return cur.fetchone()

    def create_transfer(self, from_lot, to_lot, weight_text):
        from_lot = str(from_lot or "").strip().upper()
        to_lot = str(to_lot or "").strip().upper()

        if not from_lot:
            raise ValueError("Please enter From Lot.")

        if not to_lot:
            raise ValueError("Please enter To Lot.")

        if from_lot.lower() == to_lot.lower():
            raise ValueError("From Lot and To Lot cannot be the same.")

        transfer_weight = parse_weight(weight_text)

        now = datetime.now()
        
        reference_no = None

        new_from_weight = None
        new_to_weight = None
        new_to_rate = None

        with closing(self.connect()) as conn:
            with conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

                    cur.execute(
                        """
                        SELECT 
                            stnlot_no::text AS lot_no,
                            stone_type,
                            cts AS weight,
                            per_ct AS per_cts_price
                        FROM stone_account
                        WHERE LOWER(stnlot_no::text) IN (LOWER(%s), LOWER(%s))
                        FOR UPDATE
                        """,
                        (from_lot, to_lot),
                    )

                    rows = cur.fetchall()
                    lot_map = {row["lot_no"].lower(): row for row in rows}

                    from_row = lot_map.get(from_lot.lower())
                    to_row = lot_map.get(to_lot.lower())

                    missing = []

                    if from_row is None:
                        missing.append(f"From Lot '{from_lot}'")

                    if to_row is None:
                        missing.append(f"To Lot '{to_lot}'")

                    if missing:
                        raise ValueError(
                            "Lot not found in stone_account: " + ", ".join(missing)
                        )

                    if from_row["stone_type"] != to_row["stone_type"]:
                        raise ValueError(
                            "Stone type mismatch between From Lot and To Lot."
                        )
                    from_balance = to_decimal(from_row["weight"], "0")
                    to_balance = to_decimal(to_row["weight"], "0")

                    transfer_rate = to_decimal(from_row["per_cts_price"], None)

                    if transfer_rate is None or transfer_rate <= 0:
                        raise ValueError("From Lot per cts price is missing or zero.")

                    if CHECK_FROM_LOT_AVAILABLE_WEIGHT and from_balance < transfer_weight:
                        raise ValueError(
                            f"Insufficient weight in From Lot.\n\n"
                            f"Available: {fmt_num(from_balance, 3)} cts\n"
                            f"Transfer : {fmt_num(transfer_weight, 3)} cts"
                        )

                    transfer_amount = (transfer_weight * transfer_rate).quantize(
                        MONEY_Q,
                        rounding=ROUND_HALF_UP
                    )

                    insert_sql = """
                        INSERT INTO stone_transactions
                        (
                            reference_no,
                            date,
                            stone_type,
                            stnlot_no,
                            txn_type,
                            weight,
                            per_ct,
                            amount,
                            description
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """

                    # CR entry in From Lot
                    cur.execute(
                        insert_sql,
                        (
                            reference_no,
                            now,
                            from_row["stone_type"],
                            from_row["lot_no"],
                            "CR",
                            transfer_weight,
                            transfer_rate,
                            transfer_amount,
                            f"Stone lot mixing transfer to {to_row['lot_no']}",
                        ),
                    )

                    # DR entry in To Lot
                    cur.execute(
                        insert_sql,
                        (
                            reference_no,
                            now,
                            from_row["stone_type"],
                            to_row["lot_no"],
                            "DR",
                            transfer_weight,
                            transfer_rate,
                            transfer_amount,
                            f"Stone lot mixing transfer from {from_row['lot_no']}",
                        ),
                    )

                    if UPDATE_STONE_ACCOUNT_BALANCE:
                        new_from_weight = (from_balance - transfer_weight).quantize(
                            WEIGHT_Q,
                            rounding=ROUND_HALF_UP
                        )

                        new_to_weight = (to_balance + transfer_weight).quantize(
                            WEIGHT_Q,
                            rounding=ROUND_HALF_UP
                        )

                        cur.execute(
                            """
                            UPDATE stone_account
                            SET cts = %s
                            WHERE LOWER(stnlot_no::text) = LOWER(%s)
                            """,
                            (new_from_weight, from_row["lot_no"]),
                        )

                        if UPDATE_TO_LOT_AVG_PRICE:
                            old_to_rate = to_decimal(to_row["per_cts_price"], "0")

                            old_to_value = to_balance * old_to_rate
                            incoming_value = transfer_weight * transfer_rate

                            if new_to_weight > 0:
                                new_to_rate = (
                                    (old_to_value + incoming_value) / new_to_weight
                                ).quantize(RATE_Q, rounding=ROUND_HALF_UP)
                            else:
                                new_to_rate = Decimal("0.00")

                            cur.execute(
                                """
                                UPDATE stone_account
                                SET cts = %s,
                                    per_ct = %s
                                WHERE LOWER(stnlot_no::text) = LOWER(%s)
                                """,
                                (new_to_weight, new_to_rate, to_row["lot_no"]),
                            )
                        else:
                            cur.execute(
                                """
                                UPDATE stone_account
                                SET cts = %s
                                WHERE LOWER(stnlot_no::text) = LOWER(%s)
                                """,
                                (new_to_weight, to_row["lot_no"]),
                            )

        return {
            "reference_no": reference_no,
            "date": now,
            "from_lot": from_row["lot_no"],
            "to_lot": to_row["lot_no"],
            "cts": transfer_weight,
            "per_ct": transfer_rate,
            "amount": transfer_amount,
            "from_balance_after": new_from_weight,
            "to_balance_after": new_to_weight,
            "to_rate_after": new_to_rate,
        }

class LotSearchWindow:
    def __init__(self, master, db, on_select):
        self.db = db
        self.on_select = on_select

        self.top = tk.Toplevel(master)
        self.top.title("Search Lot")
        self.top.geometry("700x420")
        self.top.transient(master)
        self.top.grab_set()

        self.search_var = tk.StringVar()

        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(1, weight=1)

        search_frame = ttk.Frame(self.top, padding=10)
        search_frame.grid(row=0, column=0, sticky="ew")
        search_frame.columnconfigure(0, weight=1)

        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        self.search_entry.grid(row=0, column=0, sticky="ew")

        ttk.Button(
            search_frame,
            text="🔍 Search",
            command=self.load_lots
        ).grid(row=0, column=1, padx=(6, 0))

        tree_frame = ttk.Frame(self.top, padding=(10, 0, 10, 10))
        tree_frame.grid(row=1, column=0, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            tree_frame,
            columns=("lot_no", "weight", "per_cts_price"),
            show="headings",
            selectmode="browse",
        )

        self.tree.heading("lot_no", text="Lot No")
        self.tree.heading("weight", text="Weight")
        self.tree.heading("per_cts_price", text="Per Cts Price")

        self.tree.column("lot_no", width=220)
        self.tree.column("weight", width=150, anchor="e")
        self.tree.column("per_cts_price", width=150, anchor="e")

        self.tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)

        button_frame = ttk.Frame(self.top, padding=(10, 0, 10, 10))
        button_frame.grid(row=2, column=0, sticky="e")

        ttk.Button(
            button_frame,
            text="Select",
            command=self.select_lot
        ).pack(side="left", padx=5)

        ttk.Button(
            button_frame,
            text="Close",
            command=self.top.destroy
        ).pack(side="left")

        self.search_entry.bind("<Return>", lambda event: self.load_lots())
        self.tree.bind("<Double-1>", lambda event: self.select_lot())
        self.top.bind("<Escape>", lambda event: self.top.destroy())

        self.search_entry.focus_set()
        self.load_lots()

    def load_lots(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        try:
            rows = self.db.search_lots(self.search_var.get())
        except Exception as exc:
            messagebox.showerror("Database Error", str(exc), parent=self.top)
            return

        for row in rows:
            self.tree.insert(
                "",
                "end",
                values=(
                    row["lot_no"],
                    fmt_num(row["weight"], 3),
                    fmt_num(row["per_cts_price"], 2),
                ),
            )

    def select_lot(self):
        selected = self.tree.selection()

        if not selected:
            messagebox.showwarning("Select Lot", "Please select a lot.", parent=self.top)
            return

        values = self.tree.item(selected[0], "values")
        lot_no = values[0]

        self.on_select(lot_no)
        self.top.destroy()


class StoneLotMixingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("💎 Stone Lot Mixing System")
        self.root.geometry("780x540")

        self.apply_styles()

        self.db = StoneDB()

        self.from_lot_var = tk.StringVar()
        self.weight_var = tk.StringVar()
        self.to_lot_var = tk.StringVar()

        self._summary_job = None

        self.build_ui()

        self.from_lot_var.trace_add("write", self.schedule_summary)
        self.weight_var.trace_add("write", self.schedule_summary)
        self.to_lot_var.trace_add("write", self.schedule_summary)

        self.from_lot_var.trace_add("write", self.force_uppercase)
        self.to_lot_var.trace_add("write", self.force_uppercase)

        self.set_summary("Enter From Lot, Weight and To Lot, then press Transfer.")
        
    def apply_styles(self):
        style = ttk.Style()

        style.theme_use("clam")

        bg_color = "#79cdcd"
        button_color = "#4fa5a5"
        button_hover = "#3d8c8c"

        self.root.configure(bg=bg_color)

        style.configure(
            "Main.TFrame",
            background=bg_color
        )

        style.configure(
            "TLabel",
            background=bg_color,
            foreground="#003333",
            font=("Segoe UI", 10, "bold")
        )

        style.configure(
            "TEntry",
            padding=6,
            font=("Segoe UI", 10)
        )

        style.configure(
            "TButton",
            background="#4fa5a5",
            foreground="white",
            font=("Segoe UI", 10, "bold"),
            padding=10,
            borderwidth=0,
            relief="flat",
            focusthickness=0,
            focuscolor="none"
        )
        style.map(
            "TButton",
            background=[
                ("active", "#3d8c8c"),
                ("pressed", "#2f6f6f")
            ],
            relief=[("pressed", "flat")]
        )

        style.configure(
            "TLabelframe",
            background=bg_color,
            foreground="#003333",
            font=("Segoe UI", 11, "bold")
        )

        style.configure(
            "TLabelframe.Label",
            background=bg_color,
            foreground="#003333",
            font=("Segoe UI", 11, "bold")
        )

        style.configure(
            "Transfer.TButton",
            background="#008080",
            foreground="white",
            font=("Segoe UI", 11, "bold"),
            padding=10,
            borderwidth=0,
            relief="flat",
            focusthickness=0,
            focuscolor="none"
        )

        style.map(
            "Transfer.TButton",
            background=[
                ("active", "#006666"),
                ("pressed", "#004c4c")
            ],
            relief=[("pressed", "flat")]
        )

    def build_ui(self):
        main = ttk.Frame(self.root, padding=15, style="Main.TFrame")
        main.pack(fill="both", expand=True)

        title_label = tk.Label(
            main,
            text="💎 STONE LOT MIXING",
            bg="#79cdcd",
            fg="#003333",
            font=("Segoe UI", 18, "bold")
        )

        title_label.grid(
            row=0,
            column=0,
            columnspan=3,
            pady=(0, 20)
        )

        main.columnconfigure(1, weight=1)
        main.rowconfigure(3, weight=1)

        ttk.Label(main, text="From Lot").grid(row=1, column=0, sticky="w", pady=6)

        ttk.Entry(
            main,
            textvariable=self.from_lot_var,
            width=35
        ).grid(row=1, column=1, sticky="ew", pady=6, padx=(8, 8))

        ttk.Button(
            main,
            text="🔍 Search",
            takefocus=0,
            command=lambda: self.open_search(self.from_lot_var)
        ).grid(row=1, column=2, pady=6)

        ttk.Label(main, text="Weight").grid(row=2, column=0, sticky="w", pady=6)

        ttk.Entry(
            main,
            textvariable=self.weight_var,
            width=35
        ).grid(row=2, column=1, sticky="ew", pady=6, padx=(8, 8))

        ttk.Label(main, text="cts").grid(row=2, column=2, sticky="w")

        ttk.Label(main, text="To Lot").grid(row=3, column=0, sticky="w", pady=6)

        ttk.Entry(
            main,
            textvariable=self.to_lot_var,
            width=35
        ).grid(row=3, column=1, sticky="ew", pady=6, padx=(8, 8))

        ttk.Button(
            main,
            text="🔍 Search",
            takefocus=0,
            command=lambda: self.open_search(self.to_lot_var)
        ).grid(row=3, column=2, pady=6)

        summary_frame = ttk.LabelFrame(main, text="Summary / Transfer Entry")
        summary_frame.grid(row=4, column=0, columnspan=3, sticky="nsew", pady=(15, 10))
        summary_frame.columnconfigure(0, weight=1)
        summary_frame.rowconfigure(0, weight=1)

        self.summary_text = tk.Text(
            summary_frame,
            height=12,
            wrap="word",
            state="disabled",
            font=("Cascadia Code", 10),
            bg="#f4ffff",
            fg="#003333",
            insertbackground="#003333",
        )
        self.summary_text.grid(row=1, column=0, sticky="nsew")

        summary_scroll = ttk.Scrollbar(
            summary_frame,
            orient="vertical",
            command=self.summary_text.yview,
        )
        summary_scroll.grid(row=1, column=1, sticky="ns")
        self.summary_text.configure(yscrollcommand=summary_scroll.set)

        button_frame = ttk.Frame(main)
        button_frame.grid(row=5, column=0, columnspan=3, sticky="e")

        ttk.Button(
            button_frame,
            text="New",
            takefocus=0,
            command=self.new_entry
        ).pack(side="left", padx=5)

        self.transfer_button = ttk.Button(
            button_frame,
            text="✓ Transfer",
            takefocus=0,
            style="Transfer.TButton",
            command=self.transfer_entry
        )
        self.transfer_button.pack(side="left", padx=5)

        ttk.Button(
            button_frame,
            text="Exit",
            takefocus=0,
            command=self.root.destroy
        ).pack(side="left", padx=5)

    def force_uppercase(self, *args):
        current_from = self.from_lot_var.get()
        current_to = self.to_lot_var.get()

        if current_from != current_from.upper():
            self.from_lot_var.set(current_from.upper())

        if current_to != current_to.upper():
            self.to_lot_var.set(current_to.upper())

    def open_search(self, target_var):
        LotSearchWindow(
            self.root,
            self.db,
            lambda lot_no: target_var.set(lot_no)
        )

    def set_summary(self, text):
        self.summary_text.configure(state="normal")
        self.summary_text.delete("1.0", "end")
        self.summary_text.insert("1.0", text)
        self.summary_text.configure(state="disabled")

    def schedule_summary(self, *args):
        if self._summary_job:
            self.root.after_cancel(self._summary_job)

        self._summary_job = self.root.after(300, self.refresh_summary)

    def refresh_summary(self):
        self._summary_job = None

        from_lot = self.from_lot_var.get().strip()
        to_lot = self.to_lot_var.get().strip()
        weight_text = self.weight_var.get().strip()

        if not from_lot and not to_lot and not weight_text:
            self.set_summary("Enter From Lot, Weight and To Lot, then press Transfer.")
            return

        lines = []
        lines.append("TRANSFER PREVIEW")
        lines.append("-" * 70)

        weight = None

        if weight_text:
            try:
                weight = parse_weight(weight_text)
                lines.append(f"Transfer Weight : {fmt_num(weight, 3)} cts")
            except Exception as exc:
                lines.append(f"Transfer Weight : ERROR - {exc}")
        else:
            lines.append("Transfer Weight : Not entered")

        try:
            from_row = self.db.get_lot(from_lot) if from_lot else None
            to_row = self.db.get_lot(to_lot) if to_lot else None
        except Exception as exc:
            self.set_summary(f"Database error while loading summary:\n{exc}")
            return

        lines.append("")

        if from_lot:
            if from_row:
                lines.append(
                    f"From Lot        : {from_row['lot_no']} | "
                    f"Balance {fmt_num(from_row['weight'], 3)} cts | "
                    f"Rate {fmt_num(from_row['per_cts_price'], 2)}"
                )
            else:
                lines.append(f"From Lot        : {from_lot} - NOT FOUND")
        else:
            lines.append("From Lot        : Not entered")


        if to_lot:
            if to_row:
                lines.append(
                    f"To Lot          : {to_row['lot_no']} | "
                    f"Balance {fmt_num(to_row['weight'], 3)} cts | "
                    f"Rate {fmt_num(to_row['per_cts_price'], 2)}"
                )
            else:
                lines.append(f"To Lot          : {to_lot} - NOT FOUND")
        else:
            lines.append("To Lot          : Not entered")

        if from_lot and to_lot and from_lot.lower() == to_lot.lower():
            lines.append("")
            lines.append("ERROR: From Lot and To Lot cannot be same.")

        if (
            from_row
            and to_row
            and weight is not None
            and from_lot.lower() != to_lot.lower()
        ):
            from_balance = to_decimal(from_row["weight"], "0")
            to_balance = to_decimal(to_row["weight"], "0")
            transfer_rate = to_decimal(from_row["per_cts_price"], None)

            lines.append("")
            lines.append("PROPOSED TRANSACTION ROWS")
            lines.append("-" * 70)

            if transfer_rate is None or transfer_rate <= 0:
                lines.append("Cannot calculate amount. From Lot per cts price is missing or zero.")
            else:
                amount = (weight * transfer_rate).quantize(
                    MONEY_Q,
                    rounding=ROUND_HALF_UP
                )

                lines.append(
                    f"CR | Lot {from_row['lot_no']} | "
                    f"Wt {fmt_num(weight, 3)} | "
                    f"Rate {fmt_num(transfer_rate, 2)} | "
                    f"Amount {fmt_num(amount, 2)}"
                )

                lines.append(
                    f"DR | Lot {to_row['lot_no']}   | "
                    f"Wt {fmt_num(weight, 3)} | "
                    f"Rate {fmt_num(transfer_rate, 2)} | "
                    f"Amount {fmt_num(amount, 2)}"
                )

                if CHECK_FROM_LOT_AVAILABLE_WEIGHT and weight > from_balance:
                    lines.append("")
                    lines.append(
                        f"WARNING: From Lot has only {fmt_num(from_balance, 3)} cts available."
                    )

                if UPDATE_STONE_ACCOUNT_BALANCE:
                    new_from_balance = from_balance - weight
                    new_to_balance = to_balance + weight

                    lines.append("")
                    lines.append("BALANCE AFTER POSTING")
                    lines.append("-" * 70)
                    lines.append(
                        f"From Lot Balance : {fmt_num(new_from_balance, 3)} cts"
                    )
                    lines.append(
                        f"To Lot Balance   : {fmt_num(new_to_balance, 3)} cts"
                    )

                    if UPDATE_TO_LOT_AVG_PRICE and new_to_balance > 0:
                        old_to_rate = to_decimal(to_row["per_cts_price"], "0")
                        new_to_rate = (
                            ((to_balance * old_to_rate) + (weight * transfer_rate))
                            / new_to_balance
                        ).quantize(RATE_Q, rounding=ROUND_HALF_UP)

                        lines.append(
                            f"New To Lot Rate  : {fmt_num(new_to_rate, 2)}"
                        )

        self.set_summary("\n".join(lines))

    def new_entry(self):
        self.from_lot_var.set("")
        self.weight_var.set("")
        self.to_lot_var.set("")
        self.set_summary("New entry. Enter From Lot, Weight and To Lot.")

    def transfer_entry(self):
        if not messagebox.askyesno(
            "Confirm Transfer",
            "Do you want to post this stone lot transfer?"
        ):
            return

        self.transfer_button.configure(state="disabled")

        try:
            result = self.db.create_transfer(
                self.from_lot_var.get(),
                self.to_lot_var.get(),
                self.weight_var.get(),
            )
        except Exception as exc:
            messagebox.showerror("Transfer Failed", str(exc))
        else:
            msg = (
                "Transfer entry completed successfully.\n\n"
                f"Reference No : {result['reference_no']}\n"
                f"From Lot     : {result['from_lot']} - CR\n"
                f"To Lot       : {result['to_lot']} - DR\n"
                f"Weight       : {fmt_num(result['cts'], 3)} cts\n"
                f"Rate         : {fmt_num(result['per_ct'], 2)}\n"
                f"Amount       : {fmt_num(result['amount'], 2)}"
            )

            messagebox.showinfo("Success", msg)
            self.refresh_summary()
        finally:
            self.transfer_button.configure(state="normal")


if __name__ == "__main__":
    root = tk.Tk()
    app = StoneLotMixingApp(root)
    root.mainloop()
