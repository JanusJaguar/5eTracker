# ---------------------------------------------------------------------------
# vtt.py — Virtual Tabletop  |  Janus D&D Tracker  |  Phase 2
# ---------------------------------------------------------------------------
# REQUIRES:  pip install Pillow gspread google-auth gspread-formatting
#
# LAYERS (bottom → top):
#   MAP LAYER   — background images, freely placed/resized (lockable)
#   TILE LAYER  — grid, labels, painted mapstate cells    (lockable)
#   TOKEN LAYER — tokens, rings, move counters            (lockable)
# ---------------------------------------------------------------------------

import os
import json
import math
import uuid
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

try:
    from PIL import Image, ImageTk
    PIL_OK = True
except ImportError:
    PIL_OK = False

# ---------------------------------------------------------------------------
# PATHS
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
    return sorted(f for f in os.listdir(folder)
                  if os.path.splitext(f)[1].lower() in IMG_EXTS)

# ---------------------------------------------------------------------------
# CELL TYPES
# ---------------------------------------------------------------------------
CELL_TYPES = {
    "edge":        {"color": "#2c3e50", "collision": True},
    "wall":        {"color": "#1a1a2e", "collision": True},
    "floor":       {"color": "#d5d8dc", "collision": False},
    "difficult":   {"color": "#f39c12", "collision": False},
    "door_closed": {"color": "#8B4513", "collision": True},
    "door_open":   {"color": "#DEB887", "collision": False},
    "water":       {"color": "#2e86c1", "collision": False},
    "trap":        {"color": "#424242", "collision": False},
    "e_dam":       {"color": "#e74c3c", "collision": False},
    "janus_a":     {"color": "#a9cce3", "collision": False},
    "janus_b":     {"color": "#7d6608", "collision": False},
}

# ---------------------------------------------------------------------------
# COORDINATE HELPERS
# ---------------------------------------------------------------------------

def col_to_letters(n):
    result = ""
    n += 1
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        result = chr(65 + remainder) + result
    return result


def coord_to_col_row(coord):
    col_str = "".join(ch for ch in coord if ch.isalpha())
    row_str = "".join(ch for ch in coord if ch.isdigit())
    col_idx = 0
    for ch in col_str.upper():
        col_idx = col_idx * 26 + (ord(ch) - ord('A') + 1)
    col_idx -= 1
    return col_idx, int(row_str) - 1

# ---------------------------------------------------------------------------
# JANUS HELPERS
# ---------------------------------------------------------------------------

def build_janus_pairs(mapstate):
    a = [k for k, v in mapstate.items() if v == "janus_a"]
    b = [k for k, v in mapstate.items() if v == "janus_b"]
    return list(zip(a, b))


def find_janus_destination(coord, mapstate):
    pairs = build_janus_pairs(mapstate)
    ctype = mapstate.get(coord, "")
    for ca, cb in pairs:
        if ctype == "janus_a" and ca == coord:
            return cb
        if ctype == "janus_b" and cb == coord:
            return ca
    return None

# ---------------------------------------------------------------------------
# SCENE IMAGE  (one placed image on the map layer)
# ---------------------------------------------------------------------------

class SceneImage:
    HANDLE_SIZE = 8

    def __init__(self, canvas, path, x=0, y=0, w=None, h=None,
                 img_id=None):
        self.canvas  = canvas
        self.path    = path
        self.x       = x        # canvas world coords
        self.y       = y
        self.img_id  = img_id or str(uuid.uuid4())[:8]
        self._photo  = None
        self._raw    = None      # PIL image at original size

        if PIL_OK:
            self._raw = Image.open(path)
            self.w = w or self._raw.width
            self.h = h or self._raw.height
        else:
            self.w = w or 400
            self.h = h or 300

        self.rect_id   = None    # canvas item for image
        self.handles   = {}      # handle_name → canvas item id
        self.selected  = False
        self._drag_data = {}

        self._draw()

    # ------------------------------------------------------------------ draw

    def _draw(self):
        self.canvas.delete(f"si_{self.img_id}")

        if PIL_OK and self._raw:
            scaled = self._raw.resize(
                (max(1, int(self.w)), max(1, int(self.h))),
                Image.LANCZOS
            )
            self._photo = ImageTk.PhotoImage(scaled)
            self.rect_id = self.canvas.create_image(
                self.x, self.y,
                anchor="nw",
                image=self._photo,
                tags=("map_layer", f"si_{self.img_id}")
            )
        else:
            self.rect_id = self.canvas.create_rectangle(
                self.x, self.y,
                self.x + self.w, self.y + self.h,
                fill="#333355", outline="#666688",
                tags=("map_layer", f"si_{self.img_id}")
            )

        self._draw_handles()

    def _draw_handles(self):
        # Remove old handles
        for hid in self.handles.values():
            self.canvas.delete(hid)
        self.handles.clear()

        if not self.selected:
            return

        hs = self.HANDLE_SIZE
        x, y, w, h = self.x, self.y, self.w, self.h
        mx, my = x + w / 2, y + h / 2

        positions = {
            "tl": (x,      y),
            "tm": (mx,     y),
            "tr": (x + w,  y),
            "ml": (x,      my),
            "mr": (x + w,  my),
            "bl": (x,      y + h),
            "bm": (mx,     y + h),
            "br": (x + w,  y + h),
        }

        for name, (hx, hy) in positions.items():
            hid = self.canvas.create_rectangle(
                hx - hs/2, hy - hs/2,
                hx + hs/2, hy + hs/2,
                fill="#f1c40f", outline="#e67e22",
                tags=("map_layer", f"si_{self.img_id}",
                      f"handle_{self.img_id}_{name}")
            )
            self.handles[name] = hid
            self.canvas.tag_bind(
                hid, "<ButtonPress-1>",
                lambda e, n=name: self._start_resize(e, n)
            )
            self.canvas.tag_bind(
                hid, "<B1-Motion>",
                lambda e, n=name: self._do_resize(e, n)
            )
            self.canvas.tag_bind(
                hid, "<ButtonRelease-1>",
                lambda e: self._end_resize(e)
            )

    def select(self):
        self.selected = True
        self._draw_handles()

    def deselect(self):
        self.selected = False
        self._draw_handles()

    def refresh(self):
        self._draw()

    # ---------------------------------------------------------------- drag

    def start_drag(self, event):
        self._drag_data = {
            "x": event.x, "y": event.y,
            "ox": self.x,  "oy": self.y
        }

    def do_drag(self, event):
        dx = event.x - self._drag_data["x"]
        dy = event.y - self._drag_data["y"]
        self.x = self._drag_data["ox"] + dx
        self.y = self._drag_data["oy"] + dy
        self._draw()

    # -------------------------------------------------------------- resize

    def _start_resize(self, event, handle):
        self._drag_data = {
            "handle": handle,
            "ex": event.x, "ey": event.y,
            "ox": self.x, "oy": self.y,
            "ow": self.w, "oh": self.h
        }

    def _do_resize(self, event, handle):
        d  = self._drag_data
        dx = event.x - d["ex"]
        dy = event.y - d["ey"]

        x, y, w, h = d["ox"], d["oy"], d["ow"], d["oh"]

        if "l" in handle:
            self.x = x + dx
            self.w = max(40, w - dx)
        if "r" in handle:
            self.w = max(40, w + dx)
        if "t" in handle:
            self.y = y + dy
            self.h = max(40, h - dy)
        if "b" in handle:
            self.h = max(40, h + dy)

        self._draw()

    def _end_resize(self, event):
        self._drag_data = {}

    # ------------------------------------------------------------ serialise

    def to_dict(self):
        return {
            "id":   self.img_id,
            "path": self.path,
            "x":    self.x,
            "y":    self.y,
            "w":    self.w,
            "h":    self.h,
        }

    @classmethod
    def from_dict(cls, canvas, d):
        return cls(
            canvas,
            path   = d["path"],
            x      = d.get("x", 0),
            y      = d.get("y", 0),
            w      = d.get("w"),
            h      = d.get("h"),
            img_id = d.get("id"),
        )

    def delete(self):
        self.canvas.delete(f"si_{self.img_id}")

# ---------------------------------------------------------------------------
# TOKEN CLASS
# ---------------------------------------------------------------------------

