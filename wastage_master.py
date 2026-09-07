# ============================================================
# WORKER WASTAGE MASTER
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from db import get_connection

try:
    from tkcalendar import DateEntry
except ImportError:
    DateEntry = None


class WorkerWastageMaster(tk.Toplevel):

    def __init__(self, parent):
        super().__init__(parent)

        self.title("Worker Wastage Master")
        self.geometry("1250x720")
        self.minsize(1100, 650)

        self.selected_id = None

        self.worker_map = {}
        self.process_list = []

        self.create_variables()
        self.create_ui()

        self.load_workers()
        self.load_processes()
        self.load_rules()

    # =========================================================
    # VARIABLES
    # =========================================================

    def create_variables(self):

        self.worker_id_var = tk.StringVar()
        self.worker_var = tk.StringVar()

        self.process_var = tk.StringVar()

        self.metal_type_var = tk.StringVar(value="GOLD")
        self.purity_var = tk.StringVar()

        self.allowed_percent_var = tk.StringVar(value="0.00")

        self.effective_from_var = tk.StringVar(
            value=date.today().strftime("%d-%m-%Y")
        )

        self.effective_to_var = tk.StringVar()

        self.status_var = tk.StringVar(value="ACTIVE")
        self.remarks_var = tk.StringVar()

        self.search_var = tk.StringVar()

    # =========================================================
    # UI
    # =========================================================

    def create_ui(self):

        main = ttk.Frame(self, padding=10)
        main.pack(fill="both", expand=True)

        # =====================================================
        # FORM
        # =====================================================

        form = ttk.LabelFrame(
            main,
            text="Worker Wastage Rule",
            padding=12
        )

        form.pack(fill="x")

        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        # -----------------------------------------------------
        # WORKER
        # -----------------------------------------------------

        ttk.Label(
            form,
            text="WORKER"
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=5,
            pady=5
        )

        self.worker_combo = ttk.Combobox(
            form,
            textvariable=self.worker_var,
            state="readonly",
            width=30
        )

        self.worker_combo.grid(
            row=0,
            column=1,
            sticky="ew",
            padx=5,
            pady=5
        )

        self.worker_combo.bind(
            "<<ComboboxSelected>>",
            self.worker_selected
        )

        # -----------------------------------------------------
        # PROCESS
        # -----------------------------------------------------

        ttk.Label(
            form,
            text="PROCESS"
        ).grid(
            row=0,
            column=2,
            sticky="w",
            padx=5,
            pady=5
        )

        self.process_combo = ttk.Combobox(
            form,
            textvariable=self.process_var,
            state="readonly",
            width=25
        )

        self.process_combo.grid(
            row=0,
            column=3,
            sticky="ew",
            padx=5,
            pady=5
        )

        # -----------------------------------------------------
        # METAL
        # -----------------------------------------------------

        ttk.Label(
            form,
            text="METAL TYPE"
        ).grid(
            row=1,
            column=0,
            sticky="w",
            padx=5,
            pady=5
        )

        self.metal_combo = ttk.Combobox(
            form,
            textvariable=self.metal_type_var,
            values=("GOLD", "SILVER"),
            state="readonly",
            width=15
        )

        self.metal_combo.grid(
            row=1,
            column=1,
            sticky="w",
            padx=5,
            pady=5
        )

        # -----------------------------------------------------
        # PURITY
        # -----------------------------------------------------

        ttk.Label(
            form,
            text="PURITY"
        ).grid(
            row=1,
            column=2,
            sticky="w",
            padx=5,
            pady=5
        )

        self.purity_combo = ttk.Combobox(
            form,
            textvariable=self.purity_var,
            values=(
                "",
                "9K",
                "14K",
                "18K",
                "22K",
                "24K",
                "925",
                "999"
            ),
            state="readonly",
            width=15
        )

        self.purity_combo.grid(
            row=1,
            column=3,
            sticky="w",
            padx=5,
            pady=5
        )

        # -----------------------------------------------------
        # ALLOWED %
        # -----------------------------------------------------

        ttk.Label(
            form,
            text="ALLOWED WASTAGE %"
        ).grid(
            row=2,
            column=0,
            sticky="w",
            padx=5,
            pady=5
        )

        self.allowed_percent_entry = ttk.Entry(
            form,
            textvariable=self.allowed_percent_var,
            width=15
        )

        self.allowed_percent_entry.grid(
            row=2,
            column=1,
            sticky="w",
            padx=5,
            pady=5
        )

        # -----------------------------------------------------
        # EFFECTIVE FROM
        # -----------------------------------------------------

        ttk.Label(
            form,
            text="EFFECTIVE FROM"
        ).grid(
            row=2,
            column=2,
            sticky="w",
            padx=5,
            pady=5
        )

        self.effective_from_entry = self.create_date_entry(
            form,
            self.effective_from_var,
            allow_blank=False
        )

        self.effective_from_entry.grid(
            row=2,
            column=3,
            sticky="w",
            padx=5,
            pady=5
        )

        # -----------------------------------------------------
        # EFFECTIVE TO - OPTIONAL
        # -----------------------------------------------------

        ttk.Label(
            form,
            text="EFFECTIVE TO (OPTIONAL)"
        ).grid(
            row=3,
            column=0,
            sticky="w",
            padx=5,
            pady=5
        )

        self.effective_to_entry = self.create_date_entry(
            form,
            self.effective_to_var,
            allow_blank=True
        )

        self.effective_to_entry.grid(
            row=3,
            column=1,
            sticky="w",
            padx=5,
            pady=5
        )

        # -----------------------------------------------------
        # STATUS
        # -----------------------------------------------------

        ttk.Label(
            form,
            text="STATUS"
        ).grid(
            row=3,
            column=2,
            sticky="w",
            padx=5,
            pady=5
        )

        self.status_combo = ttk.Combobox(
            form,
            textvariable=self.status_var,
            values=("ACTIVE", "INACTIVE"),
            state="readonly",
            width=15
        )

        self.status_combo.grid(
            row=3,
            column=3,
            sticky="w",
            padx=5,
            pady=5
        )

        # -----------------------------------------------------
        # REMARKS
        # -----------------------------------------------------

        ttk.Label(
            form,
            text="REMARKS"
        ).grid(
            row=4,
            column=0,
            sticky="nw",
            padx=5,
            pady=5
        )

        self.remarks_entry = ttk.Entry(
            form,
            textvariable=self.remarks_var
        )

        self.remarks_entry.grid(
            row=4,
            column=1,
            columnspan=3,
            sticky="ew",
            padx=5,
            pady=5
        )

        # =====================================================
        # BUTTONS
        # =====================================================

        button_frame = ttk.Frame(form)

        button_frame.grid(
            row=5,
            column=0,
            columnspan=4,
            pady=12
        )

        ttk.Button(
            button_frame,
            text="SAVE",
            command=self.save_rule
        ).pack(
            side="left",
            padx=5
        )

        ttk.Button(
            button_frame,
            text="UPDATE",
            command=self.update_rule
        ).pack(
            side="left",
            padx=5
        )

        ttk.Button(
            button_frame,
            text="DEACTIVATE",
            command=self.deactivate_rule
        ).pack(
            side="left",
            padx=5
        )

        ttk.Button(
            button_frame,
            text="CLEAR",
            command=self.clear_form
        ).pack(
            side="left",
            padx=5
        )

        # =====================================================
        # SEARCH
        # =====================================================

        search_frame = ttk.Frame(main)
        search_frame.pack(
            fill="x",
            pady=(10, 5)
        )

        ttk.Label(
            search_frame,
            text="SEARCH"
        ).pack(
            side="left"
        )

        search_entry = ttk.Entry(
            search_frame,
            textvariable=self.search_var,
            width=35
        )

        search_entry.pack(
            side="left",
            padx=5
        )

        search_entry.bind(
            "<KeyRelease>",
            self.search_rules
        )

        # =====================================================
        # TABLE
        # =====================================================

        table_frame = ttk.Frame(main)
        table_frame.pack(
            fill="both",
            expand=True
        )

        columns = (
            "id",
            "worker",
            "process",
            "metal",
            "purity",
            "percent",
            "from",
            "to",
            "status",
            "remarks"
        )

        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            selectmode="browse"
        )

        headings = {
            "id": "ID",
            "worker": "WORKER",
            "process": "PROCESS",
            "metal": "METAL",
            "purity": "PURITY",
            "percent": "ALLOWED %",
            "from": "FROM",
            "to": "TO",
            "status": "STATUS",
            "remarks": "REMARKS"
        }

        widths = {
            "id": 60,
            "worker": 180,
            "process": 130,
            "metal": 80,
            "purity": 80,
            "percent": 100,
            "from": 110,
            "to": 110,
            "status": 90,
            "remarks": 200
        }

        for column in columns:

            self.tree.heading(
                column,
                text=headings[column]
            )

            self.tree.column(
                column,
                width=widths[column],
                anchor="center"
            )

        scrollbar_y = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.tree.yview
        )

        scrollbar_x = ttk.Scrollbar(
            table_frame,
            orient="horizontal",
            command=self.tree.xview
        )

        self.tree.configure(
            yscrollcommand=scrollbar_y.set,
            xscrollcommand=scrollbar_x.set
        )

        self.tree.pack(
            side="top",
            fill="both",
            expand=True
        )

        scrollbar_y.pack(
            side="right",
            fill="y"
        )

        scrollbar_x.pack(
            side="bottom",
            fill="x"
        )

        self.tree.bind(
            "<Double-1>",
            self.load_selected_rule
        )

    # =========================================================
    # DATE ENTRY
    # =========================================================

    def create_date_entry(
        self,
        parent,
        variable,
        allow_blank=False
    ):

        if DateEntry:

            entry = DateEntry(
                parent,
                textvariable=variable,
                date_pattern="dd-mm-yyyy",
                width=14
            )

            if allow_blank:
                entry.delete(0, tk.END)

            return entry

        return ttk.Entry(
            parent,
            textvariable=variable,
            width=16
        )

    # =========================================================
    # LOAD WORKERS
    # =========================================================

    def load_workers(self):

        self.worker_map.clear()

        conn = None
        cur = None

        try:

            conn = get_connection()
            cur = conn.cursor()

            cur.execute("""
                SELECT
                    a.account_id,
                    UPPER(TRIM(a.account_name))
                FROM accounts a
                INNER JOIN account_types at
                    ON at.type_id = a.type_id
                WHERE UPPER(TRIM(at.type_name)) = 'WORKER'
                  AND a.account_name IS NOT NULL
                ORDER BY UPPER(TRIM(a.account_name))
            """)

            rows = cur.fetchall()

            worker_names = []

            for worker_id, worker_name in rows:

                worker_name = str(
                    worker_name
                ).strip().upper()

                self.worker_map[worker_name] = worker_id
                worker_names.append(worker_name)

            self.worker_combo["values"] = worker_names

        except Exception as e:

            messagebox.showerror(
                "Worker Load Error",
                str(e)
            )

        finally:

            if cur:
                cur.close()

            if conn:
                conn.close()

    # =========================================================
    # LOAD PROCESSES
    # =========================================================

    def load_processes(self):

        self.process_list.clear()

        conn = None
        cur = None

        try:

            conn = get_connection()
            cur = conn.cursor()

            cur.execute("""
                SELECT
                    UPPER(TRIM(process_code))
                FROM process_master
                WHERE UPPER(TRIM(status)) = 'ACTIVE'
                ORDER BY sort_order, process_code
            """)

            rows = cur.fetchall()

            for row in rows:

                process = str(
                    row[0]
                ).strip().upper()

                if process:
                    self.process_list.append(process)

            self.process_combo["values"] = self.process_list

        except Exception as e:

            messagebox.showerror(
                "Process Load Error",
                str(e)
            )

        finally:

            if cur:
                cur.close()

            if conn:
                conn.close()

    # =========================================================
    # WORKER SELECT
    # =========================================================

    def worker_selected(self, event=None):

        worker = (
            self.worker_var.get()
            .strip()
            .upper()
        )

        self.worker_var.set(worker)

        self.worker_id_var.set(
            str(
                self.worker_map.get(
                    worker,
                    ""
                )
            )
        )

    # =========================================================
    # NORMALIZE DATE
    # =========================================================

    def normalize_date(self, value):

        value = str(value).strip()

        if not value:
            return None

        for fmt in (
            "%d-%m-%Y",
            "%Y-%m-%d"
        ):

            try:

                return datetime.strptime(
                    value,
                    fmt
                ).date()

            except ValueError:
                continue

        raise ValueError(
            f"Invalid date: {value}"
        )

    # =========================================================
    # VALIDATE
    # =========================================================

    def validate_form(self):

        worker = (
            self.worker_var.get()
            .strip()
            .upper()
        )

        process = (
            self.process_var.get()
            .strip()
            .upper()
        )

        metal = (
            self.metal_type_var.get()
            .strip()
            .upper()
        )

        purity = (
            self.purity_var.get()
            .strip()
            .upper()
        )

        self.worker_var.set(worker)
        self.process_var.set(process)
        self.metal_type_var.set(metal)
        self.purity_var.set(purity)

        if not worker:

            messagebox.showwarning(
                "Validation",
                "Please select a worker."
            )

            return False

        if worker not in self.worker_map:

            messagebox.showwarning(
                "Validation",
                "Invalid worker selected."
            )

            return False

        if not process:

            messagebox.showwarning(
                "Validation",
                "Please select a process."
            )

            return False

        if process not in self.process_list:

            messagebox.showwarning(
                "Validation",
                "Invalid process selected."
            )

            return False

        if metal not in (
            "GOLD",
            "SILVER"
        ):

            messagebox.showwarning(
                "Validation",
                "Metal must be GOLD or SILVER."
            )

            return False

        try:

            percent = Decimal(
                self.allowed_percent_var.get()
                .strip()
            )

        except InvalidOperation:

            messagebox.showwarning(
                "Validation",
                "Allowed wastage must be a valid number."
            )

            return False

        if percent < 0 or percent > 100:

            messagebox.showwarning(
                "Validation",
                "Allowed wastage must be between 0% and 100%."
            )

            return False

        self.allowed_percent_var.set(
            f"{percent:.2f}"
        )

        try:

            effective_from = self.normalize_date(
                self.effective_from_var.get()
            )

            effective_to = self.normalize_date(
                self.effective_to_var.get()
            )

        except ValueError as e:

            messagebox.showwarning(
                "Validation",
                str(e)
            )

            return False

        if effective_from is None:

            messagebox.showwarning(
                "Validation",
                "Effective From is required."
            )

            return False

        if (
            effective_to is not None
            and effective_to < effective_from
        ):

            messagebox.showwarning(
                "Validation",
                "Effective To cannot be earlier than Effective From."
            )

            return False

        self.effective_from_db = effective_from
        self.effective_to_db = effective_to

        return True

    # =========================================================
    # SAVE
    # =========================================================

    def save_rule(self):

        if not self.validate_form():
            return

        conn = None
        cur = None

        try:

            worker = self.worker_var.get().strip().upper()
            process = self.process_var.get().strip().upper()
            metal = self.metal_type_var.get().strip().upper()
            purity = self.purity_var.get().strip().upper() or None

            worker_id = self.worker_map[worker]

            allowed_percent = Decimal(
                self.allowed_percent_var.get()
            )

            remarks = (
                self.remarks_var.get()
                .strip()
                .upper()
            )

            conn = get_connection()
            cur = conn.cursor()

            # -------------------------------------------------
            # DUPLICATE ACTIVE RULE
            # -------------------------------------------------

            cur.execute("""
                SELECT wastage_id
                FROM worker_wastage_master
                WHERE worker_id = %s
                  AND UPPER(TRIM(process)) = %s
                  AND UPPER(TRIM(metal_type)) = %s
                  AND COALESCE(
                        UPPER(TRIM(purity)),
                        ''
                      )
                      =
                      COALESCE(
                        UPPER(TRIM(%s)),
                        ''
                      )
                  AND UPPER(TRIM(status)) = 'ACTIVE'
            """, (
                worker_id,
                process,
                metal,
                purity
            ))

            if cur.fetchone():

                messagebox.showwarning(
                    "Duplicate Rule",
                    "An active wastage rule already exists "
                    "for this Worker / Process / Metal / Purity."
                )

                return

            # -------------------------------------------------
            # INSERT
            # -------------------------------------------------

            cur.execute("""
                INSERT INTO worker_wastage_master
                (
                    worker_id,
                    worker_name,
                    process,
                    metal_type,
                    purity,
                    allowed_percent,
                    effective_from,
                    effective_to,
                    status,
                    remarks
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    'ACTIVE',
                    %s
                )
            """, (
                worker_id,
                worker,
                process,
                metal,
                purity,
                allowed_percent,
                self.effective_from_db,
                self.effective_to_db,
                remarks
            ))

            conn.commit()

            messagebox.showinfo(
                "Success",
                "Worker wastage rule saved successfully."
            )

            self.clear_form()
            self.load_rules()

        except Exception as e:

            if conn:
                conn.rollback()

            messagebox.showerror(
                "Save Error",
                str(e)
            )

        finally:

            if cur:
                cur.close()

            if conn:
                conn.close()

    # =========================================================
    # LOAD RULES
    # =========================================================

    def load_rules(self):

        if not hasattr(self, "tree"):
            return

        for item in self.tree.get_children():
            self.tree.delete(item)

        search = (
            self.search_var.get()
            .strip()
            .upper()
        )

        conn = None
        cur = None

        try:

            conn = get_connection()
            cur = conn.cursor()

            if search:

                like = f"%{search}%"

                cur.execute("""
                    SELECT
                        wastage_id,
                        UPPER(TRIM(worker_name)),
                        UPPER(TRIM(process)),
                        UPPER(TRIM(metal_type)),
                        UPPER(TRIM(COALESCE(purity, ''))),
                        allowed_percent,
                        effective_from,
                        effective_to,
                        UPPER(TRIM(status)),
                        UPPER(TRIM(COALESCE(remarks, '')))
                    FROM worker_wastage_master
                    WHERE
                        UPPER(TRIM(worker_name)) LIKE %s
                        OR UPPER(TRIM(process)) LIKE %s
                        OR UPPER(TRIM(metal_type)) LIKE %s
                        OR UPPER(TRIM(COALESCE(purity, ''))) LIKE %s
                    ORDER BY
                        UPPER(TRIM(worker_name)),
                        UPPER(TRIM(process))
                """, (
                    like,
                    like,
                    like,
                    like
                ))

            else:

                cur.execute("""
                    SELECT
                        wastage_id,
                        UPPER(TRIM(worker_name)),
                        UPPER(TRIM(process)),
                        UPPER(TRIM(metal_type)),
                        UPPER(TRIM(COALESCE(purity, ''))),
                        allowed_percent,
                        effective_from,
                        effective_to,
                        UPPER(TRIM(status)),
                        UPPER(TRIM(COALESCE(remarks, '')))
                    FROM worker_wastage_master
                    ORDER BY
                        UPPER(TRIM(worker_name)),
                        UPPER(TRIM(process))
                """)

            rows = cur.fetchall()

            for row in rows:

                from_date = (
                    row[6].strftime("%d-%m-%Y")
                    if row[6]
                    else ""
                )

                to_date = (
                    row[7].strftime("%d-%m-%Y")
                    if row[7]
                    else ""
                )

                self.tree.insert(
                    "",
                    "end",
                    values=(
                        row[0],
                        row[1] or "",
                        row[2] or "",
                        row[3] or "",
                        row[4] or "",
                        f"{Decimal(row[5] or 0):.2f}",
                        from_date,
                        to_date,
                        row[8] or "",
                        row[9] or ""
                    )
                )

        except Exception as e:

            messagebox.showerror(
                "Load Error",
                str(e)
            )

        finally:

            if cur:
                cur.close()

            if conn:
                conn.close()

    # =========================================================
    # SEARCH
    # =========================================================

    def search_rules(self, event=None):

        self.search_var.set(
            self.search_var.get().upper()
        )

        self.load_rules()

    # =========================================================
    # LOAD SELECTED
    # =========================================================

    def load_selected_rule(self, event=None):

        selected = self.tree.selection()

        if not selected:
            return

        values = self.tree.item(
            selected[0],
            "values"
        )

        if not values:
            return

        self.selected_id = int(
            values[0]
        )

        worker = str(
            values[1]
        ).strip().upper()

        process = str(
            values[2]
        ).strip().upper()

        self.worker_var.set(worker)
        self.process_var.set(process)

        self.worker_selected()

        self.metal_type_var.set(
            str(values[3]).upper()
        )

        self.purity_var.set(
            str(values[4]).upper()
        )

        self.allowed_percent_var.set(
            f"{Decimal(values[5] or 0):.2f}"
        )

        self.effective_from_var.set(
            values[6]
        )

        self.effective_to_var.set(
            values[7]
        )

        self.status_var.set(
            str(values[8]).upper()
        )

        self.remarks_var.set(
            str(values[9]).upper()
        )

    # =========================================================
    # UPDATE
    # =========================================================

    def update_rule(self):

        if not self.selected_id:

            messagebox.showwarning(
                "Update",
                "Double-click a rule first."
            )

            return

        if not self.validate_form():
            return

        conn = None
        cur = None

        try:

            worker = self.worker_var.get().strip().upper()
            process = self.process_var.get().strip().upper()
            metal = self.metal_type_var.get().strip().upper()
            purity = self.purity_var.get().strip().upper() or None

            worker_id = self.worker_map[worker]

            allowed_percent = Decimal(
                self.allowed_percent_var.get()
            )

            status = (
                self.status_var.get()
                .strip()
                .upper()
            )

            remarks = (
                self.remarks_var.get()
                .strip()
                .upper()
            )

            conn = get_connection()
            cur = conn.cursor()

            # -------------------------------------------------
            # DUPLICATE CHECK
            # -------------------------------------------------

            cur.execute("""
                SELECT wastage_id
                FROM worker_wastage_master
                WHERE worker_id = %s
                  AND UPPER(TRIM(process)) = %s
                  AND UPPER(TRIM(metal_type)) = %s
                  AND COALESCE(
                        UPPER(TRIM(purity)),
                        ''
                      )
                      =
                      COALESCE(
                        UPPER(TRIM(%s)),
                        ''
                      )
                  AND UPPER(TRIM(status)) = 'ACTIVE'
                  AND wastage_id <> %s
            """, (
                worker_id,
                process,
                metal,
                purity,
                self.selected_id
            ))

            if cur.fetchone():

                messagebox.showwarning(
                    "Duplicate Rule",
                    "Another active rule already exists "
                    "for this Worker / Process / Metal / Purity."
                )

                return

            # -------------------------------------------------
            # UPDATE
            # -------------------------------------------------

            cur.execute("""
                UPDATE worker_wastage_master
                SET
                    worker_id = %s,
                    worker_name = %s,
                    process = %s,
                    metal_type = %s,
                    purity = %s,
                    allowed_percent = %s,
                    effective_from = %s,
                    effective_to = %s,
                    status = %s,
                    remarks = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE wastage_id = %s
            """, (
                worker_id,
                worker,
                process,
                metal,
                purity,
                allowed_percent,
                self.effective_from_db,
                self.effective_to_db,
                status,
                remarks,
                self.selected_id
            ))

            conn.commit()

            messagebox.showinfo(
                "Success",
                "Worker wastage rule updated successfully."
            )

            self.clear_form()
            self.load_rules()

        except Exception as e:

            if conn:
                conn.rollback()

            messagebox.showerror(
                "Update Error",
                str(e)
            )

        finally:

            if cur:
                cur.close()

            if conn:
                conn.close()

    # =========================================================
    # DEACTIVATE
    # =========================================================

    def deactivate_rule(self):

        if not self.selected_id:

            messagebox.showwarning(
                "Deactivate",
                "Double-click a rule first."
            )

            return

        if not messagebox.askyesno(
            "Confirm Deactivation",
            "Deactivate this wastage rule?"
        ):

            return

        conn = None
        cur = None

        try:

            conn = get_connection()
            cur = conn.cursor()

            cur.execute("""
                UPDATE worker_wastage_master
                SET
                    status = 'INACTIVE',
                    updated_at = CURRENT_TIMESTAMP
                WHERE wastage_id = %s
            """, (
                self.selected_id,
            ))

            conn.commit()

            messagebox.showinfo(
                "Success",
                "Wastage rule deactivated."
            )

            self.clear_form()
            self.load_rules()

        except Exception as e:

            if conn:
                conn.rollback()

            messagebox.showerror(
                "Deactivate Error",
                str(e)
            )

        finally:

            if cur:
                cur.close()

            if conn:
                conn.close()

    # =========================================================
    # CLEAR
    # =========================================================

    def clear_form(self):

        self.selected_id = None

        self.worker_id_var.set("")
        self.worker_var.set("")

        self.process_var.set("")

        self.metal_type_var.set("GOLD")
        self.purity_var.set("")

        self.allowed_percent_var.set("0.00")

        self.effective_from_var.set(
            date.today().strftime("%d-%m-%Y")
        )

        self.effective_to_var.set("")

        self.status_var.set("ACTIVE")
        self.remarks_var.set("")

        if hasattr(self, "tree"):

            for item in self.tree.selection():
                self.tree.selection_remove(item)


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    root = tk.Tk()
    root.withdraw()

    app = WorkerWastageMaster(root)

    root.mainloop()
