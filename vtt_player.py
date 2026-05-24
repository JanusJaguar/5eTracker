# ---------------------------------------------------------------------------
# vtt_player.py — Player VTT Tab for Janus D&D Tracker
# ---------------------------------------------------------------------------
# REQUIRES:  pip install Pillow gspread google-auth
#
# FLOW:
#   1. Player opens Battle Map tab
#   2. App checks character name — if blank, shows popup
#   3. Player hits Sync → pulls ActiveScene from Google Sheets
#   4. App loads scene JSON from campaign/scenes/
#   5. Map appears, player's token auto-identified by character name
#   6. Darkness on by default, vision limited to own token
#   7. Auto-polls every 60s for token position updates
#
# LAYERS (bottom → top):
#   MAP LAYER      — background images (read only)
#   TILE LAYER     — grid, labels, painted mapstate cells (read only)
#   DARKNESS LAYER — vision/light overlay
#   TOKEN LAYER    — tokens (own token WASD only)
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
# PATHS
# ---------------------------------------------------------------------------
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
CAMPAIGN_DIR = os.path.join(BASE_DIR, "campaign")
SCENES_DIR   = os.path.join(CAMPAIGN_DIR, "scenes")
MAPS_DIR     = os.path.join(CAMPAIGN_DIR, "maps")
TOKEN_DIR    = os.path.join(CAMPAIGN_DIR, "tokens")
PLAYER_DIR   = os.path.join(TOKEN_DIR, "players")
ENEMY_DIR    = os.path.join(TOKEN_DIR, "enemies")

for _d in (SCENES_DIR, MAPS_DIR, PLAYER_DIR, ENEMY_DIR):
    os.makedirs(_d, exist_ok=True)

# ---------------------------------------------------------------------------
# COORDINATE HELPERS  (duplicated from vtt.py for independence)
# ---------------------------------------------------------------------------

def col_to_letters(n):
    result = ""
    n += 1
    while n > 0:
        n, r = divmod(n - 1, 26)
        result = chr(65 + r) + result
    return result


def coord_to_col_row(coord):
    cs = "".join(c for c in coord if c.isalpha())
    rs = "".join(c for c in coord if c.isdigit())
    ci = 0
    for c in cs.upper():
        ci = ci * 26 + (ord(c) - ord('A') + 1)
    return ci - 1, int(rs) - 1

# ---------------------------------------------------------------------------
# CELL TYPES  (read only — no painting in player mode)
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
# JANUS HELPERS
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

def find_janus_destination(coord, mapstate):
    a_coords = [k for k, v in mapstate.items() if v == "janus_a"]
    b_coords = [k for k, v in mapstate.items() if v == "janus_b"]
    pairs    = list(zip(a_coords, b_coords))
    ctype    = mapstate.get(coord, "")
    for ca, cb in pairs:
        if ctype == "janus_a" and ca == coord:
            return cb
        if ctype == "janus_b" and cb == coord:
            return ca
    return None

# ---------------------------------------------------------------------------
# GOOGLE SHEETS
# ---------------------------------------------------------------------------

def get_sheets_client():
    import gspread
    from google.oauth2.service_account import Credentials
    creds = Credentials.from_service_account_file(
        os.path.join(BASE_DIR, "credentials.json"),
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ])
    return gspread.authorize(creds)


def pull_active_scene_from_sheet():
    """
    Pull ActiveScene info from DnD_VTT sheet.
    Returns dict with scene_file, darkness, or None on failure.
    """
    try:
        client = get_sheets_client()
        ss     = client.open("DnD_VTT")
        try:
            sheet = ss.worksheet("ActiveScene")
        except Exception:
            messagebox.showwarning("No Active Scene",
                "DM has not set an active scene yet.\n"
                "Ask your DM to push the scene.")
            return None

        vals = sheet.row_values(2)   # row 1 = headers, row 2 = data
        if not vals:
            messagebox.showwarning("No Active Scene",
                "DM has not pushed a scene yet.")
            return None

        return {
            "scene_name": vals[0] if len(vals) > 0 else "Unknown",
            "scene_file": vals[1] if len(vals) > 1 else "",
            "darkness":   str(vals[2]).upper() == "TRUE" if len(vals) > 2 else True,
        }
    except Exception as e:
        messagebox.showerror("Sheet Error", str(e))
        return None


