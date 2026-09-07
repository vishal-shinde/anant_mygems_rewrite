import tkinter as tk
from tkinter import ttk

NAVY = "#0a1a2f"
WHITE = "#ffffff"

root = tk.Tk()
root.title("GEMSART Jewelry - Shop Front ERP")
root.geometry("1400x800")
root.configure(bg=NAVY)

# ===================== MAIN CONTAINERS =====================

# Top section (Part 1)
top_frame = tk.Frame(root, bg=NAVY, height=400)
top_frame.pack(fill="x", padx=10, pady=5)

# Bottom section (Part 2)
bottom_frame = tk.Frame(root, bg=NAVY)
bottom_frame.pack(fill="both", expand=True, padx=10, pady=5)

# ===================== HEADER =====================

header = tk.Label(
    top_frame,
    text="GEMSART JEWELRY",
    bg=NAVY,
    fg=WHITE,
    font=("Arial", 26, "bold")
)
header.pack(fill="x", pady=10)

# ===================== TOP SPLIT =====================

content_frame = tk.Frame(top_frame, bg=NAVY)
content_frame.pack(fill="both", expand=True)

left_frame = tk.Frame(content_frame, bg=NAVY, width=600)
left_frame.pack(side="left", fill="both", expand=True, padx=10)

right_frame = tk.Frame(content_frame, bg=NAVY, width=800)
right_frame.pack(side="right", fill="both", expand=True, padx=10)

# ===================== LEFT PANEL =====================
# Lot Reference Search

lot_search_frame = tk.Frame(left_frame, bg=NAVY)
lot_search_frame.pack(anchor="nw", pady=10)

tk.Label(
    lot_search_frame, text="Lot Reference:",
    bg=NAVY, fg=WHITE, font=("Arial", 12)
).pack(side="left", padx=5)

lot_entry = tk.Entry(lot_search_frame, width=25, font=("Arial", 12))
lot_entry.pack(side="left", padx=5)

tk.Button(
    lot_search_frame, text="Search", width=10
).pack(side="left", padx=5)

# Image Box
image_box = tk.Label(
    left_frame,
    text="IMAGE PREVIEW",
    bg="#1e2f4f",
    fg=WHITE,
    width=50,
    height=15,
    relief="ridge"
)
image_box.pack(pady=20, fill="both", expand=True)

# ===================== RIGHT PANEL =====================
# Customer Search

cust_search_frame = tk.Frame(right_frame, bg=NAVY)
cust_search_frame.pack(anchor="nw", pady=5, fill="x")

tk.Label(
    cust_search_frame, text="Customer Phone:",
    bg=NAVY, fg=WHITE
).pack(side="left", padx=5)

cust_phone_entry = tk.Entry(cust_search_frame, width=20)
cust_phone_entry.pack(side="left", padx=5)

tk.Button(cust_search_frame, text="Search").pack(side="left", padx=5)
tk.Button(cust_search_frame, text="Add Customer").pack(side="left", padx=10)

# Customer Details
details_frame = tk.Frame(right_frame, bg=NAVY)
details_frame.pack(fill="x", pady=10)

# Left column
left_details = tk.Frame(details_frame, bg=NAVY)
left_details.pack(side="left", fill="both", expand=True)

tk.Label(left_details, text="Name:", bg=NAVY, fg=WHITE).pack(anchor="w")
tk.Label(left_details, text="Phone Number:", bg=NAVY, fg=WHITE).pack(anchor="w")
tk.Label(left_details, text="Address:", bg=NAVY, fg=WHITE).pack(anchor="w")

# Right column
right_details = tk.Frame(details_frame, bg=NAVY)
right_details.pack(side="right", fill="both", expand=True)

tk.Label(right_details, text="Previous Balance:", bg=NAVY, fg=WHITE).pack(anchor="w")
tk.Label(right_details, text="Customer Ref No:", bg=NAVY, fg=WHITE).pack(anchor="w")

# ===================== OPTIONS & ACTIONS =====================

options_frame = tk.Frame(right_frame, bg=NAVY)
options_frame.pack(fill="x", pady=10)

cert_var = tk.IntVar()
bill_var = tk.IntVar()

tk.Checkbutton(
    options_frame, text="Certificate",
    variable=cert_var, bg=NAVY, fg=WHITE,
    selectcolor=NAVY
).pack(side="left", padx=10)

tk.Checkbutton(
    options_frame, text="Bill",
    variable=bill_var, bg=NAVY, fg=WHITE,
    selectcolor=NAVY
).pack(side="left", padx=10)

buttons_frame = tk.Frame(right_frame, bg=NAVY)
buttons_frame.pack(fill="x", pady=10)

tk.Button(buttons_frame, text="Generate Order", width=15).pack(side="left", padx=5)
tk.Button(buttons_frame, text="Modify Order", width=15).pack(side="left", padx=5)
tk.Button(buttons_frame, text="New Order", width=15).pack(side="left", padx=5)

# ===================== BOTTOM TABLE =====================

columns = (
    "Select", "Lot Number", "BIGO Code", "Length",
    "Jewelry Type", "Weight", "Lock Type", "Price"
)

tree = ttk.Treeview(
    bottom_frame,
    columns=columns,
    show="headings",
    height=12
)

for col in columns:
    tree.heading(col, text=col)
    tree.column(col, width=150, anchor="center")

tree.pack(fill="both", expand=True)

# Dummy row example
tree.insert("", "end", values=(
    "☐", "LOT001", "BG123", "18cm",
    "Necklace", "12.5g", "Hook", "₹45,000"
))

root.mainloop()
