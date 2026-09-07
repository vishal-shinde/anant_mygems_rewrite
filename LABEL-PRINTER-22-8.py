"""
Thermal Label Printer App
==========================
A desktop tool (Tkinter) for designing a label layout, generating a matching
Excel import template, importing data from Excel, aligning/fine-tuning the
layout, adding barcodes / QR codes / images, and printing on a thermal
printer.

INSTALL (once):
    pip install pillow openpyxl python-barcode qrcode
    # Windows only, needed for direct raw printing:
    pip install pywin32

FIELD TYPES
-----------
- Text     : plain text (English, Thai, or mixed). If "Auto-fit" is on, long
             text automatically wraps to a second (or more) line, and shrinks
             the font, so it never overflows its box. A Thai-capable font
             (Tahoma / Leelawadee UI / Noto Sans Thai, depending on your OS)
             is picked automatically whenever it's found. If Thai text still
             shows as boxes, or tone marks look mis-stacked, use the
             per-field "Font file..." option to point at a specific Thai
             font (e.g. THSarabunNew.ttf) — and for best Thai tone-mark
             rendering, install the optional shaping library with
             `pip install "Pillow[raqm]"` (also needs libraqm on your OS).
- Barcode  : renders the field's value as a barcode (Code128 by default).
- QR Code  : renders the field's value as a QR code.
- Image    : renders an image. Either bind it to an Excel column that holds
             a file path, or set a fixed "Static image" for every label.

HOW IT WORKS
------------
1. Design your label: "Add Field", drag it into position, drag the little
   blue square in the bottom-right corner to resize. Pick a Type (Text /
   Barcode / QR Code / Image) and other options in the side panel.
2. "Generate Excel Template" -> creates an .xlsx whose column headers match
   your field names exactly.
3. "Import Excel" -> loads data. Use "Prev / Next" to preview rows.
4. Use the "Align" tools to line fields up, arrow keys to nudge.
5. "Preview" shows exactly what will be printed (actual size / DPI).
6. "Print" / "Print All" sends to your chosen printer.

Layouts save/load as JSON.
"""

import io
import json
import os
import platform
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from PIL import Image, ImageDraw, ImageFont, ImageTk

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill
except ImportError:
    openpyxl = None

try:
    import barcode as barcode_lib
    from barcode.writer import ImageWriter
except ImportError:
    barcode_lib = None

try:
    import qrcode
except ImportError:
    qrcode = None

IS_WINDOWS = platform.system() == "Windows"
if IS_WINDOWS:
    try:
        import win32print
        import win32ui
        import win32con
        import win32gui
        from PIL import ImageWin
    except ImportError:
        win32print = None
else:
    win32print = None

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MM_TO_INCH = 1.0 / 25.4
SCREEN_PX_PER_MM = 4.0
GRID_MM = 2.0
HANDLE_SIZE = 10                 # resize-handle box (screen px) - hit target
DEFAULT_LABEL_W_MM = 100.0
DEFAULT_LABEL_H_MM = 50.0
DEFAULT_DPI = 203
FIELD_TYPES = ["text", "barcode", "qrcode", "image"]
BARCODE_TYPES = ["code128", "ean13", "code39", "ean8", "upca"]

