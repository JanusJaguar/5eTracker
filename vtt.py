# ---------------------------------------------------------------------------
# vtt.py — Virtual Tabletop module for Janus D&D Tracker
# ---------------------------------------------------------------------------
# REQUIRES:
#   pip install Pillow gspread google-auth gspread-formatting
#
# FOLDER STRUCTURE (next to Tracker.py):
#   maps/
#   tokens/
#     players/
#     enemies/
# ---------------------------------------------------------------------------

import os
import json
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

try:
    from PIL import Image, ImageTk
    PIL_OK = True
except ImportError:
    PIL_OK = False

# ---------------------------------------------------------------------------
# PATH HELPERS
# ---------------------------------------------------------------------------

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
MAPS_DIR   = os.path.join(BASE_DIR, "maps")
TOKEN_DIR  = os.path.join(BASE_DIR, "tokens")
PLAYER_DIR = os.path.join(TOKEN_DIR, "players")
ENEMY_DIR  = os.path.join(TOKEN_DIR, "enemies")

for d in (MAPS_DIR, PLAYER_DIR, ENEMY_DIR):
    os.makedirs(d, exist_ok=True)

IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def list_images(folder):
    if not os.path.isdir(folder):
        return []
    return sorted(
        f for f in os.listdir(folder)
        if os.path.splitext(f)[1].lower() in IMG_EXTS
    )

# ---------------------------------------------------------------------------
# CELL TYPES
# ---------------------------------------------------------------------------

CELL_TYPES = {
    "edge":      {"color": "#2c3e50", "collision": True},
    "wall":      {"color": "#1a1a2e", "collision": True},
    "floor":     {"color": "#d5d8dc", "collision": False},
    "difficult": {"color": "#f39c12", "collision": False},
}

# ---------------------------------------------------------------------------
# COORDINATE HELPER
# ---------------------------------------------------------------------------

def col_to_letters(n):
    """0 → A, 25 → Z, 26 → AA, 27 → AB ..."""
    result = ""
    n += 1
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        result = chr(65 + remainder) + result
    return result

# ---------------------------------------------------------------------------
# TOKEN CLASS
# ---------------------------------------------------------------------------

