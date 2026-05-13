import os
import re
import json
import sv_ttk
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
import random


import ctypes

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except:
    pass

# ---------------------------------------------------------------------------
# LOAD EXCEL DATA
# ---------------------------------------------------------------------------

IDENTITY_LABELS = {
    "race": "Race",
    "background": "Background",
    "class": "Class",
}

PROGRESSION_LABELS = {
    "name": "Feature",
    "description ": "Description",
    "class_level": "Level",
}

RESOURCE_LABELS = {
    "slot_1": "1st",
    "slot_2": "2nd",
    "slot_3": "3rd",
    "slot_4": "4th",
    "slot_5": "5th",
    "slot_6": "6th",
    "slot_7": "7th",
    "slot_8": "8th",
    "slot_9": "9th",
}

COLUMN_LABELS = {
    "weapons": {
        "Weapon": "Name",
        "Damage": "Damage",
        "Damage_Type": "Damage Type",
        "Simple or Martial": "Category",
        "Melee or Ranged": "Range Type",
        "Properties": "Properties",
        "Weight": "Weight",
        "Cost": "Cost"
    },
    "armors": {
        "Armor": "Name",
        "AC": "Armor Class",
        "Strength": "STR Req",
        "Stealth": "Stealth Penalty",
        "Style": "Style",
        "Weight": "Weight",
        "Cost": "Cost"
    },
    "items": {
        "Name": "Name",
        "Description": "Description",
        "Weight": "Weight",
        "Cost": "Cost"
    },
    "potions": {
        "Name": "Name",
        "Effect": "Effect",
        "Duration": "Duration",
        "Cost": "Cost"
    },
    "accessories": {
        "Name": "Name",
        "Effect": "Effect",
        "Rarity": "Rarity",
        "Weight": "Weight",
        "Cost": "Cost"
    }
}
HIT_DIE_MAP = {
    "Artificer": "d8",
    "Barbarian": "d12",
    "Bard": "d8",
    "Cleric": "d8",
    "Druid": "d8",
    "Fighter": "d10",
    "Monk": "d8",
    "Paladin": "d10",
    "Ranger": "d10",
    "Rogue": "d8",
    "Sorcerer": "d6",
    "Warlock": "d8",
    "Wizard": "d6",
}
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dnd_data.xlsx")

def load_excel_data():
    try:
        xl = pd.ExcelFile(DATA_FILE)

        # --- Class Data ---
        cd = pd.read_excel(xl, sheet_name="Class Data")
        # --- Identity Lists ---
        race_list = cd["Races"].dropna().unique().tolist()
        background_list = cd["Backgrounds"].dropna().unique().tolist()

        valid_classes = ["Artificer","Barbarian","Bard","Cleric","Druid","Fighter",
                         "Monk","Paladin","Ranger","Rogue","Sorcerer","Warlock","Wizard"]

        class_info_raw = cd[["Class","Spellcasting Ability","Hit Die"]].dropna(subset=["Class"])
        class_info_raw = class_info_raw[class_info_raw["Class"].isin(valid_classes)]

        class_info = {}
        for _, row in class_info_raw.iterrows():
            sa = str(row["Spellcasting Ability"]).strip()
            class_info[row["Class"]] = {
                "spell_ability": sa if sa not in ("nan","ALL") else "—",
                "hit_die":       str(row["Hit Die"]).strip() if pd.notna(row["Hit Die"]) else "—",
            }

        # Manual fixes: subclass-only casters and hit dice corrections
        for cls, sa in [("Fighter","INT*"),("Rogue","INT*")]:
            if cls in class_info:
                class_info[cls]["spell_ability"] = sa
        for cls in ("Barbarian","Monk"):
            if cls in class_info:
                class_info[cls]["spell_ability"] = "—"
        hit_die_fixes = {
            "Barbarian":"d12","Bard":"d8","Cleric":"d8","Druid":"d8",
            "Fighter":"d10","Monk":"d8","Paladin":"d10","Ranger":"d10",
            "Rogue":"d8","Sorcerer":"d6","Warlock":"d8","Wizard":"d6",
        }
        for cls, hd in hit_die_fixes.items():
            if cls in class_info:
                class_info[cls]["hit_die"] = hd

        # Class -> subclass mapping
        prog_df = pd.read_excel(xl, sheet_name="SHEETS_PROGRESSION")

        subclass_map = {}
        sub_df = prog_df[prog_df["type"] == "subclass"]

        for cls, group in sub_df.groupby("class_id"):
            subs = (
                group["subclass_id"]
                .dropna()
                .astype(str)
                .str.strip()
                .unique()
                .tolist()
            )
            subclass_map[cls] = sorted(set(subs))



        # --- Spell Data ---
        sp = pd.read_excel(xl, sheet_name="Spell Data")
        sp["classes"] = sp["classes"].fillna("")

        # --- Item Data ---
        ITEM_SHEETS = {
            "weapons": "SHEET_WEAPONS",
            "armors": "SHEET_ARMORS",
            "accessories": "SHEET_ACCES",
            "items": "SHEET_ITEMS",
            "potions": "SHEET_POTIONS",
        }
        item_sheets = {}
        for key, sheet_name in ITEM_SHEETS.items():
            try:
                df = pd.read_excel(xl, sheet_name=sheet_name)
                if df.empty:
                    print(f"Skipping empty sheet: {key}")
                item_sheets[key] = df
            except Exception as e:
                print(f"Error loading {sheet_name}: {e}")
                item_sheets[key] = pd.DataFrame()

        return class_info, subclass_map, sp, item_sheets, race_list, background_list, prog_df
        
    except FileNotFoundError:
        messagebox.showerror("Missing File",
            f"Cannot find dnd_data.xlsx\nExpected at:\n{DATA_FILE}")
        return {}, {}, pd.DataFrame()
    except Exception as e:
        messagebox.showerror("Load Error", str(e))
        return {}, {}, pd.DataFrame()


CLASS_INFO, SUBCLASS_MAP, SPELL_DF, ITEM_SHEETS, RACE_LIST, BACKGROUND_LIST, PROG_DF = load_excel_data()


known_listbox = None
equip_listbox = None
feats_listbox = None
feats_desc_text = None
# ---------------------------------------------------------------------------
# MATH ENGINE
# ---------------------------------------------------------------------------

def calculate_modifier(score):
    try:
        return (int(score) - 10) // 2
    except (ValueError, TypeError):
        return 0

def get_proficiency_bonus(level):
    try:
        return (int(level) - 1) // 4 + 2
    except (ValueError, TypeError):
        return 2

def fmt_mod(n):
    return f"+{n}" if n >= 0 else str(n)

def roll_d20(mod, advantage=0):
    rolls = [random.randint(1,20), random.randint(1,20)]

    if advantage == 1:
        roll = max(rolls)
        note = "Advantage"
    elif advantage == -1:
        roll = min(rolls)
        note = "Disadvantage"
    else:
        roll = rolls[0]
        note = "Normal"

    total = roll + mod

    messagebox.showinfo(
        "Roll Result",
        f"{note}\n🎲 Rolls: {rolls}\n\nTotal: {total}"
    )
    if roll == 20:
        crit_text = "🔥 CRITICAL SUCCESS!"
    elif roll == 1:
        crit_text = "💀 CRITICAL FAILURE!"
    else:
        crit_text = ""
    f"{note}\n🎲 Rolls: {rolls}\n{crit_text}\n\nTotal: {total}"