def pull_tokens_from_sheet():
    """Pull token positions from Tokens sheet."""
    try:
        rows   = get_sheets_client().open("DnD_VTT").sheet1.get_all_records()
        result = []
        for row in rows:
            try:
                cs = str(row.get("col", "A")).strip().upper()
                ci = 0
                for c in cs:
                    ci = ci * 26 + (ord(c) - ord('A') + 1)
                result.append({
                    "name":  str(row.get("name", "Token")),
                    "col":   ci - 1,
                    "row":   int(row.get("row", 1)) - 1,
                    "type":  str(row.get("type", "player")),
                    "hp":    str(row.get("hp", "")) or None,
                    "speed": int(row.get("speed", 6) or 6),
                })
            except Exception:
                continue
        return result
    except Exception as e:
        messagebox.showerror("Sheet Error", str(e))
        return []


def push_own_token_to_sheet(token, all_tokens):
    """
    Player pushes only their own token position back to the sheet.
    Other tokens are preserved.
    """
    try:
        sheet = get_sheets_client().open("DnD_VTT").sheet1
        rows  = sheet.get_all_records()

        for i, row in enumerate(rows, start=2):
            if str(row.get("name","")).strip().lower() == \
               token.label.strip().lower():
                sheet.update(f"B{i}:F{i}", [[
                    col_to_letters(token.grid_col),
                    token.grid_row + 1,
                    token.token_type,
                    token.hp or "",
                    token.speed,
                ]])
                return
        messagebox.showwarning("Token Not Found",
            f"Could not find '{token.label}' in the sheet.\n"
            "Ask your DM to push tokens first.")
    except Exception as e:
        messagebox.showerror("Sheet Error", str(e))

# ---------------------------------------------------------------------------
# PLAYER TOKEN  (simplified — no resize handles, no right-click shop)
# ---------------------------------------------------------------------------