class Token:
    def __init__(self, canvas, col, row, cell_px, label="Token",
                 color="#e74c3c", img_path=None):
        self.canvas    = canvas
        self.label     = label
        self.color     = color
        self.cell_px   = cell_px
        self.grid_col  = col
        self.grid_row  = row
        self.hp        = None
        self._photo    = None
        self._img_path = img_path

        x    = col * cell_px
        y    = row * cell_px
        half = cell_px // 2

        if img_path and PIL_OK:
            img = Image.open(img_path).resize(
                (cell_px, cell_px), Image.LANCZOS
            )
            self._photo = ImageTk.PhotoImage(img)
            self.oval = canvas.create_image(
                x, y, image=self._photo, anchor="nw", tags="token"
            )
        else:
            self.oval = canvas.create_oval(
                x, y, x + cell_px, y + cell_px,
                fill=color, outline="white", width=2, tags="token"
            )

        self.text = canvas.create_text(
            x + half, y + cell_px + 8,
            text=label, fill="white",
            font=("Arial", 7, "bold"), tags="token"
        )

        self._drag_x = 0
        self._drag_y = 0

        for item in (self.oval, self.text):
            canvas.tag_bind(item, "<ButtonPress-1>",   self._on_press)
            canvas.tag_bind(item, "<B1-Motion>",       self._on_drag)
            canvas.tag_bind(item, "<ButtonRelease-1>", self._on_release)
            canvas.tag_bind(item, "<Button-3>",        self._on_right_click)

    def select(self):
        self.canvas.delete(f"sel_ring_{id(self)}")
        c = self.cell_px
        x = self.grid_col * c
        y = self.grid_row * c
        self.canvas.create_rectangle(
            x, y, x + c, y + c,
            outline="#f1c40f", width=3,
            tags=(f"sel_ring_{id(self)}", "sel_ring")
        )
        self.canvas.tag_raise("token")

    def deselect(self):
        self.canvas.delete(f"sel_ring_{id(self)}")

    def move_to(self, cell_px):
        self.cell_px = cell_px
        x    = self.grid_col * cell_px
        y    = self.grid_row * cell_px
        half = cell_px // 2

        if self._img_path and PIL_OK:
            img = Image.open(self._img_path).resize(
                (cell_px, cell_px), Image.LANCZOS
            )
            self._photo = ImageTk.PhotoImage(img)
            self.canvas.coords(self.oval, x, y)
            self.canvas.itemconfig(self.oval, image=self._photo)
        else:
            self.canvas.coords(self.oval, x, y, x + cell_px, y + cell_px)

        self.canvas.coords(self.text, x + half, y + cell_px + 8)
        self.canvas.delete(f"sel_ring_{id(self)}")

    def wiggle(self):
        c  = self.cell_px
        ox = self.grid_col * c
        oy = self.grid_row * c

        if not self._img_path:
            self.canvas.itemconfig(self.oval, fill="#e74c3c")

        steps = [8, -16, 16, -16, 8, 0]

        def do_step(i):
            if i >= len(steps):
                self.canvas.coords(self.oval, ox, oy, ox + c, oy + c)
                self.canvas.coords(self.text, ox + c // 2, oy + c + 8)
                if not self._img_path:
                    self.canvas.itemconfig(self.oval, fill=self.color)
                return
            self.canvas.move(self.oval, steps[i], 0)
            self.canvas.move(self.text, steps[i], 0)
            self.canvas.after(50, lambda: do_step(i + 1))

        do_step(0)

    def _on_press(self, event):
        if getattr(self.canvas, "paint_mode", False):
            return
        self._drag_x = event.x
        self._drag_y = event.y
        self.canvas.tag_raise(self.oval)
        self.canvas.tag_raise(self.text)
        prev = getattr(self.canvas, "selected_token", None)
        if prev and prev is not self:
            prev.deselect()
        self.canvas.selected_token = self
        self.select()

    def _on_drag(self, event):
        if getattr(self.canvas, "paint_mode", False):
            return
        dx = event.x - self._drag_x
        dy = event.y - self._drag_y
        self.canvas.move(self.oval, dx, dy)
        self.canvas.move(self.text, dx, dy)
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_release(self, event):
        if getattr(self.canvas, "paint_mode", False):
            return
        c = self.cell_px
        coords = self.canvas.coords(self.oval)
        raw_x, raw_y = coords[0], coords[1]
        snapped_x = round(raw_x / c) * c
        snapped_y = round(raw_y / c) * c
        new_col = int(snapped_x / c)
        new_row = int(snapped_y / c)
        coord     = f"{col_to_letters(new_col)}{new_row + 1}"
        cell_type = self.canvas.mapstate.get(coord, "")
        if CELL_TYPES.get(cell_type, {}).get("collision", False):
            ox = self.grid_col * c
            oy = self.grid_row * c
            self.canvas.coords(self.oval, ox, oy, ox + c, oy + c)
            self.canvas.coords(self.text, ox + c // 2, oy + c + 8)
            self.wiggle()
            return
        dx = snapped_x - raw_x
        dy = snapped_y - raw_y
        self.canvas.move(self.oval, dx, dy)
        self.canvas.move(self.text, dx, dy)
        self.grid_col = new_col
        self.grid_row = new_row
        self.select()

    def _on_right_click(self, event):
        if getattr(self.canvas, "paint_mode", False):
            return
        menu = tk.Menu(self.canvas, tearoff=0)
        menu.add_command(label=f"✏️  Rename  [{self.label}]", command=self._rename)
        menu.add_command(label="❤️  Set HP",                  command=self._set_hp)
        menu.add_separator()
        menu.add_command(label="🗑️  Remove",                  command=self._remove)
        menu.tk_popup(event.x_root, event.y_root)

    def _rename(self):
        new = simpledialog.askstring("Rename Token", "New name:",
                                     initialvalue=self.label)
        if new:
            self.label = new
            self.canvas.itemconfig(self.text, text=new)

    def _set_hp(self):
        val = simpledialog.askstring("Set HP", "HP (e.g. 30/45):",
                                     initialvalue=self.hp or "")
        if val is not None:
            self.hp = val
            self.canvas.itemconfig(self.text, text=f"{self.label}\n{val}")

    def _remove(self):
        self.canvas.delete(f"sel_ring_{id(self)}")
        self.canvas.delete(self.oval)
        self.canvas.delete(self.text)
        if getattr(self.canvas, "selected_token", None) is self:
            self.canvas.selected_token = None

# ---------------------------------------------------------------------------
# GOOGLE SHEETS HELPERS
# ---------------------------------------------------------------------------

def get_sheets_client():
    import gspread
    from google.oauth2.service_account import Credentials
    creds_path = os.path.join(BASE_DIR, "credentials.json")
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    return gspread.authorize(creds)


def open_vtt_sheet(sheet_name="DnD_VTT"):
    client = get_sheets_client()
    return client.open(sheet_name).sheet1


def push_tokens_to_sheet(tokens):
    try:
        sheet = open_vtt_sheet()
        sheet.batch_clear(["A2:E100"])
        rows = []
        for tok in tokens:
            rows.append([
                tok.label,
                col_to_letters(tok.grid_col),
                tok.grid_row + 1,
                "enemy" if tok.color == "#e74c3c" else "player",
                tok.hp or ""
            ])
        if rows:
            sheet.update(f"A2:E{1 + len(rows)}", rows)
    except Exception as e:
        messagebox.showerror("Sheet Sync Error", str(e))


def pull_tokens_from_sheet():
    try:
        sheet  = open_vtt_sheet()
        rows   = sheet.get_all_records()
        tokens = []
        for row in rows:
            try:
                col_str = str(row.get("col", "A")).strip().upper()
                col_idx = 0
                for ch in col_str:
                    col_idx = col_idx * 26 + (ord(ch) - ord('A') + 1)
                col_idx -= 1
                tokens.append({
                    "name": str(row.get("name", "Token")),
                    "col":  col_idx,
                    "row":  int(row.get("row", 1)) - 1,
                    "type": str(row.get("type", "player")),
                    "hp":   str(row.get("hp", "")) or None,
                })
            except Exception:
                continue
        return tokens
    except Exception as e:
        messagebox.showerror("Sheet Sync Error", str(e))
        return []


def start_sheet_polling(state, tokens_ref, vtt_canvas, redraw_fn,
                        interval_ms=60000):
    last_seen = [None]

    def poll():
        try:
            data      = pull_tokens_from_sheet()
            signature = tuple(
                (d["name"], d["col"], d["row"], d["hp"]) for d in data
            )
            if signature != last_seen[0]:
                last_seen[0] = signature
                vtt_canvas.delete("token")
                vtt_canvas.delete("sel_ring")
                tokens_ref.clear()
                c = state["cell_px"]
                for td in data:
                    color = "#e74c3c" if td["type"] == "enemy" else "#2980b9"
                    tok = Token(vtt_canvas, td["col"], td["row"], c,
                                label=td["name"], color=color)
                    if td["hp"]:
                        tok.hp = td["hp"]
                        vtt_canvas.itemconfig(
                            tok.text, text=f"{td['name']}\n{td['hp']}"
                        )
                    tokens_ref.append(tok)
                redraw_fn()
        except Exception:
            pass
        if state.get("polling"):
            vtt_canvas.after(interval_ms, poll)

    state["polling"] = True
    vtt_canvas.after(interval_ms, poll)

# ---------------------------------------------------------------------------
# MAPSTATE SHEET HELPERS
# ---------------------------------------------------------------------------

def push_mapstate_to_sheet(cells, grid_cols, grid_rows):
    """Write MapState cell values only — no formatting to avoid API limits."""
    try:
        client      = get_sheets_client()
        spreadsheet = client.open("DnD_VTT")

        try:
            sheet = spreadsheet.worksheet("MapState")
        except Exception:
            sheet = spreadsheet.add_worksheet("MapState", rows=300, cols=300)

        sheet.clear()

        total_cols = grid_cols + 2
        total_rows = grid_rows + 2
        grid_data  = [[""] * total_cols for _ in range(total_rows)]

        for coord, ctype in cells.items():
            col_str = "".join(ch for ch in coord if ch.isalpha())
            row_num = "".join(ch for ch in coord if ch.isdigit())
            if not col_str or not row_num:
                continue
            col_idx = 0
            for ch in col_str.upper():
                col_idx = col_idx * 26 + (ord(ch) - ord('A') + 1)
            col_idx -= 1
            row_idx = int(row_num) - 1
            if 0 <= row_idx < total_rows and 0 <= col_idx < total_cols:
                grid_data[row_idx][col_idx] = ctype

        # Write everything in one single API call
        sheet.update("A1", grid_data)

        messagebox.showinfo("MapState Synced",
                            "✅ MapState pushed to Google Sheet!")

    except Exception as e:
        messagebox.showerror("Sheet Error", str(e))


def pull_mapstate_from_sheet():
    try:
        client      = get_sheets_client()
        spreadsheet = client.open("DnD_VTT")
        sheet       = spreadsheet.worksheet("MapState")
        rows        = sheet.get_all_values()
        cells = {}
        for r_idx, row in enumerate(rows):
            for c_idx, val in enumerate(row):
                if val.strip():
                    coord = f"{col_to_letters(c_idx)}{r_idx + 1}"
                    cells[coord] = val.strip().lower()
        return cells
    except Exception as e:
        messagebox.showerror("Sheet Error", str(e))
        return None

# ---------------------------------------------------------------------------
# LOCAL SAVE / LOAD
# ---------------------------------------------------------------------------

def save_vtt_state(tokens):
    file = tk.filedialog.asksaveasfilename(
        title="Save VTT State", defaultextension=".json",
        initialdir=BASE_DIR, filetypes=[("JSON Files", "*.json")]
    )
    if not file:
        return
    data = []
    for tok in tokens:
        data.append({
            "name":     tok.label,
            "col":      tok.grid_col,
            "row":      tok.grid_row,
            "color":    tok.color,
            "hp":       tok.hp or "",
            "type":     "enemy" if tok.color == "#e74c3c" else "player",
            "img_path": tok._img_path or ""
        })
    try:
        with open(file, "w") as f:
            json.dump(data, f, indent=4)
        messagebox.showinfo("VTT Saved", f"✅ Saved {len(data)} tokens!")
    except Exception as e:
        messagebox.showerror("Save Error", str(e))


def load_vtt_state(state, vtt_canvas, redraw_fn):
    file = tk.filedialog.askopenfilename(
        title="Load VTT State", initialdir=BASE_DIR,
        filetypes=[("JSON Files", "*.json")]
    )
    if not file:
        return
    try:
        with open(file, "r") as f:
            data = json.load(f)
        vtt_canvas.delete("token")
        vtt_canvas.delete("sel_ring")
        state["tokens"].clear()
        c = state["cell_px"]
        for td in data:
            img_path = td.get("img_path") or None
            if img_path and not os.path.exists(img_path):
                img_path = None
            tok = Token(
                vtt_canvas, td["col"], td["row"], c,
                label=td["name"], color=td.get("color", "#e74c3c"),
                img_path=img_path
            )
            if td.get("hp"):
                tok.hp = td["hp"]
                vtt_canvas.itemconfig(
                    tok.text, text=f"{td['name']}\n{td['hp']}"
                )
            state["tokens"].append(tok)
        redraw_fn()
        messagebox.showinfo("VTT Loaded", f"✅ Loaded {len(data)} tokens!")
    except Exception as e:
        messagebox.showerror("Load Error", str(e))


def save_mapstate_json(map_name, grid_cols, grid_rows, cells):
    file = tk.filedialog.asksaveasfilename(
        title="Save MapState", defaultextension=".json",
        initialdir=BASE_DIR, filetypes=[("JSON Files", "*.json")]
    )
    if not file:
        return False
    try:
        with open(file, "w") as f:
            json.dump({"map_name": map_name, "grid_cols": grid_cols,
                       "grid_rows": grid_rows, "cells": cells}, f, indent=4)
        messagebox.showinfo("MapState Saved", "✅ MapState saved!")
        return True
    except Exception as e:
        messagebox.showerror("Save Error", str(e))
        return False


def load_mapstate_json():
    file = tk.filedialog.askopenfilename(
        title="Load MapState", initialdir=BASE_DIR,
        filetypes=[("JSON Files", "*.json")]
    )
    if not file:
        return None
    try:
        with open(file, "r") as f:
            return json.load(f)
    except Exception as e:
        messagebox.showerror("Load Error", str(e))
        return None

# ---------------------------------------------------------------------------
# MAIN BUILD FUNCTION
# ---------------------------------------------------------------------------

def build_vtt_tab(parent):
    """Call this with the DM-mode vtt_tab Frame as parent."""

    # -----------------------------------------------------------------------
    # STATE
    # -----------------------------------------------------------------------
    state = {
        "cell_px":        30,
        "map_photo":      None,
        "map_item":       None,
        "grid_lines":     [],
        "show_grid":      True,
        "tokens":         [],
        "_raw_map":       None,
        "selected_token": None,
        "map_name":       "unknown",
        "grid_cols":      10,
        "grid_rows":      10,
        "polling":        False,
    }

    # -----------------------------------------------------------------------
    # TOP TOOLBAR  (quick access hotkeys only)
    # -----------------------------------------------------------------------
    toolbar = tk.Frame(parent)
    toolbar.pack(side="top", fill="x", padx=6, pady=2)

    # -----------------------------------------------------------------------
    # MAIN AREA
    # -----------------------------------------------------------------------
    canvas_frame = tk.Frame(parent)
    canvas_frame.pack(fill="both", expand=True)

    vtt_canvas = tk.Canvas(canvas_frame, bg="#1a1a2e", cursor="crosshair")
    vtt_canvas.pack(fill="both", expand=True)
    vtt_canvas.mapstate   = {}
    vtt_canvas.paint_mode = False

    h_scroll = tk.Scrollbar(canvas_frame, orient="horizontal",
                             command=vtt_canvas.xview)
    v_scroll = tk.Scrollbar(canvas_frame, orient="vertical",
                             command=vtt_canvas.yview)
    vtt_canvas.config(xscrollcommand=h_scroll.set,
                      yscrollcommand=v_scroll.set)
    h_scroll.pack(side="bottom", fill="x")
    v_scroll.pack(side="right",  fill="y")

    # -----------------------------------------------------------------------
    # FLOATING SIDE PANEL
    # -----------------------------------------------------------------------
    PANEL_W = 185

    panel = tk.Frame(canvas_frame, bg="#1e1e2e", width=PANEL_W,
                     relief="flat", bd=0)
    panel.place(x=0, y=0, width=PANEL_W, relheight=1.0)
    panel.pack_propagate(False)

    # Scrollable interior
    panel_canvas = tk.Canvas(panel, bg="#1e1e2e", highlightthickness=0,
                             width=PANEL_W - 16)
    panel_scroll = tk.Scrollbar(panel, orient="vertical",
                                command=panel_canvas.yview)
    panel_canvas.config(yscrollcommand=panel_scroll.set)
    panel_scroll.pack(side="right", fill="y")
    panel_canvas.pack(side="left", fill="both", expand=True)

    inner = tk.Frame(panel_canvas, bg="#1e1e2e")
    inner_window = panel_canvas.create_window((0, 0), window=inner, anchor="nw")

    def on_inner_configure(e):
        panel_canvas.config(scrollregion=panel_canvas.bbox("all"))

    def on_canvas_configure(e):
        panel_canvas.itemconfig(inner_window, width=e.width)

    inner.bind("<Configure>", on_inner_configure)
    panel_canvas.bind("<Configure>", on_canvas_configure)

    def panel_scroll_wheel(e):
        panel_canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")

    panel_canvas.bind("<MouseWheel>", panel_scroll_wheel)
    inner.bind("<MouseWheel>",        panel_scroll_wheel)

    # Toggle tab on right edge of panel
    panel_visible = [True]
    toggle_btn = tk.Button(canvas_frame, text="◄",
                           font=("Arial", 8, "bold"),
                           bg="#2c3e50", fg="white",
                           relief="flat", cursor="hand2")
    toggle_btn.place(x=PANEL_W, y=0, width=16, relheight=0.06)

    def toggle_panel():
        if panel_visible[0]:
            panel.place_forget()
            toggle_btn.place(x=0, y=0, width=16, relheight=0.06)
            toggle_btn.config(text="►")
        else:
            panel.place(x=0, y=0, width=PANEL_W, relheight=1.0)
            toggle_btn.place(x=PANEL_W, y=0, width=16, relheight=0.06)
            toggle_btn.config(text="◄")
        panel_visible[0] = not panel_visible[0]

    toggle_btn.config(command=toggle_panel)

    # -----------------------------------------------------------------------
    # PANEL HELPERS
    # -----------------------------------------------------------------------
    def make_section(title):
        header = tk.Frame(inner, bg="#2c3e50")
        header.pack(fill="x", pady=(6, 0))
        lbl = tk.Label(header, text=f"▼ {title}", bg="#2c3e50", fg="white",
                       font=("Arial", 9, "bold"), anchor="w", cursor="hand2")
        lbl.pack(fill="x", padx=6, pady=3)
        body = tk.Frame(inner, bg="#1e1e2e")
        body.pack(fill="x", padx=4, pady=2)
        collapsed = [False]

        def toggle(e=None):
            if collapsed[0]:
                body.pack(fill="x", padx=4, pady=2)
                lbl.config(text=f"▼ {title}")
            else:
                body.pack_forget()
                lbl.config(text=f"► {title}")
            collapsed[0] = not collapsed[0]

        lbl.bind("<Button-1>", toggle)
        header.bind("<Button-1>", toggle)
        return body

    def panel_btn(parent_frame, text, command, bg="#2c3e50", fg="white"):
        tk.Button(parent_frame, text=text, command=command,
                  bg=bg, fg=fg, font=("Arial", 8),
                  relief="flat", cursor="hand2", anchor="w", padx=6
                  ).pack(fill="x", pady=1)

    def panel_sep(parent_frame):
        ttk.Separator(parent_frame, orient="horizontal").pack(fill="x", pady=4)

    # -----------------------------------------------------------------------
    # ZOOM STATE
    # -----------------------------------------------------------------------
    zoom_level = [1.0]

    # -----------------------------------------------------------------------
    # REDRAW ALL
    # -----------------------------------------------------------------------
    def redraw_all():
        z           = zoom_level[0]
        c           = state["cell_px"]
        scaled_cell = max(4, int(c * z))

        vtt_canvas.delete("mapbg")
        if state["_raw_map"]:
            w = int(state["_raw_map"].width  * z)
            h = int(state["_raw_map"].height * z)
            scaled = state["_raw_map"].resize(
                (max(1, w), max(1, h)), Image.LANCZOS
            )
            state["map_photo"] = ImageTk.PhotoImage(scaled)
            state["map_item"]  = vtt_canvas.create_image(
                scaled_cell, scaled_cell,
                anchor="nw", image=state["map_photo"], tags="mapbg"
            )
            vtt_canvas.config(scrollregion=(
                0, 0, w + scaled_cell * 2, h + scaled_cell * 2
            ))

        bb = vtt_canvas.bbox("mapbg")
        gw = bb[2] if bb else max(2000, vtt_canvas.winfo_width())
        gh = bb[3] if bb else max(2000, vtt_canvas.winfo_height())
        gw = max(gw, 2000)
        gh = max(gh, 2000)

        vtt_canvas.delete("grid")
        vtt_canvas.delete("gridlabel")
        vtt_canvas.delete("mapstate")

        if state["show_grid"]:
            for x in range(0, gw + scaled_cell, scaled_cell):
                vtt_canvas.create_line(x, 0, x, gh,
                                       fill="#444466", width=1, tags="grid")
            for y in range(0, gh + scaled_cell, scaled_cell):
                vtt_canvas.create_line(0, y, gw, y,
                                       fill="#444466", width=1, tags="grid")

            label_font = ("Arial", max(6, scaled_cell // 6), "bold")
            col = 0
            for x in range(0, gw, scaled_cell):
                vtt_canvas.create_text(
                    x + scaled_cell // 2, 8,
                    text=col_to_letters(col),
                    fill="#aaaacc", font=label_font, tags="gridlabel"
                )
                col += 1
            row = 1
            for y in range(0, gh, scaled_cell):
                vtt_canvas.create_text(
                    6, y + scaled_cell // 2,
                    text=str(row),
                    fill="#aaaacc", font=label_font,
                    anchor="w", tags="gridlabel"
                )
                row += 1

        for coord, ctype in vtt_canvas.mapstate.items():
            if ctype not in CELL_TYPES:
                continue
            col_str = "".join(ch for ch in coord if ch.isalpha())
            row_num = "".join(ch for ch in coord if ch.isdigit())
            if not col_str or not row_num:
                continue
            col_idx = 0
            for ch in col_str.upper():
                col_idx = col_idx * 26 + (ord(ch) - ord('A') + 1)
            col_idx -= 1
            row_idx = int(row_num) - 1
            x = col_idx * scaled_cell
            y = row_idx * scaled_cell
            vtt_canvas.create_rectangle(
                x, y, x + scaled_cell, y + scaled_cell,
                fill=CELL_TYPES[ctype]["color"], outline="", tags="mapstate"
            )

        for tok in state["tokens"]:
            tok.move_to(scaled_cell)

        vtt_canvas.tag_lower("mapstate")
        vtt_canvas.tag_lower("grid")
        vtt_canvas.tag_lower("mapbg")
        vtt_canvas.tag_raise("gridlabel")
        vtt_canvas.tag_raise("token")

    # -----------------------------------------------------------------------
    # ZOOM
    # -----------------------------------------------------------------------
    def zoom(factor):
        new_level = zoom_level[0] * factor
        if not (0.2 <= new_level <= 5.0):
            return
        zoom_level[0] = new_level
        redraw_all()

    vtt_canvas.bind("<MouseWheel>",
                    lambda e: zoom(1.1 if e.delta > 0 else 0.9))

    # -----------------------------------------------------------------------
    # PAINT MODE
    # -----------------------------------------------------------------------
    paint_type_var = tk.StringVar(value="edge")

    def paint_cell(event):
        if not vtt_canvas.paint_mode:
            return
        cx    = vtt_canvas.canvasx(event.x)
        cy    = vtt_canvas.canvasy(event.y)
        sc    = max(4, int(state["cell_px"] * zoom_level[0]))
        col   = int(cx // sc)
        row   = int(cy // sc)
        coord = f"{col_to_letters(col)}{row + 1}"
        ctype = paint_type_var.get()
        if ctype == "erase":
            vtt_canvas.mapstate.pop(coord, None)
        else:
            vtt_canvas.mapstate[coord] = ctype
        redraw_all()

    vtt_canvas.bind("<ButtonPress-1>", paint_cell)
    vtt_canvas.bind("<B1-Motion>",     paint_cell)

    # -----------------------------------------------------------------------
    # MAP LOADER
    # -----------------------------------------------------------------------
    def load_map_from_path(path):
        if not PIL_OK:
            messagebox.showerror("Missing Library",
                "Pillow is required.\n\npip install Pillow")
            return

        if vtt_canvas.mapstate:
            if messagebox.askyesno("Save MapState",
                    "You have an existing MapState.\n"
                    "Save it before loading new map?"):
                save_mapstate_json(
                    state.get("map_name", "unknown"),
                    state.get("grid_cols", 10),
                    state.get("grid_rows", 10),
                    vtt_canvas.mapstate
                )

        img = Image.open(path)
        MAX_W, MAX_H = 2000, 2000
        ratio = min(MAX_W / img.width, MAX_H / img.height, 1.0)
        if ratio < 1.0:
            img = img.resize(
                (int(img.width * ratio), int(img.height * ratio)),
                Image.LANCZOS
            )

        state["_raw_map"] = img
        state["map_name"] = os.path.basename(path)
        c         = state["cell_px"]
        grid_cols = img.width  // c
        grid_rows = img.height // c
        state["grid_cols"] = grid_cols
        state["grid_rows"] = grid_rows

        new_mapstate = {}
        total_cols = grid_cols + 2
        total_rows = grid_rows + 2
        for c_idx in range(total_cols):
            for r_idx in range(total_rows):
                if (c_idx == 0 or r_idx == 0 or
                        c_idx == total_cols - 1 or
                        r_idx == total_rows - 1):
                    coord = f"{col_to_letters(c_idx)}{r_idx + 1}"
                    new_mapstate[coord] = "edge"

        vtt_canvas.mapstate = new_mapstate
        map_name_var.set(os.path.basename(path))
        redraw_all()

    def browse_map():
        path = tk.filedialog.askopenfilename(
            title="Load Battlemap", initialdir=MAPS_DIR,
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp")]
        )
        if path:
            load_map_from_path(path)

    def load_map_from_dropdown(*_):
        name = map_var.get()
        if not name or name == "— select map —":
            return
        path = os.path.join(MAPS_DIR, name)
        if os.path.exists(path):
            load_map_from_path(path)

    # -----------------------------------------------------------------------
    # TOKEN PLACER
    # -----------------------------------------------------------------------
    def place_token(category="players"):
        folder  = PLAYER_DIR if category == "players" else ENEMY_DIR
        options = list_images(folder)

        win = tk.Toplevel(parent)
        win.title("Place Token")
        win.geometry("260x340")
        win.resizable(False, False)

        tk.Label(win, text="Name:").pack(pady=(10, 0))
        name_entry = tk.Entry(win, width=22)
        name_entry.pack()
        name_entry.insert(0, "Goblin" if category == "enemies" else "Hero")

        tk.Label(win, text="Token Image (optional):").pack(pady=(8, 0))
        img_var = tk.StringVar(value="— none —")
        ttk.Combobox(win, textvariable=img_var,
                     values=["— none —"] + options,
                     state="readonly", width=24).pack()

        tk.Label(win, text="Color (if no image):").pack(pady=(8, 0))
        color_var = tk.StringVar(
            value="#e74c3c" if category == "enemies" else "#2980b9"
        )
        tk.Entry(win, textvariable=color_var, width=12, justify="center").pack()

        def confirm():
            label    = name_entry.get().strip() or "Token"
            img_name = img_var.get()
            img_path = None
            if img_name != "— none —":
                img_path = os.path.join(folder, img_name)
            c         = state["cell_px"]
            cx        = int(vtt_canvas.canvasx(vtt_canvas.winfo_width()  // 2))
            cy        = int(vtt_canvas.canvasy(vtt_canvas.winfo_height() // 2))
            start_col = cx // c
            start_row = cy // c
            tok = Token(vtt_canvas, start_col, start_row, c,
                        label=label, color=color_var.get(), img_path=img_path)
            state["tokens"].append(tok)
            win.destroy()

        tk.Button(win, text="✅  Place Token", command=confirm,
                  bg="#27ae60", fg="white").pack(pady=14)

    # -----------------------------------------------------------------------
    # SHEET WRAPPERS
    # -----------------------------------------------------------------------
    def push_to_sheet():
        push_tokens_to_sheet(state["tokens"])
        messagebox.showinfo("Synced", "✅ Token positions pushed to Google Sheet!")

    def pull_from_sheet():
        data = pull_tokens_from_sheet()
        if not data:
            return
        vtt_canvas.delete("token")
        vtt_canvas.delete("sel_ring")
        state["tokens"].clear()
        c = state["cell_px"]
        for td in data:
            color = "#e74c3c" if td["type"] == "enemy" else "#2980b9"
            tok = Token(vtt_canvas, td["col"], td["row"], c,
                        label=td["name"], color=color)
            if td["hp"]:
                tok.hp = td["hp"]
                vtt_canvas.itemconfig(tok.text,
                                      text=f"{td['name']}\n{td['hp']}")
            state["tokens"].append(tok)
        redraw_all()
        messagebox.showinfo("Synced", f"✅ Loaded {len(data)} tokens from sheet!")

    def pull_mapstate():
        data = pull_mapstate_from_sheet()
        if data is not None:
            vtt_canvas.mapstate = data
            redraw_all()

    def load_mapstate():
        data = load_mapstate_json()
        if data:
            vtt_canvas.mapstate = data.get("cells", {})
            redraw_all()
            messagebox.showinfo("MapState Loaded",
                f"✅ Loaded MapState for {data.get('map_name', 'unknown')}")

    # -----------------------------------------------------------------------
    # TOP TOOLBAR  (quick access)
    # -----------------------------------------------------------------------
    map_files    = list_images(MAPS_DIR)
    map_var      = tk.StringVar(value="— select map —")
    map_name_var = tk.StringVar(value="No map loaded")

    tk.Label(toolbar, text="Map:", font=("Arial", 9, "bold")).pack(side="left")
    map_dropdown = ttk.Combobox(toolbar, textvariable=map_var,
                                values=["— select map —"] + map_files,
                                state="readonly", width=16)
    map_dropdown.pack(side="left", padx=4)
    map_dropdown.bind("<<ComboboxSelected>>", load_map_from_dropdown)

    tk.Button(toolbar, text="📂", command=browse_map,
              font=("Arial", 9)).pack(side="left", padx=2)

    def refresh_map_list():
        map_dropdown.config(values=["— select map —"] + list_images(MAPS_DIR))

    tk.Button(toolbar, text="🔄", command=refresh_map_list,
              font=("Arial", 9), relief="flat").pack(side="left")

    tk.Label(toolbar, textvariable=map_name_var,
             fg="gray", font=("Arial", 8)).pack(side="left", padx=6)

    ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=4)

    tk.Label(toolbar, text="Grid ft:", font=("Arial", 9, "bold")).pack(side="left")
    cell_ft_var = tk.IntVar(value=5)

    def update_cell_size(*_):
        try:
            state["cell_px"] = max(10, cell_ft_var.get() * 6)
            redraw_all()
        except Exception:
            pass

    tk.Spinbox(toolbar, from_=5, to=20, increment=1,
               textvariable=cell_ft_var, width=4,
               command=update_cell_size).pack(side="left", padx=2)
    cell_ft_var.trace_add("write", update_cell_size)

    ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=4)

    tk.Label(toolbar, text="Zoom:", font=("Arial", 9, "bold")).pack(side="left")
    tk.Button(toolbar, text="＋", command=lambda: zoom(1.25),
              font=("Arial", 10, "bold"), width=2).pack(side="left", padx=1)
    tk.Button(toolbar, text="－", command=lambda: zoom(0.8),
              font=("Arial", 10, "bold"), width=2).pack(side="left", padx=1)
    tk.Button(toolbar, text="⟳", command=lambda: zoom(1.0 / zoom_level[0]),
              font=("Arial", 9)).pack(side="left", padx=2)

    ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=4)

    tk.Button(toolbar, text="🧙 Player",
              command=lambda: place_token("players"),
              bg="#2980b9", fg="white",
              font=("Arial", 8)).pack(side="left", padx=2)
    tk.Button(toolbar, text="👹 Enemy",
              command=lambda: place_token("enemies"),
              bg="#c0392b", fg="white",
              font=("Arial", 8)).pack(side="left", padx=2)

    ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=4)

    grid_toggle_var = tk.BooleanVar(value=True)

    def toggle_grid():
        state["show_grid"] = grid_toggle_var.get()
        redraw_all()

    tk.Checkbutton(toolbar, text="Grid",
                   variable=grid_toggle_var,
                   command=toggle_grid).pack(side="left", padx=4)

    # -----------------------------------------------------------------------
    # SIDE PANEL — TOKENS SECTION
    # -----------------------------------------------------------------------
    tok_sec = make_section("🧙 TOKENS")

    panel_btn(tok_sec, "🧙 Add Player Token",
              lambda: place_token("players"), bg="#2980b9")
    panel_btn(tok_sec, "👹 Add Enemy Token",
              lambda: place_token("enemies"), bg="#c0392b")
    panel_sep(tok_sec)

    def clear_all_tokens():
        if messagebox.askyesno("Clear Tokens", "Remove all tokens?"):
            vtt_canvas.delete("token")
            vtt_canvas.delete("sel_ring")
            state["tokens"].clear()

    panel_btn(tok_sec, "🗑️ Clear All Tokens", clear_all_tokens)
    panel_sep(tok_sec)
    panel_btn(tok_sec, "⬆️ Push Tokens → Sheet", push_to_sheet,  bg="#8e44ad")
    panel_btn(tok_sec, "⬇️ Pull Tokens ← Sheet", pull_from_sheet, bg="#8e44ad")
    panel_sep(tok_sec)

    polling_lbl = tk.Label(tok_sec, text="⏸ Auto Sync: OFF",
                           bg="#1e1e2e", fg="#7f8c8d", font=("Arial", 8))
    polling_lbl.pack(anchor="w", padx=6)
    polling_var = tk.BooleanVar(value=False)

    def toggle_polling():
        if not polling_var.get():
            polling_var.set(True)
            state["polling"] = True
            polling_lbl.config(text="▶ Auto Sync: ON", fg="#27ae60")
            start_sheet_polling(state, state["tokens"], vtt_canvas,
                                redraw_all, interval_ms=60000)
        else:
            polling_var.set(False)
            state["polling"] = False
            polling_lbl.config(text="⏸ Auto Sync: OFF", fg="#7f8c8d")

    panel_btn(tok_sec, "⏯ Toggle Auto Sync", toggle_polling)
    panel_sep(tok_sec)
    panel_btn(tok_sec, "💾 Save Token State",
              lambda: save_vtt_state(state["tokens"]))
    panel_btn(tok_sec, "📂 Load Token State",
              lambda: load_vtt_state(state, vtt_canvas, redraw_all))

    # -----------------------------------------------------------------------
    # SIDE PANEL — MAP SECTION
    # -----------------------------------------------------------------------
    map_sec = make_section("🗺️ MAP")

    panel_btn(map_sec, "📂 Browse Map", browse_map)
    panel_sep(map_sec)

    # Paint mode
    paint_mode_lbl = tk.Label(map_sec, text="🖌️ Paint Mode: OFF",
                              bg="#1e1e2e", fg="#7f8c8d", font=("Arial", 8))
    paint_mode_lbl.pack(anchor="w", padx=6, pady=2)

    def toggle_paint_mode():
        vtt_canvas.paint_mode = not vtt_canvas.paint_mode
        if vtt_canvas.paint_mode:
            paint_mode_lbl.config(text="🖌️ Paint Mode: ON", fg="#e67e22")
            vtt_canvas.config(cursor="pencil")
        else:
            paint_mode_lbl.config(text="🖌️ Paint Mode: OFF", fg="#7f8c8d")
            vtt_canvas.config(cursor="crosshair")

    panel_btn(map_sec, "🖌️ Toggle Paint Mode", toggle_paint_mode, bg="#e67e22")

    # Cell type radio buttons
    tk.Label(map_sec, text="Paint Type:", bg="#1e1e2e", fg="#aaaacc",
             font=("Arial", 8)).pack(anchor="w", padx=6, pady=(6, 0))

    paint_colors = {
        "edge":      "#5d7a8a",
        "wall":      "#888899",
        "floor":     "#aabbaa",
        "difficult": "#e67e22",
        "erase":     "#c0392b",
    }
    for ctype in ["edge", "wall", "floor", "difficult", "erase"]:
        tk.Radiobutton(
            map_sec, text=f"  {ctype.capitalize()}",
            variable=paint_type_var, value=ctype,
            bg="#1e1e2e", fg=paint_colors[ctype],
            selectcolor="#2c3e50", activebackground="#1e1e2e",
            font=("Arial", 8)
        ).pack(anchor="w", padx=10)

    panel_sep(map_sec)
    panel_btn(map_sec, "⬆️ Push MapState → Sheet",
              lambda: push_mapstate_to_sheet(
                  vtt_canvas.mapstate,
                  state.get("grid_cols", 10),
                  state.get("grid_rows", 10)
              ), bg="#16a085")
    panel_btn(map_sec, "⬇️ Pull MapState ← Sheet", pull_mapstate, bg="#16a085")
    panel_sep(map_sec)
    panel_btn(map_sec, "💾 Save MapState",
              lambda: save_mapstate_json(
                  state.get("map_name", "unknown"),
                  state.get("grid_cols", 10),
                  state.get("grid_rows", 10),
                  vtt_canvas.mapstate
              ))
    panel_btn(map_sec, "📂 Load MapState", load_mapstate)

    # -----------------------------------------------------------------------
    # WASD TOKEN MOVEMENT
    # -----------------------------------------------------------------------
    def move_selected(event):
        if vtt_canvas.paint_mode:
            return
        tok = getattr(vtt_canvas, "selected_token", None)
        if not tok:
            return
        key     = event.keysym.lower()
        new_col = tok.grid_col
        new_row = tok.grid_row
        if key == "w": new_row -= 1
        if key == "s": new_row += 1
        if key == "a": new_col -= 1
        if key == "d": new_col += 1
        new_col   = max(0, new_col)
        new_row   = max(0, new_row)
        coord     = f"{col_to_letters(new_col)}{new_row + 1}"
        cell_type = vtt_canvas.mapstate.get(coord, "")
        if CELL_TYPES.get(cell_type, {}).get("collision", False):
            tok.wiggle()
            return
        tok.grid_col = new_col
        tok.grid_row = new_row
        tok.move_to(tok.cell_px)
        tok.select()

    vtt_canvas.bind("<w>", move_selected)
    vtt_canvas.bind("<s>", move_selected)
    vtt_canvas.bind("<a>", move_selected)
    vtt_canvas.bind("<d>", move_selected)

    # -----------------------------------------------------------------------
    # PAN
    # -----------------------------------------------------------------------
    def pan(event):
        if event.keysym == "Left":  vtt_canvas.xview_scroll(-1, "units")
        if event.keysym == "Right": vtt_canvas.xview_scroll( 1, "units")
        if event.keysym == "Up":    vtt_canvas.yview_scroll(-1, "units")
        if event.keysym == "Down":  vtt_canvas.yview_scroll( 1, "units")

    vtt_canvas.bind("<Left>",  pan)
    vtt_canvas.bind("<Right>", pan)
    vtt_canvas.bind("<Up>",    pan)
    vtt_canvas.bind("<Down>",  pan)
    vtt_canvas.bind("<Button-1>", lambda e: vtt_canvas.focus_set())
    vtt_canvas.bind("<ButtonPress-2>",
                    lambda e: vtt_canvas.scan_mark(e.x, e.y))
    vtt_canvas.bind("<B2-Motion>",
                    lambda e: vtt_canvas.scan_dragto(e.x, e.y, gain=1))

    # -----------------------------------------------------------------------
    # INITIAL DRAW
    # -----------------------------------------------------------------------
    parent.after(100, redraw_all)