class Token:
    def __init__(self, canvas, col, row, cell_px, label="Token",
                 color="#e74c3c", img_path=None, speed=6,
                 hp=None, token_type="enemy"):
        self.canvas     = canvas
        self.label      = label
        self.color      = color
        self.cell_px    = cell_px
        self.grid_col   = col
        self.grid_row   = row
        self.hp         = hp
        self.speed      = speed
        self.moves_left = speed
        self.token_type = token_type
        self._photo     = None
        self._img_path  = img_path
        self.initiative = 0

        x    = col * cell_px
        y    = row * cell_px
        half = cell_px // 2

        if img_path and PIL_OK:
            img = Image.open(img_path).resize(
                (cell_px, cell_px), Image.LANCZOS)
            self._photo = ImageTk.PhotoImage(img)
            self.oval = canvas.create_image(
                x, y, image=self._photo, anchor="nw",
                tags=("token_layer", "token"))
        else:
            self.oval = canvas.create_oval(
                x, y, x + cell_px, y + cell_px,
                fill=color, outline="white", width=2,
                tags=("token_layer", "token"))

        self.text = canvas.create_text(
            x + half, y + cell_px + 8,
            text=self._build_label(), fill="white",
            font=("Arial", 7, "bold"),
            tags=("token_layer", "token"))

        self.move_lbl = canvas.create_text(
            x + half, y - 8, text="",
            fill="#27ae60", font=("Arial", 7, "bold"),
            tags=("token_layer", "token"), state="hidden")

        self._drag_x = 0
        self._drag_y = 0
        self._drag_start_col = col
        self._drag_start_row = row

        for item in (self.oval, self.text):
            canvas.tag_bind(item, "<ButtonPress-1>",   self._on_press)
            canvas.tag_bind(item, "<B1-Motion>",       self._on_drag)
            canvas.tag_bind(item, "<ButtonRelease-1>", self._on_release)
            canvas.tag_bind(item, "<Button-3>",        self._on_right_click)

    def _build_label(self):
        parts = [self.label]
        if self.hp is not None:
            parts.append(f"HP:{self.hp}")
        return "\n".join(parts)

    def _update_text(self):
        self.canvas.itemconfig(self.text, text=self._build_label())

    def show_move_counter(self):
        self.canvas.itemconfig(
            self.move_lbl,
            text=f"▶{self.moves_left}/{self.speed}",
            state="normal")

    def hide_move_counter(self):
        self.canvas.itemconfig(self.move_lbl, state="hidden")

    def select(self):
        self.canvas.delete(f"sel_ring_{id(self)}")
        c = self.cell_px
        x, y = self.grid_col * c, self.grid_row * c
        self.canvas.create_rectangle(
            x, y, x + c, y + c,
            outline="#f1c40f", width=3,
            tags=(f"sel_ring_{id(self)}", "sel_ring", "token_layer"))
        self.canvas.tag_raise("token_layer")
        self.show_move_counter()

    def deselect(self):
        self.canvas.delete(f"sel_ring_{id(self)}")
        self.hide_move_counter()

    def move_to(self, cell_px):
        self.cell_px = cell_px
        x    = self.grid_col * cell_px
        y    = self.grid_row * cell_px
        half = cell_px // 2

        if self._img_path and PIL_OK:
            img = Image.open(self._img_path).resize(
                (cell_px, cell_px), Image.LANCZOS)
            self._photo = ImageTk.PhotoImage(img)
            self.canvas.coords(self.oval, x, y)
            self.canvas.itemconfig(self.oval, image=self._photo)
        else:
            self.canvas.coords(self.oval, x, y,
                               x + cell_px, y + cell_px)

        self.canvas.coords(self.text,     x + half, y + cell_px + 8)
        self.canvas.coords(self.move_lbl, x + half, y - 8)
        self.canvas.delete(f"sel_ring_{id(self)}")

    def _move_cost(self, dc, dr):
        return 2 if dc != 0 and dr != 0 else 1

    def can_move(self, dc, dr):
        return self.moves_left >= self._move_cost(dc, dr)

    def spend_move(self, dc, dr):
        self.moves_left = max(0, self.moves_left - self._move_cost(dc, dr))

    def reset_movement(self):
        self.moves_left = self.speed

    def _path_clear(self, dest_col, dest_row, mapstate):
        x0, y0 = self.grid_col, self.grid_row
        x1, y1 = dest_col, dest_row
        dx, dy = abs(x1-x0), abs(y1-y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        cx, cy = x0, y0
        while True:
            if not (cx == x0 and cy == y0):
                coord = f"{col_to_letters(cx)}{cy+1}"
                if CELL_TYPES.get(
                        mapstate.get(coord,""),{}).get("collision",False):
                    return False
            if cx == x1 and cy == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy; cx += sx
            if e2 < dx:
                err += dx; cy += sy
        return True

    def wiggle(self):
        c  = self.cell_px
        ox = self.grid_col * c
        oy = self.grid_row * c
        if not self._img_path:
            self.canvas.itemconfig(self.oval, fill="#e74c3c")
        steps = [8, -16, 16, -16, 8, 0]
        def do_step(i):
            if i >= len(steps):
                if self._img_path and PIL_OK:
                    self.canvas.coords(self.oval, ox, oy)
                else:
                    self.canvas.coords(self.oval, ox, oy, ox+c, oy+c)
                self.canvas.coords(self.text, ox+c//2, oy+c+8)
                if not self._img_path:
                    self.canvas.itemconfig(self.oval, fill=self.color)
                return
            self.canvas.move(self.oval, steps[i], 0)
            self.canvas.move(self.text, steps[i], 0)
            self.canvas.after(50, lambda: do_step(i+1))

    def _on_press(self, event):
        if not self.canvas.layer_unlocked("token"):
            return
        if getattr(self.canvas, "paint_mode", False):
            return
        self._drag_x = event.x
        self._drag_y = event.y
        self._drag_start_col = self.grid_col
        self._drag_start_row = self.grid_row
        self.canvas.tag_raise(self.oval)
        self.canvas.tag_raise(self.text)
        prev = getattr(self.canvas, "selected_token", None)
        if prev and prev is not self:
            prev.deselect()
        self.canvas.selected_token = self
        self.select()

    def _on_drag(self, event):
        if not self.canvas.layer_unlocked("token"):
            return
        if getattr(self.canvas, "paint_mode", False):
            return
        dx = event.x - self._drag_x
        dy = event.y - self._drag_y
        self.canvas.move(self.oval, dx, dy)
        self.canvas.move(self.text, dx, dy)
        self.canvas.move(self.move_lbl, dx, dy)
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_release(self, event):
        if not self.canvas.layer_unlocked("token"):
            return
        if getattr(self.canvas, "paint_mode", False):
            return
        c = self.cell_px
        coords = self.canvas.coords(self.oval)
        raw_x, raw_y = coords[0], coords[1]
        snapped_x = round(raw_x / c) * c
        snapped_y = round(raw_y / c) * c
        new_col = int(snapped_x / c)
        new_row = int(snapped_y / c)
        dest_coord = f"{col_to_letters(new_col)}{new_row+1}"
        cell_type  = self.canvas.mapstate.get(dest_coord, "")

        if CELL_TYPES.get(cell_type, {}).get("collision", False):
            self._snap_back(); self.wiggle(); return

        if not self._path_clear(new_col, new_row, self.canvas.mapstate):
            self._snap_back(); self.wiggle(); return

        d_col  = abs(new_col - self._drag_start_col)
        d_row  = abs(new_row - self._drag_start_row)
        steps  = max(d_col, d_row)
        cost   = steps + (steps // 2 if (d_col > 0 and d_row > 0) else 0)

        if cost > self.moves_left:
            self._snap_back()
            messagebox.showwarning("Out of Movement",
                f"{self.label} only has {self.moves_left} move(s) left!")
            return

        dx = snapped_x - raw_x
        dy = snapped_y - raw_y
        self.canvas.move(self.oval,     dx, dy)
        self.canvas.move(self.text,     dx, dy)
        self.canvas.move(self.move_lbl, dx, dy)
        self.grid_col   = new_col
        self.grid_row   = new_row
        self.moves_left = max(0, self.moves_left - cost)
        self.select()
        self._check_janus(dest_coord)

    def _snap_back(self):
        c  = self.cell_px
        ox = self._drag_start_col * c
        oy = self._drag_start_row * c
        if self._img_path and PIL_OK:
            self.canvas.coords(self.oval, ox, oy)
        else:
            self.canvas.coords(self.oval, ox, oy, ox+c, oy+c)
        self.canvas.coords(self.text,     ox+c//2, oy+c+8)
        self.canvas.coords(self.move_lbl, ox+c//2, oy-8)

    def _check_janus(self, coord):
        dest = find_janus_destination(coord, self.canvas.mapstate)
        if dest is None:
            return
        dc, dr = coord_to_col_row(dest)
        c = self.cell_px
        self.grid_col = dc
        self.grid_row = dr
        self.canvas.coords(self.oval,     dc*c, dr*c, dc*c+c, dr*c+c)
        self.canvas.coords(self.text,     dc*c+c//2, dr*c+c+8)
        self.canvas.coords(self.move_lbl, dc*c+c//2, dr*c-8)
        self.select()

    def _on_right_click(self, event):
        if getattr(self.canvas, "paint_mode", False):
            return
        menu = tk.Menu(self.canvas, tearoff=0)
        menu.add_command(label=f"✏️  Rename [{self.label}]",
                         command=self._rename)
        menu.add_command(label="❤️  Set HP",    command=self._set_hp)
        menu.add_command(label="⚡  Set Speed", command=self._set_speed)
        menu.add_separator()
        menu.add_command(label="🗑️  Remove",    command=self._remove)
        menu.tk_popup(event.x_root, event.y_root)

    def _rename(self):
        new = simpledialog.askstring("Rename", "New name:",
                                     initialvalue=self.label)
        if new:
            self.label = new; self._update_text()

    def _set_hp(self):
        val = simpledialog.askstring("Set HP", "HP (e.g. 30/45):",
                                     initialvalue=self.hp or "")
        if val is not None:
            self.hp = val; self._update_text()

    def _set_speed(self):
        val = simpledialog.askinteger("Set Speed",
                                      "Speed in squares:",
                                      initialvalue=self.speed,
                                      minvalue=0, maxvalue=30)
        if val is not None:
            self.speed = val
            self.moves_left = val
            self.show_move_counter()

    def _remove(self):
        self.canvas.delete(f"sel_ring_{id(self)}")
        self.canvas.delete(self.oval)
        self.canvas.delete(self.text)
        self.canvas.delete(self.move_lbl)
        if getattr(self.canvas, "selected_token", None) is self:
            self.canvas.selected_token = None

# ---------------------------------------------------------------------------
# GOOGLE SHEETS
# ---------------------------------------------------------------------------

def get_sheets_client():
    import gspread
    from google.oauth2.service_account import Credentials
    creds_path = os.path.join(BASE_DIR, "credentials.json")
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    return gspread.authorize(creds)


def open_vtt_sheet(name="DnD_VTT"):
    return get_sheets_client().open(name).sheet1


def push_tokens_to_sheet(tokens):
    try:
        sheet = open_vtt_sheet()
        sheet.batch_clear(["A2:F100"])
        rows = [[t.label,
                 col_to_letters(t.grid_col),
                 t.grid_row + 1,
                 t.token_type,
                 t.hp or "",
                 t.speed] for t in tokens]
        if rows:
            sheet.update(f"A2:F{1+len(rows)}", rows)
    except Exception as e:
        messagebox.showerror("Sheet Error", str(e))


def pull_tokens_from_sheet():
    try:
        rows = open_vtt_sheet().get_all_records()
        result = []
        for row in rows:
            try:
                col_str = str(row.get("col","A")).strip().upper()
                col_idx = 0
                for ch in col_str:
                    col_idx = col_idx*26 + (ord(ch)-ord('A')+1)
                col_idx -= 1
                result.append({
                    "name":  str(row.get("name","Token")),
                    "col":   col_idx,
                    "row":   int(row.get("row",1))-1,
                    "type":  str(row.get("type","enemy")),
                    "hp":    str(row.get("hp","")) or None,
                    "speed": int(row.get("speed",6) or 6),
                })
            except Exception:
                continue
        return result
    except Exception as e:
        messagebox.showerror("Sheet Error", str(e))
        return []


def start_sheet_polling(state, tokens_ref, canvas, redraw_fn,
                        interval_ms=60000):
    last = [None]

    def poll():
        try:
            data = pull_tokens_from_sheet()
            sig  = tuple((d["name"],d["col"],d["row"],d["hp"]) for d in data)
            if sig != last[0]:
                last[0] = sig
                canvas.delete("token")
                canvas.delete("sel_ring")
                tokens_ref.clear()
                c = state["cell_px"]
                for td in data:
                    color = "#e74c3c" if td["type"]=="enemy" else "#2980b9"
                    tok = Token(canvas, td["col"], td["row"], c,
                                label=td["name"], color=color,
                                speed=td.get("speed",6),
                                token_type=td["type"])
                    if td["hp"]:
                        tok.hp = td["hp"]; tok._update_text()
                    tokens_ref.append(tok)
                redraw_fn()
        except Exception:
            pass
        if state.get("polling"):
            canvas.after(interval_ms, poll)

    state["polling"] = True
    canvas.after(interval_ms, poll)


def push_mapstate_to_sheet(cells, grid_cols, grid_rows):
    try:
        client = get_sheets_client()
        ss     = client.open("DnD_VTT")
        try:
            sheet = ss.worksheet("MapState")
        except Exception:
            sheet = ss.add_worksheet("MapState", rows=300, cols=300)
        sheet.clear()
        tc = grid_cols + 2
        tr = grid_rows + 2
        grid = [[""] * tc for _ in range(tr)]
        for coord, ctype in cells.items():
            cs = "".join(ch for ch in coord if ch.isalpha())
            rn = "".join(ch for ch in coord if ch.isdigit())
            if not cs or not rn:
                continue
            ci = 0
            for ch in cs.upper():
                ci = ci*26 + (ord(ch)-ord('A')+1)
            ci -= 1
            ri = int(rn)-1
            if 0<=ri<tr and 0<=ci<tc:
                grid[ri][ci] = ctype
        sheet.update("A1", grid)
        messagebox.showinfo("Synced","✅ MapState pushed!")
    except Exception as e:
        messagebox.showerror("Sheet Error", str(e))


def pull_mapstate_from_sheet():
    try:
        client = get_sheets_client()
        sheet  = client.open("DnD_VTT").worksheet("MapState")
        rows   = sheet.get_all_values()
        cells  = {}
        for ri, row in enumerate(rows):
            for ci, val in enumerate(row):
                if val.strip():
                    cells[f"{col_to_letters(ci)}{ri+1}"] = val.strip().lower()
        return cells
    except Exception as e:
        messagebox.showerror("Sheet Error", str(e))
        return None


def push_janus_to_sheet(pairs):
    try:
        client = get_sheets_client()
        ss     = client.open("DnD_VTT")
        try:
            sheet = ss.worksheet("JanusLinks")
        except Exception:
            sheet = ss.add_worksheet("JanusLinks", rows=100, cols=2)
        sheet.clear()
        sheet.update("A1", [["janus_a","janus_b"]] +
                     [[a,b] for a,b in pairs])
        messagebox.showinfo("Synced","✅ Janus pairs pushed!")
    except Exception as e:
        messagebox.showerror("Sheet Error", str(e))

# ---------------------------------------------------------------------------
# SCENE SAVE / LOAD
# ---------------------------------------------------------------------------

def save_scene(state, vtt_canvas):
    file = tk.filedialog.asksaveasfilename(
        title="Save Scene", defaultextension=".json",
        initialdir=BASE_DIR, filetypes=[("JSON","*.json")])
    if not file:
        return
    data = {
        "scene_name":  state.get("scene_name","Scene"),
        "canvas_cols": state.get("canvas_cols", 52),
        "canvas_rows": state.get("canvas_rows",100),
        "cell_ft":     state.get("cell_ft", 5),
        "cell_px":     state["cell_px"],
        "images":      [si.to_dict() for si in state["scene_images"]],
        "cells":       vtt_canvas.mapstate,
        "janus_pairs": build_janus_pairs(vtt_canvas.mapstate),
        "tokens":      [{
            "name":     t.label,
            "col":      t.grid_col,
            "row":      t.grid_row,
            "color":    t.color,
            "hp":       t.hp or "",
            "speed":    t.speed,
            "type":     t.token_type,
            "img_path": t._img_path or "",
        } for t in state["tokens"]],
    }
    try:
        with open(file,"w") as f:
            json.dump(data, f, indent=4)
        messagebox.showinfo("Saved","✅ Scene saved!")
    except Exception as e:
        messagebox.showerror("Save Error", str(e))


def load_scene(state, vtt_canvas, redraw_fn,
               scene_name_var, update_image_list_fn):
    file = tk.filedialog.askopenfilename(
        title="Load Scene", initialdir=BASE_DIR,
        filetypes=[("JSON","*.json")])
    if not file:
        return
    try:
        with open(file) as f:
            data = json.load(f)

        # Clear canvas
        vtt_canvas.delete("map_layer")
        vtt_canvas.delete("token_layer")
        vtt_canvas.delete("sel_ring")
        state["scene_images"].clear()
        state["tokens"].clear()
        state["selected_image"] = None

        state["scene_name"]  = data.get("scene_name","Scene")
        state["canvas_cols"] = data.get("canvas_cols", 52)
        state["canvas_rows"] = data.get("canvas_rows",100)
        state["cell_ft"]     = data.get("cell_ft", 5)
        state["cell_px"]     = data.get("cell_px", 30)
        vtt_canvas.mapstate  = data.get("cells", {})

        scene_name_var.set(state["scene_name"])

        for img_d in data.get("images",[]):
            path = img_d.get("path","")
            if os.path.exists(path):
                si = SceneImage.from_dict(vtt_canvas, img_d)
                state["scene_images"].append(si)

        c = state["cell_px"]
        for td in data.get("tokens",[]):
            ip = td.get("img_path") or None
            if ip and not os.path.exists(ip):
                ip = None
            tok = Token(vtt_canvas, td["col"], td["row"], c,
                        label=td["name"],
                        color=td.get("color","#e74c3c"),
                        speed=td.get("speed",6),
                        hp=td.get("hp") or None,
                        token_type=td.get("type","enemy"),
                        img_path=ip)
            state["tokens"].append(tok)

        update_image_list_fn()
        redraw_fn()
        messagebox.showinfo("Loaded",
            f"✅ Scene '{state['scene_name']}' loaded!")
    except Exception as e:
        messagebox.showerror("Load Error", str(e))


def save_vtt_tokens(tokens):
    file = tk.filedialog.asksaveasfilename(
        title="Save Tokens", defaultextension=".json",
        initialdir=BASE_DIR, filetypes=[("JSON","*.json")])
    if not file:
        return
    try:
        with open(file,"w") as f:
            json.dump([{
                "name":     t.label, "col": t.grid_col,
                "row":      t.grid_row, "color": t.color,
                "hp":       t.hp or "", "speed": t.speed,
                "type":     t.token_type, "img_path": t._img_path or "",
            } for t in tokens], f, indent=4)
        messagebox.showinfo("Saved",f"✅ Saved {len(tokens)} tokens!")
    except Exception as e:
        messagebox.showerror("Save Error", str(e))


def load_vtt_tokens(state, vtt_canvas, redraw_fn):
    file = tk.filedialog.askopenfilename(
        title="Load Tokens", initialdir=BASE_DIR,
        filetypes=[("JSON","*.json")])
    if not file:
        return
    try:
        with open(file) as f:
            data = json.load(f)
        vtt_canvas.delete("token")
        vtt_canvas.delete("sel_ring")
        state["tokens"].clear()
        c = state["cell_px"]
        for td in data:
            ip = td.get("img_path") or None
            if ip and not os.path.exists(ip):
                ip = None
            tok = Token(vtt_canvas, td["col"], td["row"], c,
                        label=td["name"],
                        color=td.get("color","#e74c3c"),
                        speed=td.get("speed",6),
                        hp=td.get("hp") or None,
                        token_type=td.get("type","enemy"),
                        img_path=ip)
            state["tokens"].append(tok)
        redraw_fn()
        messagebox.showinfo("Loaded",f"✅ Loaded {len(data)} tokens!")
    except Exception as e:
        messagebox.showerror("Load Error", str(e))

# ---------------------------------------------------------------------------
# MAIN BUILD FUNCTION
# ---------------------------------------------------------------------------

def build_vtt_tab(parent):

    # -----------------------------------------------------------------------
    # STATE
    # -----------------------------------------------------------------------
    state = {
        "cell_px":        30,
        "cell_ft":        5,
        "show_grid":      True,
        "tokens":         [],
        "scene_images":   [],        # list of SceneImage
        "selected_image": None,      # SceneImage or None
        "scene_name":     "New Scene",
        "canvas_cols":    52,
        "canvas_rows":    100,
        "polling":        False,
        # layer locks
        "lock_map":       False,     # Map layer locked by default? No — DM starts unlocked
        "lock_tile":      False,
        "lock_token":     False,
        # initiative
        "initiative_list":  [],
        "current_turn_idx": 0,
        "combat_active":    False,
    }

    # -----------------------------------------------------------------------
    # TOP TOOLBAR
    # -----------------------------------------------------------------------
    toolbar = tk.Frame(parent)
    toolbar.pack(side="top", fill="x", padx=6, pady=2)

    # -----------------------------------------------------------------------
    # CANVAS AREA
    # -----------------------------------------------------------------------
    canvas_frame = tk.Frame(parent)
    canvas_frame.pack(fill="both", expand=True)

    vtt_canvas = tk.Canvas(canvas_frame, bg="#1a1a2e", cursor="crosshair")
    vtt_canvas.pack(fill="both", expand=True)

    # Attach state to canvas for token access
    vtt_canvas.mapstate   = {}
    vtt_canvas.paint_mode = False

    def layer_unlocked(layer):
        return not state.get(f"lock_{layer}", False)
    vtt_canvas.layer_unlocked = layer_unlocked

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
    PANEL_W = 190

    panel = tk.Frame(canvas_frame, bg="#1e1e2e", width=PANEL_W,
                     relief="flat", bd=0)
    panel.place(x=0, y=0, width=PANEL_W, relheight=1.0)
    panel.pack_propagate(False)

    pc = tk.Canvas(panel, bg="#1e1e2e", highlightthickness=0,
                   width=PANEL_W-16)
    ps = tk.Scrollbar(panel, orient="vertical", command=pc.yview)
    pc.config(yscrollcommand=ps.set)
    ps.pack(side="right", fill="y")
    pc.pack(side="left", fill="both", expand=True)

    inner = tk.Frame(pc, bg="#1e1e2e")
    iw    = pc.create_window((0,0), window=inner, anchor="nw")

    inner.bind("<Configure>",
               lambda e: pc.config(scrollregion=pc.bbox("all")))
    pc.bind("<Configure>",
            lambda e: pc.itemconfig(iw, width=e.width))

    def psw(e):
        pc.yview_scroll(-1 if e.delta > 0 else 1, "units")
    pc.bind("<MouseWheel>",  psw)
    inner.bind("<MouseWheel>", psw)

    panel_visible = [True]
    toggle_btn = tk.Button(canvas_frame, text="◄",
                           font=("Arial",8,"bold"),
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
        hdr = tk.Frame(inner, bg="#2c3e50")
        hdr.pack(fill="x", pady=(6,0))
        lbl = tk.Label(hdr, text=f"▼ {title}", bg="#2c3e50", fg="white",
                       font=("Arial",9,"bold"), anchor="w", cursor="hand2")
        lbl.pack(fill="x", padx=6, pady=3)
        body = tk.Frame(inner, bg="#1e1e2e")
        body.pack(fill="x", padx=4, pady=2)
        col  = [False]

        def tog(e=None):
            if col[0]:
                body.pack(fill="x", padx=4, pady=2)
                lbl.config(text=f"▼ {title}")
            else:
                body.pack_forget()
                lbl.config(text=f"► {title}")
            col[0] = not col[0]
        lbl.bind("<Button-1>", tog)
        hdr.bind("<Button-1>", tog)
        return body

    def pbtn(par, text, cmd, bg="#2c3e50", fg="white"):
        tk.Button(par, text=text, command=cmd,
                  bg=bg, fg=fg, font=("Arial",8),
                  relief="flat", cursor="hand2",
                  anchor="w", padx=6).pack(fill="x", pady=1)

    def psep(par):
        ttk.Separator(par, orient="horizontal").pack(fill="x", pady=4)

    # -----------------------------------------------------------------------
    # ZOOM
    # -----------------------------------------------------------------------
    zoom_level = [1.0]

    # -----------------------------------------------------------------------
    # SCROLL REGION  (based on canvas_cols × canvas_rows × cell_px)
    # -----------------------------------------------------------------------
    def update_scroll_region():
        sc = max(4, int(state["cell_px"] * zoom_level[0]))
        w  = state["canvas_cols"] * sc
        h  = state["canvas_rows"] * sc
        vtt_canvas.config(scrollregion=(0, 0, w + sc*2, h + sc*2))

    # -----------------------------------------------------------------------
    # REDRAW ALL
    # -----------------------------------------------------------------------
    def redraw_all():
        c = state["cell_px"]   # ← no zoom_level here

        vtt_canvas.delete("map_layer")
        for si in state["scene_images"]:
            si.canvas = vtt_canvas
            si._draw()

        vtt_canvas.delete("grid")
        vtt_canvas.delete("gridlabel")
        vtt_canvas.delete("mapstate_tile")

        gw = state["canvas_cols"] * c
        gh = state["canvas_rows"] * c
        vtt_canvas.config(scrollregion=(0, 0, gw + c*2, gh + c*2))

        if state["show_grid"]:
            for x in range(0, gw + c, c):
                vtt_canvas.create_line(x, 0, x, gh,
                    fill="#444466", width=1, tags=("tile_layer","grid"))
            for y in range(0, gh + c, c):
                vtt_canvas.create_line(0, y, gw, y,
                    fill="#444466", width=1, tags=("tile_layer","grid"))

            lf = ("Arial", max(6, c//6), "bold")
            for ci in range(state["canvas_cols"]):
                vtt_canvas.create_text(
                    ci*c + c//2, 8,
                    text=col_to_letters(ci),
                    fill="#aaaacc", font=lf,
                    tags=("tile_layer","gridlabel"))
            for ri in range(state["canvas_rows"]):
                vtt_canvas.create_text(
                    6, ri*c + c//2,
                    text=str(ri+1),
                    fill="#aaaacc", font=lf, anchor="w",
                    tags=("tile_layer","gridlabel"))

        for coord, ctype in vtt_canvas.mapstate.items():
            if ctype not in CELL_TYPES:
                continue
            col_str = "".join(ch for ch in coord if ch.isalpha())
            row_num = "".join(ch for ch in coord if ch.isdigit())
            if not col_str or not row_num:
                continue
            ci = 0
            for ch in col_str.upper():
                ci = ci*26 + (ord(ch)-ord('A')+1)
            ci -= 1
            ri  = int(row_num)-1
            x   = ci * c
            y   = ri * c
            vtt_canvas.create_rectangle(
                x, y, x+c, y+c,
                fill=CELL_TYPES[ctype]["color"], outline="",
                tags=("tile_layer","mapstate_tile"))

        for tok in state["tokens"]:
            tok.move_to(c)

        vtt_canvas.tag_lower("tile_layer")
        vtt_canvas.tag_lower("map_layer")
        vtt_canvas.tag_raise("tile_layer")
        vtt_canvas.tag_raise("token_layer")

    # -----------------------------------------------------------------------
    # ZOOM FUNCTIONS
    # -----------------------------------------------------------------------
    zoom_level = [1.0]

    def zoom(factor):
        new_level = zoom_level[0] * factor
        if not (0.1 <= new_level <= 10.0):
            return
        zoom_level[0] = new_level

        # Scale everything from canvas origin
        vtt_canvas.scale("all", 0, 0, factor, factor)

        # Update scroll region to match new scale
        bb = vtt_canvas.bbox("all")
        if bb:
            vtt_canvas.config(scrollregion=bb)

    def reset_zoom():
        # Scale back to 1.0 from current
        if zoom_level[0] != 0:
            factor = 1.0 / zoom_level[0]
            vtt_canvas.scale("all", 0, 0, factor, factor)
            zoom_level[0] = 1.0
            bb = vtt_canvas.bbox("all")
            if bb:
                vtt_canvas.config(scrollregion=bb)

    vtt_canvas.bind("<MouseWheel>",
                    lambda e: zoom(1.1 if e.delta > 0 else 0.9))

    # -----------------------------------------------------------------------
    # COORDINATE DISPLAY
    # -----------------------------------------------------------------------
    coord_label = tk.Label(vtt_canvas, text="",
                           bg="#2c3e50", fg="white",
                           font=("Arial",8,"bold"), padx=4, pady=2)

    def on_mouse_move(event):
        # Account for zoom when converting to cell coords
        cx  = vtt_canvas.canvasx(event.x) / zoom_level[0]
        cy  = vtt_canvas.canvasy(event.y) / zoom_level[0]
        c   = state["cell_px"]
        col = int(cx // c)
        row = int(cy // c)
        coord    = f"{col_to_letters(col)}{row+1}"
        ctype    = vtt_canvas.mapstate.get(coord,"")
        type_txt = f" — {ctype}" if ctype else ""
        coord_label.config(text=f"{coord}{type_txt}")
        lx = min(event.x + 12, vtt_canvas.winfo_width()  - 90)
        ly = min(event.y + 12, vtt_canvas.winfo_height() - 24)
        coord_label.place(x=lx, y=ly)

    def on_mouse_leave(event):
        coord_label.place_forget()

    vtt_canvas.bind("<Motion>", on_mouse_move)
    vtt_canvas.bind("<Leave>",  on_mouse_leave)

    # -----------------------------------------------------------------------
    # NEW SCENE
    # -----------------------------------------------------------------------
    def new_scene():
        if state["tokens"] or state["scene_images"] or vtt_canvas.mapstate:
            if not messagebox.askyesno("New Scene",
                    "This will clear the current scene.\nContinue?"):
                return

        win = tk.Toplevel(parent)
        win.title("New Scene")
        win.geometry("300x240")
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="Scene Name:").pack(pady=(12,0))
        name_var = tk.StringVar(value="New Scene")
        tk.Entry(win, textvariable=name_var, width=24).pack()

        tk.Label(win, text="Canvas Columns (A→ZZ):").pack(pady=(10,0))
        cols_var = tk.IntVar(value=52)
        tk.Spinbox(win, from_=10, to=702, textvariable=cols_var,
                   width=8).pack()

        tk.Label(win, text="Canvas Rows:").pack(pady=(10,0))
        rows_var = tk.IntVar(value=100)
        tk.Spinbox(win, from_=10, to=1000, textvariable=rows_var,
                   width=8).pack()

        def confirm():
            vtt_canvas.delete("all")
            state["scene_images"].clear()
            state["tokens"].clear()
            state["selected_image"] = None
            vtt_canvas.mapstate     = {}
            state["initiative_list"] = []
            state["combat_active"]   = False

            state["scene_name"]  = name_var.get().strip() or "Scene"
            state["canvas_cols"] = max(10, cols_var.get())
            state["canvas_rows"] = max(10, rows_var.get())
            scene_name_var.set(state["scene_name"])
            update_image_list()
            redraw_all()
            win.destroy()

        tk.Button(win, text="✅ Create Scene", command=confirm,
                  bg="#27ae60", fg="white",
                  font=("Arial",10,"bold")).pack(pady=14)

    # -----------------------------------------------------------------------
    # ADD IMAGE  (to map layer)
    # -----------------------------------------------------------------------
    def add_image():
        if not layer_unlocked("map"):
            messagebox.showwarning("Layer Locked",
                "Unlock the Map Layer first.")
            return
        path = tk.filedialog.askopenfilename(
            title="Add Map Image", initialdir=MAPS_DIR,
            filetypes=[("Images","*.png *.jpg *.jpeg *.webp *.bmp")])
        if not path:
            return
        si = SceneImage(vtt_canvas, path,
                        x=vtt_canvas.canvasx(40),
                        y=vtt_canvas.canvasy(40))
        state["scene_images"].append(si)
        _select_image(si)
        update_image_list()
        vtt_canvas.tag_lower("map_layer")
        vtt_canvas.tag_raise("tile_layer")
        vtt_canvas.tag_raise("token_layer")

    # -----------------------------------------------------------------------
    # IMAGE SELECTION & DRAG  (map layer)
    # -----------------------------------------------------------------------
    def _select_image(si):
        if state["selected_image"] and state["selected_image"] is not si:
            state["selected_image"].deselect()
        state["selected_image"] = si
        if si:
            si.select()

    def _deselect_all_images():
        if state["selected_image"]:
            state["selected_image"].deselect()
        state["selected_image"] = None

    # Canvas click — check if we hit an image (map layer unlocked)
    def on_canvas_press(event):
        if not layer_unlocked("map"):
            return
        if vtt_canvas.paint_mode:
            return
        cx = vtt_canvas.canvasx(event.x)
        cy = vtt_canvas.canvasy(event.y)
        hit = None
        for si in reversed(state["scene_images"]):
            if si.x <= cx <= si.x+si.w and si.y <= cy <= si.y+si.h:
                hit = si
                break
        if hit:
            _select_image(hit)
            hit.start_drag(event)
        else:
            _deselect_all_images()

    def on_canvas_drag(event):
        if not layer_unlocked("map"):
            return
        if vtt_canvas.paint_mode:
            return
        si = state["selected_image"]
        if si and si._drag_data:
            si.do_drag(event)
            vtt_canvas.tag_lower("map_layer")
            vtt_canvas.tag_raise("tile_layer")
            vtt_canvas.tag_raise("token_layer")

    def on_canvas_release(event):
        si = state["selected_image"]
        if si:
            si._drag_data = {}

    vtt_canvas.bind("<ButtonPress-1>",   on_canvas_press,   add="+")
    vtt_canvas.bind("<B1-Motion>",       on_canvas_drag,    add="+")
    vtt_canvas.bind("<ButtonRelease-1>", on_canvas_release, add="+")

    # -----------------------------------------------------------------------
    # PAINT MODE
    # -----------------------------------------------------------------------
    paint_type_var = tk.StringVar(value="edge")

    def paint_cell(event):
        if not vtt_canvas.paint_mode: return
        if not layer_unlocked("tile"): return
        cx    = vtt_canvas.canvasx(event.x) / zoom_level[0]
        cy    = vtt_canvas.canvasy(event.y) / zoom_level[0]
        c     = state["cell_px"]
        col   = int(cx // c)
        row   = int(cy // c)
        coord = f"{col_to_letters(col)}{row+1}"
        ctype = paint_type_var.get()
        if ctype == "erase":
            vtt_canvas.mapstate.pop(coord, None)
        else:
            vtt_canvas.mapstate[coord] = ctype
        redraw_all()
        # Reapply zoom scale after redraw
        if zoom_level[0] != 1.0:
            vtt_canvas.scale("all", 0, 0, zoom_level[0], zoom_level[0])
            bb = vtt_canvas.bbox("all")
            if bb:
                vtt_canvas.config(scrollregion=bb)

    def on_right_click_canvas(event):
        if not vtt_canvas.paint_mode:
            return
        cx    = vtt_canvas.canvasx(event.x)
        cy    = vtt_canvas.canvasy(event.y)
        sc    = max(4, int(state["cell_px"] * zoom_level[0]))
        col   = int(cx // sc)
        row   = int(cy // sc)
        coord = f"{col_to_letters(col)}{row+1}"
        ctype = vtt_canvas.mapstate.get(coord,"")
        if ctype == "door_closed":
            vtt_canvas.mapstate[coord] = "door_open"
        elif ctype == "door_open":
            vtt_canvas.mapstate[coord] = "door_closed"
        redraw_all()

    vtt_canvas.bind("<ButtonPress-1>", paint_cell,          add="+")
    vtt_canvas.bind("<B1-Motion>",     paint_cell,          add="+")
    vtt_canvas.bind("<Button-3>",      on_right_click_canvas)

    # -----------------------------------------------------------------------
    # TOKEN PLACER
    # -----------------------------------------------------------------------
    def place_token(category="players"):
        folder  = PLAYER_DIR if category=="players" else ENEMY_DIR
        options = list_images(folder)
        win = tk.Toplevel(parent)
        win.title("Place Token")
        win.geometry("260x420")
        win.resizable(False, False)

        tk.Label(win, text="Name:").pack(pady=(10,0))
        ne = tk.Entry(win, width=22); ne.pack()
        ne.insert(0,"Goblin" if category=="enemies" else "Hero")

        tk.Label(win, text="Token Image:").pack(pady=(8,0))
        iv = tk.StringVar(value="— none —")
        ttk.Combobox(win, textvariable=iv,
                     values=["— none —"]+options,
                     state="readonly", width=24).pack()

        tk.Label(win, text="Color:").pack(pady=(8,0))
        cv = tk.StringVar(value="#e74c3c" if category=="enemies" else "#2980b9")
        tk.Entry(win, textvariable=cv, width=12, justify="center").pack()

        tk.Label(win, text="HP:").pack(pady=(8,0))
        he = tk.Entry(win, width=12, justify="center"); he.pack()

        tk.Label(win, text="Speed (squares):").pack(pady=(8,0))
        se = tk.Entry(win, width=8, justify="center"); se.pack()
        se.insert(0,"6")

        def confirm():
            label   = ne.get().strip() or "Token"
            imgname = iv.get()
            imgpath = None
            if imgname != "— none —":
                imgpath = os.path.join(folder, imgname)
            try:
                spd = int(se.get().strip() or "6")
            except:
                spd = 6
            hp_val = he.get().strip() or None
            c      = state["cell_px"]
            cx     = int(vtt_canvas.canvasx(vtt_canvas.winfo_width()//2))
            cy     = int(vtt_canvas.canvasy(vtt_canvas.winfo_height()//2))
            tok = Token(vtt_canvas, cx//c, cy//c, c,
                        label=label, color=cv.get(),
                        img_path=imgpath, speed=spd,
                        hp=hp_val,
                        token_type="player" if category=="players" else "enemy")
            state["tokens"].append(tok)
            win.destroy()

        tk.Button(win, text="✅ Place Token", command=confirm,
                  bg="#27ae60", fg="white").pack(pady=14)

    # -----------------------------------------------------------------------
    # INITIATIVE
    # -----------------------------------------------------------------------
    initiative_listbox = [None]
    turn_label         = [None]

    def open_initiative_popup():
        if not state["tokens"]:
            messagebox.showwarning("No Tokens","Place tokens first."); return
        win = tk.Toplevel(parent)
        win.title("⚔️ Set Initiative")
        win.geometry("300x420")
        win.resizable(False, False)
        win.grab_set()
        tk.Label(win, text="Enter initiative rolls",
                 font=("Arial",11,"bold")).pack(pady=(10,4))
        entries = {}
        sf = tk.Frame(win); sf.pack(fill="both", expand=True, padx=12, pady=8)
        for tok in state["tokens"]:
            row = tk.Frame(sf); row.pack(fill="x", pady=3)
            tk.Label(row, bg=tok.color, width=2).pack(side="left", padx=(0,6))
            tk.Label(row, text=tok.label, width=16,
                     anchor="w").pack(side="left")
            var = tk.StringVar(value=str(tok.initiative or ""))
            tk.Entry(row, textvariable=var, width=6,
                     justify="center").pack(side="right")
            entries[tok] = var

        def confirm():
            order = []
            for tok, var in entries.items():
                try: tok.initiative = int(var.get())
                except: tok.initiative = 0
                order.append(tok)
            order.sort(key=lambda t: t.initiative, reverse=True)
            state["initiative_list"]  = order
            state["current_turn_idx"] = 0
            state["combat_active"]    = True
            refresh_initiative_display()
            win.destroy()

        tk.Button(win, text="⚔️ Start Combat", command=confirm,
                  bg="#c0392b", fg="white",
                  font=("Arial",10,"bold")).pack(pady=10)

    def refresh_initiative_display():
        lb = initiative_listbox[0]
        tl = turn_label[0]
        if lb is None: return
        lb.delete(0, tk.END)
        order = state["initiative_list"]
        idx   = state["current_turn_idx"]
        for i, tok in enumerate(order):
            prefix = "▶ " if i==idx else "   "
            lb.insert(tk.END, f"{prefix}{tok.initiative:>3}  {tok.label}")
            if i==idx:
                lb.itemconfig(i, bg="#2c3e50", fg="#f1c40f")
        if tl and order:
            tl.config(text=f"Turn: {order[idx % len(order)].label}")

    def end_turn():
        if not state["combat_active"]: return
        order = state["initiative_list"]
        if not order: return
        cur = order[state["current_turn_idx"] % len(order)]
        cur.reset_movement(); cur.deselect()
        state["current_turn_idx"] = (state["current_turn_idx"]+1) % len(order)
        nxt = order[state["current_turn_idx"]]
        prev = getattr(vtt_canvas, "selected_token", None)
        if prev: prev.deselect()
        vtt_canvas.selected_token = nxt
        nxt.select()
        refresh_initiative_display()
        messagebox.showinfo("Next Turn", f"⚔️ {nxt.label}'s turn!")

    def end_combat():
        if not messagebox.askyesno("End Combat","End combat & reset movement?"):
            return
        state["combat_active"]    = False
        state["initiative_list"]  = []
        state["current_turn_idx"] = 0
        for tok in state["tokens"]:
            tok.reset_movement()
        refresh_initiative_display()
        tl = turn_label[0]
        if tl: tl.config(text="No active combat")

    # -----------------------------------------------------------------------
    # IMAGE LIST (in panel)
    # -----------------------------------------------------------------------
    image_listbox = [None]

    def update_image_list():
        lb = image_listbox[0]
        if lb is None: return
        lb.delete(0, tk.END)
        for si in state["scene_images"]:
            name = os.path.basename(si.path)
            lb.insert(tk.END, name)

    def on_image_list_select(event=None):
        lb = image_listbox[0]
        if lb is None: return
        sel = lb.curselection()
        if not sel: return
        si = state["scene_images"][sel[0]]
        _select_image(si)

    def remove_selected_image():
        si = state["selected_image"]
        if si is None:
            messagebox.showwarning("None Selected",
                "Click an image in the list first.")
            return
        if not messagebox.askyesno("Remove Image",
                f"Remove {os.path.basename(si.path)}?"):
            return
        si.delete()
        state["scene_images"].remove(si)
        state["selected_image"] = None
        update_image_list()

    # -----------------------------------------------------------------------
    # LAYER LOCK BUTTONS
    # -----------------------------------------------------------------------
    # These are built inside the LAYERS section below;
    # we define the toggle functions here.

    lock_btns = {}   # layer_name → Button widget

    def toggle_lock(layer):
        state[f"lock_{layer}"] = not state[f"lock_{layer}"]
        locked = state[f"lock_{layer}"]
        btn    = lock_btns.get(layer)
        if btn:
            btn.config(
                text="🔒" if locked else "🔓",
                bg="#c0392b" if locked else "#27ae60"
            )

    # -----------------------------------------------------------------------
    # SHEET WRAPPERS
    # -----------------------------------------------------------------------
    def push_to_sheet():
        push_tokens_to_sheet(state["tokens"])
        messagebox.showinfo("Synced","✅ Tokens pushed!")

    def pull_from_sheet():
        data = pull_tokens_from_sheet()
        if not data: return
        vtt_canvas.delete("token"); vtt_canvas.delete("sel_ring")
        state["tokens"].clear()
        c = state["cell_px"]
        for td in data:
            color = "#e74c3c" if td["type"]=="enemy" else "#2980b9"
            tok   = Token(vtt_canvas, td["col"], td["row"], c,
                          label=td["name"], color=color,
                          speed=td.get("speed",6),
                          hp=td.get("hp"),
                          token_type=td["type"])
            state["tokens"].append(tok)
        redraw_all()
        messagebox.showinfo("Synced",f"✅ Loaded {len(data)} tokens!")

    def pull_ms():
        data = pull_mapstate_from_sheet()
        if data is not None:
            vtt_canvas.mapstate = data; redraw_all()

    # -----------------------------------------------------------------------
    # TOP TOOLBAR WIDGETS
    # -----------------------------------------------------------------------
    scene_name_var = tk.StringVar(value=state["scene_name"])

    tk.Label(toolbar, text="Scene:", font=("Arial",9,"bold")).pack(side="left")
    tk.Label(toolbar, textvariable=scene_name_var,
             fg="#2980b9", font=("Arial",9,"bold")).pack(side="left", padx=4)

    ttk.Separator(toolbar,orient="vertical").pack(side="left",fill="y",padx=4)

    tk.Label(toolbar, text="Grid ft:", font=("Arial",9,"bold")).pack(side="left")
    cell_ft_var = tk.IntVar(value=5)

    def update_cell_size(*_):
        try:
            ft = cell_ft_var.get()
            state["cell_px"] = max(6, ft * 5)
            redraw_all()
        except Exception:
            pass

    tk.Spinbox(toolbar, from_=3, to=10, increment=1,
               textvariable=cell_ft_var, width=4,
               command=update_cell_size).pack(side="left", padx=2)
    cell_ft_var.trace_add("write", update_cell_size)

    ttk.Separator(toolbar,orient="vertical").pack(side="left",fill="y",padx=4)
    tk.Label(toolbar, text="Zoom:", font=("Arial",9,"bold")).pack(side="left")
    tk.Button(toolbar, text="＋", command=lambda: zoom(1.25),
              font=("Arial",10,"bold"), width=2).pack(side="left", padx=1)
    tk.Button(toolbar, text="－", command=lambda: zoom(0.8),
              font=("Arial",10,"bold"), width=2).pack(side="left", padx=1)
    tk.Button(toolbar, text="⟳", command=reset_zoom,
              font=("Arial",9)).pack(side="left", padx=2)

    ttk.Separator(toolbar,orient="vertical").pack(side="left",fill="y",padx=4)
    tk.Button(toolbar, text="🧙 Player",
              command=lambda: place_token("players"),
              bg="#2980b9", fg="white",
              font=("Arial",8)).pack(side="left", padx=2)
    tk.Button(toolbar, text="👹 Enemy",
              command=lambda: place_token("enemies"),
              bg="#c0392b", fg="white",
              font=("Arial",8)).pack(side="left", padx=2)

    ttk.Separator(toolbar,orient="vertical").pack(side="left",fill="y",padx=4)
    grid_toggle_var = tk.BooleanVar(value=True)

    def toggle_grid():
        state["show_grid"] = grid_toggle_var.get(); redraw_all()

    tk.Checkbutton(toolbar, text="Grid",
                   variable=grid_toggle_var,
                   command=toggle_grid).pack(side="left", padx=4)

    # -----------------------------------------------------------------------
    # SIDE PANEL — LAYERS
    # -----------------------------------------------------------------------
    lay_sec = make_section("🔒 LAYERS")

    for layer, label in [("map","🗺️ Map Layer"),
                          ("tile","🎨 Tile Layer"),
                          ("token","🧙 Token Layer")]:
        row = tk.Frame(lay_sec, bg="#1e1e2e")
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, bg="#1e1e2e", fg="white",
                 font=("Arial",8), width=14,
                 anchor="w").pack(side="left", padx=6)
        btn = tk.Button(row, text="🔓", width=3,
                        command=lambda l=layer: toggle_lock(l),
                        bg="#27ae60", fg="white",
                        font=("Arial",8), relief="flat")
        btn.pack(side="right", padx=4)
        lock_btns[layer] = btn

    # -----------------------------------------------------------------------
    # SIDE PANEL — SCENE / IMAGES
    # -----------------------------------------------------------------------
    scene_sec = make_section("🗺️ SCENE")

    pbtn(scene_sec, "✨ New Scene",   new_scene,   bg="#8e44ad")
    pbtn(scene_sec, "➕ Add Image",  add_image,   bg="#2980b9")
    psep(scene_sec)

    tk.Label(scene_sec, text="Images on canvas:",
             bg="#1e1e2e", fg="#aaaacc",
             font=("Arial",8)).pack(anchor="w", padx=6)

    lb_img = tk.Listbox(scene_sec, height=5, width=22,
                         bg="#16213e", fg="white",
                         font=("Arial",8), selectbackground="#2c3e50",
                         relief="flat")
    lb_img.pack(fill="x", padx=4, pady=2)
    lb_img.bind("<<ListboxSelect>>", on_image_list_select)
    image_listbox[0] = lb_img

    pbtn(scene_sec, "🗑️ Remove Selected Image",
         remove_selected_image, bg="#c0392b")

    psep(scene_sec)
    pbtn(scene_sec, "💾 Save Scene",
         lambda: save_scene(state, vtt_canvas))
    pbtn(scene_sec, "📂 Load Scene",
         lambda: load_scene(state, vtt_canvas, redraw_all,
                            scene_name_var, update_image_list))

    # -----------------------------------------------------------------------
    # SIDE PANEL — TOKENS
    # -----------------------------------------------------------------------
    tok_sec = make_section("🧙 TOKENS")

    pbtn(tok_sec,"🧙 Add Player Token",
         lambda: place_token("players"), bg="#2980b9")
    pbtn(tok_sec,"👹 Add Enemy Token",
         lambda: place_token("enemies"), bg="#c0392b")
    psep(tok_sec)

    def clear_all_tokens():
        if messagebox.askyesno("Clear","Remove all tokens?"):
            vtt_canvas.delete("token_layer")
            vtt_canvas.delete("sel_ring")
            state["tokens"].clear()
            state["initiative_list"].clear()
            state["combat_active"] = False
            refresh_initiative_display()

    pbtn(tok_sec,"🗑️ Clear All Tokens", clear_all_tokens)
    psep(tok_sec)
    pbtn(tok_sec,"⬆️ Push Tokens → Sheet", push_to_sheet,  bg="#8e44ad")
    pbtn(tok_sec,"⬇️ Pull Tokens ← Sheet", pull_from_sheet, bg="#8e44ad")
    psep(tok_sec)

    polling_lbl = tk.Label(tok_sec, text="⏸ Auto Sync: OFF",
                           bg="#1e1e2e", fg="#7f8c8d", font=("Arial",8))
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

    pbtn(tok_sec,"⏯ Toggle Auto Sync", toggle_polling)
    psep(tok_sec)
    pbtn(tok_sec,"💾 Save Token State",
         lambda: save_vtt_tokens(state["tokens"]))
    pbtn(tok_sec,"📂 Load Token State",
         lambda: load_vtt_tokens(state, vtt_canvas, redraw_all))

    # -----------------------------------------------------------------------
    # SIDE PANEL — COMBAT
    # -----------------------------------------------------------------------
    combat_sec = make_section("⚔️ COMBAT")

    tl = tk.Label(combat_sec, text="No active combat",
                  bg="#1e1e2e", fg="#aaaacc",
                  font=("Arial",8,"bold"))
    tl.pack(anchor="w", padx=6, pady=(4,2))
    turn_label[0] = tl

    pbtn(combat_sec,"🎲 Set Initiative",
         open_initiative_popup, bg="#8e44ad")
    psep(combat_sec)

    lb_init = tk.Listbox(combat_sec, height=8, width=22,
                          bg="#16213e", fg="white",
                          font=("Courier",8),
                          selectbackground="#2c3e50",
                          relief="flat")
    lb_init.pack(fill="x", padx=4, pady=2)
    initiative_listbox[0] = lb_init

    psep(combat_sec)
    pbtn(combat_sec,"▶ End Turn",   end_turn,   bg="#27ae60")
    pbtn(combat_sec,"🛑 End Combat", end_combat, bg="#c0392b")

    # -----------------------------------------------------------------------
    # SIDE PANEL — MAP / TILE PAINTING
    # -----------------------------------------------------------------------
    map_sec = make_section("🎨 TILE PAINT")

    paint_mode_lbl = tk.Label(map_sec, text="🖌️ Paint Mode: OFF",
                              bg="#1e1e2e", fg="#7f8c8d", font=("Arial",8))
    paint_mode_lbl.pack(anchor="w", padx=6, pady=2)

    def toggle_paint_mode():
        if not layer_unlocked("tile"):
            messagebox.showwarning("Layer Locked",
                "Unlock the Tile Layer first.")
            return
        vtt_canvas.paint_mode = not vtt_canvas.paint_mode
        if vtt_canvas.paint_mode:
            paint_mode_lbl.config(text="🖌️ Paint Mode: ON", fg="#e67e22")
            vtt_canvas.config(cursor="pencil")
        else:
            paint_mode_lbl.config(text="🖌️ Paint Mode: OFF", fg="#7f8c8d")
            vtt_canvas.config(cursor="crosshair")

    pbtn(map_sec,"🖌️ Toggle Paint Mode", toggle_paint_mode, bg="#e67e22")

    tk.Label(map_sec, text="Paint Type:", bg="#1e1e2e", fg="#aaaacc",
             font=("Arial",8)).pack(anchor="w", padx=6, pady=(6,0))

    paint_colors = {
        "edge":"#5d7a8a","wall":"#888899","floor":"#aabbaa",
        "difficult":"#e67e22","door_closed":"#8B4513",
        "door_open":"#DEB887","water":"#2e86c1",
        "trap":"#424242","e_dam":"#e74c3c",
        "janus_a":"#a9cce3","janus_b":"#7d6608","erase":"#c0392b",
    }
    for ctype in ["edge","wall","floor","difficult",
                  "door_closed","door_open","water",
                  "trap","e_dam","janus_a","janus_b","erase"]:
        tk.Radiobutton(
            map_sec,
            text=f"  {ctype.replace('_',' ').capitalize()}",
            variable=paint_type_var, value=ctype,
            bg="#1e1e2e", fg=paint_colors[ctype],
            selectcolor="#2c3e50", activebackground="#1e1e2e",
            font=("Arial",8)
        ).pack(anchor="w", padx=10)

    psep(map_sec)
    pbtn(map_sec,"⬆️ Push MapState → Sheet",
         lambda: push_mapstate_to_sheet(
             vtt_canvas.mapstate,
             state.get("canvas_cols",52),
             state.get("canvas_rows",100)),
         bg="#16a085")
    pbtn(map_sec,"⬇️ Pull MapState ← Sheet", pull_ms, bg="#16a085")
    psep(map_sec)
    pbtn(map_sec,"⬆️ Push Janus → Sheet",
         lambda: push_janus_to_sheet(
             build_janus_pairs(vtt_canvas.mapstate)))

    # -----------------------------------------------------------------------
    # WASD TOKEN MOVEMENT
    # -----------------------------------------------------------------------
    def move_selected(event):
        if vtt_canvas.paint_mode: return
        if not layer_unlocked("token"): return
        tok = getattr(vtt_canvas, "selected_token", None)
        if not tok: return
        key = event.keysym.lower()
        dc, dr = 0, 0
        if key=="w": dr=-1
        if key=="s": dr= 1
        if key=="a": dc=-1
        if key=="d": dc= 1
        nc = max(0, tok.grid_col+dc)
        nr = max(0, tok.grid_row+dr)
        coord = f"{col_to_letters(nc)}{nr+1}"
        ctype = vtt_canvas.mapstate.get(coord,"")
        if CELL_TYPES.get(ctype,{}).get("collision",False):
            tok.wiggle(); return
        if not tok.can_move(dc, dr):
            messagebox.showwarning("Out of Movement",
                f"{tok.label} has no moves left!"); return
        tok.spend_move(dc, dr)
        tok.grid_col = nc
        tok.grid_row = nr
        tok.move_to(tok.cell_px)
        tok.select()
        tok._check_janus(coord)

    vtt_canvas.bind("<w>", move_selected)
    vtt_canvas.bind("<s>", move_selected)
    vtt_canvas.bind("<a>", move_selected)
    vtt_canvas.bind("<d>", move_selected)

    # -----------------------------------------------------------------------
    # PAN
    # -----------------------------------------------------------------------
    def pan(event):
        if event.keysym=="Left":  vtt_canvas.xview_scroll(-1,"units")
        if event.keysym=="Right": vtt_canvas.xview_scroll( 1,"units")
        if event.keysym=="Up":    vtt_canvas.yview_scroll(-1,"units")
        if event.keysym=="Down":  vtt_canvas.yview_scroll( 1,"units")

    vtt_canvas.bind("<Left>",  pan)
    vtt_canvas.bind("<Right>", pan)
    vtt_canvas.bind("<Up>",    pan)
    vtt_canvas.bind("<Down>",  pan)
    vtt_canvas.bind("<Button-1>", lambda e: vtt_canvas.focus_set(), add="+")
    vtt_canvas.bind("<ButtonPress-2>",
                    lambda e: vtt_canvas.scan_mark(e.x, e.y))
    vtt_canvas.bind("<B2-Motion>",
                    lambda e: vtt_canvas.scan_dragto(e.x, e.y, gain=1))

    # -----------------------------------------------------------------------
    # INITIAL DRAW
    # -----------------------------------------------------------------------
    parent.after(100, redraw_all)
