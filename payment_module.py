"""
payment_module.py
----------------------------------------
✅ Reusable Payment Module for ALL Modules
✅ Supports: Cash, Bank, Advance, Pending
✅ Returns structured payment data for any module to save
✅ Pending payment tracking included
"""

import tkinter as tk
from tkinter import ttk, messagebox
import psycopg2
import datetime
import os

# ---------------- PostgreSQL Connection ----------------
# FIX (design issue): the DB password was hardcoded in source. Read it from
# the environment instead. Before running the app, set:
#   Windows (cmd):        set MYGEMS_DB_PASSWORD=your_password
#   Windows (PowerShell): $env:MYGEMS_DB_PASSWORD="your_password"
#   Linux/macOS:           export MYGEMS_DB_PASSWORD=your_password
# or put it in a local .env file that is NOT committed/shared, and load it
# with a package like python-dotenv before this module is imported.
DB_HOST = os.environ.get("MYGEMS_DB_HOST", "localhost")
DB_NAME = os.environ.get("MYGEMS_DB_NAME", "mygems")
DB_USER = os.environ.get("MYGEMS_DB_USER", "myuser")
DB_PASSWORD = os.environ.get("MYGEMS_DB_PASSWORD", "28116")

def get_connection():
    if not DB_PASSWORD:
        messagebox.showerror(
            "DB Connection Error",
            "MYGEMS_DB_PASSWORD environment variable is not set.\n"
            "Set it before starting the app (see comment at top of payment_module.py)."
        )
        return None
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        return conn
    except Exception as e:
        messagebox.showerror("DB Connection Error", f"Failed to connect:\n{e}")
        return None


