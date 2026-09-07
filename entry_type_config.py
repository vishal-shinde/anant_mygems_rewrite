"""
entry_type_config.py
----------------------------------------
✅ Entry Type Configuration Management
✅ Add/Edit/Delete entry types through UI
✅ NORMAL, STOCK, LOCK are fixed (cannot be deleted)
✅ Saves configuration to database
"""

import tkinter as tk
from tkinter import ttk, messagebox
import psycopg2
import json

# ---------------- PostgreSQL Connection ----------------
def get_connection():
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="mygems",
            user="myuser",
            password="28116"
        )
        return conn
    except Exception as e:
        messagebox.showerror("DB Connection Error", f"Failed to connect:\n{e}")
        return None


# ============================================================
# ✅ DATABASE SETUP FOR ENTRY TYPES
# ============================================================
def setup_entry_types_table():
    """Create entry_types configuration table if not exists"""
    conn = get_connection()
    if not conn:
        return False
    
    cur = conn.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS entry_types_config (
                type_key VARCHAR(50) PRIMARY KEY,
                type_label VARCHAR(100) NOT NULL,
                requires_lot_name BOOLEAN DEFAULT FALSE,
                generates_lot BOOLEAN DEFAULT TRUE,
                requires_customer BOOLEAN DEFAULT FALSE,
                allow_multiple_items BOOLEAN DEFAULT FALSE,
                description TEXT,
                is_fixed BOOLEAN DEFAULT FALSE,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert default fixed types if not exists
        default_types = [
            ("NORMAL", "Normal", False, True, False, True, "Regular purchase items", True),
            ("STOCK", "Stock", True, False, False, False, "Stock items with custom lot number", True),
            ("LOCK", "Lock", True, False, False, False, "Lock items with custom lot number", True),
        ]
        
        for dtype in default_types:
            cur.execute("""
                INSERT INTO entry_types_config 
                (type_key, type_label, requires_lot_name, generates_lot, requires_customer, 
                 allow_multiple_items, description, is_fixed)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (type_key) DO NOTHING
            """, dtype)
        
        conn.commit()
        return True
    except Exception as e:
        print("⚠️ Entry types table setup error:", e)
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


def get_all_entry_types():
    """Fetch all entry types from database"""
    conn = get_connection()
    if not conn:
        return {}
    
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT type_key, type_label, requires_lot_name, generates_lot, 
                   requires_customer, allow_multiple_items, description, is_fixed, is_active
            FROM entry_types_config
            WHERE is_active = TRUE
            ORDER BY 
                CASE WHEN is_fixed = TRUE THEN 0 ELSE 1 END,
                type_key
        """)
        
        types = {}
        for row in cur.fetchall():
            types[row[0]] = {
                "label": row[1],
                "requires_lot_name": row[2],
                "generates_lot": row[3],
                "requires_customer": row[4],
                "allow_multiple_items": row[5],
                "description": row[6] or "",
                "is_fixed": row[7],
                "is_active": row[8]
            }
        return types
    except Exception as e:
        print("⚠️ Fetch entry types error:", e)
        return {}
    finally:
        cur.close()
        conn.close()


def add_entry_type(type_key, type_label, requires_lot_name=False, generates_lot=True, 
                   requires_customer=False, allow_multiple_items=False, description=""):
    """Add new entry type to database"""
    conn = get_connection()
    if not conn:
        return False, "Database connection failed"
    
    cur = conn.cursor()
    try:
        # Check if type already exists
        cur.execute("SELECT 1 FROM entry_types_config WHERE type_key = %s", (type_key.upper(),))
        if cur.fetchone():
            return False, f"Entry type '{type_key}' already exists"
        
        cur.execute("""
            INSERT INTO entry_types_config 
            (type_key, type_label, requires_lot_name, generates_lot, requires_customer, 
             allow_multiple_items, description, is_fixed)
            VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE)
        """, (type_key.upper(), type_label, requires_lot_name, generates_lot, 
              requires_customer, allow_multiple_items, description))
        
        conn.commit()
        return True, "Entry type added successfully"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cur.close()
        conn.close()


def update_entry_type(type_key, type_label, requires_lot_name, generates_lot, 
                      requires_customer, allow_multiple_items, description):
    """Update existing entry type"""
    conn = get_connection()
    if not conn:
        return False, "Database connection failed"
    
    cur = conn.cursor()
    try:
        # Check if fixed type
        cur.execute("SELECT is_fixed FROM entry_types_config WHERE type_key = %s", (type_key.upper(),))
        res = cur.fetchone()
        if not res:
            return False, "Entry type not found"
        if res[0]:
            return False, "Cannot modify fixed entry types (NORMAL, STOCK, LOCK)"
        
        cur.execute("""
            UPDATE entry_types_config 
            SET type_label = %s, requires_lot_name = %s, generates_lot = %s,
                requires_customer = %s, allow_multiple_items = %s, description = %s
            WHERE type_key = %s
        """, (type_label, requires_lot_name, generates_lot, requires_customer, 
              allow_multiple_items, description, type_key.upper()))
        
        conn.commit()
        return True, "Entry type updated successfully"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cur.close()
        conn.close()


def delete_entry_type(type_key):
    """Delete entry type (soft delete - set is_active = FALSE)"""
    conn = get_connection()
    if not conn:
        return False, "Database connection failed"
    
    cur = conn.cursor()
    try:
        # Check if fixed type
        cur.execute("SELECT is_fixed FROM entry_types_config WHERE type_key = %s", (type_key.upper(),))
        res = cur.fetchone()
        if not res:
            return False, "Entry type not found"
        if res[0]:
            return False, "Cannot delete fixed entry types (NORMAL, STOCK, LOCK)"
        
        # Soft delete
        cur.execute("""
            UPDATE entry_types_config 
            SET is_active = FALSE 
            WHERE type_key = %s
        """, (type_key.upper(),))
        
        conn.commit()
        return True, "Entry type deleted successfully"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cur.close()
        conn.close()


# ============================================================
# ✅ ENTRY TYPE CONFIGURATION DIALOG
# ============================================================
class EntryTypeConfigDialog:
    """Dialog for managing entry types"""
    
    def __init__(self, parent):
        self.parent = parent
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("⚙️ Entry Type Configuration")
        self.dialog.geometry("900x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.resizable(False, False)
        
        self._build_ui()
        self._load_types()
    
    def _build_ui(self):
        # Header
        header = tk.Frame(self.dialog, bg="#f0f0f0", pady=10)
        header.pack(fill="x")
        tk.Label(header, text="Entry Type Configuration", 
                font=("Arial", 14, "bold"), bg="#f0f0f0").pack()
        tk.Label(header, text="Manage purchase entry types (NORMAL, STOCK, LOCK are fixed)", 
                font=("Arial", 9), bg="#f0f0f0", fg="gray").pack()
        
        # Types List Frame
        list_frame = tk.LabelFrame(self.dialog, text="Entry Types", padx=10, pady=10)
        list_frame.pack(fill="both", expand=True, padx=15, pady=10)
        
        cols = ("Type Key", "Label", "Lot Name", "Auto Lot", "Customer", "Multiple", "Fixed", "Status")
        self.types_tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=15)
        
        for c in cols:
            self.types_tree.heading(c, text=c)
            width = {"Type Key": 100, "Label": 120, "Lot Name": 70, "Auto Lot": 70, 
                    "Customer": 80, "Multiple": 80, "Fixed": 60, "Status": 70}
            self.types_tree.column(c, width=width.get(c, 80), anchor="center")
        
        self.types_tree.pack(fill="both", expand=True)
        
        # Scrollbar
        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.types_tree.yview)
        vsb.pack(side="right", fill="y")
        self.types_tree.configure(yscrollcommand=vsb.set)
        
        # Buttons Frame
        btn_frame = tk.Frame(self.dialog, pady=10)
        btn_frame.pack(fill="x", padx=15)
        
        tk.Button(btn_frame, text="➕ Add New Type", bg="#bfefff", 
                 command=self._open_add_dialog).pack(side="left", padx=5)
        tk.Button(btn_frame, text="✏️ Edit Selected", bg="#ffc86b", 
                 command=self._open_edit_dialog).pack(side="left", padx=5)
        tk.Button(btn_frame, text="❌ Delete Selected", bg="#ff9999", 
                 command=self._delete_selected).pack(side="left", padx=5)
        tk.Button(btn_frame, text="🔄 Refresh", bg="#87CEFA", 
                 command=self._load_types).pack(side="left", padx=5)
        tk.Button(btn_frame, text="✅ Close", bg="green", fg="white", 
                 command=self.dialog.destroy).pack(side="right", padx=5)
    
    def _load_types(self):
        """Load entry types from database"""
        self.types_tree.delete(*self.types_tree.get_children())
        types = get_all_entry_types()
        
        for type_key, config in types.items():
            status = "✅ Active" if config["is_active"] else "❌ Inactive"
            fixed = "🔒 Yes" if config["is_fixed"] else "No"
            lot_name = "✅ Yes" if config["requires_lot_name"] else "No"
            auto_lot = "✅ Yes" if config["generates_lot"] else "No"
            customer = "✅ Yes" if config["requires_customer"] else "No"
            multiple = "✅ Yes" if config["allow_multiple_items"] else "No"
            
            self.types_tree.insert("", "end", values=(
                type_key, config["label"], lot_name, auto_lot, customer, multiple, fixed, status
            ))
    
    def _open_add_dialog(self):
        """Open dialog to add new entry type"""
        AddEntryTypeDialog(self.dialog, self._load_types)
    
    def _open_edit_dialog(self):
        """Open dialog to edit selected entry type"""
        sel = self.types_tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Please select an entry type to edit")
            return
        
        vals = self.types_tree.item(sel[0], "values")
        type_key = vals[0]
        
        # Get full config
        types = get_all_entry_types()
        config = types.get(type_key, {})
        
        if config.get("is_fixed", False):
            messagebox.showwarning("Fixed Type", "Cannot edit fixed entry types (NORMAL, STOCK, LOCK)")
            return
        
        EditEntryTypeDialog(self.dialog, type_key, config, self._load_types)
    
    def _delete_selected(self):
        """Delete selected entry type"""
        sel = self.types_tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Please select an entry type to delete")
            return
        
        vals = self.types_tree.item(sel[0], "values")
        type_key = vals[0]
        
        # Get full config
        types = get_all_entry_types()
        config = types.get(type_key, {})
        
        if config.get("is_fixed", False):
            messagebox.showwarning("Fixed Type", "Cannot delete fixed entry types (NORMAL, STOCK, LOCK)")
            return
        
        if messagebox.askyesno("Confirm Delete", f"Delete entry type '{type_key}'?"):
            success, msg = delete_entry_type(type_key)
            if success:
                messagebox.showinfo("Success", msg)
                self._load_types()
            else:
                messagebox.showerror("Error", msg)


class AddEntryTypeDialog:
    """Dialog to add new entry type"""
    
    def __init__(self, parent, refresh_callback):
        self.parent = parent
        self.refresh_callback = refresh_callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("➕ Add Entry Type")
        self.dialog.geometry("550x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.resizable(False, False)
        
        self._build_ui()
    
    def _build_ui(self):
        # Type Key
        tk.Label(self.dialog, text="Type Key (e.g., BUY_BACK):").grid(row=0, column=0, sticky="w", padx=10, pady=10)
        self.key_entry = tk.Entry(self.dialog, width=40)
        self.key_entry.grid(row=0, column=1, padx=10, pady=10)
        
        # Type Label
        tk.Label(self.dialog, text="Display Label (e.g., Buy Back):").grid(row=1, column=0, sticky="w", padx=10, pady=10)
        self.label_entry = tk.Entry(self.dialog, width=40)
        self.label_entry.grid(row=1, column=1, padx=10, pady=10)
        
        # Description
        tk.Label(self.dialog, text="Description:").grid(row=2, column=0, sticky="w", padx=10, pady=10)
        self.desc_entry = tk.Entry(self.dialog, width=40)
        self.desc_entry.grid(row=2, column=1, padx=10, pady=10)
        
        # Options
        options_frame = tk.LabelFrame(self.dialog, text="Options", padx=10, pady=10)
        options_frame.grid(row=3, column=0, columnspan=2, sticky="w", padx=10, pady=10)
        
        self.requires_lot_name = tk.BooleanVar(value=False)
        tk.Checkbutton(options_frame, text="Requires Lot Name Input", 
                      variable=self.requires_lot_name).grid(row=0, column=0, sticky="w", pady=5)
        
        self.generates_lot = tk.BooleanVar(value=True)
        tk.Checkbutton(options_frame, text="Auto-Generate Lot Number", 
                      variable=self.generates_lot).grid(row=0, column=1, sticky="w", pady=5)
        
        self.requires_customer = tk.BooleanVar(value=False)
        tk.Checkbutton(options_frame, text="Requires Customer Selection", 
                      variable=self.requires_customer).grid(row=1, column=0, sticky="w", pady=5)
        
        self.allow_multiple_items = tk.BooleanVar(value=False)
        tk.Checkbutton(options_frame, text="Allow Multiple Item Rows", 
                      variable=self.allow_multiple_items).grid(row=1, column=1, sticky="w", pady=5)
        
        # Buttons
        btn_frame = tk.Frame(self.dialog, pady=15)
        btn_frame.grid(row=4, column=0, columnspan=2)
        
        tk.Button(btn_frame, text="✅ Save", bg="green", fg="white", 
                 command=self._save).pack(side="left", padx=10)
        tk.Button(btn_frame, text="❌ Cancel", bg="red", fg="white", 
                 command=self.dialog.destroy).pack(side="left", padx=10)
    
    def _save(self):
        """Save new entry type"""
        type_key = self.key_entry.get().strip().upper()
        type_label = self.label_entry.get().strip()
        description = self.desc_entry.get().strip()
        
        if not type_key:
            messagebox.showwarning("Missing", "Type Key is required")
            return
        if not type_label:
            messagebox.showwarning("Missing", "Display Label is required")
            return
        
        # Validate key format
        if not type_key.replace("_", "").isalnum():
            messagebox.showwarning("Invalid", "Type Key can only contain letters, numbers, and underscores")
            return
        
        success, msg = add_entry_type(
            type_key, type_label,
            requires_lot_name=self.requires_lot_name.get(),
            generates_lot=self.generates_lot.get(),
            requires_customer=self.requires_customer.get(),
            allow_multiple_items=self.allow_multiple_items.get(),
            description=description
        )
        
        if success:
            messagebox.showinfo("Success", msg)
            self.dialog.destroy()
            self.refresh_callback()
        else:
            messagebox.showerror("Error", msg)


class EditEntryTypeDialog:
    """Dialog to edit entry type"""
    
    def __init__(self, parent, type_key, config, refresh_callback):
        self.parent = parent
        self.type_key = type_key
        self.config = config
        self.refresh_callback = refresh_callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"✏️ Edit Entry Type - {type_key}")
        self.dialog.geometry("550x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.resizable(False, False)
        
        self._build_ui()
    
    def _build_ui(self):
        # Type Key (read-only)
        tk.Label(self.dialog, text="Type Key:").grid(row=0, column=0, sticky="w", padx=10, pady=10)
        tk.Label(self.dialog, text=self.type_key, font=("Arial", 11, "bold")).grid(row=0, column=1, sticky="w", padx=10, pady=10)
        
        # Type Label
        tk.Label(self.dialog, text="Display Label:").grid(row=1, column=0, sticky="w", padx=10, pady=10)
        self.label_entry = tk.Entry(self.dialog, width=40)
        self.label_entry.grid(row=1, column=1, padx=10, pady=10)
        self.label_entry.insert(0, self.config["label"])
        
        # Description
        tk.Label(self.dialog, text="Description:").grid(row=2, column=0, sticky="w", padx=10, pady=10)
        self.desc_entry = tk.Entry(self.dialog, width=40)
        self.desc_entry.grid(row=2, column=1, padx=10, pady=10)
        self.desc_entry.insert(0, self.config["description"])
        
        # Options
        options_frame = tk.LabelFrame(self.dialog, text="Options", padx=10, pady=10)
        options_frame.grid(row=3, column=0, columnspan=2, sticky="w", padx=10, pady=10)
        
        self.requires_lot_name = tk.BooleanVar(value=self.config["requires_lot_name"])
        tk.Checkbutton(options_frame, text="Requires Lot Name Input", 
                      variable=self.requires_lot_name).grid(row=0, column=0, sticky="w", pady=5)
        
        self.generates_lot = tk.BooleanVar(value=self.config["generates_lot"])
        tk.Checkbutton(options_frame, text="Auto-Generate Lot Number", 
                      variable=self.generates_lot).grid(row=0, column=1, sticky="w", pady=5)
        
        self.requires_customer = tk.BooleanVar(value=self.config["requires_customer"])
        tk.Checkbutton(options_frame, text="Requires Customer Selection", 
                      variable=self.requires_customer).grid(row=1, column=0, sticky="w", pady=5)
        
        self.allow_multiple_items = tk.BooleanVar(value=self.config["allow_multiple_items"])
        tk.Checkbutton(options_frame, text="Allow Multiple Item Rows", 
                      variable=self.allow_multiple_items).grid(row=1, column=1, sticky="w", pady=5)
        
        # Buttons
        btn_frame = tk.Frame(self.dialog, pady=15)
        btn_frame.grid(row=4, column=0, columnspan=2)
        
        tk.Button(btn_frame, text="✅ Save Changes", bg="green", fg="white", 
                 command=self._save).pack(side="left", padx=10)
        tk.Button(btn_frame, text="❌ Cancel", bg="red", fg="white", 
                 command=self.dialog.destroy).pack(side="left", padx=10)
    
    def _save(self):
        """Save updated entry type"""
        type_label = self.label_entry.get().strip()
        description = self.desc_entry.get().strip()
        
        if not type_label:
            messagebox.showwarning("Missing", "Display Label is required")
            return
        
        success, msg = update_entry_type(
            self.type_key, type_label,
            requires_lot_name=self.requires_lot_name.get(),
            generates_lot=self.generates_lot.get(),
            requires_customer=self.requires_customer.get(),
            allow_multiple_items=self.allow_multiple_items.get(),
            description=description
        )
        
        if success:
            messagebox.showinfo("Success", msg)
            self.dialog.destroy()
            self.refresh_callback()
        else:
            messagebox.showerror("Error", msg)


# ============================================================
# ✅ HELPER FUNCTION
# ============================================================
def open_entry_type_config(parent):
    """Open entry type configuration dialog"""
    setup_entry_types_table()  # Ensure table exists
    EntryTypeConfigDialog(parent)