# Fonts that include Thai glyphs are listed first so Thai text (and mixed
# Thai/English text) renders correctly. Plain Arial/DejaVu Sans do NOT
# contain Thai glyphs and will show boxes/blanks for Thai characters.
FONT_CANDIDATES_REGULAR = [
    "C:/Windows/Fonts/tahoma.ttf",                              # Thai + Latin (Windows)
    "C:/Windows/Fonts/leelawUI.ttf",                             # Leelawadee UI (Thai + Latin)
    "C:/Windows/Fonts/angsa.ttc",                                # Angsana New (Thai + Latin)
    "/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf",   # Noto Sans Thai (Linux)
    "/usr/share/fonts/truetype/tlwg/Garuda.ttf",                 # TLWG Thai fonts (Linux)
    "/usr/share/fonts/truetype/tlwg/Loma.ttf",
    "/System/Library/Fonts/Supplemental/Ayuthaya.ttf",           # macOS Thai font
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",      # macOS wide-coverage font
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]
FONT_CANDIDATES_BOLD = [
    "C:/Windows/Fonts/tahomabd.ttf",
    "C:/Windows/Fonts/leelawUIb.ttf",
    "C:/Windows/Fonts/angsab.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansThai-Bold.ttf",
    "/usr/share/fonts/truetype/tlwg/Garuda-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]

# RAQM gives correct stacking of Thai tone/vowel marks above and below
# consonants. Pillow falls back silently to basic layout if libraqm isn't
# installed, so this is safe to always request.
try:
    _RAQM_LAYOUT = ImageFont.Layout.RAQM
except Exception:
    _RAQM_LAYOUT = None

_font_cache = {}


def find_font(size_px, bold=False, font_path=None):
    """Loads a font. `font_path`, if given, overrides the default search
    (use this to force a specific Thai font per field)."""
    key = (size_px, bold, font_path)
    if key in _font_cache:
        return _font_cache[key]
    search = [font_path] if font_path else (FONT_CANDIDATES_BOLD if bold else FONT_CANDIDATES_REGULAR)
    font = None
    for p in search:
        if p and os.path.exists(p):
            try:
                if _RAQM_LAYOUT is not None:
                    try:
                        font = ImageFont.truetype(p, size_px, layout_engine=_RAQM_LAYOUT)
                        break
                    except Exception:
                        pass
                font = ImageFont.truetype(p, size_px)
                break
            except Exception:
                pass
    if font is None:
        font = ImageFont.load_default()
    _font_cache[key] = font
    return font


def wrap_text(draw, text, font, max_w_px):
    """Greedy word-wrap. Falls back to hard character split for long tokens."""
    if not text:
        return [""]
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_w_px or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
        # if a single word itself is too wide, hard-split it
        while draw.textlength(cur, font=font) > max_w_px and len(cur) > 1:
            lo, hi = 1, len(cur)
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if draw.textlength(cur[:mid], font=font) <= max_w_px:
                    lo = mid
                else:
                    hi = mid - 1
            lines.append(cur[:lo])
            cur = cur[lo:]
    if cur:
        lines.append(cur)
    return lines or [""]


def fit_text(draw, text, max_w_px, max_h_px, base_font_px, bold=False, min_font_px=7, wrap=True, font_path=None):
    """Shrinks font size (and wraps, if allowed) until the text fits the box.
    Returns (lines, font)."""
    font_size = max(min_font_px, base_font_px)
    while font_size >= min_font_px:
        font = find_font(font_size, bold=bold, font_path=font_path)
        lines = wrap_text(draw, text, font, max_w_px) if wrap else [text]
        line_h = (font.getbbox("Ag")[3] - font.getbbox("Ag")[1]) + 3
        total_h = line_h * len(lines)
        widest = max((draw.textlength(l, font=font) for l in lines), default=0)
        if total_h <= max_h_px and widest <= max_w_px:
            return lines, font
        font_size -= 1
    font = find_font(min_font_px, bold=bold, font_path=font_path)
    lines = wrap_text(draw, text, font, max_w_px) if wrap else [text]
    return lines, font


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
class Field:
    def __init__(self, name, x_mm, y_mm, w_mm, h_mm, font_size=10,
                 align="left", bold=False, field_id=None, field_type="text",
                 auto_fit=True, barcode_type="code128", static_value="",
                 is_static=False, font_path=""):
        self.id = field_id or name
        self.name = name
        self.x_mm = x_mm
        self.y_mm = y_mm
        self.w_mm = w_mm
        self.h_mm = h_mm
        self.font_size = font_size
        self.align = align
        self.bold = bold
        self.field_type = field_type          # text / barcode / qrcode / image
        self.auto_fit = auto_fit              # wrap + shrink text to fit box
        self.barcode_type = barcode_type
        self.static_value = static_value      # fixed text, or fixed image path
        self.is_static = is_static            # True = same on every label, no Excel column needed
        self.font_path = font_path            # optional: force a specific font file (e.g. a Thai font)
        # canvas runtime refs
        self.tk_img = None

    def to_dict(self):
        return {
            "id": self.id, "name": self.name,
            "x_mm": self.x_mm, "y_mm": self.y_mm,
            "w_mm": self.w_mm, "h_mm": self.h_mm,
            "font_size": self.font_size, "align": self.align,
            "bold": self.bold, "field_type": self.field_type,
            "auto_fit": self.auto_fit, "barcode_type": self.barcode_type,
            "static_value": self.static_value, "is_static": self.is_static,
            "font_path": self.font_path,
        }

    @staticmethod
    def from_dict(d):
        return Field(
            d["name"], d["x_mm"], d["y_mm"], d["w_mm"], d["h_mm"],
            d.get("font_size", 10), d.get("align", "left"),
            d.get("bold", False), d.get("id"), d.get("field_type", "text"),
            d.get("auto_fit", True), d.get("barcode_type", "code128"),
            d.get("static_value", ""), d.get("is_static", False),
            d.get("font_path", ""),
        )


# ---------------------------------------------------------------------------
# Small dialog: add field (name + type)
# ---------------------------------------------------------------------------
class AddFieldDialog(simpledialog.Dialog):
    def body(self, master):
        ttk.Label(master, text="Field name:").grid(row=0, column=0, sticky="w", pady=4)
        self.name_var = tk.StringVar()
        ttk.Entry(master, textvariable=self.name_var).grid(row=0, column=1, pady=4)
        ttk.Label(master, text="Field type:").grid(row=1, column=0, sticky="w", pady=4)
        self.type_var = tk.StringVar(value="text")
        ttk.Combobox(master, textvariable=self.type_var, values=FIELD_TYPES,
                     state="readonly").grid(row=1, column=1, pady=4)
        return None

    def apply(self):
        self.result = (self.name_var.get().strip(), self.type_var.get())


class SheetLayoutDialog(simpledialog.Dialog):
    """Configures multi-up printing: N columns x M rows of the same label
    design tiled onto one printed sheet/page, e.g. a 3x3 grid on a wide
    thermal roll or a sheet of pre-cut labels."""

    def __init__(self, parent, app):
        self.app = app
        super().__init__(parent, title="Sheet / Grid Layout")

    def body(self, master):
        self.enabled_var = tk.BooleanVar(value=self.app.sheet_enabled)
        self.cols_var = tk.IntVar(value=self.app.sheet_cols)
        self.rows_var = tk.IntVar(value=self.app.sheet_rows)
        self.gap_var = tk.DoubleVar(value=self.app.sheet_gap_mm)
        self.margin_var = tk.DoubleVar(value=self.app.sheet_margin_mm)
        self.rounded_var = tk.BooleanVar(value=self.app.sheet_rounded)
        self.page_border_var = tk.BooleanVar(value=self.app.sheet_page_border)

        ttk.Checkbutton(master, text="Print labels in a multi-up grid (e.g. 3 columns x 3 rows per sheet)",
                         variable=self.enabled_var).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        r = 1
        for label, var in [
            ("Columns:", self.cols_var),
            ("Rows:", self.rows_var),
            ("Gap between labels (mm):", self.gap_var),
            ("Page margin (mm):", self.margin_var),
        ]:
            ttk.Label(master, text=label).grid(row=r, column=0, sticky="w", pady=3)
            ttk.Entry(master, textvariable=var, width=8).grid(row=r, column=1, sticky="w", pady=3)
            r += 1

        ttk.Checkbutton(master, text="Rounded corners on each label",
                         variable=self.rounded_var).grid(row=r, column=0, columnspan=2, sticky="w", pady=2)
        r += 1
        ttk.Checkbutton(master, text="Draw border around whole sheet",
                         variable=self.page_border_var).grid(row=r, column=0, columnspan=2, sticky="w", pady=2)
        r += 1
        ttk.Label(master, text="Each cell uses your label design above.\n"
                                "With data imported, each cell pulls the next row;\n"
                                "cells fill left-to-right, top-to-bottom.",
                  foreground="#666666", justify="left").grid(row=r, column=0, columnspan=2, sticky="w", pady=(8, 0))
        r += 1
        ttk.Label(master, text="\u26a0 On a thermal printer, this only works if the\n"
                                "printer driver's page/media size is set to the\n"
                                "FULL sheet (all columns x rows), not a single\n"
                                "label. Most thermal printers are configured for\n"
                                "one label at a time, in which case leave this\n"
                                "off and use Print / Print All instead.",
                  foreground="#a33", justify="left").grid(row=r, column=0, columnspan=2, sticky="w", pady=(6, 0))
        return None

    def apply(self):
        self.result = {
            "enabled": self.enabled_var.get(),
            "cols": max(1, self.cols_var.get()),
            "rows": max(1, self.rows_var.get()),
            "gap_mm": max(0.0, self.gap_var.get()),
            "margin_mm": max(0.0, self.margin_var.get()),
            "rounded": self.rounded_var.get(),
            "page_border": self.page_border_var.get(),
        }


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------
class PrinterSettingsDialog(simpledialog.Dialog):
    """Printer selection, DPI, and print-position offset, all in one popup
    so the main window doesn't need to show printer internals. Clicking
    Apply commits the settings and closes the dialog immediately."""

    def __init__(self, parent, app):
        self.app = app
        super().__init__(parent, title="Printer Settings")

    def body(self, master):
        self.app.refresh_printers(silent=True)

        ttk.Label(master, text="Printer:").grid(row=0, column=0, sticky="w", pady=3)
        self.printer_var = tk.StringVar(value=self.app.printer_var.get())
        self.printer_combo = ttk.Combobox(master, textvariable=self.printer_var,
                                           state="readonly", width=28,
                                           values=self.app.available_printers)
        self.printer_combo.grid(row=0, column=1, sticky="w", pady=3)
        ttk.Button(master, text="Refresh", command=self._refresh).grid(row=0, column=2, padx=(6, 0))

        self.status_lbl = ttk.Label(master, text=self.app.printer_status_var.get(),
                                     foreground="#a33", justify="left", wraplength=320)
        self.status_lbl.grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 6))

        ttk.Label(master, text="Printer DPI:").grid(row=2, column=0, sticky="w", pady=3)
        self.dpi_var = tk.IntVar(value=self.app.dpi)
        ttk.Spinbox(master, from_=50, to=1200, increment=1, width=8,
                    textvariable=self.dpi_var).grid(row=2, column=1, sticky="w", pady=3)
        ttk.Label(master, text="(must match your printer driver's actual\n"
                                "resolution -- check Printer Properties >\n"
                                "Advanced/Preferences. Common thermal\n"
                                "values: 203, 300, 600. A mismatch here is\n"
                                "the #1 cause of prints being the wrong size\n"
                                "or running off the printable area.)",
                  foreground="#666666", justify="left").grid(row=3, column=0, columnspan=3, sticky="w")

        ttk.Label(master, text="Print offset X (mm):").grid(row=4, column=0, sticky="w", pady=(10, 3))
        self.offset_x_var = tk.DoubleVar(value=self.app.print_offset_x_mm)
        ttk.Spinbox(master, from_=-100, to=100, increment=0.5, width=8,
                    textvariable=self.offset_x_var).grid(row=4, column=1, sticky="w", pady=(10, 3))

        ttk.Label(master, text="Print offset Y (mm):").grid(row=5, column=0, sticky="w", pady=3)
        self.offset_y_var = tk.DoubleVar(value=self.app.print_offset_y_mm)
        ttk.Spinbox(master, from_=-100, to=100, increment=0.5, width=8,
                    textvariable=self.offset_y_var).grid(row=5, column=1, sticky="w", pady=3)
        ttk.Label(master, text="(shifts everything sent to the printer, to\n"
                                "correct output that's consistently off-\n"
                                "position. Positive X = right, positive Y =\n"
                                "down. If content is missing rather than\n"
                                "shifted, the driver's page/media WIDTH is\n"
                                "probably set narrower than your label\n"
                                "stock -- fix that in Printer Properties\n"
                                "first, offset alone can't compensate.)",
                  foreground="#666666", justify="left").grid(row=6, column=0, columnspan=3, sticky="w")

        if IS_WINDOWS and win32print:
            ttk.Separator(master).grid(row=7, column=0, columnspan=3, sticky="ew", pady=8)
            self.raw_tspl_var = tk.BooleanVar(value=self.app.use_raw_tspl)
            ttk.Checkbutton(master, text="Use raw TSPL printing (bypasses the Windows driver)",
                             variable=self.raw_tspl_var).grid(row=8, column=0, columnspan=3, sticky="w")
            ttk.Label(master, text="(recommended for TP870/TP518/GZP-series,\n"
                                    "TSC, and other TSPL-compatible thermal\n"
                                    "printers. Sends label commands straight to\n"
                                    "the printer instead of going through the\n"
                                    "Windows page/paper-size machinery, which\n"
                                    "on these printers is what actually causes\n"
                                    "the printable area to be clipped.)",
                      foreground="#666666", justify="left").grid(row=9, column=0, columnspan=3, sticky="w")

            ttk.Label(master, text="Label gap (mm):").grid(row=10, column=0, sticky="w", pady=(6, 3))
            self.gap_var = tk.DoubleVar(value=self.app.tspl_gap_mm)
            ttk.Spinbox(master, from_=0, to=20, increment=0.5, width=8,
                        textvariable=self.gap_var).grid(row=10, column=1, sticky="w", pady=(6, 3))
            ttk.Label(master, text="(gap between labels on your die-cut roll --\n"
                                    "0 for continuous/no-gap stock. Only used\n"
                                    "when raw TSPL printing is on.)",
                      foreground="#666666", justify="left").grid(row=11, column=0, columnspan=3, sticky="w")
        else:
            self.raw_tspl_var = tk.BooleanVar(value=False)
            self.gap_var = tk.DoubleVar(value=self.app.tspl_gap_mm)

        return self.printer_combo

    def _refresh(self):
        self.app.refresh_printers(silent=True)
        self.printer_combo["values"] = self.app.available_printers
        self.status_lbl.config(text=self.app.printer_status_var.get())
        if self.app.available_printers and not self.printer_var.get():
            self.printer_var.set(self.app.available_printers[0])

    def buttonbox(self):
        box = ttk.Frame(self)
        ttk.Button(box, text="Apply", width=10, command=self.ok, default="active").pack(side="left", padx=5, pady=8)
        ttk.Button(box, text="Cancel", width=10, command=self.cancel).pack(side="left", padx=5, pady=8)
        self.bind("<Return>", lambda e: self.ok())
        self.bind("<Escape>", lambda e: self.cancel())
        box.pack()

    def apply(self):
        self.result = {
            "printer": self.printer_var.get(),
            "dpi": max(1, self.dpi_var.get()),
            "offset_x_mm": self.offset_x_var.get(),
            "offset_y_mm": self.offset_y_var.get(),
            "use_raw_tspl": self.raw_tspl_var.get(),
            "gap_mm": max(0.0, self.gap_var.get()),
        }


class LabelApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Thermal Label Printer")
        self.geometry("1200x740")

        self.label_w_mm = DEFAULT_LABEL_W_MM
        self.label_h_mm = DEFAULT_LABEL_H_MM
        self.dpi = DEFAULT_DPI
        self.fields = []
        self.selected_ids = set()
        self.drag_data = {"mode": None, "x": 0, "y": 0, "field": None}
        self.snap_enabled = tk.BooleanVar(value=True)

        self.records = []
        self.current_record_index = -1

        # Multi-up sheet printing (e.g. 3 columns x 3 rows of labels per page)
        self.sheet_enabled = False
        self.sheet_cols = 3
        self.sheet_rows = 3
        self.sheet_gap_mm = 3.0
        self.sheet_margin_mm = 4.0
        self.sheet_rounded = True
        self.sheet_page_border = True

        # Manual calibration offset applied to every print job, to correct
        # for thermal printers whose feed/registration doesn't line up
        # exactly with the rendered image (a very common thermal-printer
        # issue). Positive x moves content right, positive y moves it down.
        self.print_offset_x_mm = 0.0
        self.print_offset_y_mm = 0.0

        # Raw TSPL printing bypasses the Windows print driver entirely
        # (sends TSPL commands straight to the printer over the RAW spool
        # datatype), which sidesteps driver-specific page/label-size
        # settings that GDI printing can't reliably override. This is the
        # standard approach for TSPL-compatible thermal printers (TSC,
        # TP870/TP518/GZP-series, many Xprinter/Godex models).
        self.use_raw_tspl = IS_WINDOWS
        self.tspl_gap_mm = 2.0

        self._build_ui()
        self._redraw_label_outline()

    # -----------------------------------------------------------------
    def _build_ui(self):
        toolbar = ttk.Frame(self, padding=4)
        toolbar.pack(side="top", fill="x")

        ttk.Button(toolbar, text="Label Size...", command=self.set_label_size).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Sheet Layout...", command=self.open_sheet_layout_dialog).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Add Field", command=self.add_field_dialog).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Delete Field", command=self.delete_selected).pack(side="left", padx=2)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=6)

        ttk.Button(toolbar, text="Save Layout", command=self.save_layout).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Load Layout", command=self.load_layout).pack(side="left", padx=2)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=6)

        ttk.Button(toolbar, text="Generate Excel Template", command=self.generate_excel_template).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Import Excel", command=self.import_excel).pack(side="left", padx=2)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=6)

        ttk.Button(toolbar, text="Preview", command=self.open_preview).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Printer Settings...", command=self.open_printer_settings_dialog).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Print", command=self.print_current).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Print All", command=self.print_all).pack(side="left", padx=2)

        align_bar = ttk.LabelFrame(self, text="Align (select 2+ fields, or 1 field aligns to the label)", padding=4)
        align_bar.pack(side="top", fill="x", padx=4, pady=2)
        for label, cmd in [
            ("Left", lambda: self.align("left")),
            ("Center H", lambda: self.align("center_h")),
            ("Right", lambda: self.align("right")),
            ("Top", lambda: self.align("top")),
            ("Middle V", lambda: self.align("middle_v")),
            ("Bottom", lambda: self.align("bottom")),
            ("Distribute H", lambda: self.align("dist_h")),
            ("Distribute V", lambda: self.align("dist_v")),
        ]:
            ttk.Button(align_bar, text=label, command=cmd).pack(side="left", padx=2)
        ttk.Checkbutton(align_bar, text="Snap to grid", variable=self.snap_enabled).pack(side="left", padx=10)

        main = ttk.Frame(self)
        main.pack(side="top", fill="both", expand=True)

        canvas_frame = ttk.Frame(main, padding=6)
        canvas_frame.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(canvas_frame, bg="#dddddd")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.bind("<Left>", lambda e: self.nudge(-1, 0))
        self.bind("<Right>", lambda e: self.nudge(1, 0))
        self.bind("<Up>", lambda e: self.nudge(0, -1))
        self.bind("<Down>", lambda e: self.nudge(0, 1))

        side = ttk.Frame(main, padding=6, width=300)
        side.pack(side="right", fill="y")

        ttk.Label(side, text="Field Properties", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 6))
        self.prop_name_var = tk.StringVar()
        self.prop_type_var = tk.StringVar(value="text")
        self.prop_font_var = tk.IntVar(value=10)
        self.prop_align_var = tk.StringVar(value="left")
        self.prop_bold_var = tk.BooleanVar(value=False)
        self.prop_autofit_var = tk.BooleanVar(value=True)
        self.prop_barcode_type_var = tk.StringVar(value="code128")
        self.prop_static_var = tk.StringVar()
        self.prop_is_static_var = tk.BooleanVar(value=False)
        self.prop_font_path_var = tk.StringVar()

        row = ttk.Frame(side); row.pack(fill="x", pady=2)
        ttk.Label(row, text="Name:", width=10).pack(side="left")
        ttk.Entry(row, textvariable=self.prop_name_var).pack(side="left", fill="x", expand=True)

        row = ttk.Frame(side); row.pack(fill="x", pady=2)
        ttk.Label(row, text="Type:", width=10).pack(side="left")
        type_combo = ttk.Combobox(row, textvariable=self.prop_type_var, values=FIELD_TYPES,
                                   state="readonly")
        type_combo.pack(side="left", fill="x", expand=True)
        type_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_prop_panel())

        row = ttk.Frame(side); row.pack(fill="x", pady=2)
        ttk.Label(row, text="Font size:", width=10).pack(side="left")
        ttk.Spinbox(row, from_=4, to=96, textvariable=self.prop_font_var, width=5).pack(side="left")

        row = ttk.Frame(side); row.pack(fill="x", pady=2)
        ttk.Label(row, text="Align:", width=10).pack(side="left")
        ttk.Combobox(row, textvariable=self.prop_align_var, values=["left", "center", "right"],
                     width=8, state="readonly").pack(side="left")

        ttk.Checkbutton(side, text="Bold", variable=self.prop_bold_var).pack(anchor="w", pady=2)
        self.autofit_check = ttk.Checkbutton(
            side, text="Auto-fit (wrap + shrink text to box)", variable=self.prop_autofit_var)
        self.autofit_check.pack(anchor="w", pady=2)

        self.font_row = ttk.Frame(side)
        ttk.Label(self.font_row, text="Font file:", width=10).pack(side="left")
        ttk.Entry(self.font_row, textvariable=self.prop_font_path_var).pack(side="left", fill="x", expand=True)
        ttk.Button(self.font_row, text="...", width=3, command=self._browse_font).pack(side="left")
        self.font_row.pack(anchor="w", fill="x", pady=2)
        ttk.Label(side, text="(leave blank for auto — a Thai-capable font is\n"
                              "used automatically for Thai text; browse here\n"
                              "to force a specific font, e.g. a Thai typeface)",
                  foreground="#666666", justify="left").pack(anchor="w")

        self.barcode_row = ttk.Frame(side)
        ttk.Label(self.barcode_row, text="Symbology:", width=10).pack(side="left")
        ttk.Combobox(self.barcode_row, textvariable=self.prop_barcode_type_var,
                     values=BARCODE_TYPES, width=10, state="readonly").pack(side="left")

        self.static_row = ttk.Frame(side)
        self.static_label = ttk.Label(self.static_row, text="Fixed value:")
        self.static_label.pack(side="left")
        ttk.Entry(self.static_row, textvariable=self.prop_static_var).pack(side="left", fill="x", expand=True)
        self.image_browse_btn = ttk.Button(self.static_row, text="...", width=3, command=self._browse_static_image)

        self.is_static_check = ttk.Checkbutton(
            side, text="Static field (same on every label — no Excel column)",
            variable=self.prop_is_static_var, command=self._refresh_prop_panel)
        self.is_static_check.pack(anchor="w", pady=2)
        ttk.Label(side, text="(e.g. company name / logo, printed on every\nlabel. Not included in the Excel template.)",
                  foreground="#666666", justify="left").pack(anchor="w")

        ttk.Button(side, text="Apply to Selected Field", command=self.apply_field_props).pack(fill="x", pady=6)
        self._refresh_prop_panel()

        ttk.Separator(side).pack(fill="x", pady=8)
        ttk.Label(side, text="Imported Data", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.record_label = ttk.Label(side, text="No data imported")
        self.record_label.pack(anchor="w", pady=4)
        nav = ttk.Frame(side); nav.pack(fill="x", pady=2)
        ttk.Button(nav, text="<< Prev", command=self.prev_record).pack(side="left", expand=True, fill="x")
        ttk.Button(nav, text="Next >>", command=self.next_record).pack(side="left", expand=True, fill="x")

        # Printer state lives here (needed by refresh_printers / printing),
        # but the controls themselves are in the "Printer Settings..." popup
        # (see open_printer_settings_dialog) rather than cluttering this panel.
        self.available_printers = []
        self.printer_var = tk.StringVar()
        self.printer_dpi_var = tk.IntVar(value=self.dpi)
        self.print_offset_x_var = tk.DoubleVar(value=self.print_offset_x_mm)
        self.print_offset_y_var = tk.DoubleVar(value=self.print_offset_y_mm)
        self.printer_status_var = tk.StringVar(value="")

        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(self, textvariable=self.status_var, relief="sunken", anchor="w").pack(side="bottom", fill="x")

        self.refresh_printers(silent=True)

    def open_printer_settings_dialog(self):
        dlg = PrinterSettingsDialog(self, self)
        if dlg.result:
            self.printer_var.set(dlg.result["printer"])
            self.printer_dpi_var.set(dlg.result["dpi"])
            self.dpi = max(1, dlg.result["dpi"])
            self.print_offset_x_var.set(dlg.result["offset_x_mm"])
            self.print_offset_y_var.set(dlg.result["offset_y_mm"])
            self.print_offset_x_mm = dlg.result["offset_x_mm"]
            self.print_offset_y_mm = dlg.result["offset_y_mm"]
            self.use_raw_tspl = dlg.result.get("use_raw_tspl", self.use_raw_tspl)
            self.tspl_gap_mm = dlg.result.get("gap_mm", self.tspl_gap_mm)
            self.redraw_all_fields()
            mode = "raw TSPL" if (IS_WINDOWS and self.use_raw_tspl) else "Windows driver"
            self.status_var.set(
                f"Printer settings applied: {dlg.result['printer'] or '(none)'}, "
                f"{dlg.result['dpi']} DPI, offset X={dlg.result['offset_x_mm']:g}mm "
                f"Y={dlg.result['offset_y_mm']:g}mm, {mode} printing")

    def _refresh_prop_panel(self):
        ftype = self.prop_type_var.get()
        is_static = self.prop_is_static_var.get()
        self.barcode_row.pack_forget()
        self.static_row.pack_forget()
        self.image_browse_btn.pack_forget()
        if ftype == "barcode":
            self.barcode_row.pack(fill="x", pady=2, before=self.is_static_check)
        # a static field always needs its fixed value shown, regardless of type;
        # a non-static barcode/qrcode/image also gets a "fallback" value field.
        if is_static or ftype in ("barcode", "qrcode", "image"):
            self.static_label.config(
                text="Fixed image path:" if ftype == "image" else "Fixed value:")
            self.static_row.pack(fill="x", pady=2, before=self.is_static_check)
            if ftype == "image":
                self.image_browse_btn.pack(side="left")
        # auto-fit only makes sense for text
        state = "normal" if ftype == "text" else "disabled"
        self.autofit_check.config(state=state)

    def _browse_static_image(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.gif")])
        if path:
            self.prop_static_var.set(path)

    def _browse_font(self):
        path = filedialog.askopenfilename(filetypes=[("Font files", "*.ttf *.ttc *.otf")])
        if path:
            self.prop_font_path_var.set(path)

    # -----------------------------------------------------------------
    # Coordinate helpers
    # -----------------------------------------------------------------
    def mm_to_px(self, mm):
        return mm * SCREEN_PX_PER_MM

    def px_to_mm(self, px):
        return px / SCREEN_PX_PER_MM

    def snap(self, mm_value):
        if self.snap_enabled.get():
            return round(mm_value / GRID_MM) * GRID_MM
        return mm_value

    # -----------------------------------------------------------------
    # Label size / canvas drawing
    # -----------------------------------------------------------------
    def set_label_size(self):
        w = simpledialog.askfloat("Label Width (mm)", "Width in mm:", initialvalue=self.label_w_mm)
        if w is None:
            return
        h = simpledialog.askfloat("Label Height (mm)", "Height in mm:", initialvalue=self.label_h_mm)
        if h is None:
            return
        self.label_w_mm, self.label_h_mm = w, h
        self._redraw_label_outline()
        self.redraw_all_fields()

    def open_sheet_layout_dialog(self):
        dlg = SheetLayoutDialog(self, self)
        if not dlg.result:
            return
        r = dlg.result
        self.sheet_enabled = r["enabled"]
        self.sheet_cols = r["cols"]
        self.sheet_rows = r["rows"]
        self.sheet_gap_mm = r["gap_mm"]
        self.sheet_margin_mm = r["margin_mm"]
        self.sheet_rounded = r["rounded"]
        self.sheet_page_border = r["page_border"]
        status = (f"Sheet layout: {self.sheet_cols} x {self.sheet_rows} per page (enabled)"
                   if self.sheet_enabled else "Sheet layout disabled — printing one label at a time.")
        self.status_var.set(status)

    def _redraw_label_outline(self):
        self.canvas.delete("outline")
        w = self.mm_to_px(self.label_w_mm)
        h = self.mm_to_px(self.label_h_mm)
        self.canvas.config(scrollregion=(0, 0, w + 40, h + 40))
        self.canvas.create_rectangle(10, 10, 10 + w, 10 + h, fill="white",
                                      outline="black", width=2, tags="outline")
        step = self.mm_to_px(GRID_MM)
        x = 10
        while x <= 10 + w:
            self.canvas.create_line(x, 10, x, 10 + h, fill="#eeeeee", tags="outline")
            x += step
        y = 10
        while y <= 10 + h:
            self.canvas.create_line(10, y, 10 + w, y, fill="#eeeeee", tags="outline")
            y += step
        self.canvas.tag_lower("outline")

    # -----------------------------------------------------------------
    # Fields: add / delete / draw
    # -----------------------------------------------------------------
    def add_field_dialog(self):
        dlg = AddFieldDialog(self, title="New Field")
        if not dlg.result:
            return
        name, ftype = dlg.result
        if not name:
            return
        if any(f.name == name for f in self.fields):
            messagebox.showerror("Duplicate", "A field with that name already exists.")
            return
        f = Field(name, x_mm=5, y_mm=5, w_mm=35, h_mm=12, field_type=ftype)
        if ftype in ("barcode", "qrcode", "image"):
            f.w_mm, f.h_mm = (30, 15) if ftype != "image" else (25, 25)
        self.fields.append(f)
        self.select_only(f.id)
        self.redraw_all_fields()

    def delete_selected(self):
        if not self.selected_ids:
            messagebox.showinfo("Delete Field", "Select a field first.")
            return
        self.fields = [f for f in self.fields if f.id not in self.selected_ids]
        self.selected_ids.clear()
        self.redraw_all_fields()

    def redraw_all_fields(self):
        self.canvas.delete("field")
        for f in self.fields:
            self.draw_field(f)

    def resolve_value(self, f: Field):
        """Resolve what should be shown/printed for a field, given the current record."""
        if f.is_static:
            return f.static_value or (f.name if f.field_type == "text" else f"SAMPLE-{f.name}")
        if 0 <= self.current_record_index < len(self.records):
            rec = self.records[self.current_record_index]
            for k, v in rec.items():
                if k.strip().lower() == f.name.strip().lower() and v not in (None, ""):
                    return str(v)
        if f.static_value:
            return f.static_value
        return f.name if f.field_type == "text" else f"SAMPLE-{f.name}"

    def draw_field(self, f: Field):
        self.canvas.delete(f"item_{f.id}")
        x0 = 10 + self.mm_to_px(f.x_mm)
        y0 = 10 + self.mm_to_px(f.y_mm)
        x1 = x0 + self.mm_to_px(f.w_mm)
        y1 = y0 + self.mm_to_px(f.h_mm)
        selected = f.id in self.selected_ids
        outline = "#0078d7" if selected else "#888888"
        width = 2 if selected else 1
        self.canvas.create_rectangle(
            x0, y0, x1, y1, fill="#fffbe6", outline=outline, width=width,
            tags=("field", f"item_{f.id}", f"rect_{f.id}"))

        box_w_px = max(1, int(x1 - x0))
        box_h_px = max(1, int(y1 - y0))
        value = self.resolve_value(f)

        if f.field_type == "text":
            preview = Image.new("RGBA", (box_w_px, box_h_px), (0, 0, 0, 0))
            pdraw = ImageDraw.Draw(preview)
            base_font_px = max(6, int(f.font_size * SCREEN_PX_PER_MM * 0.55))
            if f.auto_fit:
                lines, font = fit_text(pdraw, value, box_w_px - 4, box_h_px - 2, base_font_px,
                                        bold=f.bold, font_path=(f.font_path or None))
            else:
                font = find_font(base_font_px, bold=f.bold, font_path=(f.font_path or None))
                lines = [value]
            line_h = (font.getbbox("Ag")[3] - font.getbbox("Ag")[1]) + 3
            total_h = line_h * len(lines)
            ty = max(0, (box_h_px - total_h) / 2)
            for line in lines:
                lw = pdraw.textlength(line, font=font)
                if f.align == "left":
                    tx = 2
                elif f.align == "center":
                    tx = (box_w_px - lw) / 2
                else:
                    tx = box_w_px - lw - 2
                pdraw.text((tx, ty), line, font=font, fill=(20, 20, 20, 255))
                ty += line_h
            f.tk_img = ImageTk.PhotoImage(preview)
            self.canvas.create_image(x0, y0, image=f.tk_img, anchor="nw",
                                      tags=("field", f"item_{f.id}", f"content_{f.id}"))
        else:
            thumb = self._render_symbol_or_image(f, value, box_w_px, box_h_px)
            if thumb is not None:
                f.tk_img = ImageTk.PhotoImage(thumb)
                self.canvas.create_image(x0, y0, image=f.tk_img, anchor="nw",
                                          tags=("field", f"item_{f.id}", f"content_{f.id}"))
            else:
                self.canvas.create_text(
                    (x0 + x1) / 2, (y0 + y1) / 2, text=f"[{f.field_type.upper()}]\n{f.name}",
                    fill="#aa0000", tags=("field", f"item_{f.id}"))

        # label the field name faintly at top-left so it's identifiable even when small
        self.canvas.create_text(x0 + 2, y0 + 1, text=f.name, anchor="nw",
                                 font=("Segoe UI", 6), fill="#0078d7",
                                 tags=("field", f"item_{f.id}"))

        handle_color = "#0078d7" if selected else "#666666"
        self.canvas.create_rectangle(
            x1 - HANDLE_SIZE, y1 - HANDLE_SIZE, x1, y1,
            fill=handle_color, outline="white",
            tags=("field", f"item_{f.id}", f"handle_{f.id}"))

    def _render_symbol_or_image(self, f: Field, value, box_w_px, box_h_px):
        """Returns a PIL image (RGBA/RGB) for barcode/qrcode/image field types, sized to box."""
        try:
            if f.field_type == "qrcode":
                if qrcode is None:
                    return None
                qr = qrcode.QRCode(border=1)
                qr.add_data(value)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
                side = min(box_w_px, box_h_px)
                return img.resize((max(1, side), max(1, side)), Image.NEAREST)
            elif f.field_type == "barcode":
                if barcode_lib is None:
                    return None
                cls = barcode_lib.get_barcode_class(f.barcode_type)
                buf = io.BytesIO()
                cls(value, writer=ImageWriter()).write(
                    buf, options={"write_text": False, "quiet_zone": 1})
                buf.seek(0)
                img = Image.open(buf).convert("RGB")
                return img.resize((max(1, box_w_px), max(1, box_h_px)))
            elif f.field_type == "image":
                path = None
                if not f.is_static and 0 <= self.current_record_index < len(self.records):
                    rec = self.records[self.current_record_index]
                    for k, v in rec.items():
                        if k.strip().lower() == f.name.strip().lower() and v:
                            path = str(v)
                            break
                if not path:
                    path = f.static_value
                if not path or not os.path.exists(path):
                    return None
                img = Image.open(path).convert("RGB")
                img.thumbnail((box_w_px, box_h_px))
                canvas_img = Image.new("RGB", (box_w_px, box_h_px), "white")
                ox = (box_w_px - img.width) // 2
                oy = (box_h_px - img.height) // 2
                canvas_img.paste(img, (ox, oy))
                return canvas_img
        except Exception:
            return None
        return None

    def field_at(self, x, y):
        """Prioritizes resize handles over move, and checks the topmost items first."""
        items = self.canvas.find_overlapping(x - 4, y - 4, x + 4, y + 4)
        for item in reversed(items):
            for t in self.canvas.gettags(item):
                if t.startswith("handle_"):
                    return t[len("handle_"):], "resize"
        for item in reversed(items):
            for t in self.canvas.gettags(item):
                if t.startswith("item_"):
                    return t[len("item_"):], "move"
        return None, None

    def get_field(self, field_id):
        for f in self.fields:
            if f.id == field_id:
                return f
        return None

    # -----------------------------------------------------------------
    # Canvas interaction
    # -----------------------------------------------------------------
    def on_canvas_click(self, event):
        field_id, mode = self.field_at(event.x, event.y)
        shift = (event.state & 0x0001) != 0
        if field_id is None:
            if not shift:
                self.select_only(None)
            return
        if shift and mode == "move":
            if field_id in self.selected_ids:
                self.selected_ids.discard(field_id)
            else:
                self.selected_ids.add(field_id)
            self.redraw_all_fields()
        else:
            if field_id not in self.selected_ids:
                self.select_only(field_id)
        self.drag_data = {"mode": mode, "x": event.x, "y": event.y, "field": field_id}
        f = self.get_field(field_id)
        if f:
            self._load_props_from_field(f)

    def _load_props_from_field(self, f: Field):
        self.prop_name_var.set(f.name)
        self.prop_type_var.set(f.field_type)
        self.prop_font_var.set(f.font_size)
        self.prop_align_var.set(f.align)
        self.prop_bold_var.set(f.bold)
        self.prop_autofit_var.set(f.auto_fit)
        self.prop_barcode_type_var.set(f.barcode_type)
        self.prop_static_var.set(f.static_value)
        self.prop_is_static_var.set(f.is_static)
        self.prop_font_path_var.set(f.font_path)
        self._refresh_prop_panel()

    def select_only(self, field_id):
        self.selected_ids = {field_id} if field_id else set()
        self.redraw_all_fields()

    def on_canvas_drag(self, event):
        if not self.drag_data.get("field"):
            return
        dx = self.px_to_mm(event.x - self.drag_data["x"])
        dy = self.px_to_mm(event.y - self.drag_data["y"])
        f = self.get_field(self.drag_data["field"])
        if not f:
            return
        if self.drag_data["mode"] == "move":
            for fid in (self.selected_ids or {f.id}):
                ff = self.get_field(fid)
                if ff:
                    ff.x_mm = max(0, ff.x_mm + dx)
                    ff.y_mm = max(0, ff.y_mm + dy)
        else:  # resize - only affects the field whose handle was grabbed
            f.w_mm = max(4, f.w_mm + dx)
            f.h_mm = max(4, f.h_mm + dy)
        self.drag_data["x"], self.drag_data["y"] = event.x, event.y
        self.redraw_all_fields()

    def on_canvas_release(self, event):
        if self.drag_data.get("field"):
            ids = self.selected_ids or {self.drag_data["field"]}
            for fid in ids:
                f = self.get_field(fid)
                if f:
                    f.x_mm = self.snap(f.x_mm)
                    f.y_mm = self.snap(f.y_mm)
                    if self.drag_data["mode"] == "resize":
                        f.w_mm = self.snap(f.w_mm)
                        f.h_mm = self.snap(f.h_mm)
            self.redraw_all_fields()
        self.drag_data = {"mode": None, "x": 0, "y": 0, "field": None}

    def nudge(self, dx_dir, dy_dir):
        if not self.selected_ids:
            return
        step = GRID_MM if self.snap_enabled.get() else 0.5
        for fid in self.selected_ids:
            f = self.get_field(fid)
            if f:
                f.x_mm = max(0, f.x_mm + dx_dir * step)
                f.y_mm = max(0, f.y_mm + dy_dir * step)
        self.redraw_all_fields()

    def apply_field_props(self):
        if not self.selected_ids:
            messagebox.showinfo("Field Properties", "Select a field first.")
            return
        for fid in self.selected_ids:
            f = self.get_field(fid)
            if not f:
                continue
            new_name = self.prop_name_var.get().strip()
            if new_name and len(self.selected_ids) == 1:
                f.name = new_name
            f.field_type = self.prop_type_var.get()
            f.font_size = self.prop_font_var.get()
            f.align = self.prop_align_var.get()
            f.bold = self.prop_bold_var.get()
            f.auto_fit = self.prop_autofit_var.get()
            f.barcode_type = self.prop_barcode_type_var.get()
            f.static_value = self.prop_static_var.get()
            f.is_static = self.prop_is_static_var.get()
            f.font_path = self.prop_font_path_var.get().strip()
        self.redraw_all_fields()

    # -----------------------------------------------------------------
    # Align tools
    # -----------------------------------------------------------------
    def align(self, mode):
        fields = [self.get_field(fid) for fid in self.selected_ids]
        fields = [f for f in fields if f]
        if len(fields) < 2:
            if len(fields) == 1 and mode in ("left", "right", "center_h", "top", "bottom", "middle_v"):
                f = fields[0]
                if mode == "left":
                    f.x_mm = 0
                elif mode == "right":
                    f.x_mm = self.label_w_mm - f.w_mm
                elif mode == "center_h":
                    f.x_mm = (self.label_w_mm - f.w_mm) / 2
                elif mode == "top":
                    f.y_mm = 0
                elif mode == "bottom":
                    f.y_mm = self.label_h_mm - f.h_mm
                elif mode == "middle_v":
                    f.y_mm = (self.label_h_mm - f.h_mm) / 2
                self.redraw_all_fields()
            else:
                messagebox.showinfo("Align", "Select at least two fields (or one, to align to the label).")
            return

        if mode == "left":
            ref = min(f.x_mm for f in fields)
            for f in fields: f.x_mm = ref
        elif mode == "right":
            ref = max(f.x_mm + f.w_mm for f in fields)
            for f in fields: f.x_mm = ref - f.w_mm
        elif mode == "center_h":
            ref = sum(f.x_mm + f.w_mm / 2 for f in fields) / len(fields)
            for f in fields: f.x_mm = ref - f.w_mm / 2
        elif mode == "top":
            ref = min(f.y_mm for f in fields)
            for f in fields: f.y_mm = ref
        elif mode == "bottom":
            ref = max(f.y_mm + f.h_mm for f in fields)
            for f in fields: f.y_mm = ref - f.h_mm
        elif mode == "middle_v":
            ref = sum(f.y_mm + f.h_mm / 2 for f in fields) / len(fields)
            for f in fields: f.y_mm = ref - f.h_mm / 2
        elif mode == "dist_h":
            fields.sort(key=lambda f: f.x_mm)
            left = fields[0].x_mm
            right = fields[-1].x_mm + fields[-1].w_mm
            total_w = sum(f.w_mm for f in fields)
            gap = (right - left - total_w) / (len(fields) - 1) if len(fields) > 1 else 0
            cursor = left
            for f in fields:
                f.x_mm = cursor
                cursor += f.w_mm + gap
        elif mode == "dist_v":
            fields.sort(key=lambda f: f.y_mm)
            top = fields[0].y_mm
            bottom = fields[-1].y_mm + fields[-1].h_mm
            total_h = sum(f.h_mm for f in fields)
            gap = (bottom - top - total_h) / (len(fields) - 1) if len(fields) > 1 else 0
            cursor = top
            for f in fields:
                f.y_mm = cursor
                cursor += f.h_mm + gap

        self.redraw_all_fields()

    # -----------------------------------------------------------------
    # Layout save / load
    # -----------------------------------------------------------------
    def save_layout(self):
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                             filetypes=[("Layout JSON", "*.json")])
        if not path:
            return
        data = {
            "label_w_mm": self.label_w_mm, "label_h_mm": self.label_h_mm,
            "dpi": self.dpi, "fields": [f.to_dict() for f in self.fields],
            "sheet_enabled": self.sheet_enabled, "sheet_cols": self.sheet_cols,
            "sheet_rows": self.sheet_rows, "sheet_gap_mm": self.sheet_gap_mm,
            "sheet_margin_mm": self.sheet_margin_mm, "sheet_rounded": self.sheet_rounded,
            "sheet_page_border": self.sheet_page_border,
            "print_offset_x_mm": self.print_offset_x_var.get(),
            "print_offset_y_mm": self.print_offset_y_var.get(),
            "use_raw_tspl": self.use_raw_tspl,
            "tspl_gap_mm": self.tspl_gap_mm,
        }
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(data, fp, indent=2)
        self.status_var.set(f"Layout saved: {path}")

    def load_layout(self):
        path = filedialog.askopenfilename(filetypes=[("Layout JSON", "*.json")])
        if not path:
            return
        with open(path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        self.label_w_mm = data.get("label_w_mm", DEFAULT_LABEL_W_MM)
        self.label_h_mm = data.get("label_h_mm", DEFAULT_LABEL_H_MM)
        self.dpi = data.get("dpi", DEFAULT_DPI)
        if hasattr(self, "printer_dpi_var"):
            self.printer_dpi_var.set(self.dpi)
        self.fields = [Field.from_dict(d) for d in data.get("fields", [])]
        self.sheet_enabled = data.get("sheet_enabled", False)
        self.sheet_cols = data.get("sheet_cols", 3)
        self.sheet_rows = data.get("sheet_rows", 3)
        self.sheet_gap_mm = data.get("sheet_gap_mm", 3.0)
        self.sheet_margin_mm = data.get("sheet_margin_mm", 4.0)
        self.sheet_rounded = data.get("sheet_rounded", True)
        self.sheet_page_border = data.get("sheet_page_border", True)
        self.print_offset_x_var.set(data.get("print_offset_x_mm", 0.0))
        self.print_offset_y_var.set(data.get("print_offset_y_mm", 0.0))
        self.print_offset_x_mm = self.print_offset_x_var.get()
        self.print_offset_y_mm = self.print_offset_y_var.get()
        self.use_raw_tspl = data.get("use_raw_tspl", IS_WINDOWS)
        self.tspl_gap_mm = data.get("tspl_gap_mm", 2.0)
        self.selected_ids.clear()
        self._redraw_label_outline()
        self.redraw_all_fields()
        self.status_var.set(f"Layout loaded: {path}")

    # -----------------------------------------------------------------
    # Excel
    # -----------------------------------------------------------------
    def _require_openpyxl(self):
        if openpyxl is None:
            messagebox.showerror("Missing dependency", "Please install openpyxl:\n\npip install openpyxl")
            return False
        return True

    def generate_excel_template(self):
        if not self._require_openpyxl():
            return
        dynamic_fields = [f for f in self.fields if not f.is_static]
        static_fields = [f for f in self.fields if f.is_static]
        if not dynamic_fields:
            messagebox.showinfo("Generate Template",
                                 "All your fields are marked as static — there's nothing that "
                                 "varies per label, so no Excel columns are needed.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".xlsx",
                                             filetypes=[("Excel Workbook", "*.xlsx")],
                                             initialfile="label_import_template.xlsx")
        if not path:
            return
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Labels"
        headers = [f.name for f in dynamic_fields]
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="0078D7", end_color="0078D7", fill_type="solid")
        for col, f in enumerate(dynamic_fields, start=1):
            cell = ws.cell(row=1, column=col, value=f.name)
            cell.font = header_font
            cell.fill = header_fill
            ws.column_dimensions[cell.column_letter].width = max(16, len(f.name) + 6)
            hint = {"text": f"Sample {f.name}", "barcode": "0123456789",
                    "qrcode": "https://example.com", "image": "C:\\images\\sample.png"}[f.field_type]
            ws.cell(row=2, column=col, value=hint)
        wb.save(path)
        self.status_var.set(f"Template generated: {path}")
        msg = (f"Template saved to:\n{path}\n\n"
               f"Columns (one per label, varies by row):\n{', '.join(headers)}\n\n"
               "For 'image' fields, put the full file path to the picture in that column.\n"
               "Fill your data starting at row 2, then use Import Excel.")
        if static_fields:
            msg += ("\n\nNot included (static — same on every label):\n"
                    + ', '.join(f.name for f in static_fields))
        messagebox.showinfo("Template Generated", msg)

    def import_excel(self):
        if not self._require_openpyxl():
            return
        path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx *.xlsm")])
        if not path:
            return
        wb = openpyxl.load_workbook(path, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            messagebox.showerror("Import Excel", "The sheet appears to be empty.")
            return
        headers = [str(h).strip() if h is not None else "" for h in rows[0]]
        dynamic_fields = [f for f in self.fields if not f.is_static]
        field_names = {f.name.strip().lower() for f in dynamic_fields}
        imported_names = {h.strip().lower() for h in headers if h}
        missing = [f.name for f in dynamic_fields if f.name.strip().lower() not in imported_names]
        extra = [h for h in headers if h and h.strip().lower() not in field_names]

        records = []
        for r in rows[1:]:
            if r is None or all(v is None for v in r):
                continue
            rec = {h: (r[i] if i < len(r) else None) for i, h in enumerate(headers) if h}
            records.append(rec)

        self.records = records
        self.current_record_index = 0 if records else -1
        self.update_record_label()
        self.redraw_all_fields()

        msg = f"Imported {len(records)} row(s) from:\n{path}"
        if missing:
            msg += f"\n\n\u26a0 These layout fields have NO matching Excel column:\n{', '.join(missing)}"
        if extra:
            msg += f"\n\n\u2139 These Excel columns are not used by the layout:\n{', '.join(extra)}"
        self.status_var.set(f"Imported {len(records)} row(s) from {os.path.basename(path)}")
        messagebox.showinfo("Import Excel", msg)

    def update_record_label(self):
        if self.records and 0 <= self.current_record_index < len(self.records):
            self.record_label.config(text=f"Row {self.current_record_index + 1} of {len(self.records)}")
        else:
            self.record_label.config(text="No data imported")

    def prev_record(self):
        if not self.records:
            return
        self.current_record_index = max(0, self.current_record_index - 1)
        self.update_record_label()
        self.redraw_all_fields()

    def next_record(self):
        if not self.records:
            return
        self.current_record_index = min(len(self.records) - 1, self.current_record_index + 1)
        self.update_record_label()
        self.redraw_all_fields()

    # -----------------------------------------------------------------
    # Rendering a label to a real image (for printing / preview)
    # -----------------------------------------------------------------
    def _value_for(self, f, record):
        if f.is_static:
            return f.static_value or (f.name if f.field_type == "text" else f"SAMPLE-{f.name}")
        if record:
            for k, v in record.items():
                if k.strip().lower() == f.name.strip().lower() and v not in (None, ""):
                    return str(v)
        return f.static_value or (f.name if f.field_type == "text" else f"SAMPLE-{f.name}")

    def _draw_fields_onto(self, img, draw, record, offset_x_px=0, offset_y_px=0):
        """Draws every field for one label's worth of data onto `img`/`draw`,
        shifted by the given pixel offset. Used both for a single label and
        for each cell of a multi-up sheet."""

        def mm_to_ipx(mm):
            return mm * MM_TO_INCH * self.dpi

        for f in self.fields:
            x0 = offset_x_px + mm_to_ipx(f.x_mm)
            y0 = offset_y_px + mm_to_ipx(f.y_mm)
            w, h = mm_to_ipx(f.w_mm), mm_to_ipx(f.h_mm)
            value = self._value_for(f, record)

            if f.field_type == "text":
                base_font_px = max(6, round(f.font_size * self.dpi / 72))
                if f.auto_fit:
                    lines, font = fit_text(draw, value, w - 4, h - 2, base_font_px,
                                            bold=f.bold, font_path=(f.font_path or None))
                else:
                    font = find_font(base_font_px, bold=f.bold, font_path=(f.font_path or None))
                    lines = [value]
                line_h = (font.getbbox("Ag")[3] - font.getbbox("Ag")[1]) + 3
                total_h = line_h * len(lines)
                ty = y0 + max(0, (h - total_h) / 2)
                for line in lines:
                    lw = draw.textlength(line, font=font)
                    if f.align == "left":
                        tx = x0 + 2
                    elif f.align == "center":
                        tx = x0 + (w - lw) / 2
                    else:
                        tx = x0 + w - lw - 2
                    draw.text((tx, ty), line, font=font, fill=0)
                    ty += line_h
            else:
                symbol_img = self._render_symbol_or_image_full(f, value, int(w), int(h))
                if symbol_img is not None:
                    img.paste(symbol_img, (int(x0), int(y0)))
                else:
                    draw.rectangle([x0, y0, x0 + w, y0 + h], outline=0)
                    draw.text((x0 + 2, y0 + 2), f"[{f.field_type}]", font=find_font(10), fill=0)

    def render_label_image(self, record=None):
        """Renders ONE label (single cell) at real print resolution."""
        px_w = max(1, round(self.label_w_mm * MM_TO_INCH * self.dpi))
        px_h = max(1, round(self.label_h_mm * MM_TO_INCH * self.dpi))
        img = Image.new("RGB", (px_w, px_h), color="white")
        draw = ImageDraw.Draw(img)
        self._draw_fields_onto(img, draw, record, 0, 0)
        return img

    def get_page_chunks(self):
        """Splits records into groups of (sheet_cols * sheet_rows) for
        multi-up sheet printing. Returns a list of lists of records
        (each inner list has at most cols*rows items). If there are no
        records, returns a single page of [None] so a sample sheet can
        still be previewed/printed."""
        n = max(1, self.sheet_cols * self.sheet_rows)
        if not self.records:
            return [[None]]
        return [self.records[i:i + n] for i in range(0, len(self.records), n)]

    def render_sheet_page(self, records_chunk):
        """Renders a full multi-up sheet: sheet_cols x sheet_rows copies of
        the label layout, each cell filled from the next record in the chunk
        (or blank if the chunk runs out, e.g. the last page)."""
        cols, rows = self.sheet_cols, self.sheet_rows
        cell_w_px = self.label_w_mm * MM_TO_INCH * self.dpi
        cell_h_px = self.label_h_mm * MM_TO_INCH * self.dpi
        gap_px = self.sheet_gap_mm * MM_TO_INCH * self.dpi
        margin_px = self.sheet_margin_mm * MM_TO_INCH * self.dpi

        page_w = margin_px * 2 + cols * cell_w_px + (cols - 1) * gap_px
        page_h = margin_px * 2 + rows * cell_h_px + (rows - 1) * gap_px
        img = Image.new("RGB", (max(1, round(page_w)), max(1, round(page_h))), color="white")
        draw = ImageDraw.Draw(img)

        if self.sheet_page_border:
            draw.rectangle([0, 0, img.width - 1, img.height - 1], outline=0, width=2)

        for idx in range(cols * rows):
            r, c = divmod(idx, cols)
            x0 = margin_px + c * (cell_w_px + gap_px)
            y0 = margin_px + r * (cell_h_px + gap_px)
            record = records_chunk[idx] if idx < len(records_chunk) else None
            has_data = idx < len(records_chunk)
            if not has_data and self.records:
                continue  # leave trailing empty cells on the last page blank
            if self.sheet_rounded:
                draw.rounded_rectangle(
                    [x0, y0, x0 + cell_w_px, y0 + cell_h_px], radius=min(cell_w_px, cell_h_px) * 0.08, outline=0)
            else:
                draw.rectangle([x0, y0, x0 + cell_w_px, y0 + cell_h_px], outline=0)
            self._draw_fields_onto(img, draw, record, x0, y0)

        return img



    def _render_symbol_or_image_full(self, f: Field, value, box_w_px, box_h_px):
        try:
            if f.field_type == "qrcode":
                if qrcode is None:
                    return None
                qr = qrcode.QRCode(border=1)
                qr.add_data(value)
                qr.make(fit=True)
                pil_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
                side = min(box_w_px, box_h_px)
                return pil_img.resize((max(1, side), max(1, side)), Image.NEAREST)
            elif f.field_type == "barcode":
                if barcode_lib is None:
                    return None
                cls = barcode_lib.get_barcode_class(f.barcode_type)
                buf = io.BytesIO()
                cls(value, writer=ImageWriter()).write(
                    buf, options={"write_text": False, "quiet_zone": 1})
                buf.seek(0)
                pil_img = Image.open(buf).convert("RGB")
                return pil_img.resize((max(1, box_w_px), max(1, box_h_px)))
            elif f.field_type == "image":
                if f.is_static:
                    path = f.static_value
                else:
                    path = value if value and os.path.exists(value) else f.static_value
                if not path or not os.path.exists(path):
                    return None
                pil_img = Image.open(path).convert("RGB")
                pil_img.thumbnail((box_w_px, box_h_px))
                canvas_img = Image.new("RGB", (box_w_px, box_h_px), "white")
                ox = (box_w_px - pil_img.width) // 2
                oy = (box_h_px - pil_img.height) // 2
                canvas_img.paste(pil_img, (ox, oy))
                return canvas_img
        except Exception:
            return None
        return None

    # -----------------------------------------------------------------
    # Preview window
    # -----------------------------------------------------------------
    def _current_page_image(self):
        """Renders whichever page (single label or full sheet) corresponds
        to the currently-selected record."""
        if self.sheet_enabled:
            n = max(1, self.sheet_cols * self.sheet_rows)
            page_idx = max(0, self.current_record_index) // n if self.records else 0
            chunks = self.get_page_chunks()
            chunk = chunks[min(page_idx, len(chunks) - 1)]
            return self.render_sheet_page(chunk)
        record = None
        if 0 <= self.current_record_index < len(self.records):
            record = self.records[self.current_record_index]
        return self.render_label_image(record)

    def open_preview(self):
        img = self._current_page_image()

        win = tk.Toplevel(self)
        title = "Sheet Preview" if self.sheet_enabled else "Label Preview"
        win.title(f"{title} - actual print resolution ({self.dpi} DPI)")

        # scale for comfortable on-screen viewing without changing print output
        max_dim = 800
        scale = min(1.0, max_dim / max(img.width, img.height)) if max(img.width, img.height) > 0 else 1.0
        display_img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))),
                                  Image.LANCZOS) if scale != 1.0 else img
        tk_img = ImageTk.PhotoImage(display_img)

        frame = ttk.Frame(win, padding=10)
        frame.pack(fill="both", expand=True)
        lbl = ttk.Label(frame, image=tk_img, relief="solid", borderwidth=1)
        lbl.image = tk_img  # keep reference
        lbl.pack()

        if self.sheet_enabled:
            info = (f"{self.sheet_cols} x {self.sheet_rows} grid, "
                     f"{self.label_w_mm:g}mm x {self.label_h_mm:g}mm per label @ {self.dpi} DPI  ->  "
                     f"{img.width}x{img.height}px page")
        else:
            info = f"{self.label_w_mm:g}mm x {self.label_h_mm:g}mm @ {self.dpi} DPI  ->  {img.width}x{img.height}px"
        ttk.Label(frame, text=info, foreground="#555555").pack(pady=(6, 0))

        btn_row = ttk.Frame(frame)
        btn_row.pack(pady=8)
        btn_text = "Print This Sheet" if self.sheet_enabled else "Print This Label"
        ttk.Button(btn_row, text=btn_text,
                   command=lambda: self._send_to_printer(img)).pack(side="left", padx=4)
        ttk.Button(btn_row, text="Close", command=win.destroy).pack(side="left", padx=4)

    # -----------------------------------------------------------------
    # Printing
    # -----------------------------------------------------------------
    def refresh_printers(self, silent=False):
        printers = []
        error = None
        if IS_WINDOWS and win32print is None:
            error = ("pywin32 is not installed, so Windows printers can't be "
                      "listed or used. Run: pip install pywin32")
        else:
            try:
                if IS_WINDOWS:
                    printers = [p[2] for p in win32print.EnumPrinters(2)]
                else:
                    out = subprocess.run(["lpstat", "-p"], capture_output=True,
                                          text=True, timeout=3)
                    for line in out.stdout.splitlines():
                        if line.startswith("printer "):
                            printers.append(line.split()[1])
            except FileNotFoundError:
                error = ("Couldn't find 'lpstat' (CUPS). Make sure CUPS is "
                          "installed and a printer is configured.")
            except Exception as e:
                error = f"Couldn't list printers: {e}"

        self.available_printers = printers
        if printers:
            if not self.printer_var.get() or self.printer_var.get() not in printers:
                self.printer_var.set(printers[0])
        else:
            self.printer_var.set("")

        if error:
            self.printer_status_var.set(error)
            self.status_var.set("No printer available.")
            if not silent:
                messagebox.showwarning("No Printer Available", error)
        elif not printers:
            msg = ("No printers were found. Make sure your thermal printer is "
                   "powered on, connected, and its driver is installed, then "
                   "click 'Refresh' in Printer Settings.")
            self.printer_status_var.set(msg)
            self.status_var.set("No printer available.")
            if not silent:
                messagebox.showwarning("No Printer Available", msg)
        else:
            self.printer_status_var.set("")

    def _printer_ready(self):
        """Checks a printer is actually available before we try to print,
        and warns the user (instead of failing silently or with a raw
        exception) if not."""
        if IS_WINDOWS and win32print is None:
            messagebox.showwarning(
                "No Printer Available",
                "pywin32 is not installed, so printing isn't available. "
                "Run: pip install pywin32")
            return False
        if not self.printer_var.get() and not self.available_printers:
            messagebox.showwarning(
                "No Printer Available",
                "No printer was found. Make sure your thermal printer is "
                "powered on and connected, then click 'Refresh Printers'.")
            return False
        return True

    def print_current(self):
        if not self._printer_ready():
            return
        img = self._current_page_image()
        self._send_to_printer(img)

    def print_all(self):
        if not self._printer_ready():
            return
        if not self.records:
            messagebox.showinfo("Print All", "No imported data. Import Excel first.")
            return
        if self.sheet_enabled:
            chunks = self.get_page_chunks()
            if not messagebox.askyesno(
                    "Print All", f"Print {len(chunks)} sheet(s) "
                                 f"({self.sheet_cols} x {self.sheet_rows} labels each, "
                                 f"{len(self.records)} label(s) total)?"):
                return
            for chunk in chunks:
                img = self.render_sheet_page(chunk)
                self._send_to_printer(img)
            self.status_var.set(f"Sent {len(chunks)} sheet(s) to printer.")
        else:
            if not messagebox.askyesno("Print All", f"Print all {len(self.records)} label(s)?"):
                return
            for rec in self.records:
                img = self.render_label_image(rec)
                self._send_to_printer(img)
            self.status_var.set(f"Sent {len(self.records)} label(s) to printer.")

    def _apply_print_offset(self, img: Image.Image):
        """Shifts the finished page image by the configured calibration
        offset without changing its size, so the physical print lines up
        with the label stock on printers that are consistently off."""
        ox = round(self.print_offset_x_var.get() * MM_TO_INCH * self.dpi)
        oy = round(self.print_offset_y_var.get() * MM_TO_INCH * self.dpi)
        if ox == 0 and oy == 0:
            return img
        shifted = Image.new(img.mode, img.size, "white")
        shifted.paste(img, (ox, oy))
        return shifted

    def _send_to_printer(self, img: Image.Image):
        if not self._printer_ready():
            return
        img = self._apply_print_offset(img)
        printer_name = self.printer_var.get()
        try:
            if IS_WINDOWS and win32print and self.use_raw_tspl:
                self._print_windows_raw_tspl(img, printer_name)
            elif IS_WINDOWS and win32print:
                self._print_windows(img, printer_name)
            else:
                self._print_unix(img, printer_name)
            self.status_var.set("Label sent to printer.")
        except Exception as e:
            messagebox.showerror("Print Error", str(e))

    def _img_to_tspl_bitmap(self, img: Image.Image):
        """Converts a PIL image to TSPL BITMAP command payload: 1-bit,
        MSB-first, each row padded to a whole byte. bit=1 means "print a
        dot" (black)."""
        bw = img.convert("L").point(lambda p: 0 if p < 128 else 255, mode="L")
        width, height = bw.size
        width_bytes = (width + 7) // 8
        px = bw.load()
        data = bytearray(width_bytes * height)
        for y in range(height):
            row_off = y * width_bytes
            for x in range(width):
                if px[x, y] == 0:
                    data[row_off + (x // 8)] |= (0x80 >> (x % 8))
        return bytes(data), width_bytes, height

    def _print_windows_raw_tspl(self, img: Image.Image, printer_name):
        """Sends TSPL commands directly to the printer via the RAW spool
        datatype, bypassing the Windows GDI print driver entirely. This is
        the reliable path for TSPL-compatible thermal printers (TSC,
        TP870/TP518/GZP-series, many Xprinter/Godex models) where the
        driver's own private label-size setting overrides anything we try
        to configure through the standard Windows page-size APIs."""
        width_mm = img.width / self.dpi * 25.4
        height_mm = img.height / self.dpi * 25.4
        bitmap_data, width_bytes, height = self._img_to_tspl_bitmap(img)

        cmds = bytearray()
        cmds += f"SIZE {width_mm:.2f} mm,{height_mm:.2f} mm\r\n".encode("ascii")
        cmds += f"GAP {self.tspl_gap_mm:.2f} mm,0 mm\r\n".encode("ascii")
        cmds += b"DIRECTION 0\r\n"
        cmds += b"CLS\r\n"
        cmds += f"BITMAP 0,0,{width_bytes},{height},0,".encode("ascii")
        cmds += bitmap_data
        cmds += b"\r\n"
        cmds += b"PRINT 1,1\r\n"

        hprinter = win32print.OpenPrinter(printer_name)
        try:
            win32print.StartDocPrinter(hprinter, 1, ("Thermal Label (TSPL)", None, "RAW"))
            try:
                win32print.StartPagePrinter(hprinter)
                win32print.WritePrinter(hprinter, bytes(cmds))
                win32print.EndPagePrinter(hprinter)
            finally:
                win32print.EndDocPrinter(hprinter)
        finally:
            win32print.ClosePrinter(hprinter)

    def _build_custom_devmode(self, hprinter, printer_name, width_mm, height_mm):
        """Forces this print job's page size to our own computed
        dimensions, instead of leaving it up to whatever page/label size
        happens to be configured in the printer driver's Printing
        Preferences. That driver-side setting is what actually decides the
        printable area -- if it's set smaller than your sticker (very easy
        to have happen on thermal printers, and not something DPI or
        offset can work around), everything past it gets clipped no matter
        what we draw. Returns None if the driver won't accept a custom
        size, so the caller can fall back to its default page."""
        try:
            props = win32print.GetPrinter(hprinter, 2)
            devmode = props["pDevMode"]
            if devmode is None:
                return None
            devmode.PaperSize = 0  # 0 = use PaperWidth/PaperLength instead of a named size
            devmode.PaperWidth = max(1, round(width_mm * 10))    # DEVMODE units: tenths of a mm
            devmode.PaperLength = max(1, round(height_mm * 10))
            devmode.Orientation = 1
            devmode.Fields |= (win32con.DM_PAPERSIZE | win32con.DM_PAPERWIDTH |
                                win32con.DM_PAPERLENGTH | win32con.DM_ORIENTATION)
            try:
                hwnd = self.winfo_id()
            except Exception:
                hwnd = 0
            # Let the driver validate/merge our requested size -- some
            # drivers need this call to actually accept a custom size.
            win32print.DocumentProperties(
                hwnd, hprinter, printer_name, devmode, devmode,
                win32con.DM_IN_BUFFER | win32con.DM_OUT_BUFFER)
            return devmode
        except Exception:
            return None

    def _print_windows(self, img: Image.Image, printer_name):
        if not printer_name:
            try:
                printer_name = win32print.GetDefaultPrinter()
            except Exception:
                raise RuntimeError(
                    "No printer is selected and Windows has no default "
                    "printer set. Pick one from the Printer list.")
        hprinter = win32print.OpenPrinter(printer_name)
        try:
            width_mm = img.width / self.dpi * 25.4
            height_mm = img.height / self.dpi * 25.4
            devmode = self._build_custom_devmode(hprinter, printer_name, width_mm, height_mm)

            if devmode is not None:
                try:
                    hdc_handle = win32gui.CreateDC("WINSPOOL", printer_name, None, devmode)
                    hdc = win32ui.CreateDCFromHandle(hdc_handle)
                except Exception:
                    devmode = None

            if devmode is None:
                # Driver rejected (or doesn't support) a custom page size.
                # Falls back to whatever page it's currently configured
                # for -- if that's the narrow strip you're seeing, it has
                # to be fixed in the driver's own Printing Preferences
                # dialog (label Width/Height fields there), not in this app.
                hdc = win32ui.CreateDC()
                hdc.CreatePrinterDC(printer_name)

            hdc.StartDoc("Thermal Label")
            hdc.StartPage()
            dib = ImageWin.Dib(img)
            dib.draw(hdc.GetHandleOutput(), (0, 0, img.width, img.height))
            hdc.EndPage()
            hdc.EndDoc()
            hdc.DeleteDC()
        finally:
            win32print.ClosePrinter(hprinter)

    def _print_unix(self, img: Image.Image, printer_name):
        tmp_path = os.path.join(os.path.expanduser("~"), ".label_print_tmp.png")
        img.save(tmp_path)

        # Match the CUPS page size to the image itself and zero out the
        # driver's default margins. Without this, the printer's default
        # page size/margins (not our label size) decide what's printable,
        # which is what causes content to run off one edge or a multi-up
        # sheet to get cropped down to its first cell.
        width_mm = img.width / self.dpi * 25.4
        height_mm = img.height / self.dpi * 25.4

        cmd = ["lp"]
        if printer_name:
            cmd += ["-d", printer_name]
        cmd += [
            "-o", f"media=Custom.{width_mm:.2f}x{height_mm:.2f}mm",
            "-o", "page-left=0", "-o", "page-right=0",
            "-o", "page-top=0", "-o", "page-bottom=0",
            tmp_path,
        ]
        subprocess.run(cmd, check=True)


if __name__ == "__main__":
    app = LabelApp()
    app.mainloop()
