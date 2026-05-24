# ---------------------------------------------------------------------------
# vtt.py — Virtual Tabletop  |  Janus D&D Tracker  |  Phase 2
# ---------------------------------------------------------------------------
# REQUIRES:  pip install Pillow gspread google-auth gspread-formatting
#
# LAYERS (bottom → top):
#   MAP LAYER   — background images, freely placed/resized (lockable)
#   TILE LAYER  — grid, labels, painted mapstate cells    (lockable)
#   TOKEN LAYER — tokens, rings, move counters            (lockable)
#
# ZOOM: PIL-resize approach — redraw_all scales everything via cell_px*zoom.
#       Grid, tiles, images, tokens all recalculate at the same scaled_cell.
#       This keeps all layers perfectly locked together at any zoom level.
# ---------------------------------------------------------------------------

import os
import json
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

for _d in (MAPS_DIR, PLAYER_DIR, ENEMY_DIR):
    os.makedirs(_d, exist_ok=True)

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
    """0→A, 25→Z, 26→AA …"""
    result = ""
    n += 1
    while n > 0:
        n, r = divmod(n - 1, 26)
        result = chr(65 + r) + result
    return result


def coord_to_col_row(coord):
    """'AA12' → (col_idx, row_idx) both 0-based."""
    cs = "".join(c for c in coord if c.isalpha())
    rs = "".join(c for c in coord if c.isdigit())
    ci = 0
    for c in cs.upper():
        ci = ci * 26 + (ord(c) - ord('A') + 1)
    return ci - 1, int(rs) - 1

# ---------------------------------------------------------------------------
# JANUS HELPERS
# ---------------------------------------------------------------------------

def build_janus_pairs(mapstate):
    a = [k for k, v in mapstate.items() if v == "janus_a"]
    b = [k for k, v in mapstate.items() if v == "janus_b"]
    return list(zip(a, b))


def find_janus_destination(coord, mapstate):
    ctype = mapstate.get(coord, "")
    for ca, cb in build_janus_pairs(mapstate):
        if ctype == "janus_a" and ca == coord:
            return cb
        if ctype == "janus_b" and cb == coord:
            return ca
    return None

# ---------------------------------------------------------------------------
# SCENE IMAGE  — one placed image on the map layer
# ---------------------------------------------------------------------------