class PlayerToken:
    def __init__(self, canvas, col, row, cell_px, label="Token",
                 color="#2980b9", img_path=None, speed=6,
                 hp=None, token_type="player", is_own=False):
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
        self.is_own     = is_own      # True = this player's token
        self._photo     = None
        self._img_path  = img_path
        self.vision_range = 0
        self.light_radius = 0
        self.dim_radius   = 0
        self.darkvision   = 0

        x, y, half = col*cell_px, row*cell_px, cell_px//2

        if img_path and PIL_OK:
            try:
                img = Image.open(img_path).resize(
                    (cell_px, cell_px), Image.LANCZOS)
                self._photo = ImageTk.PhotoImage(img)
                self.oval = canvas.create_image(
                    x, y, image=self._photo, anchor="nw",
                    tags=("token_layer","token"))
            except Exception:
                self._photo = None
                self.oval = canvas.create_oval(
                    x, y, x+cell_px, y+cell_px,
                    fill=color, outline="white", width=2,
                    tags=("token_layer","token"))
        else:
            self.oval = canvas.create_oval(
                x, y, x+cell_px, y+cell_px,
                fill=color, outline="white", width=2,
                tags=("token_layer","token"))

        # Own token gets a gold border
        if is_own:
            self.own_ring = canvas.create_oval(
                x-2, y-2, x+cell_px+2, y+cell_px+2,
                outline="#f1c40f", width=3,
                tags=("token_layer","token"))
        else:
            self.own_ring = None

        self.text = canvas.create_text(
            x+half, y+cell_px+8,
            text=self._build_label(), fill="white",
            font=("Arial", 7, "bold"),
            tags=("token_layer","token"))

        self.move_lbl = canvas.create_text(
            x+half, y-8, text="",
            fill="#27ae60", font=("Arial", 7, "bold"),
            tags=("token_layer","token"), state="hidden")

        self._drag_x = self._drag_y = 0
        self._drag_start_col = col
        self._drag_start_row = row

        # Only bind drag/movement for own token
        if is_own:
            for item in (self.oval, self.text):
                canvas.tag_bind(item, "<ButtonPress-1>",
                                self._on_press)
                canvas.tag_bind(item, "<B1-Motion>",
                                self._on_drag)
                canvas.tag_bind(item, "<ButtonRelease-1>",
                                self._on_release)
            # Right-click for own token: set HP display only
            canvas.tag_bind(self.oval, "<Button-3>",
                            self._on_right_click)

    def _build_label(self):
        parts = [self.label]
        if self.hp:
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
        self.canvas.delete(f"psel_{id(self)}")
        c = self.cell_px
        x, y = self.grid_col*c, self.grid_row*c
        self.canvas.create_rectangle(
            x, y, x+c, y+c,
            outline="#f1c40f", width=3,
            tags=(f"psel_{id(self)}", "sel_ring", "token_layer"))
        self.canvas.tag_raise("token_layer")
        self.show_move_counter()

    def deselect(self):
        self.canvas.delete(f"psel_{id(self)}")
        self.hide_move_counter()

    def move_to(self, cell_px):
        self.cell_px = cell_px
        x, y, half = self.grid_col*cell_px, self.grid_row*cell_px, cell_px//2

        if self._img_path and self._photo and PIL_OK:
            try:
                img = Image.open(self._img_path).resize(
                    (cell_px, cell_px), Image.LANCZOS)
                self._photo = ImageTk.PhotoImage(img)
                self.canvas.coords(self.oval, x, y)
                self.canvas.itemconfig(self.oval, image=self._photo)
            except Exception:
                pass
        else:
            self.canvas.coords(self.oval, x, y, x+cell_px, y+cell_px)

        if self.own_ring:
            self.canvas.coords(self.own_ring,
                               x-2, y-2, x+cell_px+2, y+cell_px+2)

        self.canvas.coords(self.text,     x+half, y+cell_px+8)
        self.canvas.coords(self.move_lbl, x+half, y-8)
        self.canvas.delete(f"psel_{id(self)}")

    def _move_cost(self, dc, dr):
        return 2 if dc != 0 and dr != 0 else 1

    def can_move(self, dc, dr):
        return self.moves_left >= self._move_cost(dc, dr)

    def spend_move(self, dc, dr):
        self.moves_left = max(0, self.moves_left - self._move_cost(dc, dr))

    def reset_movement(self):
        self.moves_left = self.speed

    def _snap_back(self):
        c = self.cell_px
        ox, oy = self._drag_start_col*c, self._drag_start_row*c
        if self._photo and PIL_OK:
            self.canvas.coords(self.oval, ox, oy)
        else:
            self.canvas.coords(self.oval, ox, oy, ox+c, oy+c)
        self.canvas.coords(self.text,     ox+c//2, oy+c+8)
        self.canvas.coords(self.move_lbl, ox+c//2, oy-8)

    def _on_press(self, event):
        self._drag_x, self._drag_y = event.x, event.y
        self._drag_start_col = self.grid_col
        self._drag_start_row = self.grid_row
        self.canvas.tag_raise(self.oval)
        self.canvas.tag_raise(self.text)
        self.select()

    def _on_drag(self, event):
        dx, dy = event.x-self._drag_x, event.y-self._drag_y
        self.canvas.move(self.oval,     dx, dy)
        self.canvas.move(self.text,     dx, dy)
        self.canvas.move(self.move_lbl, dx, dy)
        if self.own_ring:
            self.canvas.move(self.own_ring, dx, dy)
        self._drag_x, self._drag_y = event.x, event.y

    def _on_release(self, event):
        c = self.cell_px
        coords  = self.canvas.coords(self.oval)
        raw_x, raw_y = coords[0], coords[1]
        snapped_x = round(raw_x/c)*c
        snapped_y = round(raw_y/c)*c
        new_col   = int(snapped_x/c)
        new_row   = int(snapped_y/c)
        dest      = f"{col_to_letters(new_col)}{new_row+1}"
        ctype     = self.canvas.mapstate.get(dest,"")

        if CELL_TYPES.get(ctype,{}).get("collision",False):
            self._snap_back(); return

        d_col  = abs(new_col - self._drag_start_col)
        d_row  = abs(new_row - self._drag_start_row)
        steps  = max(d_col, d_row)
        cost   = steps + (steps//2 if (d_col>0 and d_row>0) else 0)

        if cost > self.moves_left:
            self._snap_back()
            messagebox.showwarning("Out of Movement",
                f"You only have {self.moves_left} move(s) left!")
            return

        dx, dy = snapped_x-raw_x, snapped_y-raw_y
        self.canvas.move(self.oval,     dx, dy)
        self.canvas.move(self.text,     dx, dy)
        self.canvas.move(self.move_lbl, dx, dy)
        if self.own_ring:
            self.canvas.move(self.own_ring, dx, dy)

        self.grid_col   = new_col
        self.grid_row   = new_row
        self.moves_left = max(0, self.moves_left-cost)
        self.select()

        # Janus check
        jdest = find_janus_destination(dest, self.canvas.mapstate)
        if jdest:
            dc, dr = coord_to_col_row(jdest)
            self.grid_col, self.grid_row = dc, dr
            self.canvas.coords(self.oval,     dc*c, dr*c, dc*c+c, dr*c+c)
            self.canvas.coords(self.text,     dc*c+c//2, dr*c+c+8)
            self.canvas.coords(self.move_lbl, dc*c+c//2, dr*c-8)
            if self.own_ring:
                self.canvas.coords(self.own_ring,
                                   dc*c-2, dr*c-2,
                                   dc*c+c+2, dr*c+c+2)
            self.select()

        if hasattr(self.canvas, "_redraw_fn"):
            self.canvas._redraw_fn()

    def _on_right_click(self, event):
        menu = tk.Menu(self.canvas, tearoff=0)
        menu.add_command(label="⚙️  Properties",
                         command=self.open_properties)
        menu.tk_popup(event.x_root, event.y_root)

    def open_properties(self):
        win = tk.Toplevel(self.canvas)
        win.title(f"Properties — {self.label}")
        win.geometry("280x300")
        win.resizable(False, False)
        win.grab_set()

        fields = {}

        def field(parent, label, val, row):
            tk.Label(parent, text=label, anchor="w",
                     width=16).grid(row=row, column=0, padx=8, pady=4)
            var = tk.StringVar(value=str(val))
            tk.Entry(parent, textvariable=var,
                     width=8, justify="center").grid(
                row=row, column=1, padx=8, pady=4)
            return var

        id_f = ttk.LabelFrame(win, text=" Identity ")
        id_f.pack(fill="x", padx=10, pady=(10,4))
        fields["hp"]    = field(id_f, "HP:", self.hp or "", 0)

        vis_f = ttk.LabelFrame(win, text=" Vision & Light ")
        vis_f.pack(fill="x", padx=10, pady=4)
        fields["vision_range"] = field(vis_f, "Vision Range:",
                                       self.vision_range, 0)
        fields["light_radius"] = field(vis_f, "Light Radius:",
                                       self.light_radius, 1)
        fields["dim_radius"]   = field(vis_f, "Dim Radius:",
                                       self.dim_radius,   2)
        fields["darkvision"]   = field(vis_f, "Darkvision:",
                                       self.darkvision,   3)

        def apply():
            try:
                self.hp           = fields["hp"].get().strip() or None
                self.vision_range = int(fields["vision_range"].get() or 0)
                self.light_radius = int(fields["light_radius"].get() or 0)
                self.dim_radius   = int(fields["dim_radius"].get() or 0)
                self.darkvision   = int(fields["darkvision"].get() or 0)
                self._update_text()
                if hasattr(self.canvas, "_redraw_fn"):
                    self.canvas._redraw_fn()
            except ValueError:
                messagebox.showwarning("Invalid",
                    "Please enter whole numbers.")
                return
            win.destroy()

        tk.Button(win, text="✅ Apply", command=apply,
                  bg="#27ae60", fg="white",
                  font=("Arial",10,"bold")).pack(pady=10)

    def _update_hp_display(self):
        val = simpledialog.askstring("HP Display",
                                     "Your HP (e.g. 24/45):",
                                     initialvalue=self.hp or "")
        if val is not None:
            self.hp = val; self._update_text()

    def _set_light(self):
        val = simpledialog.askinteger("Light Radius",
                                      "Bright light radius in squares:",
                                      initialvalue=self.light_radius,
                                      minvalue=0, maxvalue=24)
        if val is not None:
            self.light_radius = val
            if hasattr(self.canvas, "_redraw_fn"):
                self.canvas._redraw_fn()

    def _set_darkvision(self):
        val = simpledialog.askinteger("Darkvision",
                                      "Darkvision radius in squares:",
                                      initialvalue=self.darkvision,
                                      minvalue=0, maxvalue=24)
        if val is not None:
            self.darkvision = val
            if hasattr(self.canvas, "_redraw_fn"):
                self.canvas._redraw_fn()

    def remove(self):
        self.canvas.delete(f"psel_{id(self)}")
        self.canvas.delete(self.oval)
        self.canvas.delete(self.text)
        self.canvas.delete(self.move_lbl)
        if self.own_ring:
            self.canvas.delete(self.own_ring)

# ---------------------------------------------------------------------------
# SCENE IMAGE  (read-only, no handles, no drag)
# ---------------------------------------------------------------------------

class PlayerSceneImage:
    def __init__(self, canvas, path, x=0, y=0, base_w=None, base_h=None):
        self.canvas  = canvas
        self.path    = path
        self.x       = x
        self.y       = y
        self._raw    = None
        self._photo  = None
        self._id     = str(id(self))

        if PIL_OK:
            try:
                self._raw   = Image.open(path)
                self.base_w = base_w or self._raw.width
                self.base_h = base_h or self._raw.height
            except Exception:
                self.base_w = base_w or 400
                self.base_h = base_h or 300
        else:
            self.base_w = base_w or 400
            self.base_h = base_h or 300

    def draw(self, zoom):
        self.canvas.delete(f"psi_{self._id}")
        w  = max(1, int(self.base_w * zoom))
        h  = max(1, int(self.base_h * zoom))
        sx = int(self.x * zoom)
        sy = int(self.y * zoom)

        if PIL_OK and self._raw:
            scaled      = self._raw.resize((w, h), Image.LANCZOS)
            self._photo = ImageTk.PhotoImage(scaled)
            self.canvas.create_image(
                sx, sy, anchor="nw", image=self._photo,
                tags=("map_layer", f"psi_{self._id}"))
        else:
            self.canvas.create_rectangle(
                sx, sy, sx+w, sy+h,
                fill="#333355", outline="#666688",
                tags=("map_layer", f"psi_{self._id}"))

    def delete(self):
        self.canvas.delete(f"psi_{self._id}")

# ---------------------------------------------------------------------------
# MAIN BUILD FUNCTION
# ---------------------------------------------------------------------------

def build_player_vtt_tab(parent, get_char_name):
    """
    parent        — the player VTT tab Frame
    get_char_name — callable returning current character name string
    """

    # -----------------------------------------------------------------------
    # GUARD: character must exist before entering
    # -----------------------------------------------------------------------
    def check_character():
        name = get_char_name().strip()
        if not name or name.lower() in ("name", ""):
            messagebox.showinfo(
                "Create a Character First",
                "You need to create a character before using the Battle Map.\n\n"
                "Go to the Character tab and use the ✨ New Character wizard,\n"
                "or enter your character name manually."
            )
            return None
        return name

    # -----------------------------------------------------------------------
    # STATE
    # -----------------------------------------------------------------------
    state = {
        "cell_px":          30,
        "show_grid":        True,
        "tokens":           [],       # list of PlayerToken
        "own_token":        None,     # PlayerToken that belongs to this player
        "scene_images":     [],       # list of PlayerSceneImage
        "scene_name":       "",
        "canvas_cols":      52,
        "canvas_rows":      100,
        "darkness_enabled": True,     # darkness ON by default for players
        "polling":          False,
    }

    zoom_level = [1.0]

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
    vtt_canvas.mapstate = {}

    h_scroll = tk.Scrollbar(canvas_frame, orient="horizontal",
                             command=vtt_canvas.xview)
    v_scroll = tk.Scrollbar(canvas_frame, orient="vertical",
                             command=vtt_canvas.yview)
    vtt_canvas.config(xscrollcommand=h_scroll.set,
                      yscrollcommand=v_scroll.set)
    h_scroll.pack(side="bottom", fill="x")
    v_scroll.pack(side="right",  fill="y")

    # -----------------------------------------------------------------------
    # REDRAW ALL
    # -----------------------------------------------------------------------
    def redraw_all():
        z  = zoom_level[0]
        c  = state["cell_px"]
        sc = max(4, int(c * z))

        # --- MAP LAYER ---
        vtt_canvas.delete("map_layer")
        for si in state["scene_images"]:
            si.draw(z)

        # --- TILE LAYER ---
        vtt_canvas.delete("grid")
        vtt_canvas.delete("gridlabel")
        vtt_canvas.delete("mapstate_tile")

        gw = state["canvas_cols"] * sc
        gh = state["canvas_rows"] * sc
        vtt_canvas.config(scrollregion=(0, 0, gw+sc*2, gh+sc*2))

        if state["show_grid"]:
            for x in range(0, gw+sc, sc):
                vtt_canvas.create_line(x, 0, x, gh,
                    fill="#444466", width=1,
                    tags=("tile_layer","grid"))
            for y in range(0, gh+sc, sc):
                vtt_canvas.create_line(0, y, gw, y,
                    fill="#444466", width=1,
                    tags=("tile_layer","grid"))

            lf = ("Arial", max(6, sc//6), "bold")
            for ci in range(state["canvas_cols"]):
                vtt_canvas.create_text(
                    ci*sc+sc//2, 8,
                    text=col_to_letters(ci),
                    fill="#aaaacc", font=lf,
                    tags=("tile_layer","gridlabel"))
            for ri in range(state["canvas_rows"]):
                vtt_canvas.create_text(
                    6, ri*sc+sc//2,
                    text=str(ri+1),
                    fill="#aaaacc", font=lf, anchor="w",
                    tags=("tile_layer","gridlabel"))

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

        # --- TOKEN LAYER ---
        for tok in state["tokens"]:
            tok.move_to(sc)

        # --- DARKNESS LAYER ---
        vtt_canvas.delete("darkness_layer")

        if state["darkness_enabled"]:
            own = state["own_token"]
            if own:
                # Build bright and dim cell sets from own token only
                bright_cells = set()
                dim_cells    = set()
                col, row     = own.grid_col, own.grid_row

                if own.light_radius > 0:
                    for dc in range(-own.light_radius, own.light_radius+1):
                        for dr in range(-own.light_radius, own.light_radius+1):
                            if max(abs(dc), abs(dr)) <= own.light_radius:
                                bright_cells.add((col+dc, row+dr))

                if own.darkvision > 0:
                    for dc in range(-own.darkvision, own.darkvision+1):
                        for dr in range(-own.darkvision, own.darkvision+1):
                            if max(abs(dc), abs(dr)) <= own.darkvision:
                                cell = (col+dc, row+dr)
                                if cell not in bright_cells:
                                    dim_cells.add(cell)

                # Check visible enemy tokens — add their light if visible
                for tok in state["tokens"]:
                    if tok is own or tok.token_type == "player":
                        continue
                    dx  = tok.grid_col - col
                    dy  = tok.grid_row - row
                    vis = own.light_radius > 0 and \
                          max(abs(dx), abs(dy)) <= own.light_radius
                    if vis and tok.light_radius > 0:
                        for dc in range(-tok.light_radius, tok.light_radius+1):
                            for dr in range(-tok.light_radius, tok.light_radius+1):
                                if max(abs(dc),abs(dr)) <= tok.light_radius:
                                    bright_cells.add(
                                        (tok.grid_col+dc, tok.grid_row+dr))

                # Draw darkness
                for ci in range(state["canvas_cols"]):
                    for ri in range(state["canvas_rows"]):
                        cell = (ci, ri)
                        x, y = ci*sc, ri*sc
                        if cell in bright_cells:
                            continue
                        elif cell in dim_cells:
                            vtt_canvas.create_rectangle(
                                x, y, x+sc, y+sc,
                                fill="grey10", stipple="gray75",
                                outline="",
                                tags="darkness_layer")
                        else:
                            vtt_canvas.create_rectangle(
                                x, y, x+sc, y+sc,
                                fill="black", outline="",
                                tags="darkness_layer")
            else:
                # No own token — full darkness
                vtt_canvas.create_rectangle(
                    0, 0, gw+sc*2, gh+sc*2,
                    fill="black", outline="",
                    tags="darkness_layer")

        # --- DRAW ORDER ---
        vtt_canvas.tag_lower("tile_layer")
        vtt_canvas.tag_lower("map_layer")
        vtt_canvas.tag_raise("tile_layer")
        vtt_canvas.tag_raise("darkness_layer")
        vtt_canvas.tag_raise("token_layer")

    vtt_canvas._redraw_fn = redraw_all

    # -----------------------------------------------------------------------
    # ZOOM
    # -----------------------------------------------------------------------
    def zoom(factor):
        nz = zoom_level[0] * factor
        if not (0.1 <= nz <= 8.0): return
        zoom_level[0] = nz
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
        coord_label.config(text=f"{col_to_letters(col)}{row+1}")
        lx = min(event.x+12, vtt_canvas.winfo_width()-70)
        ly = min(event.y+12, vtt_canvas.winfo_height()-24)
        coord_label.place(x=lx, y=ly)

    vtt_canvas.bind("<Motion>", on_mouse_move)
    vtt_canvas.bind("<Leave>",  lambda e: coord_label.place_forget())

    # -----------------------------------------------------------------------
    # LOAD SCENE FROM FILE
    # -----------------------------------------------------------------------
    def _load_scene_file(scene_file, char_name, darkness):
        """Load a scene JSON and populate canvas."""
        # Try campaign/scenes/ first
        path = os.path.join(SCENES_DIR, scene_file)
        if not os.path.exists(path):
            # Try as absolute path
            path = scene_file
        if not os.path.exists(path):
            messagebox.showerror("Scene Not Found",
                f"Could not find scene file:\n{scene_file}\n\n"
                f"Make sure your campaign folder is up to date.")
            return

        try:
            with open(path) as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror("Load Error", str(e))
            return

        # Clear canvas
        vtt_canvas.delete("all")
        state["scene_images"].clear()
        state["tokens"].clear()
        state["own_token"]    = None
        vtt_canvas.mapstate   = {}

        state["scene_name"]       = data.get("scene_name","Scene")
        state["canvas_cols"]      = data.get("canvas_cols", 52)
        state["canvas_rows"]      = data.get("canvas_rows",100)
        state["cell_px"]          = data.get("cell_px", 30)
        state["darkness_enabled"] = darkness
        vtt_canvas.mapstate       = data.get("cells",{})

        scene_name_var.set(state["scene_name"])

        # Load images
        for img_d in data.get("images",[]):
            img_path = img_d.get("path","")
            # Also check in campaign/maps/
            if not os.path.exists(img_path):
                img_path = os.path.join(MAPS_DIR,
                                        os.path.basename(img_path))
            if os.path.exists(img_path):
                si = PlayerSceneImage(
                    vtt_canvas, img_path,
                    x=img_d.get("x",0), y=img_d.get("y",0),
                    base_w=img_d.get("base_w"), base_h=img_d.get("base_h"))
                state["scene_images"].append(si)

        # Load tokens from sheet (live positions)
        sheet_tokens = pull_tokens_from_sheet()
        c = state["cell_px"]

        for td in sheet_tokens:
            is_own = td["name"].strip().lower() == char_name.strip().lower()
            color  = "#2980b9" if td["type"]=="player" else "#e74c3c"

            # Try to find token image in campaign/tokens/
            img_path = None
            img_name = td["name"].lower().replace(" ","_") + ".png"
            for search_dir in (PLAYER_DIR, ENEMY_DIR):
                candidate = os.path.join(search_dir, img_name)
                if os.path.exists(candidate):
                    img_path = candidate
                    break

            tok = PlayerToken(
                vtt_canvas, td["col"], td["row"], c,
                label=td["name"], color=color,
                img_path=img_path,
                speed=td.get("speed",6),
                hp=td.get("hp"),
                token_type=td["type"],
                is_own=is_own)

            # Restore light settings from scene file if saved
            for saved_tok in data.get("tokens",[]):
                if saved_tok.get("name","").strip().lower() == \
                   td["name"].strip().lower():
                    tok.light_radius  = saved_tok.get("light_radius", 0)
                    tok.dim_radius    = saved_tok.get("dim_radius",   0)   # ← add
                    tok.darkvision    = saved_tok.get("darkvision",   0)
                    tok.vision_range  = saved_tok.get("vision_range", 0)   # ← add
                    break

            state["tokens"].append(tok)
            if is_own:
                state["own_token"] = tok

        if state["own_token"] is None and sheet_tokens:
            messagebox.showwarning("Token Not Found",
                f"No token named '{char_name}' found on the map.\n"
                "Ask your DM to add your token.")

        redraw_all()
        messagebox.showinfo("Scene Loaded",
            f"✅ {state['scene_name']} loaded!\n"
            + (f"Your token: {char_name}" if state["own_token"]
               else "⚠️ Your token was not found on this map."))

    # -----------------------------------------------------------------------
    # SYNC FROM SHEET
    # -----------------------------------------------------------------------
    def sync_from_sheet():
        char_name = check_character()
        if not char_name:
            return

        info = pull_active_scene_from_sheet()
        if not info:
            return

        _load_scene_file(
            info["scene_file"],
            char_name,
            info["darkness"]
        )

    def sync_tokens_only():
        """Re-pull token positions without reloading the whole scene."""
        char_name = get_char_name().strip()
        if not char_name:
            return

        sheet_tokens = pull_tokens_from_sheet()
        c = state["cell_px"]

        for td in sheet_tokens:
            # Find matching existing token and update position
            for tok in state["tokens"]:
                if tok.label.strip().lower() == td["name"].strip().lower():
                    tok.grid_col = td["col"]
                    tok.grid_row = td["row"]
                    if td.get("hp"):
                        tok.hp = td["hp"]
                        tok._update_text()
                    break

        redraw_all()

    def push_own_position():
        """Push own token position back to the sheet."""
        char_name = check_character()
        if not char_name:
            return
        own = state["own_token"]
        if own is None:
            messagebox.showwarning("No Token",
                "Your token is not on the map.")
            return
        push_own_token_to_sheet(own, state["tokens"])
        messagebox.showinfo("Pushed", "✅ Your position pushed to sheet!")

    # -----------------------------------------------------------------------
    # AUTO POLL
    # -----------------------------------------------------------------------
    def start_polling():
        def poll():
            try:
                sync_tokens_only()
            except Exception:
                pass
            if state["polling"]:
                vtt_canvas.after(60000, poll)

        state["polling"] = True
        vtt_canvas.after(60000, poll)

    def stop_polling():
        state["polling"] = False

    # -----------------------------------------------------------------------
    # WASD  (own token only)
    # -----------------------------------------------------------------------
    def move_own_token(event):
        own = state["own_token"]
        if not own: return
        key = event.keysym.lower()
        dc = dr = 0
        if key=="w": dr=-1
        if key=="s": dr= 1
        if key=="a": dc=-1
        if key=="d": dc= 1
        nc = max(0, own.grid_col+dc)
        nr = max(0, own.grid_row+dr)
        coord = f"{col_to_letters(nc)}{nr+1}"
        ctype = vtt_canvas.mapstate.get(coord,"")

        if CELL_TYPES.get(ctype,{}).get("collision",False):
            return

        if not own.can_move(dc,dr):
            messagebox.showwarning("Out of Movement",
                "You have no moves left this turn!")
            return

        own.spend_move(dc,dr)
        own.grid_col, own.grid_row = nc, nr
        own.move_to(own.cell_px)
        own.select()
        redraw_all()

    vtt_canvas.bind("<w>", move_own_token)
    vtt_canvas.bind("<s>", move_own_token)
    vtt_canvas.bind("<a>", move_own_token)
    vtt_canvas.bind("<d>", move_own_token)

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
    # TOOLBAR WIDGETS
    # -----------------------------------------------------------------------
    scene_name_var = tk.StringVar(value="No scene loaded")

    tk.Label(toolbar, text="Scene:",
             font=("Arial",9,"bold")).pack(side="left")
    tk.Label(toolbar, textvariable=scene_name_var,
             fg="#2980b9",
             font=("Arial",9,"bold")).pack(side="left", padx=4)

    ttk.Separator(toolbar,orient="vertical").pack(side="left",fill="y",padx=6)

    tk.Button(toolbar, text="🔄 Sync Scene",
              command=sync_from_sheet,
              bg="#27ae60", fg="white",
              font=("Arial",9,"bold")).pack(side="left", padx=3)

    tk.Button(toolbar, text="🔄 Sync Tokens",
              command=sync_tokens_only,
              bg="#2980b9", fg="white",
              font=("Arial",8)).pack(side="left", padx=3)

    tk.Button(toolbar, text="⬆️ Push My Position",
              command=push_own_position,
              bg="#8e44ad", fg="white",
              font=("Arial",8)).pack(side="left", padx=3)

    ttk.Separator(toolbar,orient="vertical").pack(side="left",fill="y",padx=6)

    # Auto poll toggle
    polling_var = tk.BooleanVar(value=False)
    polling_btn = tk.Button(toolbar, text="⏸ Auto: OFF",
                            bg="#7f8c8d", fg="white",
                            font=("Arial",8))
    polling_btn.pack(side="left", padx=3)

    def toggle_polling():
        if not polling_var.get():
            polling_var.set(True)
            polling_btn.config(text="▶ Auto: ON", bg="#27ae60")
            start_polling()
        else:
            polling_var.set(False)
            polling_btn.config(text="⏸ Auto: OFF", bg="#7f8c8d")
            stop_polling()

    polling_btn.config(command=toggle_polling)

    ttk.Separator(toolbar,orient="vertical").pack(side="left",fill="y",padx=6)

    # Zoom
    tk.Label(toolbar,text="Zoom:",
             font=("Arial",9,"bold")).pack(side="left")
    tk.Button(toolbar, text="＋",
              command=lambda: zoom(1.25),
              font=("Arial",10,"bold"), width=2).pack(side="left",padx=1)
    tk.Button(toolbar, text="－",
              command=lambda: zoom(0.8),
              font=("Arial",10,"bold"), width=2).pack(side="left",padx=1)
    tk.Button(toolbar, text="⟳",
              command=lambda: [zoom_level.__setitem__(0,1.0), redraw_all()],
              font=("Arial",9)).pack(side="left",padx=2)

    ttk.Separator(toolbar,orient="vertical").pack(side="left",fill="y",padx=6)

    # Grid toggle
    grid_var = tk.BooleanVar(value=True)

    def toggle_grid():
        state["show_grid"] = grid_var.get(); redraw_all()

    tk.Checkbutton(toolbar, text="Grid",
                   variable=grid_var,
                   command=toggle_grid).pack(side="left",padx=4)

    ttk.Separator(toolbar,orient="vertical").pack(side="left",fill="y",padx=6)

    # Darkness toggle (player can turn it off if DM allows)
    darkness_var = tk.BooleanVar(value=True)

    def toggle_darkness():
        state["darkness_enabled"] = darkness_var.get()
        redraw_all()

    tk.Checkbutton(toolbar, text="🌑 Darkness",
                   variable=darkness_var,
                   command=toggle_darkness).pack(side="left",padx=4)

    # -----------------------------------------------------------------------
    # WELCOME MESSAGE  (shown on first open)
    # -----------------------------------------------------------------------
    welcome = tk.Label(
        vtt_canvas,
        text="⚔️  Battle Map\n\n"
             "Click  🔄 Sync Scene  to load the current map from your DM.\n\n"
             "Your token will appear automatically if your character name\n"
             "matches the token on the map.\n\n"
             "WASD to move  |  Scroll to zoom  |  Middle-click to pan",
        bg="#1a1a2e", fg="#aaaacc",
        font=("Arial",11), justify="center"
    )
    welcome.place(relx=0.5, rely=0.5, anchor="center")

    def hide_welcome(*_):
        welcome.place_forget()

    vtt_canvas.bind("<Button-1>", hide_welcome, add="+")