def update_hit_dice(*args):

    cls1 = class1_var.get()
    lvl1 = class1_level_var.get()

    cls2 = class2_var.get()
    lvl2 = class2_level_var.get()

    if cls1 in HIT_DIE_MAP and lvl1 > 0:
        hitdice1_var.set(f"{lvl1}{HIT_DIE_MAP[cls1]}")
    else:
        hitdice1_var.set("")

    if cls2 in HIT_DIE_MAP and lvl2 > 0:
        hitdice2_var.set(f"{lvl2}{HIT_DIE_MAP[cls2]}")
    else:
        hitdice2_var.set("")


# ---------------------------------------------------------------------------
# GLOBAL STATE
# ---------------------------------------------------------------------------
class Character:
    def __init__(self):
        self.name = ""
        self.level = 1

        self.stats = {
            "STR": 10,
            "DEX": 10,
            "CON": 10,
            "INT": 10,
            "WIS": 10,
            "CHA": 10,
        }

        self.hp_max = 10
        self.hp_cur = 10
        self.hp_tmp = 0

        self.class_name = ""
        self.subclass = ""
        self.race = ""
        self.background = ""

character = Character()
mods_hive          = {s: 0 for s in ["STR","DEX","CON","INT","WIS","CHA"]}
skill_labels       = []
mod_display_labels = {}
prof_info_label    = None
initiative_label   = None
level_var          = None
sb_vars            = {}

# Spell panel refs (set during build)
spell_class_var  = None
spell_level_var  = None
spell_search_var = None
spell_listbox    = None
spell_results    = []

# Inventory
inventory_state = {
    "weapons": [],
    "armor": [],
    "potions": [],
    "accessories": []
}
selected_feats = []

def add_placeholder(widget, text):

    widget.insert(0, text)

    try:
        widget.config(foreground="gray")
    except:
        widget.config(fg="gray")

    def on_focus_in(event):

        if widget.get() == text:

            widget.delete(0, tk.END)

            try:
                widget.config(foreground="black")
            except:
                widget.config(fg="black")

    def on_focus_out(event):

        if not widget.get():

            widget.insert(0, text)

            try:
                widget.config(foreground="gray")
            except:
                widget.config(fg="gray")

    widget.bind("<FocusIn>", on_focus_in)
    widget.bind("<FocusOut>", on_focus_out)
# ---------------------------------------------------------------------------
# UPDATE FUNCTIONS
# ---------------------------------------------------------------------------

def update_all_skills(*_):
    try:
        prof = get_proficiency_bonus(level_var.get())
    except Exception:
        prof = 2
    for label, stat, var in skill_labels:
        total = mods_hive.get(stat, 0) + (prof if var.get() else 0)
        label.config(text=fmt_mod(total))
    if initiative_label:
        initiative_label.config(text=fmt_mod(mods_hive.get("DEX", 0)))
    if prof_info_label:
        prof_info_label.config(text=f"Prof: {fmt_mod(prof)}")

def on_stat_change(stat, *_):
    try:
        mod = calculate_modifier(sb_vars[stat].get())
    except Exception:
        mod = 0
    mods_hive[stat] = mod
    if stat in mod_display_labels:
        mod_display_labels[stat].config(text=f"({fmt_mod(mod)})")
    update_all_skills()

def get_character_data():

    try:
        player_level = int(player_level_var.get())
    except:
        player_level = 0
    try:
        class1_level = int(class1_level_var.get())
    except:
        class1_level = 0
    try:
        class2_level = int(class2_level_var.get())
    except:
        class2_level = 0
    return {

        "player_level": player_level,

        "class1": {
            "name": class1_var.get(),
            "level": class1_level,
            "subclass": subclass1_var.get(),
        },

        "class2": {
            "name": class2_var.get(),
            "level": class2_level,
            "subclass": subclass2_var.get(),
        },

        "stats": {
            s: sb_vars[s].get()
            for s in sb_vars
        },

        "hp": {
            "max": hp_vars["max"].get(),
            "cur": hp_vars["cur"].get(),
            "tmp": hp_vars["tmp"].get(),
        },

        "race": race_var.get(),
        "background": background_var.get(),
    }