class SceneImage:
    """A freely positioned, resizable image on the VTT canvas."""

    HANDLE_SIZE = 8

    def __init__(self, canvas, path, x=0, y=0,
                 base_w=None, base_h=None, img_id=None):
        self.canvas  = canvas
        self.path    = path
        self.img_id  = img_id or str(uuid.uuid4())[:8]
        self._raw    = None   # PIL image at original file size
        self._photo  = None   # current ImageTk reference

        # Load raw image
        if PIL_OK:
            try:
                self._raw = Image.open(path)
            except Exception:
                self._raw = None

        # Base (unzoomed) size — defaults to image natural size capped at 2000px
        if self._raw:
            MAX = 2000
            ratio = min(MAX / self._raw.width, MAX / self._raw.height, 1.0)
            self.base_w = base_w or int(self._raw.width  * ratio)
            self.base_h = base_h or int(self._raw.height * ratio)
        else:
            self.base_w = base_w or 400
            self.base_h = base_h or 300

        # Canvas position (unzoomed world coords)
        self.x = x
        self.y = y

        self.selected   = False
        self._drag_data = {}
        self.canvas_item  = None
        self.handle_items = {}   # name → canvas id

    # ---------------------------------------------------------------- draw

    def draw(self, zoom):
        """Draw/redraw the image at the given zoom level."""
        self.canvas.delete(f"si_{self.img_id}")
        self.handle_items.clear()

        w = max(1, int(self.base_w * zoom))
        h = max(1, int(self.base_h * zoom))
        sx = int(self.x * zoom)
        sy = int(self.y * zoom)

        if PIL_OK and self._raw:
            scaled = self._raw.resize((w, h), Image.LANCZOS)
            self._photo = ImageTk.PhotoImage(scaled)
            self.canvas_item = self.canvas.create_image(
                sx, sy, anchor="nw", image=self._photo,
                tags=("map_layer", f"si_{self.img_id}")
            )
        else:
            self.canvas_item = self.canvas.create_rectangle(
                sx, sy, sx + w, sy + h,
                fill="#333355", outline="#666688",
                tags=("map_layer", f"si_{self.img_id}")
            )

        if self.selected:
            self._draw_handles(zoom)

    def _draw_handles(self, zoom):
        hs = self.HANDLE_SIZE
        w  = int(self.base_w * zoom)
        h  = int(self.base_h * zoom)
        sx = int(self.x * zoom)
        sy = int(self.y * zoom)
        mx, my = sx + w // 2, sy + h // 2

        positions = {
            "tl": (sx,      sy),
            "tm": (mx,      sy),
            "tr": (sx + w,  sy),
            "ml": (sx,      my),
            "mr": (sx + w,  my),
            "bl": (sx,      sy + h),
            "bm": (mx,      sy + h),
            "br": (sx + w,  sy + h),
        }

        for name, (hx, hy) in positions.items():
            hid = self.canvas.create_rectangle(
                hx - hs/2, hy - hs/2, hx + hs/2, hy + hs/2,
                fill="#f1c40f", outline="#e67e22",
                tags=("map_layer", f"si_{self.img_id}",
                      f"handle_{self.img_id}_{name}")
            )
            self.handle_items[name] = hid
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
                lambda e: self._end_drag()
            )

    def select(self):
        self.selected = True

    def deselect(self):
        self.selected = False

    def delete(self):
        self.canvas.delete(f"si_{self.img_id}")

    # ---------------------------------------------------------------- drag

    def start_drag(self, canvas_x, canvas_y, zoom):
        self._drag_data = {
            "cx": canvas_x, "cy": canvas_y,
            "ox": self.x,   "oy": self.y,
            "zoom": zoom,
        }

    def do_drag(self, canvas_x, canvas_y):
        d    = self._drag_data
        zoom = d.get("zoom", 1.0)
        # Convert canvas pixel delta to world coord delta
        dx = (canvas_x - d["cx"]) / zoom
        dy = (canvas_y - d["cy"]) / zoom
        self.x = d["ox"] + dx
        self.y = d["oy"] + dy

    # -------------------------------------------------------------- resize

    def _start_resize(self, event, handle):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        self._drag_data = {
            "handle": handle,
            "cx": cx,   "cy": cy,
            "ox": self.x,   "oy": self.y,
            "ow": self.base_w, "oh": self.base_h,
            "zoom": getattr(self.canvas, "_zoom", 1.0),
        }

    def _do_resize(self, event, handle):
        d    = self._drag_data
        zoom = d.get("zoom", 1.0)
        cx   = self.canvas.canvasx(event.x)
        cy   = self.canvas.canvasy(event.y)
        dx   = (cx - d["cx"]) / zoom
        dy   = (cy - d["cy"]) / zoom

        if "l" in handle:
            self.x      = d["ox"] + dx
            self.base_w = max(40, d["ow"] - dx)
        if "r" in handle:
            self.base_w = max(40, d["ow"] + dx)
        if "t" in handle:
            self.y      = d["oy"] + dy
            self.base_h = max(40, d["oh"] - dy)
        if "b" in handle:
            self.base_h = max(40, d["oh"] + dy)

        # Trigger a lightweight redraw
        if hasattr(self.canvas, "_redraw_fn"):
            self.canvas._redraw_fn()

    def _end_drag(self):
        self._drag_data = {}

    # ------------------------------------------------------------ hit test

    def hit_test(self, canvas_x, canvas_y, zoom):
        """Return True if canvas point is inside this image."""
        sx = self.x * zoom
        sy = self.y * zoom
        return sx <= canvas_x <= sx + self.base_w * zoom \
           and sy <= canvas_y <= sy + self.base_h * zoom

    # ------------------------------------------------------------ serialise

    def to_dict(self):
        return {
            "id":     self.img_id,
            "path":   self.path,
            "x":      self.x,
            "y":      self.y,
            "base_w": self.base_w,
            "base_h": self.base_h,
        }

    @classmethod
    def from_dict(cls, canvas, d):
        return cls(
            canvas,
            path   = d["path"],
            x      = d.get("x", 0),
            y      = d.get("y", 0),
            base_w = d.get("base_w"),
            base_h = d.get("base_h"),
            img_id = d.get("id"),
        )

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
        self.vision_range  = 0    # how far you see in light (0 = unlimited)
        self.light_radius  = 0    # bright light emitted in squares
        self.dim_radius    = 0    # dim light beyond bright
        self.darkvision    = 0    # sees darkness as dim within this range


        x, y, half = col * cell_px, row * cell_px, cell_px // 2

        if img_path and PIL_OK:
            img = Image.open(img_path).resize((cell_px, cell_px), Image.LANCZOS)
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

        self._drag_x = self._drag_y = 0
        self._drag_start_col = col
        self._drag_start_row = row

        for item in (self.oval, self.text):
            canvas.tag_bind(item, "<ButtonPress-1>",   self._on_press)
            canvas.tag_bind(item, "<B1-Motion>",       self._on_drag)
            canvas.tag_bind(item, "<ButtonRelease-1>", self._on_release)
            canvas.tag_bind(item, "<Button-3>",        self._on_right_click)

    # ---------------------------------------------------------------- label

    def _build_label(self):
        parts = [self.label]
        if self.hp is not None:
            parts.append(f"HP:{self.hp}")
        return "\n".join(parts)

    def _update_text(self):
        self.canvas.itemconfig(self.text, text=self._build_label())

    # ----------------------------------------------------------- move counter

    def show_move_counter(self):
        self.canvas.itemconfig(
            self.move_lbl,
            text=f"▶{self.moves_left}/{self.speed}",
            state="normal")

    def hide_move_counter(self):
        self.canvas.itemconfig(self.move_lbl, state="hidden")

    # ---------------------------------------------------------------- select

    def select(self):
        self.canvas.delete(f"sel_ring_{id(self)}")
        self.canvas.delete(f"vis_rings_{id(self)}")
        c = self.cell_px
        x, y = self.grid_col * c, self.grid_row * c

        # Selection ring
        self.canvas.create_rectangle(
            x, y, x + c, y + c,
            outline="#f1c40f", width=3,
            tags=(f"sel_ring_{id(self)}", "sel_ring", "token_layer"))

        # Vision/light outline circles (DM reference)
        cx = x + c // 2
        cy = y + c // 2

        ring_specs = [
            (self.light_radius,  "#f1c40f", "●  Light"),
            (self.dim_radius,    "#e67e22", "●  Dim"),
            (self.darkvision,    "#2980b9", "●  Darkvision"),
            (self.vision_range,  "#27ae60", "●  Vision"),
        ]

        for radius, color, _ in ring_specs:
            if radius > 0:
                r_px = radius * c
                self.canvas.create_oval(
                    cx - r_px, cy - r_px,
                    cx + r_px, cy + r_px,
                    outline=color, width=2,
                    dash=(4, 4),
                    tags=(f"vis_rings_{id(self)}", "token_layer"))

        self.canvas.tag_raise("token_layer")
        self.show_move_counter()

    def deselect(self):
        self.canvas.delete(f"sel_ring_{id(self)}")
        self.canvas.delete(f"vis_rings_{id(self)}")
        self.hide_move_counter()

    def deselect(self):
        self.canvas.delete(f"sel_ring_{id(self)}")
        self.hide_move_counter()

    # ---------------------------------------------------------------- move_to

    def move_to(self, cell_px):
        self.cell_px = cell_px
        x, y, half = self.grid_col * cell_px, self.grid_row * cell_px, cell_px // 2

        if self._img_path and PIL_OK:
            img = Image.open(self._img_path).resize(
                (cell_px, cell_px), Image.LANCZOS)
            self._photo = ImageTk.PhotoImage(img)
            self.canvas.coords(self.oval, x, y)
            self.canvas.itemconfig(self.oval, image=self._photo)
        else:
            self.canvas.coords(self.oval, x, y, x + cell_px, y + cell_px)

        self.canvas.coords(self.text,     x + half, y + cell_px + 8)
        self.canvas.coords(self.move_lbl, x + half, y - 8)
        self.canvas.delete(f"sel_ring_{id(self)}")

    # ---------------------------------------------------------------- movement

    def _move_cost(self, dc, dr):
        return 2 if dc != 0 and dr != 0 else 1

    def can_move(self, dc, dr):
        return self.moves_left >= self._move_cost(dc, dr)

    def spend_move(self, dc, dr):
        self.moves_left = max(0, self.moves_left - self._move_cost(dc, dr))

    def reset_movement(self):
        self.moves_left = self.speed

    # ---------------------------------------------------------------- path check

    def _path_clear(self, dest_col, dest_row, mapstate):
        x0, y0, x1, y1 = self.grid_col, self.grid_row, dest_col, dest_row
        dx, dy = abs(x1-x0), abs(y1-y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        cx, cy = x0, y0
        while True:
            if not (cx == x0 and cy == y0):
                coord = f"{col_to_letters(cx)}{cy+1}"
                if CELL_TYPES.get(mapstate.get(coord,""),{}).get("collision",False):
                    return False
            if cx == x1 and cy == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy; cx += sx
            if e2 < dx:
                err += dx; cy += sy
        return True

    # ---------------------------------------------------------------- wiggle

    def wiggle(self):
        c  = self.cell_px
        ox, oy = self.grid_col * c, self.grid_row * c
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
        do_step(0)

    # ---------------------------------------------------------------- snap back

    def _snap_back(self):
        c = self.cell_px
        ox, oy = self._drag_start_col * c, self._drag_start_row * c
        if self._img_path and PIL_OK:
            self.canvas.coords(self.oval, ox, oy)
        else:
            self.canvas.coords(self.oval, ox, oy, ox+c, oy+c)
        self.canvas.coords(self.text,     ox+c//2, oy+c+8)
        self.canvas.coords(self.move_lbl, ox+c//2, oy-8)

    # ---------------------------------------------------------------- janus

    def _check_janus(self, coord):
        dest = find_janus_destination(coord, self.canvas.mapstate)
        if dest is None:
            return
        dc, dr = coord_to_col_row(dest)
        c = self.cell_px
        self.grid_col, self.grid_row = dc, dr
        if self._img_path and PIL_OK:
            self.canvas.coords(self.oval, dc*c, dr*c)
        else:
            self.canvas.coords(self.oval, dc*c, dr*c, dc*c+c, dr*c+c)
        self.canvas.coords(self.text,     dc*c+c//2, dr*c+c+8)
        self.canvas.coords(self.move_lbl, dc*c+c//2, dr*c-8)
        self.select()
        if hasattr(self.canvas, "_redraw_fn"):
            self.canvas._redraw_fn()

    # ---------------------------------------------------------------- drag handlers

    def _on_press(self, event):
        if not self.canvas._layer_unlocked("token"): return
        if getattr(self.canvas, "paint_mode", False): return
        self._drag_x, self._drag_y = event.x, event.y
        self._drag_start_col, self._drag_start_row = self.grid_col, self.grid_row
        self.canvas.tag_raise(self.oval)
        self.canvas.tag_raise(self.text)
        prev = getattr(self.canvas, "selected_token", None)
        if prev and prev is not self:
            prev.deselect()
        self.canvas.selected_token = self
        self.select()

    def _on_drag(self, event):
        if not self.canvas._layer_unlocked("token"): return
        if getattr(self.canvas, "paint_mode", False): return
        dx, dy = event.x - self._drag_x, event.y - self._drag_y
        self.canvas.move(self.oval,     dx, dy)
        self.canvas.move(self.text,     dx, dy)
        self.canvas.move(self.move_lbl, dx, dy)
        self._drag_x, self._drag_y = event.x, event.y

    def _on_release(self, event):
        if not self.canvas._layer_unlocked("token"): return
        if getattr(self.canvas, "paint_mode", False): return
        c = self.cell_px
        coords = self.canvas.coords(self.oval)
        raw_x, raw_y = coords[0], coords[1]
        snapped_x = round(raw_x / c) * c
        snapped_y = round(raw_y / c) * c
        new_col, new_row = int(snapped_x / c), int(snapped_y / c)
        dest_coord = f"{col_to_letters(new_col)}{new_row+1}"
        cell_type  = self.canvas.mapstate.get(dest_coord, "")

        if CELL_TYPES.get(cell_type,{}).get("collision",False):
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

        dx, dy = snapped_x - raw_x, snapped_y - raw_y
        self.canvas.move(self.oval,     dx, dy)
        self.canvas.move(self.text,     dx, dy)
        self.canvas.move(self.move_lbl, dx, dy)
        self.grid_col, self.grid_row = new_col, new_row
        self.moves_left = max(0, self.moves_left - cost)
        self.select()
        self._check_janus(dest_coord)
        if hasattr(self.canvas, "_redraw_fn"):
            self.canvas._redraw_fn()

    def _on_right_click(self, event):
        if getattr(self.canvas, "paint_mode", False): return
        menu = tk.Menu(self.canvas, tearoff=0)
        menu.add_command(label=f"⚙️  Properties", command=self.open_properties)
        menu.add_separator()
        menu.add_command(label="🗑️  Remove", command=self._remove)
        menu.tk_popup(event.x_root, event.y_root)

    def _rename(self):
        new = simpledialog.askstring("Rename","New name:",initialvalue=self.label)
        if new:
            self.label = new; self._update_text()

    def _set_hp(self):
        val = simpledialog.askstring("Set HP","HP (e.g. 30/45):",
                                     initialvalue=self.hp or "")
        if val is not None:
            self.hp = val; self._update_text()

    def _set_speed(self):
        val = simpledialog.askinteger("Set Speed","Speed in squares:",
                                      initialvalue=self.speed,
                                      minvalue=0, maxvalue=30)
        if val is not None:
            self.speed = val; self.moves_left = val
            self.show_move_counter()
    def open_properties(self):
        win = tk.Toplevel(self.canvas)
        win.title(f"Token Properties — {self.label}")
        win.geometry("300x380")
        win.resizable(False, False)
        win.grab_set()

        fields = {}

        def add_field(parent, label, initial, row):
            tk.Label(parent, text=label, anchor="w",
                     width=16).grid(row=row, column=0,
                                    padx=8, pady=4, sticky="w")
            var = tk.StringVar(value=str(initial))
            tk.Entry(parent, textvariable=var,
                     width=10, justify="center").grid(
                row=row, column=1, padx=8, pady=4)
            return var

        # Identity section
        id_frame = ttk.LabelFrame(win, text=" Identity ")
        id_frame.pack(fill="x", padx=10, pady=(10,4))
        fields["name"]  = add_field(id_frame, "Name:",  self.label,  0)
        fields["hp"]    = add_field(id_frame, "HP:",    self.hp or "",  1)
        fields["speed"] = add_field(id_frame, "Speed (sq):", self.speed, 2)

        # Vision section
        vis_frame = ttk.LabelFrame(win, text=" Vision & Light ")
        vis_frame.pack(fill="x", padx=10, pady=4)
        fields["vision_range"] = add_field(
            vis_frame, "Vision Range:", self.vision_range, 0)
        fields["light_radius"] = add_field(
            vis_frame, "Light Radius:", self.light_radius, 1)
        fields["dim_radius"]   = add_field(
            vis_frame, "Dim Radius:",   self.dim_radius,   2)
        fields["darkvision"]   = add_field(
            vis_frame, "Darkvision:",   self.darkvision,   3)

        tk.Label(vis_frame,
                 text="All values in squares  (0 = none / unlimited)",
                 fg="gray", font=("Arial",7)).grid(
            row=4, column=0, columnspan=2, pady=(0,4))

        def apply():
            try:
                self.label        = fields["name"].get().strip() or self.label
                self.hp           = fields["hp"].get().strip() or None
                self.speed        = int(fields["speed"].get() or 6)
                self.vision_range = int(fields["vision_range"].get() or 0)
                self.light_radius = int(fields["light_radius"].get() or 0)
                self.dim_radius   = int(fields["dim_radius"].get() or 0)
                self.darkvision   = int(fields["darkvision"].get() or 0)
                self._update_text()
                # Trigger redraw so DM outlines update immediately
                if hasattr(self.canvas, "_redraw_fn"):
                    self.canvas._redraw_fn()
            except ValueError:
                messagebox.showwarning("Invalid Value",
                    "Please enter whole numbers for numeric fields.")
                return
            win.destroy()

        btn_row = tk.Frame(win)
        btn_row.pack(pady=10)
        tk.Button(btn_row, text="✅ Apply",
                  command=apply,
                  bg="#27ae60", fg="white",
                  font=("Arial",10,"bold"),
                  width=10).pack(side="left", padx=8)
        tk.Button(btn_row, text="Cancel",
                  command=win.destroy,
                  font=("Arial",10),
                  width=10).pack(side="left", padx=8)
    def _remove(self):
        self.canvas.delete(f"sel_ring_{id(self)}")
        self.canvas.delete(self.oval)
        self.canvas.delete(self.text)
        self.canvas.delete(self.move_lbl)
        if getattr(self.canvas,"selected_token",None) is self:
            self.canvas.selected_token = None

# ---------------------------------------------------------------------------
# GOOGLE SHEETS
# ---------------------------------------------------------------------------

def get_sheets_client():
    import gspread
    from google.oauth2.service_account import Credentials
    creds = Credentials.from_service_account_file(
        os.path.join(BASE_DIR,"credentials.json"),
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)


def push_tokens_to_sheet(tokens):
    try:
        sheet = get_sheets_client().open("DnD_VTT").sheet1
        sheet.batch_clear(["A2:F100"])
        rows = [[t.label, col_to_letters(t.grid_col), t.grid_row+1,
                 t.token_type, t.hp or "", t.speed] for t in tokens]
        if rows:
            sheet.update(f"A2:F{1+len(rows)}", rows)
    except Exception as e:
        messagebox.showerror("Sheet Error", str(e))


def pull_tokens_from_sheet():
    try:
        rows = get_sheets_client().open("DnD_VTT").sheet1.get_all_records()
        result = []
        for row in rows:
            try:
                cs = str(row.get("col","A")).strip().upper()
                ci = 0
                for c in cs:
                    ci = ci*26 + (ord(c)-ord('A')+1)
                result.append({
                    "name":  str(row.get("name","Token")),
                    "col":   ci-1,
                    "row":   int(row.get("row",1))-1,
                    "type":  str(row.get("type","enemy")),
                    "hp":    str(row.get("hp","")) or None,
                    "speed": int(row.get("speed",6) or 6),
                })
            except Exception:
                continue
        return result
    except Exception as e:
        messagebox.showerror("Sheet Error",str(e)); return []


def start_sheet_polling(state, tokens_ref, canvas, redraw_fn,
                        interval_ms=60000):
    last = [None]

    def poll():
        try:
            data = pull_tokens_from_sheet()
            sig  = tuple((d["name"],d["col"],d["row"],d["hp"]) for d in data)
            if sig != last[0]:
                last[0] = sig
                canvas.delete("token"); canvas.delete("sel_ring")
                tokens_ref.clear()
                c = state["cell_px"]
                for td in data:
                    color = "#e74c3c" if td["type"]=="enemy" else "#2980b9"
                    tok = Token(canvas,td["col"],td["row"],c,
                                label=td["name"],color=color,
                                speed=td.get("speed",6),
                                token_type=td["type"])
                    if td["hp"]:
                        tok.hp=td["hp"]; tok._update_text()
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
        ss = get_sheets_client().open("DnD_VTT")
        try:
            sheet = ss.worksheet("MapState")
        except Exception:
            sheet = ss.add_worksheet("MapState",rows=300,cols=300)
        sheet.clear()
        tc, tr = grid_cols+2, grid_rows+2
        grid = [[""] * tc for _ in range(tr)]
        for coord, ctype in cells.items():
            cs = "".join(c for c in coord if c.isalpha())
            rn = "".join(c for c in coord if c.isdigit())
            if not cs or not rn: continue
            ci = 0
            for c in cs.upper():
                ci = ci*26+(ord(c)-ord('A')+1)
            ri = int(rn)-1
            if 0<=ri<tr and 0<=ci-1<tc:
                grid[ri][ci-1] = ctype
        sheet.update("A1", grid)
        messagebox.showinfo("Synced","✅ MapState pushed!")
    except Exception as e:
        messagebox.showerror("Sheet Error",str(e))


def pull_mapstate_from_sheet():
    try:
        sheet = get_sheets_client().open("DnD_VTT").worksheet("MapState")
        cells = {}
        for ri,row in enumerate(sheet.get_all_values()):
            for ci,val in enumerate(row):
                if val.strip():
                    cells[f"{col_to_letters(ci)}{ri+1}"] = val.strip().lower()
        return cells
    except Exception as e:
        messagebox.showerror("Sheet Error",str(e)); return None


def push_janus_to_sheet(pairs):
    try:
        ss = get_sheets_client().open("DnD_VTT")
        try:
            sheet = ss.worksheet("JanusLinks")
        except Exception:
            sheet = ss.add_worksheet("JanusLinks",rows=100,cols=2)
        sheet.clear()
        sheet.update("A1",[["janus_a","janus_b"]]+[[a,b] for a,b in pairs])
        messagebox.showinfo("Synced","✅ Janus pairs pushed!")
    except Exception as e:
        messagebox.showerror("Sheet Error",str(e))

# ---------------------------------------------------------------------------
# SCENE SAVE / LOAD
# ---------------------------------------------------------------------------

def save_scene(state, vtt_canvas):
    file = tk.filedialog.asksaveasfilename(
        title="Save Scene", defaultextension=".json",
        initialdir=BASE_DIR, filetypes=[("JSON","*.json")])
    if not file: return
    try:
        with open(file,"w") as f:
            json.dump({
                "scene_name":  state.get("scene_name","Scene"),
                "canvas_cols": state.get("canvas_cols",52),
                "canvas_rows": state.get("canvas_rows",100),
                "cell_px":     state["cell_px"],
                "images":      [si.to_dict() for si in state["scene_images"]],
                "cells":       vtt_canvas.mapstate,
                "janus_pairs": build_janus_pairs(vtt_canvas.mapstate),
                "tokens": [{
                    "name":         t.label,
                    "col":          t.grid_col,
                    "row":          t.grid_row,
                    "color":        t.color,
                    "hp":           t.hp or "",
                    "speed":        t.speed,
                    "type":         t.token_type,
                    "img_path":     t._img_path or "",
                    "light_radius": t.light_radius,
                    "dim_radius":   t.dim_radius,        # ← add
                    "darkvision":   t.darkvision,
                    "vision_range": t.vision_range,        # ← add
                } for t in state["tokens"]],
            }, f, indent=4)
        messagebox.showinfo("Saved","✅ Scene saved!")
    except Exception as e:
        messagebox.showerror("Save Error",str(e))


def load_scene(state, vtt_canvas, redraw_fn,
               scene_name_var, update_image_list_fn):
    file = tk.filedialog.askopenfilename(
        title="Load Scene", initialdir=BASE_DIR,
        filetypes=[("JSON","*.json")])
    if not file: return
    try:
        with open(file) as f:
            data = json.load(f)
        vtt_canvas.delete("all")
        state["scene_images"].clear()
        state["tokens"].clear()
        state["selected_image"] = None
        vtt_canvas.mapstate = {}
        state["initiative_list"]  = []
        state["combat_active"]    = False

        state["scene_name"]  = data.get("scene_name","Scene")
        state["canvas_cols"] = data.get("canvas_cols",52)
        state["canvas_rows"] = data.get("canvas_rows",100)
        state["cell_px"]     = data.get("cell_px",30)
        vtt_canvas.mapstate  = data.get("cells",{})
        scene_name_var.set(state["scene_name"])

        for d in data.get("images",[]):
            if os.path.exists(d.get("path","")):
                state["scene_images"].append(
                    SceneImage.from_dict(vtt_canvas, d))

        c = state["cell_px"]
        for td in data.get("tokens",[]):
            ip = td.get("img_path") or None
            if ip and not os.path.exists(ip): ip = None
            tok = Token(vtt_canvas,td["col"],td["row"],c,
                        label=td["name"],color=td.get("color","#e74c3c"),
                        speed=td.get("speed",6),hp=td.get("hp") or None,
                        token_type=td.get("type","enemy"),img_path=ip)
            tok.light_radius  = td.get("light_radius",  0)
            tok.dim_radius    = td.get("dim_radius",    0)   # ← add
            tok.darkvision    = td.get("darkvision",    0)
            tok.vision_range  = td.get("vision_range",  0)   # ← add
            state["tokens"].append(tok)

        update_image_list_fn()
        redraw_fn()
        messagebox.showinfo("Loaded",
            f"✅ Scene '{state['scene_name']}' loaded!")
    except Exception as e:
        messagebox.showerror("Load Error",str(e))

def save_vtt_state(tokens):
    file = tk.filedialog.asksaveasfilename(
        title="Save Tokens", defaultextension=".json",
        initialdir=BASE_DIR, filetypes=[("JSON","*.json")])
    if not file:
        return
    try:
        with open(file,"w") as f:
            json.dump([{
                "name":     t.label,
                "col":      t.grid_col,
                "row":      t.grid_row,
                "color":    t.color,
                "hp":       t.hp or "",
                "speed":    t.speed,
                "type":     t.token_type,
                "img_path": t._img_path or "",
                "light_radius": t.light_radius,
                "dim_radius":   t.dim_radius,        # ← add
                "darkvision":   t.darkvision,
                "vision_range": t.vision_range,      # ← add
            } for t in tokens], f, indent=4)
        messagebox.showinfo("Saved", f"✅ Saved {len(tokens)} tokens!")
    except Exception as e:
        messagebox.showerror("Save Error", str(e))

def load_vtt_state(state, vtt_canvas, redraw_fn):
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
        sc = max(4, int(state["cell_px"]))
        for td in data:
            ip = td.get("img_path") or None
            if ip and not os.path.exists(ip):
                ip = None
            tok = Token(vtt_canvas, td["col"], td["row"], sc,
                        label=td["name"],
                        color=td.get("color","#e74c3c"),
                        speed=td.get("speed",6),
                        hp=td.get("hp") or None,
                        token_type=td.get("type","enemy"),
                        img_path=ip)
            tok.light_radius  = td.get("light_radius",  0)
            tok.dim_radius    = td.get("dim_radius",    0)   # ← add
            tok.darkvision    = td.get("darkvision",    0)
            tok.vision_range  = td.get("vision_range",  0)   # ← add
            state["tokens"].append(tok)
        redraw_fn()
        messagebox.showinfo("Loaded", f"✅ Loaded {len(data)} tokens!")
    except Exception as e:
        messagebox.showerror("Load Error", str(e))


# ---------------------------------------------------------------------------
# MAIN BUILD FUNCTION
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# SHADOWCASTING  — Recursive shadowcasting by octant (Björn Bergström)
# ---------------------------------------------------------------------------

# Octant transformation matrices
_OCTANT_TRANSFORMS = [
    ( 1,  0,  0,  1),  # 0
    ( 0,  1,  1,  0),  # 1
    ( 0, -1,  1,  0),  # 2
    (-1,  0,  0,  1),  # 3
    (-1,  0,  0, -1),  # 4
    ( 0, -1, -1,  0),  # 5
    ( 0,  1, -1,  0),  # 6
    ( 1,  0,  0, -1),  # 7
]

def _is_blocking(col, row, mapstate):
    """Return True if this cell blocks light/vision."""
    coord = f"{col_to_letters(col)}{row + 1}"
    ctype = mapstate.get(coord, "")
    return CELL_TYPES.get(ctype, {}).get("collision", False)


def _cast_octant(visible, mapstate, ox, oy,
                 max_r, row_dist, start_slope, end_slope,
                 xx, xy, yx, yy):
    """Recursive shadowcast for one octant."""
    if start_slope < end_slope:
        return

    next_start = start_slope

    for i in range(row_dist, max_r + 1):
        blocked = False
        dx, dy = -i - 1, -i

        while dx <= 0:
            dx += 1
            # Transform to world coordinates
            col = ox + dx * xx + dy * xy
            row = oy + dx * yx + dy * yy

            l_slope = (dx - 0.5) / (dy + 0.5)
            r_slope = (dx + 0.5) / (dy - 0.5)

            if start_slope < r_slope:
                continue
            if end_slope > l_slope:
                break

            # Within vision radius — mark visible
            if dx * dx + dy * dy <= max_r * max_r:
                visible.add((col, row))

            if blocked:
                if _is_blocking(col, row, mapstate):
                    next_start = r_slope
                    continue
                else:
                    blocked = False
                    start_slope = next_start
            else:
                if _is_blocking(col, row, mapstate) and i < max_r:
                    blocked = True
                    _cast_octant(visible, mapstate, ox, oy,
                                 max_r, i + 1,
                                 start_slope, l_slope,
                                 xx, xy, yx, yy)
                    next_start = r_slope

        if blocked:
            break


def compute_fov(origin_col, origin_row, max_radius, mapstate):
    """
    Returns set of (col, row) tuples visible from origin using
    recursive shadowcasting. Walls cast proper shadows.
    """
    if max_radius <= 0:
        return None   # None means unlimited (no darkness computation)

    visible = {(origin_col, origin_row)}

    for xx, xy, yx, yy in _OCTANT_TRANSFORMS:
        _cast_octant(visible, mapstate,
                     origin_col, origin_row,
                     max_radius, 1,
                     1.0, 0.0,
                     xx, xy, yx, yy)
    return visible


def build_vtt_tab(parent):

    # -----------------------------------------------------------------------
    # STATE
    # -----------------------------------------------------------------------
    state = {
        "cell_px":        30,
        "show_grid":      True,
        "tokens":         [],
        "scene_images":   [],
        "selected_image": None,
        "scene_name":     "New Scene",
        "canvas_cols":    52,
        "canvas_rows":    100,
        "polling":        False,
        # layer locks
        "lock_map":       False,
        "lock_tile":      False,
        "lock_token":     False,
        # initiative
        "initiative_list":  [],
        "current_turn_idx": 0,
        "combat_active":    False,
        "darkness_enabled": False,
    }

    # -----------------------------------------------------------------------
    # TOOLBAR
    # -----------------------------------------------------------------------
    toolbar = tk.Frame(parent)
    toolbar.pack(side="top", fill="x", padx=6, pady=2)

    # -----------------------------------------------------------------------
    # CANVAS
    # -----------------------------------------------------------------------
    canvas_frame = tk.Frame(parent)
    canvas_frame.pack(fill="both", expand=True)

    vtt_canvas = tk.Canvas(canvas_frame, bg="#1a1a2e", cursor="crosshair")
    vtt_canvas.pack(fill="both", expand=True)
    vtt_canvas.mapstate   = {}
    vtt_canvas.paint_mode = False

    # Attach layer lock checker and zoom ref to canvas
    def _layer_unlocked(layer):
        return not state.get(f"lock_{layer}", False)
    vtt_canvas._layer_unlocked = _layer_unlocked

    zoom_level = [1.0]
    vtt_canvas._zoom = zoom_level[0]   # kept in sync

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
    inner.bind("<Configure>", lambda e: pc.config(scrollregion=pc.bbox("all")))
    pc.bind("<Configure>",    lambda e: pc.itemconfig(iw, width=e.width))

    def psw(e):
        pc.yview_scroll(-1 if e.delta > 0 else 1, "units")
    pc.bind("<MouseWheel>",    psw)
    inner.bind("<MouseWheel>", psw)

    panel_visible = [True]
    toggle_btn = tk.Button(canvas_frame, text="◄",
                           font=("Arial",8,"bold"), bg="#2c3e50",
                           fg="white", relief="flat", cursor="hand2")
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
        col = [False]

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
        tk.Button(par, text=text, command=cmd, bg=bg, fg=fg,
                  font=("Arial",8), relief="flat", cursor="hand2",
                  anchor="w", padx=6).pack(fill="x", pady=1)

    def psep(par):
        ttk.Separator(par, orient="horizontal").pack(fill="x", pady=4)

    # -----------------------------------------------------------------------
    # REDRAW ALL  — PIL-resize approach, single source of truth
    # -----------------------------------------------------------------------
    def redraw_all():
        z  = zoom_level[0]
        c  = state["cell_px"]
        sc = max(4, int(c * z))   # scaled cell size in pixels

        vtt_canvas._zoom = z

        # --- MAP LAYER: draw each SceneImage at current zoom ---
        vtt_canvas.delete("map_layer")
        for si in state["scene_images"]:
            si.canvas = vtt_canvas
            si.draw(z)

        # --- TILE LAYER ---
        vtt_canvas.delete("grid")
        vtt_canvas.delete("gridlabel")
        vtt_canvas.delete("mapstate_tile")

        gw = state["canvas_cols"] * sc
        gh = state["canvas_rows"] * sc
        vtt_canvas.config(scrollregion=(0, 0, gw + sc*2, gh + sc*2))

        if state["show_grid"]:
            for x in range(0, gw + sc, sc):
                vtt_canvas.create_line(x, 0, x, gh,
                    fill="#444466", width=1,
                    tags=("tile_layer","grid"))
            for y in range(0, gh + sc, sc):
                vtt_canvas.create_line(0, y, gw, y,
                    fill="#444466", width=1,
                    tags=("tile_layer","grid"))

            lf = ("Arial", max(6, sc//6), "bold")
            for ci in range(state["canvas_cols"]):
                vtt_canvas.create_text(
                    ci*sc + sc//2, 8,
                    text=col_to_letters(ci),
                    fill="#aaaacc", font=lf,
                    tags=("tile_layer","gridlabel"))
            for ri in range(state["canvas_rows"]):
                vtt_canvas.create_text(
                    6, ri*sc + sc//2,
                    text=str(ri+1),
                    fill="#aaaacc", font=lf, anchor="w",
                    tags=("tile_layer","gridlabel"))

        # painted cells
        for coord, ctype in vtt_canvas.mapstate.items():
            if ctype not in CELL_TYPES: continue
            cs = "".join(ch for ch in coord if ch.isalpha())
            rn = "".join(ch for ch in coord if ch.isdigit())
            if not cs or not rn: continue
            ci = 0
            for ch in cs.upper():
                ci = ci*26+(ord(ch)-ord('A')+1)
            ci -= 1
            ri  = int(rn)-1
            x, y = ci*sc, ri*sc
            vtt_canvas.create_rectangle(
                x, y, x+sc, y+sc,
                fill=CELL_TYPES[ctype]["color"], outline="",
                tags=("tile_layer","mapstate_tile"))

# --- DARKNESS LAYER (player canvas only — DM skips this) ---
        vtt_canvas.delete("darkness_layer")

        if state["darkness_enabled"]:
            player_tokens = [t for t in state["tokens"]
                             if t.token_type == "player"]
            enemy_tokens  = [t for t in state["tokens"]
                             if t.token_type != "player"]

            bright_cells = set()
            dim_cells    = set()

            for tok in player_tokens:
                col, row = tok.grid_col, tok.grid_row

                # Max range for FOV computation
                max_r = max(tok.light_radius + tok.dim_radius,
                            tok.darkvision,
                            tok.vision_range if tok.vision_range > 0 else 0)

                if max_r == 0 and tok.vision_range == 0:
                    # Unlimited vision — skip raycasting, see everything
                    continue

                # Compute FOV using shadowcasting
                fov = compute_fov(col, row, max_r,
                                  vtt_canvas.mapstate)
                if fov is None:
                    continue

                for (fc, fr) in fov:
                    dx = abs(fc - col)
                    dy = abs(fr - row)
                    dist = max(dx, dy)  # Chebyshev

                    if tok.light_radius > 0 and dist <= tok.light_radius:
                        bright_cells.add((fc, fr))
                    elif tok.dim_radius > 0 and \
                            dist <= tok.light_radius + tok.dim_radius:
                        if (fc, fr) not in bright_cells:
                            dim_cells.add((fc, fr))
                    elif tok.darkvision > 0 and dist <= tok.darkvision:
                        if (fc, fr) not in bright_cells:
                            dim_cells.add((fc, fr))

            # Check visible enemies — add their light
            for enemy in enemy_tokens:
                for player in player_tokens:
                    dx = abs(enemy.grid_col - player.grid_col)
                    dy = abs(enemy.grid_row - player.grid_row)
                    vis_r = max(player.light_radius, player.darkvision)
                    if max(dx, dy) <= vis_r:
                        if enemy.light_radius > 0:
                            efov = compute_fov(
                                enemy.grid_col, enemy.grid_row,
                                enemy.light_radius,
                                vtt_canvas.mapstate)
                            if efov:
                                bright_cells.update(efov)
                        if enemy.dim_radius > 0:
                            efov = compute_fov(
                                enemy.grid_col, enemy.grid_row,
                                enemy.light_radius + enemy.dim_radius,
                                vtt_canvas.mapstate)
                            if efov:
                                for cell in efov:
                                    if cell not in bright_cells:
                                        dim_cells.add(cell)
                        break

            # Draw darkness — only within bounding box of all tokens
            if player_tokens:
                max_r_total = max(
                    max(t.light_radius + t.dim_radius,
                        t.darkvision,
                        t.vision_range) for t in player_tokens
                )
                # If any token has unlimited vision skip darkness
                if any(t.vision_range == 0 and
                       t.light_radius == 0 and
                       t.darkvision == 0
                       for t in player_tokens):
                    pass  # fully visible
                else:
                    for ci in range(state["canvas_cols"]):
                        for ri in range(state["canvas_rows"]):
                            cell = (ci, ri)
                            x, y = ci * sc, ri * sc
                            if cell in bright_cells:
                                continue
                            elif cell in dim_cells:
                                vtt_canvas.create_rectangle(
                                    x, y, x+sc, y+sc,
                                    fill="grey10",
                                    stipple="gray75",
                                    outline="",
                                    tags="darkness_layer")
                            else:
                                vtt_canvas.create_rectangle(
                                    x, y, x+sc, y+sc,
                                    fill="black",
                                    outline="",
                                    tags="darkness_layer")
        # --- TOKEN LAYER ---
        for tok in state["tokens"]:
            tok.move_to(sc)

        # --- DRAW ORDER ---
        vtt_canvas.tag_lower("tile_layer")
        vtt_canvas.tag_lower("map_layer")
        vtt_canvas.tag_raise("tile_layer")
        vtt_canvas.tag_raise("darkness_layer")
        vtt_canvas.tag_raise("token_layer")

    # Attach redraw to canvas so SceneImage resize can trigger it
    vtt_canvas._redraw_fn = redraw_all

    # -----------------------------------------------------------------------
    # ZOOM
    # -----------------------------------------------------------------------
    def zoom(factor):
        nz = zoom_level[0] * factor
        if not (0.1 <= nz <= 8.0): return
        zoom_level[0] = nz
        redraw_all()

    def reset_zoom():
        zoom_level[0] = 1.0
        redraw_all()

    vtt_canvas.bind("<MouseWheel>",
                    lambda e: zoom(1.1 if e.delta > 0 else 0.9))

    # -----------------------------------------------------------------------
    # COORDINATE DISPLAY
    # -----------------------------------------------------------------------
    coord_label = tk.Label(vtt_canvas, text="",
                           bg="#2c3e50", fg="white",
                           font=("Arial",8,"bold"), padx=4, pady=2)

    def on_mouse_move(event):
        z   = zoom_level[0]
        sc  = max(4, int(state["cell_px"] * z))
        cx  = vtt_canvas.canvasx(event.x)
        cy  = vtt_canvas.canvasy(event.y)
        col = int(cx // sc)
        row = int(cy // sc)
        coord    = f"{col_to_letters(col)}{row+1}"
        ctype    = vtt_canvas.mapstate.get(coord,"")
        type_txt = f" — {ctype}" if ctype else ""
        coord_label.config(text=f"{coord}{type_txt}")
        lx = min(event.x+12, vtt_canvas.winfo_width()-90)
        ly = min(event.y+12, vtt_canvas.winfo_height()-24)
        coord_label.place(x=lx, y=ly)

    def on_mouse_leave(event):
        coord_label.place_forget()

    vtt_canvas.bind("<Motion>", on_mouse_move)
    vtt_canvas.bind("<Leave>",  on_mouse_leave)

    # -----------------------------------------------------------------------
    # PAINT MODE
    # -----------------------------------------------------------------------
    paint_type_var = tk.StringVar(value="edge")

    def paint_cell(event):
        if not vtt_canvas.paint_mode: return
        if not _layer_unlocked("tile"): return
        z     = zoom_level[0]
        sc    = max(4, int(state["cell_px"] * z))
        cx    = vtt_canvas.canvasx(event.x)
        cy    = vtt_canvas.canvasy(event.y)
        col   = int(cx // sc)
        row   = int(cy // sc)
        coord = f"{col_to_letters(col)}{row+1}"
        ctype = paint_type_var.get()
        if ctype == "erase":
            vtt_canvas.mapstate.pop(coord, None)
        else:
            vtt_canvas.mapstate[coord] = ctype
        redraw_all()

    def on_right_click_canvas(event):
        if not vtt_canvas.paint_mode: return
        z     = zoom_level[0]
        sc    = max(4, int(state["cell_px"] * z))
        cx    = vtt_canvas.canvasx(event.x)
        cy    = vtt_canvas.canvasy(event.y)
        col   = int(cx // sc)
        row   = int(cy // sc)
        coord = f"{col_to_letters(col)}{row+1}"
        ctype = vtt_canvas.mapstate.get(coord,"")
        if ctype == "door_closed":
            vtt_canvas.mapstate[coord] = "door_open"
        elif ctype == "door_open":
            vtt_canvas.mapstate[coord] = "door_closed"
        redraw_all()

    vtt_canvas.bind("<ButtonPress-1>", paint_cell,           add="+")
    vtt_canvas.bind("<B1-Motion>",     paint_cell,           add="+")
    vtt_canvas.bind("<Button-3>",      on_right_click_canvas)

    # -----------------------------------------------------------------------
    # IMAGE DRAG  (map layer, only when unlocked)
    # -----------------------------------------------------------------------
    _dragging_image = [False]

    def on_canvas_press(event):
        if not _layer_unlocked("map"): return
        if vtt_canvas.paint_mode: return
        cx = vtt_canvas.canvasx(event.x)
        cy = vtt_canvas.canvasy(event.y)
        z  = zoom_level[0]
        hit = None
        for si in reversed(state["scene_images"]):
            if si.hit_test(cx, cy, z):
                hit = si; break
        if hit:
            _select_image(hit)
            hit.start_drag(cx, cy, z)
            _dragging_image[0] = True
        else:
            _deselect_all_images()
            _dragging_image[0] = False

    def on_canvas_drag(event):
        if not _dragging_image[0]: return
        si = state["selected_image"]
        if si:
            cx = vtt_canvas.canvasx(event.x)
            cy = vtt_canvas.canvasy(event.y)
            si.do_drag(cx, cy)
            redraw_all()

    def on_canvas_release(event):
        si = state["selected_image"]
        if si: si._end_drag()
        _dragging_image[0] = False

    vtt_canvas.bind("<ButtonPress-1>",   on_canvas_press,   add="+")
    vtt_canvas.bind("<B1-Motion>",       on_canvas_drag,    add="+")
    vtt_canvas.bind("<ButtonRelease-1>", on_canvas_release, add="+")

    def _select_image(si):
        if state["selected_image"] and state["selected_image"] is not si:
            state["selected_image"].deselect()
        state["selected_image"] = si
        si.select()

    def _deselect_all_images():
        if state["selected_image"]:
            state["selected_image"].deselect()
        state["selected_image"] = None

    # -----------------------------------------------------------------------
    # NEW SCENE
    # -----------------------------------------------------------------------
    def new_scene():
        if (state["tokens"] or state["scene_images"] or vtt_canvas.mapstate):
            if not messagebox.askyesno("New Scene",
                    "This will clear the current scene.\nContinue?"):
                return

        win = tk.Toplevel(parent)
        win.title("New Scene")
        win.geometry("300x240")
        win.resizable(False,False)
        win.grab_set()

        tk.Label(win,text="Scene Name:").pack(pady=(12,0))
        nv = tk.StringVar(value="New Scene")
        tk.Entry(win,textvariable=nv,width=24).pack()

        tk.Label(win,text="Canvas Columns:").pack(pady=(10,0))
        cv = tk.IntVar(value=52)
        tk.Spinbox(win,from_=10,to=702,textvariable=cv,width=8).pack()

        tk.Label(win,text="Canvas Rows:").pack(pady=(10,0))
        rv = tk.IntVar(value=100)
        tk.Spinbox(win,from_=10,to=1000,textvariable=rv,width=8).pack()

        def confirm():
            vtt_canvas.delete("all")
            state["scene_images"].clear()
            state["tokens"].clear()
            state["selected_image"]   = None
            vtt_canvas.mapstate       = {}
            state["initiative_list"]  = []
            state["combat_active"]    = False
            state["scene_name"]       = nv.get().strip() or "Scene"
            state["canvas_cols"]      = max(10,cv.get())
            state["canvas_rows"]      = max(10,rv.get())
            scene_name_var.set(state["scene_name"])
            update_image_list()
            redraw_all()
            win.destroy()

        tk.Button(win,text="✅ Create Scene",command=confirm,
                  bg="#27ae60",fg="white",
                  font=("Arial",10,"bold")).pack(pady=14)

    # -----------------------------------------------------------------------
    # ADD IMAGE
    # -----------------------------------------------------------------------
    def add_image():
        if not _layer_unlocked("map"):
            messagebox.showwarning("Layer Locked",
                "Unlock the Map Layer first."); return
        path = tk.filedialog.askopenfilename(
            title="Add Map Image", initialdir=MAPS_DIR,
            filetypes=[("Images","*.png *.jpg *.jpeg *.webp *.bmp")])
        if not path: return
        si = SceneImage(vtt_canvas, path,
                        x=vtt_canvas.canvasx(40) / zoom_level[0],
                        y=vtt_canvas.canvasy(40) / zoom_level[0])
        state["scene_images"].append(si)
        _select_image(si)
        update_image_list()
        redraw_all()

    # -----------------------------------------------------------------------
    # IMAGE LIST
    # -----------------------------------------------------------------------
    image_listbox = [None]

    def update_image_list():
        lb = image_listbox[0]
        if lb is None: return
        lb.delete(0, tk.END)
        for si in state["scene_images"]:
            lb.insert(tk.END, os.path.basename(si.path))

    def on_image_select(event=None):
        lb = image_listbox[0]
        if lb is None: return
        sel = lb.curselection()
        if not sel: return
        _select_image(state["scene_images"][sel[0]])

    def remove_selected_image():
        si = state["selected_image"]
        if si is None:
            messagebox.showwarning("None Selected",
                "Click an image in the list first."); return
        if not messagebox.askyesno("Remove",
                f"Remove {os.path.basename(si.path)}?"): return
        si.delete()
        state["scene_images"].remove(si)
        state["selected_image"] = None
        update_image_list()
        redraw_all()

    # -----------------------------------------------------------------------
    # LAYER LOCKS
    # -----------------------------------------------------------------------
    lock_btns = {}

    def toggle_lock(layer):
        state[f"lock_{layer}"] = not state[f"lock_{layer}"]
        locked = state[f"lock_{layer}"]
        btn = lock_btns.get(layer)
        if btn:
            btn.config(text="🔒" if locked else "🔓",
                       bg="#c0392b" if locked else "#27ae60")

    # -----------------------------------------------------------------------
    # TOKEN PLACER
    # -----------------------------------------------------------------------
    def place_token(category="players"):
        folder  = PLAYER_DIR if category=="players" else ENEMY_DIR
        options = list_images(folder)
        win = tk.Toplevel(parent)
        win.title("Place Token")
        win.geometry("260x420")
        win.resizable(False,False)

        tk.Label(win,text="Name:").pack(pady=(10,0))
        ne = tk.Entry(win,width=22); ne.pack()
        ne.insert(0,"Goblin" if category=="enemies" else "Hero")

        tk.Label(win,text="Token Image:").pack(pady=(8,0))
        iv = tk.StringVar(value="— none —")
        ttk.Combobox(win,textvariable=iv,values=["— none —"]+options,
                     state="readonly",width=24).pack()

        tk.Label(win,text="Color:").pack(pady=(8,0))
        cv = tk.StringVar(value="#e74c3c" if category=="enemies" else "#2980b9")
        tk.Entry(win,textvariable=cv,width=12,justify="center").pack()

        tk.Label(win,text="HP:").pack(pady=(8,0))
        he = tk.Entry(win,width=12,justify="center"); he.pack()

        tk.Label(win,text="Speed (squares):").pack(pady=(8,0))
        se = tk.Entry(win,width=8,justify="center"); se.pack()
        se.insert(0,"6")

        def confirm():
            label   = ne.get().strip() or "Token"
            imgname = iv.get()
            imgpath = None
            if imgname != "— none —":
                imgpath = os.path.join(folder,imgname)
            try: spd = int(se.get().strip() or "6")
            except: spd = 6
            hp_val = he.get().strip() or None
            sc = max(4, int(state["cell_px"] * zoom_level[0]))
            cx = int(vtt_canvas.canvasx(vtt_canvas.winfo_width()//2))
            cy = int(vtt_canvas.canvasy(vtt_canvas.winfo_height()//2))
            tok = Token(vtt_canvas, cx//sc, cy//sc, sc,
                        label=label, color=cv.get(),
                        img_path=imgpath, speed=spd, hp=hp_val,
                        token_type="player" if category=="players" else "enemy")
            state["tokens"].append(tok)
            win.destroy()

        tk.Button(win,text="✅ Place Token",command=confirm,
                  bg="#27ae60",fg="white").pack(pady=14)

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
        win.resizable(False,False)
        win.grab_set()
        tk.Label(win,text="Enter initiative rolls",
                 font=("Arial",11,"bold")).pack(pady=(10,4))
        entries = {}
        sf = tk.Frame(win); sf.pack(fill="both",expand=True,padx=12,pady=8)
        for tok in state["tokens"]:
            row = tk.Frame(sf); row.pack(fill="x",pady=3)
            tk.Label(row,bg=tok.color,width=2).pack(side="left",padx=(0,6))
            tk.Label(row,text=tok.label,width=16,anchor="w").pack(side="left")
            var = tk.StringVar(value=str(tok.initiative or ""))
            tk.Entry(row,textvariable=var,width=6,justify="center").pack(side="right")
            entries[tok] = var

        def confirm():
            order = []
            for tok,var in entries.items():
                try: tok.initiative = int(var.get())
                except: tok.initiative = 0
                order.append(tok)
            order.sort(key=lambda t: t.initiative, reverse=True)
            state["initiative_list"]  = order
            state["current_turn_idx"] = 0
            state["combat_active"]    = True
            refresh_initiative_display()
            win.destroy()

        tk.Button(win,text="⚔️ Start Combat",command=confirm,
                  bg="#c0392b",fg="white",
                  font=("Arial",10,"bold")).pack(pady=10)

    def refresh_initiative_display():
        lb = initiative_listbox[0]
        tl = turn_label[0]
        if lb is None: return
        lb.delete(0,tk.END)
        order = state["initiative_list"]
        idx   = state["current_turn_idx"]
        for i,tok in enumerate(order):
            prefix = "▶ " if i==idx else "   "
            lb.insert(tk.END,f"{prefix}{tok.initiative:>3}  {tok.label}")
            if i==idx: lb.itemconfig(i,bg="#2c3e50",fg="#f1c40f")
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
        prev = getattr(vtt_canvas,"selected_token",None)
        if prev: prev.deselect()
        vtt_canvas.selected_token = nxt
        nxt.select()
        refresh_initiative_display()
        messagebox.showinfo("Next Turn",f"⚔️ {nxt.label}'s turn!")

    def end_combat():
        if not messagebox.askyesno("End Combat",
                "End combat & reset movement?"): return
        state["combat_active"]    = False
        state["initiative_list"]  = []
        state["current_turn_idx"] = 0
        for tok in state["tokens"]: tok.reset_movement()
        refresh_initiative_display()
        tl = turn_label[0]
        if tl: tl.config(text="No active combat")

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
        sc = max(4, int(state["cell_px"] * zoom_level[0]))
        for td in data:
            color = "#e74c3c" if td["type"]=="enemy" else "#2980b9"
            tok   = Token(vtt_canvas,td["col"],td["row"],sc,
                          label=td["name"],color=color,
                          speed=td.get("speed",6),hp=td.get("hp"),
                          token_type=td["type"])
            state["tokens"].append(tok)
        redraw_all()
        messagebox.showinfo("Synced",f"✅ Loaded {len(data)} tokens!")

    def pull_ms():
        data = pull_mapstate_from_sheet()
        if data is not None:
            vtt_canvas.mapstate = data; redraw_all()

    # -----------------------------------------------------------------------
    # TOP TOOLBAR
    # -----------------------------------------------------------------------
    scene_name_var = tk.StringVar(value=state["scene_name"])

    tk.Label(toolbar,text="Scene:",font=("Arial",9,"bold")).pack(side="left")
    tk.Label(toolbar,textvariable=scene_name_var,
             fg="#2980b9",font=("Arial",9,"bold")).pack(side="left",padx=4)

    ttk.Separator(toolbar,orient="vertical").pack(side="left",fill="y",padx=4)
    tk.Label(toolbar,text="Grid ft:",font=("Arial",9,"bold")).pack(side="left")

    cell_ft_var = tk.IntVar(value=5)

    def update_cell_size(*_):
        try:
            state["cell_px"] = max(6, cell_ft_var.get() * 6)
            redraw_all()
        except Exception: pass

    tk.Spinbox(toolbar,from_=3,to=10,increment=1,
               textvariable=cell_ft_var,width=4,
               command=update_cell_size).pack(side="left",padx=2)
    cell_ft_var.trace_add("write",update_cell_size)

    ttk.Separator(toolbar,orient="vertical").pack(side="left",fill="y",padx=4)
    tk.Label(toolbar,text="Zoom:",font=("Arial",9,"bold")).pack(side="left")
    tk.Button(toolbar,text="＋",command=lambda: zoom(1.25),
              font=("Arial",10,"bold"),width=2).pack(side="left",padx=1)
    tk.Button(toolbar,text="－",command=lambda: zoom(0.8),
              font=("Arial",10,"bold"),width=2).pack(side="left",padx=1)
    tk.Button(toolbar,text="⟳",command=reset_zoom,
              font=("Arial",9)).pack(side="left",padx=2)

    ttk.Separator(toolbar,orient="vertical").pack(side="left",fill="y",padx=4)
    tk.Button(toolbar,text="🧙 Player",
              command=lambda: place_token("players"),
              bg="#2980b9",fg="white",
              font=("Arial",8)).pack(side="left",padx=2)
    tk.Button(toolbar,text="👹 Enemy",
              command=lambda: place_token("enemies"),
              bg="#c0392b",fg="white",
              font=("Arial",8)).pack(side="left",padx=2)

    ttk.Separator(toolbar,orient="vertical").pack(side="left",fill="y",padx=4)
    grid_toggle_var = tk.BooleanVar(value=True)

    def toggle_grid():
        state["show_grid"] = grid_toggle_var.get(); redraw_all()

    tk.Checkbutton(toolbar,text="Grid",
                   variable=grid_toggle_var,
                   command=toggle_grid).pack(side="left",padx=4)

    # -----------------------------------------------------------------------
    # SIDE PANEL — LAYERS
    # -----------------------------------------------------------------------
    lay_sec = make_section("🔒 LAYERS")

    for layer, label in [("map","🗺️ Map Layer"),
                          ("tile","🎨 Tile Layer"),
                          ("token","🧙 Token Layer")]:
        row = tk.Frame(lay_sec,bg="#1e1e2e")
        row.pack(fill="x",pady=2)
        tk.Label(row,text=label,bg="#1e1e2e",fg="white",
                 font=("Arial",8),width=14,
                 anchor="w").pack(side="left",padx=6)
        btn = tk.Button(row,text="🔓",width=3,
                        command=lambda l=layer: toggle_lock(l),
                        bg="#27ae60",fg="white",
                        font=("Arial",8),relief="flat")
        btn.pack(side="right",padx=4)
        lock_btns[layer] = btn

    # -----------------------------------------------------------------------
    # SIDE PANEL — SCENE
    # -----------------------------------------------------------------------
    scene_sec = make_section("🗺️ SCENE")

    pbtn(scene_sec,"✨ New Scene",  new_scene,  bg="#8e44ad")
    pbtn(scene_sec,"➕ Add Image", add_image,  bg="#2980b9")
    psep(scene_sec)

    tk.Label(scene_sec,text="Images on canvas:",
             bg="#1e1e2e",fg="#aaaacc",
             font=("Arial",8)).pack(anchor="w",padx=6)

    lb_img = tk.Listbox(scene_sec,height=5,width=22,
                         bg="#16213e",fg="white",
                         font=("Arial",8),
                         selectbackground="#2c3e50",
                         relief="flat")
    lb_img.pack(fill="x",padx=4,pady=2)
    lb_img.bind("<<ListboxSelect>>",on_image_select)
    image_listbox[0] = lb_img

    pbtn(scene_sec,"🗑️ Remove Selected Image",
         remove_selected_image,bg="#c0392b")
    psep(scene_sec)
    pbtn(scene_sec,"💾 Save Scene",
         lambda: save_scene(state,vtt_canvas))
    pbtn(scene_sec,"📂 Load Scene",
         lambda: load_scene(state,vtt_canvas,redraw_all,
                            scene_name_var,update_image_list))
    def push_active_scene():
        """Push current scene as the active scene for players."""
        scene_file = os.path.join(
            "scenes",
            f"{state['scene_name'].lower().replace(' ','_')}.json"
        )

        # Check if the scene file exists in campaign/scenes/
        campaign_scenes = os.path.join(BASE_DIR, "campaign", "scenes")
        full_path = os.path.join(campaign_scenes, 
                                 os.path.basename(scene_file))

        if not os.path.exists(full_path):
            if not messagebox.askyesno("Scene Not Saved",
                    f"Scene file not found in campaign/scenes/.\n"
                    f"Save it there first?\n\n"
                    f"Players need this file to load the scene."):
                return
            # Save it to campaign/scenes/ automatically
            os.makedirs(campaign_scenes, exist_ok=True)
            save_path = full_path
            try:
                with open(save_path, "w") as f:
                    json.dump({
                        "scene_name":  state["scene_name"],
                        "canvas_cols": state["canvas_cols"],
                        "canvas_rows": state["canvas_rows"],
                        "cell_px":     state["cell_px"],
                        "images":      [si.to_dict()
                                        for si in state["scene_images"]],
                        "cells":       vtt_canvas.mapstate,
                        "janus_pairs": build_janus_pairs(vtt_canvas.mapstate),
                        "tokens": [{
                            "name":         t.label,
                            "col":          t.grid_col,
                            "row":          t.grid_row,
                            "color":        t.color,
                            "hp":           t.hp or "",
                            "speed":        t.speed,
                            "type":         t.token_type,
                            "light_radius": t.light_radius,
                            "dim_radius":   t.dim_radius,        # ← add
                            "darkvision":   t.darkvision,
                            "vision_range": t.vision_range,      # ← add
                        } for t in state["tokens"]],
                    }, f, indent=4)
            except Exception as e:
                messagebox.showerror("Save Error", str(e))
                return

        # Push to Google Sheets
        try:
            import datetime
            client      = get_sheets_client()
            spreadsheet = client.open("DnD_VTT")

            try:
                sheet = spreadsheet.worksheet("ActiveScene")
            except Exception:
                sheet = spreadsheet.add_worksheet(
                    "ActiveScene", rows=10, cols=4)
                sheet.update("A1", [["scene_name", "scene_file",
                                     "darkness", "updated_at"]])

            darkness = state.get("darkness_enabled", True)
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

            sheet.update("A2", [[
                state["scene_name"],
                os.path.basename(scene_file),
                str(darkness).upper(),
                timestamp,
            ]])

            messagebox.showinfo("Active Scene Pushed",
                f"✅ '{state['scene_name']}' is now the active scene!\n"
                f"Players can sync to load it.\n"
                f"Darkness: {'ON' if darkness else 'OFF'}\n"
                f"Updated: {timestamp}")

        except Exception as e:
            messagebox.showerror("Sheet Error", str(e))

    psep(scene_sec)
    pbtn(scene_sec, "📡 Push Active Scene → Players",
         push_active_scene, bg="#c0392b")
    # -----------------------------------------------------------------------
    # SIDE PANEL — TOKENS
    # -----------------------------------------------------------------------
    tok_sec = make_section("🧙 TOKENS")

    pbtn(tok_sec,"🧙 Add Player Token",
         lambda: place_token("players"),bg="#2980b9")
    pbtn(tok_sec,"👹 Add Enemy Token",
         lambda: place_token("enemies"),bg="#c0392b")
    psep(tok_sec)

    def clear_all_tokens():
        if messagebox.askyesno("Clear","Remove all tokens?"):
            vtt_canvas.delete("token_layer")
            vtt_canvas.delete("sel_ring")
            state["tokens"].clear()
            state["initiative_list"].clear()
            state["combat_active"] = False
            refresh_initiative_display()

    pbtn(tok_sec,"🗑️ Clear All Tokens",clear_all_tokens)
    psep(tok_sec)
    pbtn(tok_sec,"⬆️ Push Tokens → Sheet",push_to_sheet, bg="#8e44ad")
    pbtn(tok_sec,"⬇️ Pull Tokens ← Sheet",pull_from_sheet,bg="#8e44ad")
    psep(tok_sec)

    polling_lbl = tk.Label(tok_sec,text="⏸ Auto Sync: OFF",
                           bg="#1e1e2e",fg="#7f8c8d",font=("Arial",8))
    polling_lbl.pack(anchor="w",padx=6)
    polling_var = tk.BooleanVar(value=False)

    def toggle_polling():
        if not polling_var.get():
            polling_var.set(True)
            state["polling"] = True
            polling_lbl.config(text="▶ Auto Sync: ON",fg="#27ae60")
            start_sheet_polling(state,state["tokens"],vtt_canvas,
                                redraw_all,interval_ms=90000)
        else:
            polling_var.set(False)
            state["polling"] = False
            polling_lbl.config(text="⏸ Auto Sync: OFF",fg="#7f8c8d")

    pbtn(tok_sec,"⏯ Toggle Auto Sync",toggle_polling)
    psep(tok_sec)
    pbtn(tok_sec,"💾 Save Tokens",
         lambda: save_vtt_state(state["tokens"]))
    pbtn(tok_sec,"📂 Load Tokens",
         lambda: load_vtt_state(state, vtt_canvas, redraw_all))
    # -----------------------------------------------------------------------
    # SIDE PANEL — COMBAT
    # -----------------------------------------------------------------------
    combat_sec = make_section("⚔️ COMBAT")

    tl = tk.Label(combat_sec,text="No active combat",
                  bg="#1e1e2e",fg="#aaaacc",font=("Arial",8,"bold"))
    tl.pack(anchor="w",padx=6,pady=(4,2))
    turn_label[0] = tl

    pbtn(combat_sec,"🎲 Set Initiative",open_initiative_popup,bg="#8e44ad")
    psep(combat_sec)

    lb_init = tk.Listbox(combat_sec,height=8,width=22,
                          bg="#16213e",fg="white",
                          font=("Courier",8),
                          selectbackground="#2c3e50",relief="flat")
    lb_init.pack(fill="x",padx=4,pady=2)
    initiative_listbox[0] = lb_init

    psep(combat_sec)
    pbtn(combat_sec,"▶ End Turn",  end_turn,  bg="#27ae60")
    pbtn(combat_sec,"🛑 End Combat",end_combat,bg="#c0392b")

    # -----------------------------------------------------------------------
    # SIDE PANEL — TILE PAINT
    # -----------------------------------------------------------------------
    map_sec = make_section("🎨 TILE PAINT")

    paint_mode_lbl = tk.Label(map_sec,text="🖌️ Paint Mode: OFF",
                              bg="#1e1e2e",fg="#7f8c8d",font=("Arial",8))
    paint_mode_lbl.pack(anchor="w",padx=6,pady=2)

    def toggle_paint_mode():
        if not _layer_unlocked("tile"):
            messagebox.showwarning("Layer Locked",
                "Unlock the Tile Layer first."); return
        vtt_canvas.paint_mode = not vtt_canvas.paint_mode
        if vtt_canvas.paint_mode:
            paint_mode_lbl.config(text="🖌️ Paint Mode: ON",fg="#e67e22")
            vtt_canvas.config(cursor="pencil")
        else:
            paint_mode_lbl.config(text="🖌️ Paint Mode: OFF",fg="#7f8c8d")
            vtt_canvas.config(cursor="crosshair")

    pbtn(map_sec,"🖌️ Toggle Paint Mode",toggle_paint_mode,bg="#e67e22")

    tk.Label(map_sec,text="Paint Type:",bg="#1e1e2e",fg="#aaaacc",
             font=("Arial",8)).pack(anchor="w",padx=6,pady=(6,0))

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
        ).pack(anchor="w",padx=10)

    psep(map_sec)
    pbtn(map_sec,"⬆️ Push MapState → Sheet",
         lambda: push_mapstate_to_sheet(
             vtt_canvas.mapstate,
             state.get("canvas_cols",52),
             state.get("canvas_rows",100)),bg="#16a085")
    pbtn(map_sec,"⬇️ Pull MapState ← Sheet",pull_ms,bg="#16a085")
    psep(map_sec)
    pbtn(map_sec,"⬆️ Push Janus → Sheet",
         lambda: push_janus_to_sheet(
             build_janus_pairs(vtt_canvas.mapstate)))
    darkness_lbl = tk.Label(map_sec, text="⚫ Darkness: OFF",
                            bg="#1e1e2e", fg="#7f8c8d", font=("Arial",8))
    darkness_lbl.pack(anchor="w", padx=6, pady=2)

    def toggle_darkness():
        if not _layer_unlocked("tile"):
            messagebox.showwarning("Layer Locked",
                "Unlock the Tile Layer first.")
            return
        state["darkness_enabled"] = not state["darkness_enabled"]
        if state["darkness_enabled"]:
            darkness_lbl.config(text="⚫ Darkness: ON", fg="#f1c40f")
        else:
            darkness_lbl.config(text="⚫ Darkness: OFF", fg="#7f8c8d")
        redraw_all()

    pbtn(map_sec, "⚫ Toggle Darkness", toggle_darkness, bg="#2c3e50")
    # -----------------------------------------------------------------------
    # WASD
    # -----------------------------------------------------------------------
    def move_selected(event):
        if vtt_canvas.paint_mode: return
        if not _layer_unlocked("token"): return
        tok = getattr(vtt_canvas,"selected_token",None)
        if not tok: return
        key = event.keysym.lower()
        dc = dr = 0
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
        if not tok.can_move(dc,dr):
            messagebox.showwarning("Out of Movement",
                f"{tok.label} has no moves left!"); return
        tok.spend_move(dc,dr)
        tok.grid_col, tok.grid_row = nc, nr
        sc = max(4, int(state["cell_px"] * zoom_level[0]))
        tok.move_to(sc)
        tok.select()
        tok._check_janus(coord)
        redraw_all()

    vtt_canvas.bind("<w>",move_selected)
    vtt_canvas.bind("<s>",move_selected)
    vtt_canvas.bind("<a>",move_selected)
    vtt_canvas.bind("<d>",move_selected)

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
    vtt_canvas.bind("<Button-1>",
                    lambda e: vtt_canvas.focus_set(), add="+")
    vtt_canvas.bind("<ButtonPress-2>",
                    lambda e: vtt_canvas.scan_mark(e.x,e.y))
    vtt_canvas.bind("<B2-Motion>",
                    lambda e: vtt_canvas.scan_dragto(e.x,e.y,gain=1))

    # -----------------------------------------------------------------------
    # INITIAL DRAW
    # -----------------------------------------------------------------------
    parent.after(100, redraw_all)