class PaymentDialog:
    """
    Reusable Payment Dialog
    Returns payment details as a dictionary for the calling module to save
    """
    
    def __init__(self, parent, total_amount, txn_type="PURCHASE", module_name="General"):
        self.parent = parent
        self.total_amount = total_amount
        self.txn_type = txn_type  # e.g., "PURCHASE", "LABOR", "STONE"
        self.module_name = module_name
        self.result = None  # Will store payment details
        # FIX: self.dialog must exist (even as None) before any early
        # return, so get_result() can check for it instead of crashing
        # with AttributeError when the DB connection fails.
        self.dialog = None
        self.conn = get_connection()
        
        if not self.conn:
            messagebox.showerror("Error", "Database connection failed")
            return
        
        self.cur = self.conn.cursor()
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"💰 Payment Entry - {module_name}")
        self.dialog.geometry("650x750")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.resizable(False, False)
        
        self._build_ui()
    
    def _build_ui(self):
        # Header
        header = tk.Frame(self.dialog, bg="#f0f0f0", pady=10)
        header.pack(fill="x")
        tk.Label(header, text=f"Total Amount: ₹ {self.total_amount:.2f}", 
                font=("Arial", 14, "bold"), bg="#f0f0f0", fg="darkgreen").pack()
        tk.Label(header, text=f"Module: {self.module_name}", 
                font=("Arial", 10), bg="#f0f0f0").pack()
        
        # Payment Mode Frame
        mode_frame = tk.LabelFrame(self.dialog, text="Payment Mode", padx=10, pady=10)
        mode_frame.pack(fill="x", padx=15, pady=10)
        
        self.payment_mode = tk.StringVar(value="Cash")
        tk.Radiobutton(mode_frame, text="💵 Cash", variable=self.payment_mode, 
                      value="Cash", command=self._on_mode_change).pack(side="left", padx=10)
        tk.Radiobutton(mode_frame, text="🏦 Bank", variable=self.payment_mode, 
                      value="Bank", command=self._on_mode_change).pack(side="left", padx=10)
        tk.Radiobutton(mode_frame, text="📋 Advance", variable=self.payment_mode, 
                      value="Advance", command=self._on_mode_change).pack(side="left", padx=10)
        tk.Radiobutton(mode_frame, text="⏳ Pending", variable=self.payment_mode, 
                      value="Pending", command=self._on_mode_change).pack(side="left", padx=10)
        tk.Radiobutton(mode_frame, text="🗓️ Installment", variable=self.payment_mode,
                      value="Installment", command=self._on_mode_change).pack(side="left", padx=10)
        
        # Account Selection Frame
        account_frame = tk.LabelFrame(self.dialog, text="Account Details", padx=10, pady=10)
        account_frame.pack(fill="x", padx=15, pady=5)
        
        tk.Label(account_frame, text="Account:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.account_cb = ttk.Combobox(account_frame, width=35, state="readonly")
        self.account_cb.grid(row=0, column=1, padx=5, pady=5)
        tk.Button(account_frame, text="🔄 Refresh", command=self._load_accounts).grid(row=0, column=2, padx=5)
        
        # Advance Payment Frame (hidden by default)
        self.advance_frame = tk.LabelFrame(self.dialog, text="Advance Payment", padx=10, pady=10)
        tk.Label(self.advance_frame, text="Advance Amount (₹):").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.advance_amount_entry = tk.Entry(self.advance_frame, width=15, font=("Arial", 11))
        self.advance_amount_entry.grid(row=0, column=1, padx=5, pady=5)
        self.advance_amount_entry.insert(0, f"{self.total_amount:.2f}")
        
        tk.Label(self.advance_frame, text="Advance Mode:").grid(row=0, column=2, sticky="w", padx=15, pady=5)
        self.advance_pay_mode = tk.StringVar(value="Cash")
        tk.Radiobutton(self.advance_frame, text="Cash", variable=self.advance_pay_mode, 
                      value="Cash", command=self._load_accounts).grid(row=0, column=3, padx=5)
        tk.Radiobutton(self.advance_frame, text="Bank", variable=self.advance_pay_mode, 
                      value="Bank", command=self._load_accounts).grid(row=0, column=4, padx=5)

        # Installment Frame (hidden by default) -- equal monthly amounts,
        # first due ~30 days out. No money moves right now (paid=0), so
        # no account selection here -- this just sets up the schedule.
        self.installment_frame = tk.LabelFrame(self.dialog, text="Installment Plan", padx=10, pady=10)
        tk.Label(self.installment_frame, text="Number of Months:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.installment_months_var = tk.StringVar(value="3")
        months_cb = ttk.Combobox(self.installment_frame, textvariable=self.installment_months_var,
                                  values=[str(n) for n in range(2, 25)], width=6, state="readonly")
        months_cb.grid(row=0, column=1, padx=5, pady=5)
        months_cb.bind("<<ComboboxSelected>>", lambda e: self._update_summary())
        self.installment_preview_lbl = tk.Label(self.installment_frame, text="", fg="#555", justify="left")
        self.installment_preview_lbl.grid(row=1, column=0, columnspan=2, sticky="w", padx=5, pady=(0, 5))
        
        # Summary Frame
        summary_frame = tk.LabelFrame(self.dialog, text="Payment Summary", padx=10, pady=10)
        summary_frame.pack(fill="x", padx=15, pady=10)
        
        self.summary_labels = {}
        summary_data = [
            ("Total Amount:", "total_lbl", "darkgreen"),
            ("Paid Amount:", "paid_lbl", "blue"),
            ("Balance Amount:", "balance_lbl", "red"),
            ("Payment Status:", "status_lbl", "purple")
        ]
        
        for i, (label_text, var_name, color) in enumerate(summary_data):
            tk.Label(summary_frame, text=label_text, font=("Arial", 10, "bold")).grid(row=i, column=0, sticky="w", padx=5, pady=3)
            lbl = tk.Label(summary_frame, text="₹ 0.00", font=("Arial", 11), fg=color)
            lbl.grid(row=i, column=1, sticky="w", padx=5, pady=3)
            self.summary_labels[var_name] = lbl
        
        self._update_summary()
        
        # Remarks
        remarks_frame = tk.Frame(self.dialog)
        remarks_frame.pack(fill="x", padx=15, pady=5)
        tk.Label(remarks_frame, text="Remarks:").pack(anchor="w")
        self.remarks_entry = tk.Entry(remarks_frame, width=70)
        self.remarks_entry.pack(fill="x", pady=3)
        
        # Buttons
        btn_frame = tk.Frame(self.dialog, pady=15)
        btn_frame.pack(fill="x")
        tk.Button(btn_frame, text="✅ Confirm Payment", bg="green", fg="white", 
                 font=("Arial", 11, "bold"), command=self._confirm_payment).pack(side="left", padx=10)
        tk.Button(btn_frame, text="❌ Cancel", bg="red", fg="white", 
                 command=self._cancel).pack(side="left", padx=10)
        
        # Initial load
        self._on_mode_change()
    
    def _load_accounts(self):
        """Load cash or bank accounts based on payment mode"""
        try:
            mode = self.payment_mode.get().upper()
            if mode == "ADVANCE":
                mode = self.advance_pay_mode.get().upper()
            
            if mode == "CASH":
                type_id = 2  # Cash accounts
            elif mode == "BANK":
                type_id = 6  # Bank accounts
            else:
                type_id = 2
            
            self.cur.execute("""
                SELECT DISTINCT short_name 
                FROM accounts
                WHERE type_id = %s AND short_name IS NOT NULL 
                ORDER BY short_name
            """, (type_id,))
            
            accounts = [r[0].strip().upper() for r in self.cur.fetchall()]
            self.account_cb['values'] = accounts
            if accounts:
                self.account_cb.set(accounts[0])
        except Exception as e:
            print("⚠️ Account load error:", e)
            self.account_cb['values'] = []
    
    def _on_mode_change(self):
        """Handle payment mode changes"""
        mode = self.payment_mode.get().upper()
        
        # Show/hide advance frame
        if mode == "ADVANCE":
            self.advance_frame.pack(fill="x", padx=15, pady=5)
            self._load_accounts()
        else:
            self.advance_frame.pack_forget()

        # Show/hide installment frame -- no account needed, nothing is
        # collected right now (paid=0 until the first installment comes in).
        if mode == "INSTALLMENT":
            self.installment_frame.pack(fill="x", padx=15, pady=5)
            self.account_cb.set("")
            self.account_cb['values'] = []
        else:
            self.installment_frame.pack_forget()
        
        # Load appropriate accounts
        if mode in ("CASH", "BANK"):
            self._load_accounts()
        elif mode in ("PENDING", "INSTALLMENT"):
            self.account_cb.set("")
            self.account_cb['values'] = []
        
        self._update_summary()

    def _compute_installment_schedule(self):
        """
        Equal monthly amounts, remainder absorbed into the LAST
        installment so they sum exactly to total_amount (avoids a
        1-cent-off total from naive division). First due date is 30
        days out, then +30 days per installment after that.
        """
        try:
            months = int(self.installment_months_var.get())
        except (ValueError, TypeError):
            months = 3
        months = max(months, 1)
        base = round(self.total_amount / months, 2)
        schedule = []
        running = 0.0
        due = datetime.date.today() + datetime.timedelta(days=30)
        for n in range(1, months + 1):
            if n == months:
                amt = round(self.total_amount - running, 2)  # remainder goes here
            else:
                amt = base
                running += amt
            schedule.append({"installment_no": n, "due_date": due, "amount": amt})
            due = due + datetime.timedelta(days=30)
        return schedule
    
    def _update_summary(self):
        """Update payment summary labels"""
        mode = self.payment_mode.get().upper()
        total = self.total_amount
        
        self.summary_labels["total_lbl"].config(text=f"₹ {total:.2f}")
        
        if mode == "PENDING":
            paid = 0
            balance = total
            status = "PENDING"
        elif mode == "INSTALLMENT":
            # FIX/NEW: nothing is collected at the point of sale -- the
            # schedule is what governs collection going forward. Status is
            # its own distinct value (not PENDING) since a plan exists.
            paid = 0
            balance = total
            status = "INSTALLMENT"
            schedule = self._compute_installment_schedule()
            preview = "\n".join(f"#{s['installment_no']}: ₹{s['amount']:.2f} due {s['due_date']}" for s in schedule)
            self.installment_preview_lbl.config(text=preview)
        elif mode == "ADVANCE":
            try:
                paid = float(self.advance_amount_entry.get() or "0")
            except:
                paid = 0
            balance = round(total - paid, 2)
            # FIX (bug #6): an advance that covers the full amount is PAID,
            # not stuck labeled ADVANCE forever (which was leaving fully-paid
            # bills sitting in pending_payments with a 0 balance).
            if balance <= 0:
                status = "PAID"
            elif paid > 0:
                status = "ADVANCE"
            else:
                status = "PENDING"
        else:  # CASH or BANK
            paid = total
            balance = 0
            status = "PAID"
        
        self.summary_labels["paid_lbl"].config(text=f"₹ {paid:.2f}")
        self.summary_labels["balance_lbl"].config(text=f"₹ {balance:.2f}")
        self.summary_labels["status_lbl"].config(text=status)
        
        return paid, balance, status
    
    def _validate_payment(self):
        """Validate payment details before confirmation"""
        mode = self.payment_mode.get().upper()
        account = self.account_cb.get().strip()
        
        if mode in ("CASH", "BANK"):
            if not account:
                return False, "❌ Please select an account"
        elif mode == "ADVANCE":
            if not account:
                return False, "❌ Please select an account"
            try:
                advance_amt = float(self.advance_amount_entry.get() or "0")
                if advance_amt <= 0:
                    return False, "❌ Advance amount must be greater than 0"
                if advance_amt > self.total_amount:
                    return False, "❌ Advance amount cannot exceed total"
            except:
                return False, "❌ Invalid advance amount"
        # PENDING and INSTALLMENT modes don't require an account
        
        return True, ""
    
    def _confirm_payment(self):
        """Validate and return payment details"""
        valid, error = self._validate_payment()
        if not valid:
            messagebox.showwarning("Validation Error", error)
            return
        
        paid, balance, status = self._update_summary()
        mode = self.payment_mode.get().upper()
        account = self.account_cb.get().strip().upper()
        remarks = self.remarks_entry.get().strip()
        
        # Determine account type for advance
        advance_mode = None
        if mode == "ADVANCE":
            advance_mode = self.advance_pay_mode.get().upper()
            account_type = 2 if advance_mode == "CASH" else 6
        else:
            account_type = 2 if mode == "CASH" else 6
        
        # Get account ID if account is selected
        account_id = None
        if account and mode in ("CASH", "BANK", "ADVANCE"):
            try:
                self.cur.execute("""
                    SELECT account_id 
                    FROM accounts 
                    WHERE UPPER(short_name) = %s AND type_id = %s 
                    LIMIT 1
                """, (account, account_type))
                res = self.cur.fetchone()
                if res:
                    account_id = res[0]
            except Exception as e:
                print("⚠️ Account ID fetch error:", e)

        # NEW: installment schedule, only meaningful for this mode -- the
        # calling module is responsible for creating whatever rows track
        # this schedule against its own entity (e.g. sales_order_items).
        installment_months = None
        installment_schedule = None
        if mode == "INSTALLMENT":
            installment_schedule = self._compute_installment_schedule()
            installment_months = len(installment_schedule)
        
        # Prepare result dictionary
        self.result = {
            "payment_mode": mode,
            "advance_mode": advance_mode,  # Only for ADVANCE
            "account_name": account if account else None,
            "account_id": account_id,
            "total_amount": self.total_amount,
            "paid_amount": paid,
            "balance_amount": balance,
            "payment_status": status,
            "remarks": remarks,
            "txn_date": datetime.date.today(),
            "txn_type": self.txn_type,
            "module_name": self.module_name,
            "installment_months": installment_months,
            "installment_schedule": installment_schedule,
        }
        
        # FIX (bug #8): close the connection this dialog opened in __init__ —
        # it was never being closed, leaking one connection per payment dialog.
        self._close_connection()
        self.dialog.destroy()

    def _cancel(self):
        """Close the dialog without a result, also releasing the DB connection."""
        self._close_connection()
        self.dialog.destroy()

    def _close_connection(self):
        try:
            if getattr(self, "cur", None):
                self.cur.close()
        except Exception:
            pass
        try:
            if getattr(self, "conn", None):
                self.conn.close()
        except Exception:
            pass

    def get_result(self):
        """Return payment details after dialog closes"""
        if self.dialog is None:
            # Connection failed in __init__ -- nothing to wait on.
            return None
        self.dialog.wait_window()  # Wait for dialog to close
        return self.result


# ============================================================
# ✅ HELPER FUNCTION FOR EASY INTEGRATION
# ============================================================

def open_payment_dialog(parent, total_amount, txn_type="PURCHASE", module_name="General"):
    """
    Easy function to open payment dialog and get result
    
    Usage in any module:
        payment_details = open_payment_dialog(self.root, total_amount, "LABOR", "Labor Module")
        if payment_details:
            # Save to your module's database structure
            save_payment_to_db(payment_details)
    
    Returns:
        dict with keys:
            - payment_mode: "CASH", "BANK", "ADVANCE", "PENDING"
            - advance_mode: "CASH" or "BANK" (only for ADVANCE)
            - account_name: Selected account name
            - account_id: Account ID from database
            - total_amount: Total transaction amount
            - paid_amount: Amount paid
            - balance_amount: Remaining balance
            - payment_status: "PAID", "ADVANCE", "PENDING"
            - remarks: User remarks
            - txn_date: Transaction date
            - txn_type: Transaction type
            - module_name: Calling module name
    """
    dialog = PaymentDialog(parent, total_amount, txn_type, module_name)
    return dialog.get_result()


# ============================================================
# ✅ TEST STANDALONE
# ============================================================
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Payment Module Test")
    root.geometry("400x300")
    
    def test_payment():
        result = open_payment_dialog(root, 50000.00, "PURCHASE", "Test Module")
        if result:
            print("\n" + "="*50)
            print("✅ PAYMENT DETAILS RECEIVED:")
            print("="*50)
            for key, value in result.items():
                print(f"{key}: {value}")
            print("="*50 + "\n")
            messagebox.showinfo("Payment Details", f"Payment Mode: {result['payment_mode']}\nStatus: {result['payment_status']}\nBalance: ₹ {result['balance_amount']:.2f}")
    
    tk.Button(root, text="🧪 Test Payment Dialog", font=("Arial", 12), 
             command=test_payment).pack(pady=50)
    
    root.mainloop()