def save_character():
    data = get_character_data()

    file = tk.filedialog.asksaveasfilename(
        defaultextension=".json",
        filetypes=[("JSON Files", "*.json")]
    )

    if not file:
        return

    try:
        with open(file, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        messagebox.showerror("Save Error", str(e))

def load_character_data(data):

    try:

        # =========================
        # PLAYER LEVELS
        # =========================

        class1_level_var.set(
            data.get("class1", {}).get("level", 0)
        )

        class2_level_var.set(
            data.get("class2", {}).get("level", 0)
        )

        # =========================
        # STATS
        # =========================

        for stat, val in data.get("stats", {}).items():

            if stat in sb_vars:
                sb_vars[stat].set(val)

        # =========================
        # HP
        # =========================

        hp = data.get("hp", {})

        for key in ["max", "cur", "tmp"]:

            if key in hp and key in hp_vars:
                hp_vars[key].set(hp[key])

        # =========================
        # CLASS 1
        # =========================

        cls1 = data.get("class1", {}).get("name", "")

        if cls1:
            class1_var.set(cls1)

            subs = SUBCLASS_MAP.get(cls1, [])
            subclass1_box.config(values=subs)

        sub1 = data.get("class1", {}).get("subclass", "")

        if sub1:
            subclass1_var.set(sub1)

        # =========================
        # CLASS 2
        # =========================

        cls2 = data.get("class2", {}).get("name", "")

        if cls2:
            class2_var.set(cls2)

            subs = SUBCLASS_MAP.get(cls2, [])
            subclass2_box.config(values=subs)

        sub2 = data.get("class2", {}).get("subclass", "")

        if sub2:
            subclass2_var.set(sub2)

        # =========================
        # RACE / BACKGROUND
        # =========================

        race_var.set(
            data.get("race", "")
        )

        background_var.set(
            data.get("background", "")
        )

        # =========================
        # FORCE UI UPDATES
        # =========================

        #update_player_level()
        refresh_feats()
        update_all_skills()
        refresh_spells()

    except Exception as e:

        messagebox.showerror(
            "Load Error",
            str(e)
        )
def load_character():
    file = tk.filedialog.askopenfilename(
        filetypes=[("JSON Files", "*.json")]
    )

    if not file:
        return

    try:
        with open(file, "r") as f:
            data = json.load(f)
        load_character_data(data)
    except Exception as e:
        messagebox.showerror("Load Error", str(e))

# ---------------------------------------------------------------------------
# BUILD0: Chracter Feats
# ---------------------------------------------------------------------------

def build_feats_tab(parent):
    global feats_listbox, feats_desc_text

    main = tk.Frame(parent)
    main.pack(fill="both", expand=True)

    # Left = feature list
    left = tk.Frame(main)
    left.pack(side="left", fill="y", padx=5, pady=5)

    tk.Label(left, text="Features", font=("Arial", 10, "bold")).pack()

    feats_listbox = tk.Listbox(left, width=30, height=25)
    feats_listbox.pack(fill="y", expand=True)

    # Right = description
    right = tk.Frame(main)
    right.pack(side="left", fill="both", expand=True, padx=5, pady=5)

    tk.Label(right, text="Description", font=("Arial", 10, "bold")).pack()

    feats_desc_text = tk.Text(right, wrap="word")
    feats_desc_text.pack(fill="both", expand=True)

    feats_listbox.bind("<<ListboxSelect>>", show_feat_description)
def show_feat_description(event=None):

    sel = feats_listbox.curselection()

    if not sel:
        return

    index = sel[0]

    df = PROG_DF

    all_feats = pd.DataFrame()

    # =========================
    # CLASS 1
    # =========================

    cls1 = class1_var.get()
    sub1 = subclass1_var.get()

    try:
        lvl1 = int(class1_level_var.get())
    except:
        lvl1 = 0

    if cls1 and lvl1 > 0:

        class_feats_1 = df[
            (df["class_id"] == cls1) &
            (df["subclass_id"].isna()) &
            (df["class_level"] <= lvl1)
        ]

        if sub1:
            sub_feats_1 = df[
                (df["class_id"] == cls1) &
                (df["subclass_id"] == sub1) &
                (df["class_level"] <= lvl1)
            ]
        else:
            sub_feats_1 = pd.DataFrame()

        all_feats = pd.concat([
            all_feats,
            class_feats_1,
            sub_feats_1
        ])

    # =========================
    # CLASS 2
    # =========================

    cls2 = class2_var.get()
    sub2 = subclass2_var.get()

    try:
        lvl2 = int(class2_level_var.get())
    except:
        lvl2 = 0

    if cls2 and lvl2 > 0:

        class_feats_2 = df[
            (df["class_id"] == cls2) &
            (df["subclass_id"].isna()) &
            (df["class_level"] <= lvl2)
        ]

        if sub2:
            sub_feats_2 = df[
                (df["class_id"] == cls2) &
                (df["subclass_id"] == sub2) &
                (df["class_level"] <= lvl2)
            ]
        else:
            sub_feats_2 = pd.DataFrame()

        all_feats = pd.concat([
            all_feats,
            class_feats_2,
            sub_feats_2
        ])

    # =========================
    # SORT
    # =========================

    if all_feats.empty:
        return

    all_feats = all_feats.sort_values(by="class_level")
    row = all_feats.iloc[index]

    feats_desc_text.delete("1.0", tk.END)

    text = (
        f"{row['name']}\n\n"
        f"Class: {row['class_id']}\n"
        f"Level: {int(row['class_level'])}\n\n"
        f"{row['description']}"
    )

    feats_desc_text.insert("1.0", text)
def refresh_feats():

    if feats_listbox is None:
        return

    feats_listbox.delete(0, tk.END)

    df = PROG_DF

    all_feats = pd.DataFrame()

    # =========================
    # CLASS 1
    # =========================

    cls1 = class1_var.get()
    sub1 = subclass1_var.get()

    try:
        lvl1 = int(class1_level_var.get())
    except:
        lvl1 = 0

    if cls1 and lvl1 > 0:

        class_feats_1 = df[
            (df["class_id"] == cls1) &
            (df["subclass_id"].isna()) &
            (df["class_level"] <= lvl1)
        ]

        if sub1:
            sub_feats_1 = df[
                (df["class_id"] == cls1) &
                (df["subclass_id"] == sub1) &
                (df["class_level"] <= lvl1)
            ]
        else:
            sub_feats_1 = pd.DataFrame()

        all_feats = pd.concat([
            all_feats,
            class_feats_1,
            sub_feats_1
        ])

    # =========================
    # CLASS 2
    # =========================

    cls2 = class2_var.get()
    sub2 = subclass2_var.get()

    try:
        lvl2 = int(class2_level_var.get())
    except:
        lvl2 = 0

    if cls2 and lvl2 > 0:

        class_feats_2 = df[
            (df["class_id"] == cls2) &
            (df["subclass_id"].isna()) &
            (df["class_level"] <= lvl2)
        ]

        if sub2:
            sub_feats_2 = df[
                (df["class_id"] == cls2) &
                (df["subclass_id"] == sub2) &
                (df["class_level"] <= lvl2)
            ]
        else:
            sub_feats_2 = pd.DataFrame()

        all_feats = pd.concat([
            all_feats,
            class_feats_2,
            sub_feats_2
        ])

    # =========================
    # SORT + DISPLAY
    # =========================

    if all_feats.empty:
        return

    all_feats = all_feats.sort_values(by="class_level")

    for _, row in all_feats.iterrows():

        cls_name = row["class_id"]

        name = (
            f"{cls_name} "
            f"Lv {int(row['class_level'])} "
            f"- {row['name']}"
        )

        feats_listbox.insert(tk.END, name)
# ---------------------------------------------------------------------------
# BUILD000: CHARACTER IDENTITY
# ---------------------------------------------------------------------------

def build_identity(parent):
    frame = ttk.LabelFrame(parent, text=" Character Identity ")
    frame.pack(fill="x", padx=10, pady=5)
    global race_var, background_var

    global class1_var, subclass1_var
    global class2_var, subclass2_var

    global class1_level_var, class2_level_var
    global player_level_var
    global subclass1_box
    global subclass2_box
    # Row 0: Name / Level
    name_entry = tk.Entry(frame, width=18)
    name_entry.grid(row=0, column=0, padx=8, pady=4)
    add_placeholder(name_entry, "Name")
    player_level_var = tk.StringVar(value="0")

    tk.Label(frame, text="Player Lv:").grid(row=1, column=0, sticky="w", padx=2)
    tk.Label(
        frame,
        textvariable=player_level_var,
        fg="blue",
        font=("Arial", 10, "bold")
    ).grid(row=1, column=0,  padx=25, sticky="e")

# Row 2: Race / Background / Sex
# RACE
    race_var = tk.StringVar(value="Race")
    race_box = ttk.Combobox(
        frame,
        textvariable=race_var,
        values=["Race"] + RACE_LIST,
        width=16,
        state="readonly"
    )
    race_box.grid(row=0, column=1, padx=4, pady=4)

# BACKGROUND
    background_var = tk.StringVar(value="Background")
    background_box = ttk.Combobox(
        frame,
        textvariable=background_var,
        values=["Background"] + BACKGROUND_LIST,
        width=18,
        state="readonly"
    )
    background_box.grid(row=0, column=2, padx=4, pady=4)
# SEX
    sex_entry = tk.Entry(frame, width=10)
    sex_entry.grid(row=1, column=1, padx=1, pady=1, sticky="w")
    add_placeholder(sex_entry, "Sex")

# -------row1--------------
# CLASS 1
# -------------------------
    class_names = sorted(CLASS_INFO.keys()) if CLASS_INFO else ["—"]
    class1_var = tk.StringVar(value="Class")
    class1_box = ttk.Combobox(
        frame,
        values=["Class"] + class_names,
        textvariable=class1_var,
        width=14,
        state="readonly"
    )
    class1_box.grid(row=0, column=4, padx=0, pady=4)
    tk.Label(frame, text="Lv").grid(row=0, column=4, padx=60, sticky="e")
    class1_level_var = tk.StringVar(value="0")
    tk.Spinbox(
        frame,
        from_=0,
        to=20,
        textvariable=class1_level_var,
        width=4
    ).grid(row=0, column=4, padx=10, sticky="e")
    subclass1_var = tk.StringVar(value="SubClass")
    subclass1_box = ttk.Combobox(
        frame,
        values=["SubClass"], 
        textvariable=subclass1_var,
        width=18,
        state="readonly"
    )
    subclass1_box.grid(row=0, column=5, padx=0, pady=0)

# ------row2----------------
# CLASS 2
# -------------------------
    class2_var = tk.StringVar(value="Class")
    class2_box = ttk.Combobox(
        frame,
        values=["Class"] + class_names,
        textvariable=class2_var,
        width=14,
        state="readonly"
    )
    class2_box.grid(row=1, column=4, padx=4, pady=4)
    tk.Label(frame, text="Lv").grid(row=1, column=4, padx=60, sticky="e")
    class2_level_var = tk.StringVar(value="0")
    tk.Spinbox(
        frame,
        from_=0,
        to=20,
        textvariable=class2_level_var,
        width=4
    ).grid(row=1, column=4, padx=10, sticky="e")
    subclass2_var = tk.StringVar(value="SubClass")
    subclass2_box = ttk.Combobox(
        frame,
        values=["SubClass"], 
        textvariable=subclass2_var,
        width=18,
        state="readonly"
    )
    subclass2_box.grid(row=1, column=5, padx=0, pady=4)

    
    # Row 3: Auto-filled readouts
    tk.Label(frame, text="Spell Ability:").grid(row=1, column=2, sticky="w", padx=4)
    spell_ability_lbl = tk.Label(frame, text="—", fg="blue", font=("Arial",10,"bold"))
    spell_ability_lbl.grid(row=1, column=2, sticky="e", padx=5)
    
    def on_class1_selected(event=None):
        cls = class1_var.get()

        info = CLASS_INFO.get(cls, {})

        spell_ability_lbl.config(text=info.get("spell_ability", "—"))

        subs = SUBCLASS_MAP.get(cls, [])
        subclass1_box.config(values=subs)

        subclass1_var.set("")

        refresh_feats()
    def on_class2_selected(event=None):
        cls = class2_var.get()

        subs = SUBCLASS_MAP.get(cls, [])
        subclass2_box.config(values=subs)

        subclass2_var.set("")

        refresh_feats()

    def update_player_level(*args):
        try:
            lv1 = int(class1_level_var.get())
        except:
            lv1 = 0

        try:
            lv2 = int(class2_level_var.get())
        except:
            lv2 = 0

        total = lv1 + lv2

        player_level_var.set(str(total))

    class1_level_var.trace_add("write", update_player_level)
    class2_level_var.trace_add("write", update_player_level)
    update_all_skills()
    refresh_feats()
    class1_box.bind("<<ComboboxSelected>>", on_class1_selected)
    class2_box.bind("<<ComboboxSelected>>", on_class2_selected)

    subclass1_box.bind("<<ComboboxSelected>>", lambda e: refresh_feats())
    subclass2_box.bind("<<ComboboxSelected>>", lambda e: refresh_feats())
    level_var.trace_add("write", lambda *args: refresh_feats())
    class1_var.trace_add("write", update_hit_dice)
    class2_var.trace_add("write", update_hit_dice)

    class1_level_var.trace_add("write", update_hit_dice)
    class2_level_var.trace_add("write", update_hit_dice)
def build_save_load(parent):
    frame = tk.Frame(parent)
    frame.pack(fill="x", padx=10, pady=5)

def build_ability_scores(parent):
    frame = ttk.LabelFrame(parent, text=" Ability Scores ")
    frame.pack(fill="x", padx=10, pady=5)
    for i, stat in enumerate(["STR","DEX","CON","INT","WIS","CHA"]):
        col = tk.Frame(frame)
        col.grid(row=0, column=i, padx=12, pady=6)
        tk.Label(col, text=stat, font=("Arial",10,"bold")).pack()
        tk.Spinbox(col, from_=1, to=30, textvariable=sb_vars[stat], width=4,
                   command=lambda s=stat: on_stat_change(s)).pack()
        sb_vars[stat].trace_add("write", lambda *_, s=stat: on_stat_change(s))
        lbl = tk.Label(col, text="(+0)", fg="gray")
        lbl.pack()
        mod_display_labels[stat] = lbl

def build_combat_hud(parent):
    global initiative_label
    frame = ttk.LabelFrame(parent, text=" Combat & Actions ")
    frame.pack(side="left", fill="both", expand=True, padx=5)

    # Quick-stat bubbles
    top = tk.Frame(frame)
    top.pack(fill="x", pady=(6,2))

    def editable_bubble(container, label_text, default="10"):
        b = tk.Frame(container, relief="groove", bd=1)
        b.pack(side="left", padx=8)
        tk.Label(b, text=label_text, font=("Arial",8)).pack()
        var = tk.StringVar(value=default)
        tk.Entry(b, textvariable=var, width=5,
                 font=("Arial",13,"bold"), justify="center").pack(padx=4, pady=2)
        return var

    editable_bubble(top, "AC", "10")

    init_b = tk.Frame(top, relief="groove", bd=1)
    init_b.pack(side="left", padx=8)
    tk.Label(init_b, text="Initiative", font=("Arial",8)).pack()
    initiative_label = tk.Label(init_b, text="+0",
                                 font=("Arial",13,"bold"), fg="blue", width=4)
    initiative_label.pack(padx=4, pady=2)

    editable_bubble(top, "Speed (ft)", "30")
    editable_bubble(top, "Passive Perc.", "10")

    # HP Tracker
    hp_frame = ttk.LabelFrame(frame, text=" Hit Points ")
    hp_frame.pack(fill="x", padx=6, pady=6)
    global hp_vars
    hp_vars = {k: tk.StringVar(value=v)
               for k,v in [("max","10"),("cur","10"),("tmp","0")]}
    for col,(key,lbl,fg) in enumerate([("max","Max HP","black"),
                                        ("cur","Current HP","green"),
                                        ("tmp","Temp HP","purple")]):
        cell = tk.Frame(hp_frame)
        cell.grid(row=0, column=col, padx=10, pady=4)
        tk.Label(cell, text=lbl, font=("Arial",8)).pack()
        tk.Entry(cell, textvariable=hp_vars[key], width=6,
                 font=("Arial",13,"bold"), justify="center", fg=fg).pack()
    # -------------------------
    # HIT DICE
    # -------------------------

    hitdice_cell = tk.Frame(hp_frame)
    hitdice_cell.grid(row=0, column=4, rowspan=2, padx=14)

    tk.Label(
        hitdice_cell,
        text="Hit Dice",
        font=("Arial",8,"bold")
    ).pack()

    hitdice1_var = tk.StringVar(value="")
    hitdice2_var = tk.StringVar(value="")

    tk.Entry(
        hitdice_cell,
        textvariable=hitdice1_var,
        width=6,
        justify="center",
        font=("Arial",11,"bold")
    ).pack(pady=1)

    tk.Entry(
        hitdice_cell,
        textvariable=hitdice2_var,
        width=6,
        justify="center",
        font=("Arial",11,"bold")
    ).pack(pady=1)
    def adjust_hp(delta):
        try:
            hp_vars["cur"].set(str(max(0, min(int(hp_vars["max"].get()),
                                              int(hp_vars["cur"].get()) + delta))))
        except ValueError:
            pass

    btn_row = tk.Frame(hp_frame)
    btn_row.grid(row=1, column=0, columnspan=3, pady=4)
    amt_var = tk.StringVar()

    def apply_amt(sign):
        try:
            adjust_hp(sign * int(amt_var.get())); amt_var.set("")
        except ValueError:
            pass

    tk.Button(btn_row, text="– Damage", bg="#c0392b", fg="white",
              command=lambda: adjust_hp(-1)).pack(side="left", padx=3)
    tk.Button(btn_row, text="+ Heal", bg="#27ae60", fg="white",
              command=lambda: adjust_hp(1)).pack(side="left", padx=3)
    tk.Entry(btn_row, textvariable=amt_var, width=5, justify="center").pack(side="left", padx=3)
    tk.Label(btn_row, text="amt").pack(side="left")
    tk.Button(btn_row, text="Apply–", bg="#c0392b", fg="white",
              command=lambda: apply_amt(-1)).pack(side="left", padx=2)
    tk.Button(btn_row, text="Apply+", bg="#27ae60", fg="white",
              command=lambda: apply_amt(1)).pack(side="left", padx=2)

    # Weapon slots
    wp_frame = ttk.LabelFrame(frame, text=" Weapon / Attack Slots ")
    wp_frame.pack(fill="x", padx=6, pady=6)
    for col,(hdr,w) in enumerate([("Weapon",14),("To Hit",7),("Damage",8),("Type",8)]):
        tk.Label(wp_frame, text=hdr, font=("Arial",8,"bold"),
                 width=w, anchor="center").grid(row=0, column=col, padx=3, pady=2)
    for r in range(1,4):
        for col,w in enumerate([14,7,8,8]):
            tk.Entry(wp_frame, width=w, justify="center").grid(
                row=r, column=col, padx=3, pady=2)

def build_utility(parent):
    frame = ttk.LabelFrame(parent, text=" Tools & Utility ")
    frame.pack(side="left", fill="both", padx=5)
    for util in ["Thieves' Tools","Cook's Utensils","Herbalism Kit",
                 "Alchemist's Supplies","Woodcarver's Tools"]:
        row = tk.Frame(frame)
        row.pack(fill="x", anchor="w", pady=2)
        tk.Checkbutton(row, variable=tk.BooleanVar()).pack(side="left")
        tk.Label(row, text=util, anchor="w").pack(side="left")

def build_skills(parent):
    global prof_info_label
    frame = ttk.LabelFrame(parent, text=" Core Skills ")
    frame.pack(side="left", fill="both", padx=5)
    prof_info_label = tk.Label(frame, text="Prof: +2", font=("Arial",8), fg="gray")
    prof_info_label.pack(anchor="w", padx=4)
    for name, stat in [
        ("Acrobatics","DEX"),("Animal Handling","WIS"),("Arcana","INT"),
        ("Athletics","STR"),("Deception","CHA"),("History","INT"),
        ("Insight","WIS"),("Intimidation","CHA"),("Investigation","INT"),
        ("Medicine","WIS"),("Nature","INT"),("Perception","WIS"),
        ("Performance","CHA"),("Persuasion","CHA"),("Religion","INT"),
        ("Sleight of Hand","DEX"),("Stealth","DEX"),("Survival","WIS"),
    ]:
        row = tk.Frame(frame)
        row.pack(fill="x", anchor="w", pady=1)
        prof_var = tk.BooleanVar()
        tk.Checkbutton(row, variable=prof_var, command=update_all_skills).pack(side="left")
        tk.Label(row, text=f"{name} ({stat})", width=20, anchor="w").pack(side="left")
        lbl = tk.Label(row, text="+0", fg="blue", font=("Arial",10,"bold"), width=4)
        lbl.pack(side="right")
        # Inside build_skills(parent) loop:
        btn = tk.Button(row, text="🎲")
        btn.pack(side="right")
        def handle_click(event, stat, prof_var, mode):
            event.widget.config(relief="raised")
            roll_skill(stat, prof_var, mode)
        # Bind the three click types
        btn.bind("<Button-1>",       lambda e, s=stat, v=prof_var: roll_skill(s, v, 0))
        btn.bind("<Shift-Button-1>", lambda e, s=stat, v=prof_var: roll_skill(s, v, 1))
        btn.bind("<Button-3>",       lambda e, s=stat, v=prof_var: roll_skill(s, v, -1))
        skill_labels.append((lbl, stat, prof_var))

def roll_skill(stat, prof_var, mode):
    # mode: 0 = Normal, 1 = Advantage, -1 = Disadvantage
    roll1 = random.randint(1, 20)
    roll2 = random.randint(1, 20)
    
    if mode == 1:
        roll = max(roll1, roll2)
        rolls_shown = [roll1, roll2]
        note = "Advantage"
        detail = f"[{roll1}, {roll2}]"
    elif mode == -1:
        roll = min(roll1, roll2)
        rolls_shown = [roll1, roll2]
        note = "Disadvantage"
        detail = f"[{roll1}, {roll2}]"
    else:
        roll = roll1
        rolls_shown = [roll1]
        note = "Normal"
        detail = f"[{roll1}]"      

  
    mod = mods_hive.get(stat, 0)
    prof = get_proficiency_bonus(level_var.get()) if prof_var.get() else 0
    total = roll + mod + prof

    result_text = f"{stat} ({note}): {detail} {fmt_mod(mod+prof)} = Total: {total}"
    tray_label.config(text=result_text)
    result_text = f"{stat} ({note}): {detail} {fmt_mod(mod+prof)} = Total: {total}\n"
    
    # Update the History box
    tray_history.config(state="normal") # Unlock
    tray_history.insert("1.0", result_text) # Insert at the top[cite: 1]
    tray_history.config(state="disabled") # Relock[cite: 1]


    if roll == 20: tray_label.config(fg="green")
    elif roll == 1: tray_label.config(fg="red")
    else: tray_label.config(fg="#2c3e50")

# ---------------------------------------------------------------------------
# BUILD001: SPELL LOOKUP PANEL
# ---------------------------------------------------------------------------

def refresh_spells(*_):
    if SPELL_DF.empty or spell_listbox is None:
        return
    cls   = spell_class_var.get()
    level = spell_level_var.get()
    query = spell_search_var.get().strip().lower()

    df = SPELL_DF.copy()
    if cls and cls != "All":
        df = df[df["classes"].str.contains(cls, case=False, na=False)]
    if level != "All":
        try:
            df = df[df["level"] == int(level)]
        except ValueError:
            pass
    if query:
        df = df[df["name"].str.lower().str.contains(query, na=False)]

    df = df.sort_values(["level","name"])
    spell_listbox.delete(0, tk.END)
    spell_results.clear()
    for _, row in df.iterrows():
        lvl_str = "Cantrip" if row["level"] == 0 else f"Lvl {row['level']}"
        spell_listbox.insert(tk.END, f"{row['name']}  [{lvl_str}]")
        spell_results.append(row.to_dict())
    count_label.config(text=f"{len(spell_results)} spells")


def show_spell_detail(event=None):
    sel = spell_listbox.curselection()
    if not sel or not spell_results:
        return
    s = spell_results[sel[0]]

    win = tk.Toplevel(root)
    win.title(s["name"])
    win.geometry("540x500")

    header = tk.Frame(win, bg="#2c3e50", pady=8)
    header.pack(fill="x")
    tk.Label(header, text=s["name"], font=("Arial",14,"bold"),
             fg="white", bg="#2c3e50").pack()
    lvl_txt = "Cantrip" if s["level"] == 0 else f"Level {s['level']}"
    tk.Label(header, text=f"{lvl_txt}  •  {s.get('school','')}",
             fg="#bdc3c7", bg="#2c3e50").pack()

    info = tk.Frame(win, padx=10, pady=6)
    info.pack(fill="x")

    def info_row(label, value):
        r = tk.Frame(info)
        r.pack(fill="x", pady=1)
        tk.Label(r, text=f"{label}:", width=14, anchor="w",
                 font=("Arial",9,"bold")).pack(side="left")
        tk.Label(r, text=str(value), anchor="w", wraplength=340,
                 justify="left").pack(side="left")

    info_row("Casting Time", s.get("casting_time","—"))
    info_row("Range",        s.get("range","—"))
    info_row("Components",   s.get("components","—"))
    info_row("Duration",     s.get("duration","—"))
    info_row("Concentration","Yes" if s.get("concentration") else "No")
    info_row("Ritual",       "Yes" if s.get("ritual") else "No")
    info_row("Source",       f"{s.get('source','')}  p.{s.get('page','')}")
    if pd.notna(s.get("materials","")) and str(s.get("materials","")) not in ("nan",""):
        info_row("Materials", str(s["materials"])[:120])

    ttk.Separator(win, orient="horizontal").pack(fill="x", padx=10, pady=4)

    tk.Label(win, text="Description:", font=("Arial",9,"bold"),
             anchor="w", padx=10).pack(anchor="w")
    txt = tk.Text(win, wrap="word", font=("Arial",9), relief="flat",
                  bg=win.cget("bg"), padx=10)
    txt.pack(fill="both", expand=True, padx=10, pady=(0,10))
    raw   = str(s.get("description",""))
    clean = re.sub(r'\{@\w+ ([^}]+)\}', r'\1', raw)
    txt.insert("1.0", clean)
    txt.config(state="disabled")
    
    
    def add_to_known(event=None):
        sel = spell_listbox.curselection()
        if not sel:
            return

        spell_name = spell_listbox.get(sel[0])
        known_listbox.insert(tk.END, spell_name)

    spell_listbox.bind("<Double-Button-1>", add_to_known)  # right-click add
    def equip_spell(event=None):
        sel = known_listbox.curselection()
        if not sel:
            return

        spell_name = known_listbox.get(sel[0])
        equip_listbox.insert(tk.END, spell_name)

    known_listbox.bind("<Double-Button-1>", equip_spell)


def build_spell_panel(parent):
    global spell_class_var, spell_level_var, spell_search_var, spell_listbox, count_label, known_listbox, equip_listbox, diagram_canvas

    main_row = tk.Frame(parent)
    main_row.pack(fill="both", expand=True)
    
    diagram_col = tk.Frame(main_row)
    search_col = tk.Frame(main_row)
    known_col  = tk.Frame(main_row)
    equip_col  = tk.Frame(main_row)

    known_col.pack(side="left", fill="y", padx=5)
    equip_col.pack(side="left", fill="y", padx=5)
    diagram_col.pack(side="left", fill="both", expand=True, padx=5)
    search_col.pack(side="left", fill="y")
    
    frame = ttk.LabelFrame(search_col, text=" Spell Lookup ")
    tk.Label(known_col, text="Known", font=("Arial", 10, "bold")).pack()

    known_listbox = tk.Listbox(known_col, width=20, height=20, selectmode="single")
    known_listbox.pack(fill="y", expand=True)
    
    tk.Label(equip_col, text="Equipped", font=("Arial", 10, "bold")).pack()

    equip_listbox = tk.Listbox(equip_col, width=18, height=10, selectmode="single")
    equip_listbox.pack(fill="y")
    
    tk.Label(diagram_col, text="Spell Visual", font=("Arial", 10, "bold")).pack()

    diagram_canvas = tk.Canvas(diagram_col, bg="white", height=250)
    diagram_canvas.pack(fill="both", expand=True)


    bar = tk.Frame(main_row)
    bar.pack(fill="x", padx=6, pady=4)

    tk.Label(bar, text="Class:").pack(side="left")
    spell_class_var = tk.StringVar(value="All")
    cb = ttk.Combobox(bar, textvariable=spell_class_var,
                      values=["All"] + sorted(CLASS_INFO.keys()),
                      width=12, state="readonly")
    cb.pack(side="left", padx=4)
    cb.bind("<<ComboboxSelected>>", refresh_spells)

    tk.Label(bar, text="Level:").pack(side="left", padx=(8,0))
    spell_level_var = tk.StringVar(value="All")
    lcb = ttk.Combobox(bar, textvariable=spell_level_var,
                       values=["All","0","1","2","3","4","5","6","7","8","9"],
                       width=6, state="readonly")
    lcb.pack(side="left", padx=4)
    lcb.bind("<<ComboboxSelected>>", refresh_spells)

    tk.Label(bar, text="Search:").pack(side="left", padx=(8,0))
    spell_search_var = tk.StringVar()
    spell_search_var.trace_add("write", refresh_spells)
    tk.Entry(bar, textvariable=spell_search_var, width=14).pack(side="left", padx=4)
    tk.Button(bar, text="✕", command=lambda: spell_search_var.set(""),
              font=("Arial",8), relief="flat").pack(side="left")

    count_label = tk.Label(bar, text="", fg="gray", font=("Arial",8))
    count_label.pack(side="right", padx=8)
    
    list_frame = tk.Frame(main_row)
    list_frame.pack(fill="both", expand=True, padx=6, pady=(0,6))
    sb = tk.Scrollbar(list_frame, orient="vertical")
    spell_listbox = tk.Listbox(list_frame, yscrollcommand=sb.set,
                               font=("Courier",9), selectmode="single",
                               activestyle="dotbox", height=8)
    sb.config(command=spell_listbox.yview)
    sb.pack(side="right", fill="y")
    spell_listbox.pack(side="left", fill="both", expand=True)
    spell_listbox.bind("<Button-2>", show_spell_detail)
    spell_listbox.bind("<Return>",          show_spell_detail)

    refresh_spells()
    def add_to_known(event=None):
        sel = spell_listbox.curselection()
        if not sel:
            return

        spell_name = spell_listbox.get(sel[0])
        known_listbox.insert(tk.END, spell_name)
    spell_listbox.bind("<Double-Button-2>", add_to_known)
    def remove_selected(listbox):
        sel = listbox.curselection()
        if not sel:
            return
        listbox.delete(sel[0])

    spell_listbox.bind("<<ListboxSelect>>", update_diagram)
    known_listbox.bind("<<ListboxSelect>>", update_diagram)
    equip_listbox.bind("<<ListboxSelect>>", update_diagram)        
    known_listbox.bind("<Delete>", lambda e: remove_selected(known_listbox))
    equip_listbox.bind("<Delete>", lambda e: remove_selected(equip_listbox))
    known_listbox.bind("<Button-2>", lambda e: remove_selected(known_listbox))
    equip_listbox.bind("<Button-2>", lambda e: remove_selected(equip_listbox))


def update_diagram(event=None):
    widget = event.widget
    sel = widget.curselection()
    if not sel:
        return

    diagram_canvas.delete("all")
    diagram_canvas.config(bg="white")
    if widget == spell_listbox:
        spell = spell_results[sel[0]]
        text = str(spell.get("description", "")).lower()
    else:
        spell_name = widget.get(sel[0]).split("  [")[0]
        match = SPELL_DF[SPELL_DF["name"] == spell_name]
        if match.empty:
            return
        spell = match.iloc[0].to_dict()
        text = str(spell.get("description", "")).lower()

    import re

    shape = "square"
    size = 20

    m = re.search(r"(\d+)[-\s]?foot[-\s]?radius", text)
    if m:
        shape = "circle"
        size = int(m.group(1))

    m = re.search(r"(\d+)[-\s]?foot cone", text)
    if m:
        shape = "cone"
        size = int(m.group(1))

    m = re.search(r"(\d+)[-\s]?foot cube", text)
    if m:
        shape = "square"
        size = int(m.group(1))

    m = re.search(r"(\d+)[-\s]?foot line", text)
    if m:
        shape = "line"
        size = int(m.group(1))

    cell = 25              # pixels per 5ft square
    grid_size = max(1, size // 5)

    diagram_canvas.update_idletasks()

    canvas_w = max(300, diagram_canvas.winfo_width())
    canvas_h = max(300, diagram_canvas.winfo_height())

    if canvas_w < 50: canvas_w = 300
    if canvas_h < 50: canvas_h = 300

    for x in range(0, canvas_w, cell):
        diagram_canvas.create_line(x, 0, x, canvas_h, fill="#e0e0e0")

    for y in range(0, canvas_h, cell):
        diagram_canvas.create_line(0, y, canvas_w, y, fill="#e0e0e0")

    cols = canvas_w // cell
    rows = canvas_h // cell

    grid_center_col = cols // 2
    grid_center_row = rows // 2

    center_x = grid_center_col * cell 
    center_y = grid_center_row * cell
    half = (grid_size * cell) // 2

    # Caster origin marker
    marker_size = 6

    diagram_canvas.create_oval(
        center_x - marker_size,
        center_y - marker_size,
        center_x + marker_size,
        center_y + marker_size,
        fill="black",
        outline=""
    )

    diagram_canvas.create_text(
        center_x,
        center_y - 10,
        text="You",
        fill="black",
        font=("Arial", 8, "bold")
    )
    diagram_canvas.create_line(center_x - 10, center_y, center_x + 10, center_y, fill="black")
    diagram_canvas.create_line(center_x, center_y - 10, center_x, center_y + 10, fill="black")
    
    if shape == "square":
        diagram_canvas.create_rectangle(
            center_x - half,
            center_y - half,
            center_x + half,
            center_y + half,
        )

    elif shape == "circle":
        px = grid_size * cell

        diagram_canvas.create_oval(
            center_x - px,
            center_y - px,
            center_x + px,
            center_y + px,
            outline="red", width=2
        )

    elif shape == "cone":
        diagram_canvas.create_polygon(
            center_x, center_y,
            center_x - px, center_y + px,
            center_x + px, center_y + px,
            outline="orange", fill=""
        )

    elif shape == "line":
        diagram_canvas.create_line(
            center_x, center_y,
            center_x + px, center_y,
            fill="purple", width=3
        )
    diagram_canvas.create_text(
        10, 10,
        anchor="nw",
        text=f"{size} ft = {grid_size} squares",
        fill="black",
        font=("Arial", 9, "bold")
    )
    diagram_canvas.update()

# ---------------------------------------------------------------------------
# BUILD001: INVENTORY LOOKUP
# ---------------------------------------------------------------------------

NAME_COLUMNS = {
    "weapons": "Weapon",
    "armors": "Armor",
    "accessories": "Accessory",
    "items": "Item",
    "potions": "Potion",
}

def build_item_browser(parent, on_add_callback):

    for category, df in ITEM_SHEETS.items():

        section = ttk.LabelFrame(parent, text=category.capitalize())
        section.pack(fill="x", padx=5, pady=5)

        for _, row in df.iterrows():
            name = str(row.iloc[0])  # adjust column

            row_frame = tk.Frame(section)
            row_frame.pack(fill="x")

            tk.Label(row_frame, text=name, width=25, anchor="w").pack(side="left")

            tk.Button(
                row_frame,
                text="➕",
                command=lambda n=name: on_add_callback(n)
            ).pack(side="right")
        for category, df in ITEM_SHEETS.items():

            if df is None or df.empty or len(df.columns) == 0:
                print(f"Skipping empty sheet: {category}")
                continue

            name_col = NAME_COLUMNS.get(category)

            # 🚫 If we don't know the column, skip safely
            if name_col not in df.columns:
                print(f"Missing column '{name_col}' in {category}, found: {list(df.columns)}")
                continue

            for _, row in df.iterrows():
                name = str(row[name_col])


def build_inventory_tab(parent):
    global backpack_listbox, equipped_listbox, item_listbox, item_type_var, item_desc_text
    backpack_items = []
    equipped_items = []
    # ---------------------------
    # MAIN LAYOUT (like spells)
    # ---------------------------
    main_row = tk.Frame(parent)
    main_row.pack(fill="both", expand=True)

    left_col   = tk.Frame(main_row)
    center_col = tk.Frame(main_row)
    right_col  = tk.Frame(main_row)

    left_col.pack(side="left", fill="y", padx=5)
    center_col.pack(side="left", fill="both", expand=True, padx=5)
    right_col.pack(side="left", fill="y", padx=5)

    # ---------------------------
    # LEFT: Backpack + Equipped
    # ---------------------------
    tk.Label(left_col, text="Backpack", font=("Arial",10,"bold")).pack()

    backpack_listbox = tk.Listbox(left_col, width=30, height=13, selectmode="single")
    backpack_listbox.pack(fill="y", expand=True)

    tk.Label(left_col, text="Equipped", font=("Arial",10,"bold")).pack(pady=(10,0))

    equipped_listbox = tk.Listbox(left_col, width=30, height=18, selectmode="single")
    equipped_listbox.pack(fill="y")

    # ---------------------------
    # CENTER: Inspector
    # ---------------------------
    tk.Label(center_col, text="Item Details", font=("Arial",10,"bold")).pack()

    item_desc_text = tk.Text(center_col, width=55, height=15, wrap="word")
    item_desc_text.pack(fill="both", expand=True)

    # ---------------------------
    # RIGHT: Shop
    # ---------------------------
    tk.Label(right_col, text="Item Shop", font=("Arial",10,"bold")).pack()

    # Filter dropdown
    item_type_var = tk.StringVar(value="weapons")
    type_box = ttk.Combobox(
        right_col,
        textvariable=item_type_var,
        values=list(ITEM_SHEETS.keys()),
        state="readonly",
        width=22
    )
    type_box.pack(pady=4)
    type_box.bind("<<ComboboxSelected>>", lambda e: refresh_shop())

    # Item list
    item_listbox = tk.Listbox(right_col, width=25, height=20)
    item_listbox.pack(fill="y", expand=True)

    # ---------------------------
    # DATA FUNCTIONS
    # ---------------------------

    def refresh_backpack():
        backpack_listbox.delete(0, tk.END)
        for item in backpack_items:
            backpack_listbox.insert(tk.END, item)

    def refresh_equipped():
        equipped_listbox.delete(0, tk.END)
        for item in equipped_items:
            equipped_listbox.insert(tk.END, item)

    def refresh_shop():
        item_listbox.delete(0, tk.END)

        category = item_type_var.get()
        df = ITEM_SHEETS.get(category)

        if df is None or df.empty:
            return

        name_col = df.columns[0]  # safe fallback (you cleaned names already)

        for _, row in df.iterrows():
            item_listbox.insert(tk.END, str(row[name_col]))

    # ---------------------------
    # ACTIONS
    # ---------------------------

    def add_to_backpack(event=None):
        sel = item_listbox.curselection()
        if not sel:
            return

        item_name = item_listbox.get(sel[0])
        backpack_items.append(item_name)
        refresh_backpack()

    def equip_item(event=None):
        sel = backpack_listbox.curselection()
        if not sel:
            return

        item = backpack_items.pop(sel[0])
        equipped_items.append(item)

        refresh_backpack()
        refresh_equipped()

    def unequip_item(event=None):
        sel = equipped_listbox.curselection()
        if not sel:
            return

        item = equipped_items.pop(sel[0])
        backpack_items.append(item)

        refresh_backpack()
        refresh_equipped()
    def remove_from_backpack(event=None):
        sel = backpack_listbox.curselection()
        if not sel:
            return

        backpack_items.pop(sel[0])
        refresh_backpack()
    # ---------------------------
    # INSPECTOR (center panel)
    # ---------------------------

    def show_item_details(event=None):
        widget = event.widget
        sel = widget.curselection()
        if not sel:
            return

        item_name = widget.get(sel[0])
        item_desc_text.delete("1.0", tk.END)

        # Find item in sheets
        category = item_type_var.get()
        df = ITEM_SHEETS.get(category)

        if df is None or df.empty:
            return

        name_col = df.columns[0]

        match = df[df[name_col] == item_name]
        if match.empty:
            return

        row = match.iloc[0]

        # Build description text
        desc = f"{item_name}\n\n"
        labels = COLUMN_LABELS.get(category, {})

        for col in df.columns:
            if col not in labels:
                continue

            label = labels[col]
            value = row[col]

            if pd.isna(value) or value == "":
                continue

            desc += f"{label}: {value}\n"

        item_desc_text.insert("1.0", desc)

    # ---------------------------
    # BINDINGS (same style as spells)
    # ---------------------------

    item_listbox.bind("<Double-Button-1>", add_to_backpack)

    backpack_listbox.bind("<Double-Button-1>", equip_item)
    equipped_listbox.bind("<Double-Button-1>", unequip_item)
    backpack_listbox.bind("<Double-Button-3>", remove_from_backpack)

    item_listbox.bind("<<ListboxSelect>>", show_item_details)
    backpack_listbox.bind("<<ListboxSelect>>", show_item_details)
    equipped_listbox.bind("<<ListboxSelect>>", show_item_details)

    # ---------------------------
    # INITIAL LOAD
    # ---------------------------
    refresh_shop()
    refresh_backpack()
    refresh_equipped()


# ---------------------------------------------------------------------------
# BUILD001: ITEM LOOKUP
# ---------------------------------------------------------------------------
def build_item_row(parent, item_name):
    row = tk.Frame(parent)
    row.pack(fill="x", pady=2)

    tk.Label(row, text=item_name, width=20, anchor="w").pack(side="left")

    bonus_var = tk.IntVar(value=0)

    tk.Label(row, text="+").pack(side="left")
    tk.Spinbox(row, from_=0, to=3, textvariable=bonus_var, width=3).pack(side="left")

    return {"name": item_name, "bonus_var": bonus_var}

def build_items_tab(parent):
    weapons_frame = ttk.LabelFrame(parent, text="Weapons")
    weapons_frame.pack(fill="x", padx=10, pady=5)

    weapon_items = []

    for category, df in ITEM_SHEETS.items():

        DEBUG = False

        if df.empty:
            if DEBUG:
                print(f"Skipping empty sheet: {category}")
            continue

        for _, row in df.iterrows():
            name = row.get("Weapon")  # or mapped column later


# ---------------------------------------------------------------------------
# MAIN WINDOW
# ---------------------------------------------------------------------------

root = tk.Tk()
global advantage_var
advantage_var = tk.IntVar(value=0)
root.title("Janus D&D Tracker")
mode_var = tk.StringVar(root, value="PLAYER")
root.geometry("950x900")
#root.state("zoomed")
root.resizable(True, True)
#root.minsize(750, 700)

#try:
#    root.state("zoomed")
#except:
#    pass


sv_ttk.set_theme("dark")
style = ttk.Style()
style.configure("TNotebook.Tab", font=("MSPGothic", 8, "bold"))
style.configure("Vertical.TScrollbar", arrowsize=10, width=10, troughcolor="#00f583", background="#050505")

top_bar = tk.Frame(root)
top_bar.pack(fill="x", side="top")
ttk.Separator(root, orient="horizontal").pack(fill="x")

notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True)


tk.Label(top_bar, text="Mode:").pack(side="left", padx=5)

ttk.Combobox(top_bar, textvariable=mode_var,
             values=["PLAYER", "DM", "NPC"],
             state="readonly", width=10).pack(side="left")

tk.Button(top_bar, text="💾 Save",
          command=save_character).pack(side="right", padx=5)

tk.Button(top_bar, text="📂 Load",
          command=load_character).pack(side="right", padx=5)


level_var = tk.StringVar(value="1")
sb_vars   = {s: tk.StringVar(value="10")
             for s in ["STR","DEX","CON","INT","WIS","CHA"]}
count_label = None

# FRAMES
sheet_tab  = tk.Frame(notebook)
spells_tab = tk.Frame(notebook)
inventory_tab = tk.Frame(notebook)
feats_tab = tk.Frame(notebook)
#items_tab = tk.Frame(notebook)
background_tab = tk.Frame(notebook)
notes_tab = tk.Frame(notebook)
pets_tab = tk.Frame(notebook)

notebook.add(sheet_tab,  text="Character")
notebook.add(spells_tab, text="Spells")
notebook.add(inventory_tab,  text="Equipment")
notebook.add(feats_tab,  text="Class Feats")
notebook.add(background_tab,  text="Background")
#notebook.add(items_tab,  text="Items")
notebook.add(notes_tab, text="Notes")
notebook.add(pets_tab, text="Pets")


build_spell_panel(spells_tab)
build_inventory_tab(inventory_tab)

#build_bg_panel(background_frame)
#build_items_tab(items_tab)
#build_pet_panel(pets_frame)

#
##CHARACTER
#
build_feats_tab(feats_tab)
build_identity(sheet_tab)
build_ability_scores(sheet_tab)
build_save_load(sheet_tab)

mid = tk.Frame(sheet_tab)
mid.pack(fill="x", padx=10, pady=5)
build_utility(mid)
build_combat_hud(mid)

def build_dice_tray(parent):
    global tray_label, tray_history
    frame = ttk.LabelFrame(parent, text=" 🎲 Dice Tray ")
    frame.pack(side="bottom", fill="x", padx=10, pady=5)
    
    tray_label = tk.Label(
        frame, 
        text="Roll a skill to see results...", 
        font=("Courier", 11, "bold"),
        fg="#2c3e50",
        justify="left",
        anchor="w",
        height=3 # Room for a couple of lines
    )
    tray_label.pack(fill="x", padx=10, pady=5)
    
    tray_history = tk.Text(
        frame, 
        height=4, 
        width=50, 
        font=("Courier", 10),
        state="disabled", # Prevents user from typing in it
        bg="#f4f4f4"
    )
    tray_history.pack(fill="x", padx=10, pady=5)

build_dice_tray(sheet_tab)

build_skills(mid)

for stat in ["STR","DEX","CON","INT","WIS","CHA"]:
    on_stat_change(stat)

def update_mode(*_):
    mode = mode_var.get()

    if mode == "PLAYER":
        # normal gameplay
        pass

    elif mode == "DM":
        # unlock NPC tools later
        pass

    elif mode == "NPC":
        # simplify UI later
        pass
mode_var.trace_add("write", update_mode)



#----------------------------------
root.mainloop()