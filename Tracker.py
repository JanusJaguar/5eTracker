import os
import re
import json
import sv_ttk
import tkinter as tk
from tkinter import ttk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
import random
import winsound
from vtt import build_vtt_tab
from vtt_player import build_player_vtt_tab
from vtt import VTT
from npc_mode import NPCMode
from minigames import SimTowerApp
from notes import build_notes_tab
from notes import build_companions_tab
from tkinter import ttk, simpledialog, messagebox
from tkinter import ttk, messagebox
try:
    from PIL import Image, ImageTk, ImageDraw
    PIL_OK = True
except ImportError:
    PIL_OK = False
import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except:
    pass
BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))

sheet_tab = None
spells_tab = None
equipment_tab = None
feats_tab = None
vtt_tab = None
npc_tab = None
vtt_instance = None  
player_vtt_built = True  
vtt_canvas_ref = None
global_refs = {
    "backpack_listbox": None,
    "equipped_listbox": None,
}
add_to_backpack_callback = None
def get_sheets_client():
    import gspread
    from google.oauth2.service_account import Credentials

    creds_path = os.path.join(BASE_DIR, "credentials.json")
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds  = Credentials.from_service_account_file(creds_path, scopes=scopes)
    return gspread.authorize(creds)

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

CANTRIP_COL = {
"Artificer": "Artificer_Cantrips",
"Bard":      "Bard_Cantrips",
"Cleric":    "Cleric_Cantrips",
"Druid":     "Druid_Cantrips",
"Fighter":   "Fighter_Cantrips",
"Rogue":     "Rogue_Cantrips",
"Sorcerer":  "Sorcerer_Cantrips",
"Warlock":   "Warlock_Cantrips",
"Wizard":    "Wizard_Cantrips",
}
SPELLS_COL = {
    "Artificer": "Artificer_Spells",
    "Bard":      "Bard_Spells",
    "Fighter":   "Fighter_Spells",
    "Ranger":    "Ranger_Spells",
    "Rogue":     "Rogue_Spells",
    "Sorcerer":  "Sorcerer_Spells",
    "Warlock":   "Warlock_Spells",
    "Monk":      "Ki_Points",
}

COIN_VALUES = {
    "PP": 1000,
    "GP": 100,
    "EP": 50,
    "SP": 10,
    "CP": 1,
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
CHARACTER_PROFS = {
    "skills": [],
    "armor": [],
    "weapons": [],
    "tools": [],
    "languages": [],
    "saving_throws": []
}
ARMOR_BASE = {
    "Padded": 11, "Leather": 11, "Studded leather": 12,
    "Hide": 12, "Chain shirt": 13, "Scale mail": 14,
    "Breastplate": 14, "Half plate": 15,
    "Ring mail": 14, "Chain mail": 16, "Splint": 17, "Plate": 18,
    "Shield": 2,
}
ARMOR_STYLE = {
    "Padded": "Light", "Leather": "Light", "Studded leather": "Light",
    "Hide": "Medium", "Chain shirt": "Medium", "Scale mail": "Medium",
    "Breastplate": "Medium", "Half plate": "Medium",
    "Ring mail": "Heavy", "Chain mail": "Heavy", "Splint": "Heavy",
    "Plate": "Heavy",
    "Shield": "Off-Hand",
}
spell_slot_vars = {}
spell_slot_labels = {}
npc_list = []
initiative_active = False
def calculate_ac(equipped_items):
    """Calculate AC from equipped armor list."""
    dex_mod = mods_hive.get("DEX", 0)

    body_armor = None
    has_shield = False

    for item in equipped_items:
        style = ARMOR_STYLE.get(item)
        if style == "Off-Hand":
            has_shield = True
        elif style in ("Light", "Medium", "Heavy"):
            body_armor = item

    if body_armor is None:
        # Unarmored
        ac = 10 + dex_mod
    else:
        base  = ARMOR_BASE.get(body_armor, 10)
        style = ARMOR_STYLE.get(body_armor)
        if style == "Light":
            ac = base + dex_mod
        elif style == "Medium":
            ac = base + min(dex_mod, 2)
        else:  # Heavy
            ac = base

    if has_shield:
        ac += 2

    return ac

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

        class_info_raw = cd[["Class", "Spellcasting Ability", "Hit Die", "Caster_Type"]].dropna(subset=["Class"])
        class_info_raw = class_info_raw[class_info_raw["Class"].isin(valid_classes)]

        class_info = {}
        for _, row in class_info_raw.iterrows():
            sa  = str(row["Spellcasting Ability"]).strip()
            ct  = str(row.get("Caster_Type", "")).strip()
            class_info[row["Class"]] = {
                "spell_ability": sa if sa not in ("nan", "ALL") else "—",
                "hit_die":       str(row["Hit Die"]).strip() if pd.notna(row["Hit Die"]) else "—",
                "caster_type":   ct if ct not in ("nan", "") else "none",
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

        slots_df = pd.read_excel(xl, sheet_name="SHEET_SLOTS")

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

        return (
            class_info,
            subclass_map,
            sp,
            item_sheets,
            race_list,
            background_list,
            slots_df,
            prog_df
        )
        
    except FileNotFoundError:
        messagebox.showerror("Missing File",
            f"Cannot find dnd_data.xlsx\nExpected at:\n{DATA_FILE}")
        return (
            {},                     # class_info
            {},                     # subclass_map
            pd.DataFrame(),         # spell_df
            {},                     # item_sheets
            [],                     # race_list
            [],                     # background_list
            pd.DataFrame(),         # prog_df
            pd.DataFrame()          # slots_df
        )
    except Exception as e:
        messagebox.showerror("Load Error", str(e))
        return (
            {},                     # class_info
            {},                     # subclass_map
            pd.DataFrame(),         # spell_df
            {},                     # item_sheets
            [],                     # race_list
            [],                     # background_list
            pd.DataFrame(),         # prog_df
            pd.DataFrame()          # slots_df
        )


CLASS_INFO, SUBCLASS_MAP, SPELL_DF, ITEM_SHEETS, RACE_LIST, BACKGROUND_LIST, SLOTS_DF, PROG_DF = load_excel_data()

SKILL_STAT = {
    "Acrobatics":     "DEX",
    "Animal Handling":"WIS",
    "Arcana":         "INT",
    "Athletics":      "STR",
    "Deception":      "CHA",
    "History":        "INT",
    "Insight":        "WIS",
    "Intimidation":   "CHA",
    "Investigation":  "INT",
    "Medicine":       "WIS",
    "Nature":         "INT",
    "Perception":     "WIS",
    "Performance":    "CHA",
    "Persuasion":     "CHA",
    "Religion":       "INT",
    "Sleight of Hand":"DEX",
    "Stealth":        "DEX",
    "Survival":       "WIS",
}
ALL_SKILLS = sorted(SKILL_STAT.keys())
STATS = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
STAT_FULL = {
    "STR": "Strength",
    "DEX": "Dexterity",
    "CON": "Constitution",
    "INT": "Intelligence",
    "WIS": "Wisdom",
    "CHA": "Charisma",
}
STAT_COL = {
    "STR": "Str",
    "DEX": "Dex",
    "CON": "Con",
    "INT": "Int",
    "WIS": "Wis",
    "CHA": "Cha",
}
known_listbox = None
equip_listbox = None
feats_listbox = None
feats_desc_text = None
vtt_built = False


# LOAD JSON DATA

def load_class_jsons():
    classes = {}

    class_folder = "Resources/DND5E/classes"

    if not os.path.exists(class_folder):
        return classes

    for filename in os.listdir(class_folder):
        if not filename.endswith(".json"):
            continue

        filepath = os.path.join(class_folder, filename)

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            class_name = data.get("class", "").lower()

            if class_name:
                classes[class_name] = data

        except Exception as e:
            print(f"Failed loading {filename}: {e}")

    return classes
CLASS_JSON = load_class_jsons()
JSON_FEATS_CACHE = []
#print("Loaded Classes:")
#print(CLASS_JSON.keys())
def get_features_for_character(class_name, subclass_name, level):

    feats = []

    class_data = CLASS_JSON.get(class_name.lower())

    if not class_data:
        return feats

    for feat in class_data["features"]:

        feat_level = feat.get("level", 0)

        if feat_level > level:
            continue

        feat_subclass = feat.get("subclass")

        if feat_subclass is None:
            feats.append(feat)

        elif subclass_name and feat_subclass.lower() == subclass_name.lower():
            feats.append(feat)

    return sorted(feats, key=lambda x: x["level"])

def get_features_for_character(
        class_name,
        subclass_name,
        level):

    class_name = str(class_name).lower()
    subclass_name = str(subclass_name).lower()

    class_data = CLASS_JSON.get(class_name)

    if not class_data:
        return []

    results = []

    for feature in class_data["features"]:

        feature_level = feature.get("level", 0)

        if feature_level > level:
            continue

        feature_subclass = feature.get("subclass")

        #
        # Base class feature
        #
        if feature_subclass is None:
            results.append(feature)
            continue

        #
        # Matching subclass feature
        #
        if str(feature_subclass).lower() == subclass_name:
            results.append(feature)

    return results

def get_class_features(class_name):
    class_name = class_name.lower()

    if class_name not in CLASS_JSON:
        return []

    return CLASS_JSON[class_name].get("features", [])
def get_feature_display_list(
        class_name,
        subclass_name,
        level):

    features = get_features_for_character(
        class_name,
        subclass_name,
        level
    )

    return [
        f"Lv {f['level']} - {f['data']['name']}"
        for f in features
    ]

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
def get_spell_slots():

    slots = {
        1:0, 2:0, 3:0,
        4:0, 5:0, 6:0,
        7:0, 8:0, 9:0
    }

    class_data = [
        (class1_var.get(), int(class1_level_var.get())),
        (class2_var.get(), int(class2_level_var.get()))
    ]

    for cls, lvl in class_data:

        if cls not in CLASS_INFO:
            continue

        if lvl <= 0:
            continue

        caster_type = CLASS_INFO[cls].get("caster_type", "None")

        if caster_type in ("None", "KI", "—"):
            continue

        row_name = f"L{lvl}_{caster_type}"

        match = SLOTS_DF[
            SLOTS_DF["Caster_Level"] == row_name
        ]

        if match.empty:
            continue

        row = match.iloc[0]

        for spell_lvl in range(1, 10):

            col = f"Slot_Level_{spell_lvl}"

            if col in row:

                try:
                    slots[spell_lvl] += int(row[col])
                except:
                    pass

    return slots
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

def handle_click(event, stat, prof_var, mode):
    # 1. Immediate UI Reset
    event.widget.config(relief="raised")
    
    # 2. Play Sound (Async so it doesn't freeze)
    # Note: Replace 'dice_roll.wav' with a path to your file, 
    # or use a system sound for now:
    winsound.PlaySound("SystemAsterisk", winsound.SND_ASYNC)
    
    # 3. Start the Animation
    animate_roll_sequence(stat, prof_var, mode, 12) # 12 frames = ~0.6 seconds

def animate_roll_sequence(stat, prof_var, mode, frames_left):
    if frames_left > 0:
        # A. Create the "Shake" effect by shifting the main window slightly
        offset = random.choice([-3, 0, 3])
        root.geometry(f"+{root.winfo_x() + offset}+{root.winfo_y()}")
        
        # B. Show "Tumbling" dice numbers
        fake_val = random.randint(1, 20)
        tray_label.config(text=f"🎲 {stat}: Rolling... [{fake_val}]", fg="gray")
        
        # C. Loop back in 50ms
        root.after(50, lambda: animate_roll_sequence(stat, prof_var, mode, frames_left - 1))
    else:
        # Finalize
        root.geometry(f"+{root.winfo_x()}+{root.winfo_y()}") # Reset shake position
        finalize_physical_roll(stat, prof_var, mode)

def finalize_physical_roll(stat, prof_var, mode):
    roll1 = random.randint(1, 20)
    roll2 = random.randint(1, 20)
    
    mod = mods_hive.get(stat, 0)
    prof = get_proficiency_bonus(level_var.get()) if prof_var.get() else 0
    bonus = mod + prof
    
    # PROGRESSIVE REVEAL LOGIC
    if mode == 1: # Advantage
        note = "ADVANTAGE"
        tray_label.config(text=f"🎲 {stat} (ADV): [{roll1}] ...", fg="blue")
        # Reveal second die 300ms later
        root.after(300, lambda: display_final(stat, max(roll1, roll2), bonus, f"[{roll1}, {roll2}]", "ADV"))
    
    elif mode == -1: # Disadvantage
        note = "DISADVANTAGE"
        tray_label.config(text=f"🎲 {stat} (DIS): [{roll1}] ...", fg="red")
        # Reveal second die 300ms later
        root.after(300, lambda: display_final(stat, min(roll1, roll2), bonus, f"[{roll1}, {roll2}]", "DIS"))
        
    else: # Normal
        display_final(stat, roll1, bonus, f"[{roll1}]", "NRM")

def display_final(stat, final_die, bonus, detail, mode_str):
    total = final_die + bonus
    color = "black"
    if final_die == 20: color = "green"
    if final_die == 1: color = "red"
    
    res = f"🎲 {stat} ({mode_str}): {detail} {fmt_mod(bonus)} = TOTAL: {total}"
    tray_label.config(text=res, fg=color)
    winsound.PlaySound("SystemExclamation", winsound.SND_ASYNC) # Final "thud" sound

def update_hit_dice(*args):

    cls1 = class1_var.get()
    cls2 = class2_var.get()
    try:
        lvl1 = int(class1_level_var.get())
    except:
        lvl1 = 0

    try:
        lvl2 = int(class2_level_var.get())
    except:
        lvl2 = 0

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
save_prof_vars = {}
save_labels    = {}
skills_lbl    = None
languages_lbl = None
equipment_lbl = None
speed_var   = None
passive_var = None
levelup_btn = None
ac_var = None
weapon_slot_vars = []

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
def _reset_all_slots():
    """Reset all spell slot toggles to available (cyan ★)."""
    for level in range(1, 10):
        if level not in spell_slot_vars or level not in spell_slot_labels:
            continue
        for i, lbl in enumerate(spell_slot_labels[level]):
            # Only reset slots that actually exist (not invisible ones)
            if lbl.cget("fg") != "#1e1e2e":
                if i < len(spell_slot_vars[level]):
                    spell_slot_vars[level][i] = True
                lbl.config(fg="cyan", text="★")

def open_rest_popup():
    """Rest popup — short rest spends hit dice, long rest fully recovers."""
    win = tk.Toplevel(root)
    win.title("⛺ Rest")
    win.geometry("340x460")
    win.resizable(False, False)
    win.grab_set()

    tk.Label(win, text="⛺ Take a Rest",
             font=("Arial", 13, "bold")).pack(pady=(14, 2))

    # Hit dice info
    cls1  = class1_var.get()
    cls2  = class2_var.get()
    try: lvl1 = int(class1_level_var.get() or 0)
    except: lvl1 = 0
    try: lvl2 = int(class2_level_var.get() or 0)
    except: lvl2 = 0

    hd1 = CLASS_INFO.get(cls1, {}).get("hit_die", "d8") if cls1 else "d8"
    hd2 = CLASS_INFO.get(cls2, {}).get("hit_die", "d8") if cls2 else None

    total_lvl   = max(1, lvl1 + lvl2)
    max_hit_die = total_lvl

    # Hit dice available tracker (stored between rests)
    # We use hp_vars as source of truth for current HP
    try:
        cur_hp  = int(hp_vars["cur"].get())
        max_hp  = int(hp_vars["max"].get())
    except:
        cur_hp  = 0
        max_hp  = 0

    # -----------------------------------------------------------------------
    # HIT DICE SECTION
    # -----------------------------------------------------------------------
    hd_frame = ttk.LabelFrame(win, text=" Hit Dice ")
    hd_frame.pack(fill="x", padx=12, pady=8)

    hd_info = f"{cls1}: {lvl1}{hd1}" if cls1 else ""
    if cls2 and lvl2 > 0:
        hd_info += f"  +  {cls2}: {lvl2}{hd2}"
    tk.Label(hd_frame, text=hd_info, fg="gray",
             font=("Arial", 9)).pack(pady=(4, 2))

    tk.Label(hd_frame,
             text="Click dice to spend on Short Rest:",
             font=("Arial", 9)).pack(anchor="w", padx=8)

    dice_frame  = tk.Frame(hd_frame)
    dice_frame.pack(pady=4)

    dice_vars   = []   # BooleanVar per die
    dice_btns   = []   # Button per die

    MAX_DISPLAY = min(total_lvl, 20)

    for i in range(MAX_DISPLAY):
        var = tk.BooleanVar(value=False)
        dice_vars.append(var)

        btn = tk.Checkbutton(
            dice_frame,
            variable=var,
            text="⬡",
            indicatoron=False,
            selectcolor="#2980b9",
            fg="white",
            bg="#2c3e50",
            activebackground="#2980b9",
            font=("Arial", 11),
            relief="flat",
            width=2,
            cursor="hand2"
        )
        btn.grid(row=i//10, column=i%10, padx=2, pady=2)
        dice_btns.append(btn)

    hp_preview = tk.Label(hd_frame, text=f"HP: {cur_hp} / {max_hp}",
                          font=("Arial", 9, "bold"), fg="#27ae60")
    hp_preview.pack(pady=(4, 6))

    # SHORT REST
    def short_rest():
        spent = sum(1 for v in dice_vars if v.get())
        if spent == 0:
            messagebox.showinfo("Short Rest",
                "Select at least one hit die to spend.")
            return

        import random
        total_heal = 0
        rolls      = []

        try:
            con_mod = mods_hive.get("CON", 0)
        except:
            con_mod = 0

        # Roll each spent die — heroic minimum of 3
        for i in range(spent):
            # Determine which class die to use
            if i < lvl1 and cls1:
                die_size = int(hd1.replace("d","").replace("D",""))
            elif cls2 and hd2:
                die_size = int(hd2.replace("d","").replace("D",""))
            else:
                die_size = 8

            roll  = max(3, random.randint(1, die_size))  # ← heroic minimum
            heal  = roll + con_mod
            total_heal += max(1, heal)
            rolls.append(roll)

        new_hp = min(max_hp, cur_hp + total_heal)
        hp_vars["cur"].set(str(new_hp))
        hp_preview.config(text=f"HP: {new_hp} / {max_hp}")

        # Recover Warlock slots
        ct1 = CLASS_INFO.get(cls1, {}).get("caster_type", "none")
        ct2 = CLASS_INFO.get(cls2, {}).get("caster_type", "none")
        if ct1 == "Warlock" or ct2 == "Warlock":
            _reset_all_slots()

        messagebox.showinfo("Short Rest",
            f"🎲 Rolled: {rolls}\n"
            f"CON mod: {'+' if con_mod>=0 else ''}{con_mod} per die\n"
            f"Healed: +{total_heal} HP\n"
            f"New HP: {new_hp}/{max_hp}")
        win.destroy()
    # LONG REST
    def long_rest():
        if not messagebox.askyesno("Long Rest",
                "Take a Long Rest?\n\n"
                "✅ Full HP restored\n"
                "✅ All spell slots restored\n"
                "✅ Hit dice refreshed (half total)\n\n"
                "Continue?"):
            return

        # Full HP
        hp_vars["cur"].set(hp_vars["max"].get())
        hp_vars["tmp"].set("0")

        # All spell slots
        _reset_all_slots()

        # Hit dice recover half (rounded up)
        import math
        recovered = math.ceil(total_lvl / 2)

        messagebox.showinfo("Long Rest",
            f"🌙 Long Rest complete!\n\n"
            f"❤️  HP fully restored: {hp_vars['max'].get()}\n"
            f"✨ All spell slots restored\n"
            f"🎲 Hit dice recovered: {recovered}/{total_lvl}")
        win.destroy()
    # BUTTONS
    btn_row = tk.Frame(win)
    btn_row.pack(pady=10)

    tk.Button(btn_row, text="💤 Short Rest",
              command=short_rest,
              bg="#2980b9", fg="white",
              font=("Arial", 10, "bold"),
              width=12).pack(side="left", padx=8)

    tk.Button(btn_row, text="🌙 Long Rest",
              command=long_rest,
              bg="#8e44ad", fg="white",
              font=("Arial", 10, "bold"),
              width=12).pack(side="left", padx=8)

    tk.Button(btn_row, text="Cancel",
              command=win.destroy,
              font=("Arial", 9),
              width=8).pack(side="left", padx=4)
def recalc_weapon_slot(slot):
    """Calculate to hit, damage and type for a weapon slot."""
    weapon_name = slot["weapon"].get()
    if not weapon_name or weapon_name == "—":
        slot["to_hit"].set("—")
        slot["damage"].set("—")
        slot["type"].set("—")
        return

    # Look up weapon in SHEET_WEAPONS
    df = ITEM_SHEETS.get("weapons")
    if df is None or df.empty:
        return

    name_col = df.columns[0]
    match = df[df[name_col].astype(str).str.strip() == weapon_name]
    if match.empty:
        return

    row = match.iloc[0]

    # Pull weapon data
    damage_die  = str(row.get("Damage", "1d4") or "1d4").strip()
    damage_type = str(row.get("Damage_Type", "—") or "—").strip().capitalize()
    properties  = str(row.get("Properties", "") or "").lower()
    range_type  = str(row.get("Melee or Ranged", "Melee") or "Melee").strip()

    is_finesse = "finesse" in properties
    is_ranged  = range_type.lower() == "ranged"

    # Determine which mod to use
    str_mod = mods_hive.get("STR", 0)
    dex_mod = mods_hive.get("DEX", 0)

    if is_finesse:
        stat_mod = max(str_mod, dex_mod)
    elif is_ranged:
        stat_mod = dex_mod
    else:
        stat_mod = str_mod

    # Proficiency check
    prof_bonus = 0
    try:
        lvl1 = int(class1_level_var.get() or 0)
        lvl2 = int(class2_level_var.get() or 0)
        total_lvl = max(1, lvl1 + lvl2)
        base_prof = get_proficiency_bonus(total_lvl)

        # Check if character is proficient with this weapon
        if is_proficient_with_weapon(weapon_name, properties):
            prof_bonus = base_prof
    except:
        pass

    # Bonus (fighting style, magic weapon etc)
    try:
        bonus = int(slot["bonus"].get() or 0)
    except:
        bonus = 0

    # Calculate
    to_hit_total = stat_mod + prof_bonus + bonus
    sign         = "+" if to_hit_total >= 0 else ""

    # Damage string — e.g. "1d6+3"
    dmg_mod = stat_mod + bonus
    if dmg_mod >= 0:
        dmg_str = f"{damage_die}+{dmg_mod}"
    elif dmg_mod < 0:
        dmg_str = f"{damage_die}{dmg_mod}"
    else:
        dmg_str = damage_die

    slot["to_hit"].set(f"{sign}{to_hit_total}")
    slot["damage"].set(dmg_str)
    slot["type"].set(damage_type)


def is_proficient_with_weapon(weapon_name, properties):
    """Check if current class grants proficiency with this weapon."""
    df = ITEM_SHEETS.get("weapons")
    if df is None or df.empty:
        return False

    # Get weapon category (Simple or Martial)
    name_col = df.columns[0]
    match = df[df[name_col].astype(str).str.strip() == weapon_name]
    if match.empty:
        return False

    row      = match.iloc[0]
    category = str(row.get("Simple or Martial", "") or "").strip().lower()

    # Get class proficiencies
    prof_df  = None
    try:
        xl       = pd.ExcelFile(DATA_FILE)
        prof_df  = pd.read_excel(xl, sheet_name="SHEETS_PROF")
        prof_df.columns = [c.strip() for c in prof_df.columns]
    except:
        return False

    cls1 = class1_var.get()
    cls2 = class2_var.get()

    for cls in [cls1, cls2]:
        if not cls:
            continue
        rows = prof_df[prof_df["Class"] == cls]
        if rows.empty:
            continue
        raw = str(rows.iloc[0].get("Weapons_Pro", "") or "").lower()

        # Check broad tags first
        if "simple" in raw and category == "simple":
            return True
        if "martial" in raw and category == "martial":
            return True
        # Check specific weapon name
        if weapon_name.lower() in raw:
            return True

    return False

def recalc_all_weapon_slots():
    """Recalculate all weapon slots — called when stats or level change."""
    for slot in weapon_slot_vars:
        recalc_weapon_slot(slot)

def refresh_weapon_dropdowns():
    """Update weapon dropdowns to show currently equipped weapons."""
    if not weapon_slot_vars:
        return
    try:
        equipped = list(equipped_listbox.get(0, tk.END))
    except:
        equipped = []

    # Filter to weapons only
    weapon_df   = ITEM_SHEETS.get("weapons", pd.DataFrame())
    weapon_names = set()
    if not weapon_df.empty:
        weapon_names = set(weapon_df.iloc[:, 0].astype(str).str.strip().tolist())

    equipped_weapons = ["—"] + [e for e in equipped if e in weapon_names]

    for slot in weapon_slot_vars:
        cb_val = slot["weapon"].get()
        slot["cb"].config(values=equipped_weapons)
        if cb_val not in equipped_weapons:
            slot["weapon"].set("—")
            recalc_weapon_slot(slot)

def update_all_skills(*_):
    try:
        lvl1 = int(class1_level_var.get() or 0)
        lvl2 = int(class2_level_var.get() or 0)
        prof = get_proficiency_bonus(max(1, lvl1 + lvl2))
    except Exception:
        prof = 2
    for label, stat, var in skill_labels:
        total = mods_hive.get(stat, 0) + (prof if var.get() else 0)
        label.config(text=fmt_mod(total))
    if initiative_label:
        initiative_label.config(text=fmt_mod(mods_hive.get("DEX", 0)))
    if prof_info_label:
        prof_info_label.config(text=f"Prof: {fmt_mod(prof)}")
    try:
        lvl1 = int(class1_level_var.get() or 0)
        lvl2 = int(class2_level_var.get() or 0)
        total_lvl = max(1, lvl1 + lvl2)
        prof = get_proficiency_bonus(total_lvl)

        for stat in ["STR","DEX","CON","INT","WIS","CHA"]:
            if stat not in save_prof_vars or stat not in mod_display_labels:
                continue
            try:
                score = int(sb_vars[stat].get())
            except:
                score = 10
            mod = (score - 10) // 2
            bonus = mod + (prof if save_prof_vars[stat].get() else 0)
            sign  = "+" if bonus >= 0 else ""
            if stat in save_labels:
                save_labels[stat].config(text=f"Save {sign}{bonus}")
    except:
        pass
    if passive_var is not None:
        try:
            wis_mod = mods_hive.get("WIS", 0)
            perc_prof = 0
            if hasattr(tk, "_skill_name_map"):
                perc_var = tk._skill_name_map.get("Perception")
                if perc_var and perc_var.get():
                    perc_prof = prof
            passive_var.set(str(10 + wis_mod + perc_prof))
        except:
            pass
def on_stat_change(stat, *_):
    try:
        mod = calculate_modifier(sb_vars[stat].get())
    except Exception:
        mod = 0
    mods_hive[stat] = mod
    if stat in mod_display_labels:
        mod_display_labels[stat].config(text=f"({fmt_mod(mod)})")
    update_all_skills()

    # Recalc AC if DEX changed and armor is equipped
    if stat == "DEX" and ac_var is not None:
        try:
            # Need equipped_items — stored locally in build_inventory_tab
            # so we trigger via the global listbox
            items = list(equipped_listbox.get(0, tk.END))
            ac_var.set(str(calculate_ac(items)))
        except:
            pass
    recalc_all_weapon_slots()
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
        refresh_spell_slots()
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

# PC WIZARD(called once when wizard opens) 
def load_wizard_data(excel_path):
    """Load race, background, and proficiency data from Excel."""
    xl   = pd.ExcelFile(excel_path)
    data = {}
 
    # --- Races ---
    try:
        df = pd.read_excel(xl, sheet_name="SHEET_RACE2")
        df.columns = [c.strip() for c in df.columns]
        data["races"] = df
    except Exception as e:
        print(f"SHEET_RACE2 load error: {e}")
        data["races"] = pd.DataFrame()
 
    # --- Backgrounds ---
    try:
        df = pd.read_excel(xl, sheet_name="SHEETS_BG")
        df.columns = [c.strip() for c in df.columns]
        data["backgrounds"] = df
    except Exception as e:
        print(f"SHEETS_BG load error: {e}")
        data["backgrounds"] = pd.DataFrame()
 
    # --- Class proficiencies ---
    try:
        df = pd.read_excel(xl, sheet_name="SHEETS_PROF")
        df.columns = [c.strip() for c in df.columns]
        data["profs"] = df
    except Exception as e:
        print(f"SHEETS_PROF load error: {e}")
        data["profs"] = pd.DataFrame()
 
    # --- Class info (subclasses, spell ability) ---
    try:
        cd = pd.read_excel(xl, sheet_name="Class Data")
        data["class_data"] = cd
    except Exception as e:
        print(f"Class Data load error: {e}")
        data["class_data"] = pd.DataFrame()
 
    try:
        prog = pd.read_excel(xl, sheet_name="SHEETS_PROGRESSION")
        data["progression"] = prog
    except Exception as e:
        print(f"SHEETS_PROGRESSION load error: {e}")
        data["progression"] = pd.DataFrame()
 
    return data

def open_character_wizard(parent, excel_path, class_info, subclass_map,
                           on_complete):
    """
    Opens the character creation wizard popup.
 
    parent          — root or any tk widget
    excel_path      — path to dnd_data.xlsx
    class_info      — dict from main app  {ClassName: {spell_ability, hit_die}}
    subclass_map    — dict from main app  {ClassName: [subclass, ...]}
    on_complete     — callback(result_dict) called on finish
    """ 
    data = load_wizard_data(excel_path)
 
    # WIZARD STATE  (shared across pages)
    # -----------------------------------------------------------------------
    wiz = {
        "page":        0,
        "name":        tk.StringVar(value=""),
        "sex":         tk.StringVar(value=""),
        "alignment":   tk.StringVar(value=""),
 
        "race":        tk.StringVar(value=""),
        "subrace":     tk.StringVar(value=""),
        "race_row":    None,   # pd.Series of chosen race
 
        "background":  tk.StringVar(value=""),
        "bg_row":      None,   # pd.Series of chosen background
 
        "class_name":  tk.StringVar(value=""),
        "level":       tk.StringVar(value="1"),
        "subclass":    tk.StringVar(value=""),
        "prof_row":    None,   # pd.Series of class prof row
 
        # base scores (before racial bonus)
        "scores": {s: tk.StringVar(value="10") for s in STATS},
 
        # skill proficiencies
        "bg_skills":    [],    # given by background — locked
        "class_skills": [],    # chosen by player from class list
        "skill_picks":  0,     # how many class skills allowed
        "skill_choice_list": [],  # valid skills for class
    }
 
    PAGES = [
        "Name & Details",
        "Race",
        "Background",
        "Class",
        "Ability Scores",
        "Skills",
        "Review & Confirm",
    ]
 
    # -----------------------------------------------------------------------
    # WINDOW
    # -----------------------------------------------------------------------
    win = tk.Toplevel(parent)
    win.title("✨ New Character Wizard")
    win.geometry("780x620")
    win.resizable(False, False)
    win.grab_set()   # modal
 
    # Header
    header_frame = tk.Frame(win, bg="#2c3e50", height=52)
    header_frame.pack(fill="x")
    header_frame.pack_propagate(False)
 
    page_title_lbl = tk.Label(header_frame, text="", bg="#2c3e50",
                               fg="white", font=("Arial", 14, "bold"))
    page_title_lbl.pack(side="left", padx=16, pady=10)
 
    step_lbl = tk.Label(header_frame, text="", bg="#2c3e50",
                         fg="#95a5a6", font=("Arial", 10))
    step_lbl.pack(side="right", padx=16, pady=10)
 
    # Content area (swapped per page)
    content = tk.Frame(win, padx=16, pady=12)
    content.pack(fill="both", expand=True)
 
    # Bottom nav
    nav = tk.Frame(win, pady=8)
    nav.pack(fill="x", side="bottom")
    ttk.Separator(win, orient="horizontal").pack(fill="x", side="bottom")
 
    btn_back = tk.Button(nav, text="◄ Back", width=10,
                         font=("Arial", 10))
    btn_back.pack(side="left", padx=16)
 
    btn_next = tk.Button(nav, text="Next ►", width=10,
                         font=("Arial", 10), bg="#2980b9", fg="white")
    btn_next.pack(side="right", padx=16)
 
    # -----------------------------------------------------------------------
    # HELPERS
    # -----------------------------------------------------------------------
    def clear_content():
        for w in content.winfo_children():
            w.destroy()
 
    def section(parent_frame, title):
        lf = ttk.LabelFrame(parent_frame, text=f"  {title}  ")
        lf.pack(fill="x", pady=6)
        return lf
 
    def labeled_entry(parent_frame, label, var, width=24):
        row = tk.Frame(parent_frame)
        row.pack(fill="x", pady=3)
        tk.Label(row, text=label, width=16, anchor="w").pack(side="left")
        tk.Entry(row, textvariable=var, width=width).pack(side="left", padx=4)
        return row
 
    def labeled_combo(parent_frame, label, var, values, width=24,
                      on_select=None):
        row = tk.Frame(parent_frame)
        row.pack(fill="x", pady=3)
        tk.Label(row, text=label, width=16, anchor="w").pack(side="left")
        cb = ttk.Combobox(row, textvariable=var, values=values,
                          width=width, state="readonly")
        cb.pack(side="left", padx=4)
        if on_select:
            cb.bind("<<ComboboxSelected>>", on_select)
        return cb
 
    def preview_box(parent_frame, height=5):
        txt = tk.Text(parent_frame, height=height, wrap="word",
                      font=("Arial", 9), state="disabled",
                      relief="flat", bg=win.cget("bg"))
        txt.pack(fill="x", padx=6, pady=4)
        return txt
 
    def set_preview(txt_widget, text):
        txt_widget.config(state="normal")
        txt_widget.delete("1.0", tk.END)
        txt_widget.insert("1.0", text)
        txt_widget.config(state="disabled")
 
    # -----------------------------------------------------------------------
    # PAGE BUILDERS
    # -----------------------------------------------------------------------
    def get_spellcasting_info():

        cls1 = class1_var.get()
        cls2 = class2_var.get()

        try:
            lvl1 = int(class1_level_var.get())
        except:
            lvl1 = 0

        try:
            lvl2 = int(class2_level_var.get())
        except:
            lvl2 = 0

        result = {
            "caster_level": 0,
            "spell_ability": "—",
            "spell_mod": 0,
            "save_dc": 0,
            "attack_bonus": 0,
            "slots_key": None,
        }

        # -------------------------
        # PRIMARY CLASS
        # -------------------------

        main_class = None
        main_level = 0

        if cls1 in CLASS_INFO and lvl1 > 0:
            main_class = cls1
            main_level = lvl1

        elif cls2 in CLASS_INFO and lvl2 > 0:
            main_class = cls2
            main_level = lvl2

        if not main_class:
            return result

        info = CLASS_INFO[main_class]

        caster_type = info.get("caster_type", "None")
        spell_ability = info.get("spell_ability", "—")

        # -------------------------
        # SPELL MODIFIER
        # -------------------------

        if spell_ability in mods_hive:

            spell_mod = mods_hive[spell_ability]

            prof_bonus = get_proficiency_bonus(
                lvl1 + lvl2
            )

            save_dc = 8 + prof_bonus + spell_mod

            attack_bonus = prof_bonus + spell_mod

        else:
            spell_mod = 0
            save_dc = 0
            attack_bonus = 0

        # -------------------------
        # SLOT KEY
        # -------------------------

        if caster_type not in ("None", "—"):

            slots_key = f"L{main_level}_{caster_type}"

        else:
            slots_key = None

        result = {

            "caster_level":
                main_level,

            "spell_ability":
                spell_ability,

            "spell_mod":
                spell_mod,

            "save_dc":
                save_dc,

            "attack_bonus":
                attack_bonus,

            "slots_key":
                slots_key,
        }

        return result

    def page_details():
        clear_content()
        page_title_lbl.config(text="Name & Details")
 
        det = section(content, "Character Identity")
 
        labeled_entry(det, "Character Name:", wiz["name"], width=28)
        labeled_entry(det, "Sex / Gender:",   wiz["sex"],  width=20)
 
        alignments = [
            "Lawful Good", "Neutral Good", "Chaotic Good",
            "Lawful Neutral", "True Neutral", "Chaotic Neutral",
            "Lawful Evil", "Neutral Evil", "Chaotic Evil"
        ]
        labeled_combo(det, "Alignment:", wiz["alignment"], alignments, width=20)
 
        tk.Label(content, text="You can fill in backstory, personality traits,\n"
                               "and other flavour details on the Background tab\n"
                               "after your character is created.",
                 fg="gray", font=("Arial", 9), justify="left").pack(
            anchor="w", pady=(12, 0))
 
    # ------------------------------------------------------------------

    def page_race():
        clear_content()
        page_title_lbl.config(text="Choose Your Race")

        df = data["races"]
        if df.empty:
            tk.Label(content, text="⚠️ Race data not found (SHEET_RACE2).",
                     fg="red").pack()
            return

        race_names = sorted(df["Race"].dropna().unique().tolist())

        top = tk.Frame(content)
        top.pack(fill="x")

        subrace_lbl = tk.Label(top, text="Subrace:", width=16, anchor="w")
        subrace_cb  = ttk.Combobox(top, textvariable=wiz["subrace"],
                                    width=24, state="readonly")
        subrace_lbl.pack_forget()
        subrace_cb.pack_forget()

        preview = preview_box(content, height=8)

        def on_subrace(*_):
            update_race_preview()

        def update_race_preview():
            race = wiz["race"].get()
            sub  = wiz["subrace"].get()
            rows = df[df["Race"] == race]
            if rows.empty:
                return

            # Base row — the (choose one) or (none) row carries shared traits
            base_rows = rows[rows["Subrace"].fillna("").astype(str).str.strip()
                             .isin(["(none)", "(choose one)", ""])]
            base_row  = base_rows.iloc[0] if not base_rows.empty else rows.iloc[0]

            # Subrace row — carries additional bonuses
            sub_row = None
            if sub and sub not in ("", "(none)", "(choose one)"):
                sub_rows = rows[rows["Subrace"].fillna("").astype(str)
                                .str.strip() == sub]
                if not sub_rows.empty:
                    sub_row = sub_rows.iloc[0]

            # Accumulate stats from both rows
            bonuses = []
            for stat in STATS:
                col = STAT_COL[stat]
                total = 0
                try:
                    total += int(base_row.get(col, 0) or 0)
                except:
                    pass
                if sub_row is not None:
                    try:
                        total += int(sub_row.get(col, 0) or 0)
                    except:
                        pass
                if total != 0:
                    bonuses.append(f"{stat} {'+' if total > 0 else ''}{total}")

            # Combine traits from both rows
            base_bonus = str(base_row.get("Bonus", "") or "")
            sub_bonus  = str(sub_row.get("Bonus", "") or "") if sub_row is not None else ""
            all_traits = " | ".join(filter(None, [base_bonus, sub_bonus]))

            # Combine languages
            base_lang = str(base_row.get("Language", "") or "")
            sub_lang  = str(sub_row.get("Language", "") or "") if sub_row is not None else ""
            all_lang  = ", ".join(filter(None, [base_lang, sub_lang]))

            # Store the combined race_row info for later use
            # We store base_row as primary but patch stats with sub_row
            wiz["race_row"]      = base_row
            wiz["race_sub_row"]  = sub_row   # ← store separately

            lines = [
                f"Race:      {race}",
                f"Subrace:   {sub or '—'}",
                f"Size:      {base_row.get('Size', '—')}",
                f"Speed:     {base_row.get('Speed', '—')} ft",
                f"Languages: {all_lang or '—'}",
                f"Bonuses:   {', '.join(bonuses) if bonuses else '—'}",
                f"Source:    {base_row.get('Source', '—')}",
                "",
                "Racial Traits:",
                all_traits or "—",
            ]
            set_preview(preview, "\n".join(str(l) for l in lines))
 
        def on_race(*_):
            race = wiz["race"].get()
            wiz["subrace"].set("")
            wiz["race_row"] = None
            rows = df[df["Race"] == race]
            if rows.empty:
                return

            subraces = rows["Subrace"].fillna("").astype(str).str.strip().tolist()

            # Does this race need a subrace choice?
            needs_choice = "(choose one)" in subraces

            if needs_choice:
                # Show subrace dropdown — exclude the base row marker
                real_subs = [s for s in subraces
                             if s not in ("", "(none)", "(choose one)")]
                subrace_cb.config(values=real_subs)
                subrace_lbl.pack(side="left", padx=(0, 4))
                subrace_cb.pack(side="left")
                subrace_cb.bind("<<ComboboxSelected>>", on_subrace)
                # Don't set race_row yet — wait for subrace pick
            else:
                # No subrace needed — hide dropdown, use first row
                subrace_lbl.pack_forget()
                subrace_cb.pack_forget()
                wiz["subrace"].set("(none)")
                wiz["race_row"] = rows.iloc[0]

            update_race_preview()

        labeled_combo(top, "Race:", wiz["race"], race_names,
                      on_select=on_race)

        if wiz["race"].get():
            on_race()
    # ------------------------------------------------------------------
    def page_background():
        clear_content()
        page_title_lbl.config(text="Choose Your Background")
 
        df = data["backgrounds"]
        if df.empty:
            tk.Label(content, text="⚠️ Background data not found (SHEETS_BG).",
                     fg="red").pack()
            return
 
        bg_names = sorted(df["Background"].dropna().unique().tolist())
        preview  = preview_box(content, height=10)
 
        def on_bg(*_):
            bg = wiz["background"].get()
            rows = df[df["Background"] == bg]
            if rows.empty:
                return
            row = rows.iloc[0]
            wiz["bg_row"] = row
 
            # Parse background skills into list
            skills_raw = str(row.get("Skills", "") or "")
            wiz["bg_skills"] = [
                s.strip() for s in skills_raw.replace(",", " ").split()
                if s.strip() in ALL_SKILLS
            ]
 
            lines = [
                f"Background:  {bg}",
                f"Source:      {row.get('Source','—')}",
                f"Feature:     {row.get('Feature','—')}",
                "",
                f"Skills:      {row.get('Skills','—')}",
                f"Languages:   {row.get('Languages','—')}",
                f"Tools:       {row.get('Tools','—')}",
                f"Gold:        {row.get('Gold','—')} gp",
                f"Equipment:   {row.get('Equipment','—')}",
                "",
                "Description:",
                str(row.get("Description", "—")),
            ]
            set_preview(preview, "\n".join(str(l) for l in lines))
 
        labeled_combo(content, "Background:", wiz["background"],
                      bg_names, on_select=on_bg)
 
        if wiz["background"].get():
            on_bg()
 
    # ------------------------------------------------------------------
    def page_class():
        clear_content()
        page_title_lbl.config(text="Choose Your Class")
 
        class_names = sorted(class_info.keys())
        top  = tk.Frame(content)
        top.pack(fill="x")
 
        sub_lbl = tk.Label(top, text="Subclass:", width=16, anchor="w")
        sub_cb  = ttk.Combobox(top, textvariable=wiz["subclass"],
                                width=24, state="readonly")
        sub_lbl.pack_forget()
        sub_cb.pack_forget()
 
        preview = preview_box(content, height=8)
 
        def update_class_preview():
            cls  = wiz["class_name"].get()
            info = class_info.get(cls, {})
            df   = data["profs"]
 
            prof_row = None
            if not df.empty and cls:
                rows = df[df["Class"] == cls]
                if not rows.empty:
                    prof_row = rows.iloc[0]
                    wiz["prof_row"] = prof_row
 
            try:
                lvl = int(wiz["level"].get())
            except:
                lvl = 1
 
            lines = [
                f"Class:           {cls}",
                f"Level:           {lvl}",
                f"Hit Die:         {info.get('hit_die','—')}",
                f"Spell Ability:   {info.get('spell_ability','—')}",
                "",
            ]
            if prof_row is not None:
                lines += [
                    f"Skill Choices:   {prof_row.get('Skill_Number','—')}",
                    f"Choose From:     {prof_row.get('Skill_Choice','—')}",
                    f"Armor Prof:      {prof_row.get('Armor_Pro','—')}",
                    f"Weapon Prof:     {prof_row.get('Weapons_Pro','—')}",
                    f"Tool Prof:       {prof_row.get('Tools_Pro','—')}",
                    f"Saving Throws:   {prof_row.get('Savingthrows','—')}",
                ]
            set_preview(preview, "\n".join(str(l) for l in lines))
 
        def on_class(*_):
            cls = wiz["class_name"].get()
            wiz["subclass"].set("")
            subs = subclass_map.get(cls, [])
            try:
                lvl = int(wiz["level"].get())
            except:
                lvl = 1
 
            if subs and lvl >= 3:
                sub_lbl.pack(side="left", padx=(0, 4))
                sub_cb.config(values=subs)
                sub_cb.pack(side="left")
            else:
                sub_lbl.pack_forget()
                sub_cb.pack_forget()
 
            update_class_preview()
 
        def on_level(*_):
            on_class()
 
        labeled_combo(top, "Class:", wiz["class_name"],
                      class_names, on_select=on_class)
 
        lvl_row = tk.Frame(content)
        lvl_row.pack(fill="x", pady=4)
        tk.Label(lvl_row, text="Starting Level:", width=16,
                 anchor="w").pack(side="left")
        tk.Spinbox(lvl_row, from_=1, to=20,
                   textvariable=wiz["level"], width=5,
                   command=on_level).pack(side="left", padx=4)
        wiz["level"].trace_add("write", on_level)
 
        if wiz["class_name"].get():
            on_class()
 
    # ------------------------------------------------------------------
    def page_scores():
        clear_content()
        page_title_lbl.config(text="Ability Scores")
 
        tk.Label(content,
                 text="Enter your base ability scores (before racial bonuses).\n"
                       "Racial bonuses are shown on the right and will be applied "
                       "automatically.",
                 fg="gray", font=("Arial", 9), justify="left").pack(
            anchor="w", pady=(0, 8))
 
        scores_frame = tk.Frame(content)
        scores_frame.pack(fill="x")
 
        race_row = wiz.get("race_row")
 
        for i, stat in enumerate(STATS):
            row = tk.Frame(scores_frame)
            row.pack(fill="x", pady=3)
 
            tk.Label(row, text=f"{stat}  ({STAT_FULL[stat]})",
                     width=20, anchor="w",
                     font=("Arial", 9, "bold")).pack(side="left")
 
            tk.Entry(row, textvariable=wiz["scores"][stat],
                     width=5, justify="center",
                     font=("Arial", 11, "bold")).pack(side="left", padx=4)
 
            # Racial bonus readout
            racial_bonus = 0
            if race_row is not None:
                try:
                    racial_bonus += int(race_row.get(STAT_COL[stat], 0) or 0)
                except:
                    pass
            sub_row = wiz.get("race_sub_row")
            if sub_row is not None:
                try:
                    racial_bonus += int(sub_row.get(STAT_COL[stat], 0) or 0)
                except:
                    pass
 
            bonus_txt = (f"  + {racial_bonus} racial  →  "
                         if racial_bonus != 0 else "  (no racial bonus)   ")
            tk.Label(row, text=bonus_txt, fg="#2980b9",
                     font=("Arial", 9)).pack(side="left")
 
            # Live final score label
            final_lbl = tk.Label(row, text="= 10", fg="#27ae60",
                                  font=("Arial", 11, "bold"), width=5)
            final_lbl.pack(side="left")
 
            def make_updater(s=stat, rb=racial_bonus, lbl=final_lbl):
                def update(*_):
                    try:
                        base  = int(wiz["scores"][s].get())
                        total = base + rb
                        lbl.config(text=f"= {total}")
                    except:
                        lbl.config(text="= ?")
                wiz["scores"][s].trace_add("write", update)
                update()
 
            make_updater()
 
    # ------------------------------------------------------------------
    def page_skills():
        clear_content()
        page_title_lbl.config(text="Skill Proficiencies")
 
        # Pull class skill data
        prof_row = wiz.get("prof_row")
        num_picks = 0
        choice_list = []
 
        if prof_row is not None:
            try:
                num_picks = int(prof_row.get("Skill_Number", 0) or 0)
            except:
                num_picks = 0
 
            raw = str(prof_row.get("Skill_Choice", "") or "")
            choice_list = [
                s.strip() for s in raw.replace(",", " ").split()
                if s.strip() in ALL_SKILLS
            ]
 
        wiz["skill_picks"]       = num_picks
        wiz["skill_choice_list"] = choice_list
 
        bg_skills = wiz["bg_skills"]
 
        info_txt = (
            f"Background grants: {', '.join(bg_skills) if bg_skills else '—'}\n"
            f"Class allows {num_picks} skill pick(s) from the highlighted list."
        )
        tk.Label(content, text=info_txt, fg="gray",
                 font=("Arial", 9), justify="left").pack(
            anchor="w", pady=(0, 8))
 
        chosen_class_skills = []
 
        # Canvas + scrollbar for skill list
        outer = tk.Frame(content)
        outer.pack(fill="both", expand=True)
 
        sb = tk.Scrollbar(outer, orient="vertical")
        sb.pack(side="right", fill="y")
 
        skill_canvas = tk.Canvas(outer, yscrollcommand=sb.set,
                                  highlightthickness=0)
        skill_canvas.pack(side="left", fill="both", expand=True)
        sb.config(command=skill_canvas.yview)
 
        inner = tk.Frame(skill_canvas)
        skill_canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda e: skill_canvas.config(
                       scrollregion=skill_canvas.bbox("all")))
 
        pick_lbl = tk.Label(content,
                            text=f"Class picks used: 0 / {num_picks}",
                            font=("Arial", 9), fg="#2980b9")
        pick_lbl.pack(anchor="w")
 
        skill_vars = {}
 
        def update_pick_count():
            used = sum(1 for s, v in skill_vars.items()
                       if v.get() and s not in bg_skills)
            pick_lbl.config(
                text=f"Class picks used: {used} / {num_picks}",
                fg="#27ae60" if used == num_picks else "#2980b9"
            )
            wiz["class_skills"] = [
                s for s, v in skill_vars.items()
                if v.get() and s not in bg_skills
            ]
 
        for skill in ALL_SKILLS:
            var     = tk.BooleanVar()
            is_bg   = skill in bg_skills
            in_list = skill in choice_list or not choice_list
 
            row = tk.Frame(inner)
            row.pack(fill="x", pady=1)
 
            if is_bg:
                var.set(True)
                cb = tk.Checkbutton(row, text=f"✔  {skill}  [Background]",
                                     variable=var, state="disabled",
                                     fg="#27ae60", anchor="w",
                                     disabledforeground="#27ae60")
            elif in_list:
                cb = tk.Checkbutton(row, text=f"    {skill}",
                                     variable=var, anchor="w",
                                     command=lambda s=skill, v=var:
                                         on_skill_toggle(s, v))
            else:
                cb = tk.Checkbutton(row, text=f"    {skill}",
                                     variable=var, state="disabled",
                                     fg="gray", anchor="w",
                                     disabledforeground="gray")
 
            cb.pack(side="left", fill="x")
 
            stat_lbl = tk.Label(row,
                                text=f"({SKILL_STAT.get(skill, '?')})",
                                fg="gray", font=("Arial", 8), width=5)
            stat_lbl.pack(side="right")
 
            skill_vars[skill] = var
 
        def on_skill_toggle(skill, var):
            used = sum(1 for s, v in skill_vars.items()
                       if v.get() and s not in bg_skills)
            if var.get() and used > num_picks:
                var.set(False)
                messagebox.showwarning(
                    "Skill Limit",
                    f"Your class only allows {num_picks} skill pick(s)."
                )
                return
            update_pick_count()
 
        # Restore previous picks if user navigated back
        for s in wiz.get("class_skills", []):
            if s in skill_vars and s not in bg_skills:
                skill_vars[s].set(True)
 
        update_pick_count()
 
    # ------------------------------------------------------------------
    def page_review():
        clear_content()
        page_title_lbl.config(text="Review & Confirm")
 
        race_row = wiz.get("race_row")
        bg_row   = wiz.get("bg_row")
 
        lines = ["═" * 48, "  CHARACTER SUMMARY", "═" * 48, ""]
 
        lines += [
            f"  Name:        {wiz['name'].get() or '—'}",
            f"  Sex:         {wiz['sex'].get() or '—'}",
            f"  Alignment:   {wiz['alignment'].get() or '—'}",
            "",
            f"  Race:        {wiz['race'].get() or '—'}",
            f"  Subrace:     {wiz['subrace'].get() or '—'}",
            "",
            f"  Background:  {wiz['background'].get() or '—'}",
            f"  Bg Skills:   {', '.join(wiz['bg_skills']) or '—'}",
            "",
            f"  Class:       {wiz['class_name'].get() or '—'}",
            f"  Level:       {wiz['level'].get()}",
            f"  Subclass:    {wiz['subclass'].get() or '—'}",
            "",
            "  ABILITY SCORES",
        ]
 
        for stat in STATS:
            base = 10
            racial = 0
            try:
                base = int(wiz["scores"][stat].get())
            except:
                pass
            if race_row is not None:
                try:
                    racial = int(race_row.get(stat, 0) or 0)
                except:
                    pass
            total = base + racial
            bonus = (total - 10) // 2
            sign  = "+" if bonus >= 0 else ""
            lines.append(
                f"  {stat}:  {base:>2}"
                + (f" + {racial}" if racial else "      ")
                + f"  = {total:>2}  ({sign}{bonus})"
            )
        lines += [
            "",
            f"  SKILL PROFS:",
            f"  {', '.join(wiz['bg_skills'] + wiz['class_skills']) or '—'}",
        ]
        if bg_row is not None:
            lines += [
                "",
                f"  Equipment:   {bg_row.get('Equipment','—')}",
                f"  Gold:        {bg_row.get('Gold','—')} gp",
            ]
        lines += ["", f"  MAX HP:      {calc_hp()}"] 
        txt = tk.Text(content, wrap="word", font=("Courier", 9),
                      relief="flat", bg=win.cget("bg"))
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", "\n".join(str(l) for l in lines))
        txt.config(state="disabled")
 
    # -----------------------------------------------------------------------
    # PAGE NAVIGATION
    # -----------------------------------------------------------------------
    page_builders = [
        page_details,
        page_race,
        page_background,
        page_class,
        page_scores,
        page_skills,
        page_review,
    ]
 
    def show_page(idx):
        wiz["page"] = idx
        page_builders[idx]()
        page_title_lbl.config(text=PAGES[idx])
        step_lbl.config(text=f"Step {idx + 1} of {len(PAGES)}")
 
        btn_back.config(state="normal" if idx > 0 else "disabled")
        if idx == len(PAGES) - 1:
            btn_next.config(text="✅ Create Character", bg="#27ae60")
        else:
            btn_next.config(text="Next ►", bg="#2980b9")
 
    def validate_page(idx):
        """Returns (ok, error_message)."""
        if idx == 0:
            if not wiz["name"].get().strip():
                return False, "Please enter a character name."
        elif idx == 1:
            if not wiz["race"].get():
                return False, "Please choose a race."
            # Check if subrace is required
            df = data["races"]
            if not df.empty:
                rows = df[df["Race"] == wiz["race"].get()]
                subs = rows["Subrace"].dropna().astype(str).str.strip().tolist()
                needs_choice = any(s == "(choose one)" for s in subs) or \
                               len([s for s in subs
                                    if s not in ("(none)", "(choose one)")]) > 1
                if needs_choice and not wiz["subrace"].get():
                    return False, "Please choose a subrace."
        elif idx == 2:
            if not wiz["background"].get():
                return False, "Please choose a background."
        elif idx == 3:
            if not wiz["class_name"].get():
                return False, "Please choose a class."
        elif idx == 4:
            for stat in STATS:
                try:
                    val = int(wiz["scores"][stat].get())
                    if not (1 <= val <= 30):
                        raise ValueError
                except:
                    return False, f"{stat} must be a number between 1 and 30."
        elif idx == 5:
            used = len(wiz["class_skills"])
            picks = wiz["skill_picks"]
            if used < picks:
                return False, (f"Please choose {picks} class skill(s). "
                               f"You have chosen {used}.")
        return True, ""
 
    def on_next():
        idx = wiz["page"]
        ok, msg = validate_page(idx)
        if not ok:
            messagebox.showwarning("Missing Info", msg)
            return
 
        if idx == len(PAGES) - 1:
            finish()
        else:
            show_page(idx + 1)
 
    def on_back():
        idx = wiz["page"]
        if idx > 0:
            show_page(idx - 1)
 
    btn_next.config(command=on_next)
    btn_back.config(command=on_back)
 
    # -----------------------------------------------------------------------
    # FINISH — build result dict and call back
    # -----------------------------------------------------------------------
    def calc_hp():
        hd_str = str(class_info.get(wiz["class_name"].get(), {}).get("hit_die","d8"))
        try:
            hd_max = int(hd_str.replace("d","").replace("D",""))
        except:
            hd_max = 8
        try:
            lvl = int(wiz["level"].get())
        except:
            lvl = 1
        try:
            con = int(wiz["scores"]["CON"].get())
        except:
            con = 10
        con_racial = 0
        if wiz.get("race_row") is not None:
            try:
                con_racial += int(wiz["race_row"].get("Con", 0) or 0)
            except:
                pass
        if wiz.get("race_sub_row") is not None:
            try:
                con_racial += int(wiz["race_sub_row"].get("Con", 0) or 0)
            except:
                pass
        con_mod = (con - 10) // 2
        avg     = (hd_max // 2) + 1
        return max(1, (hd_max + con_mod) + (lvl - 1) * (avg + con_mod))

    def _clean(row, col, fallback):
        """Read value — subrace takes priority over base race row."""
        import math

        def is_empty(val):
            if val is None:
                return True
            if isinstance(val, float) and math.isnan(val):
                return True
            if str(val).strip().lower() in ("", "nan"):
                return True
            return False

        # Check subrace first
        sub = wiz.get("race_sub_row")
        if sub is not None:
            val = sub.get(col, None)
            if not is_empty(val):
                return str(val).strip()

        # Fall back to base race row
        if row is not None:
            val = row.get(col, None)
            if not is_empty(val):
                return str(val).strip()

        return fallback

    def finish():
        race_row = wiz.get("race_row")
        bg_row   = wiz.get("bg_row")
        prof_row = wiz.get("prof_row")
        final_scores = {}
        for stat in STATS:
            base   = 10
            racial = 0
            try:
                base = int(wiz["scores"][stat].get())
            except:
                pass
            col = STAT_COL[stat]
            if race_row is not None:
                try:
                    racial += int(race_row.get(col, 0) or 0)
                except:
                    pass
            # Add subrace bonus on top
            sub_row = wiz.get("race_sub_row")
            if sub_row is not None:
                try:
                    racial += int(sub_row.get(col, 0) or 0)
                except:
                    pass
            final_scores[stat] = base + racial
    # Silent HP calc
        hd_str = str(class_info.get(wiz["class_name"].get(), {}).get("hit_die", "d8"))
        try:
            hd_max = int(hd_str.replace("d","").replace("D",""))
        except:
            hd_max = 8
        try:
            lvl = int(wiz["level"].get())
        except:
            lvl = 1
        con_mod       = (final_scores.get("CON", 10) - 10) // 2
        avg_per_level = (hd_max // 2) + 1
        lv1_hp        = hd_max + con_mod
        extra_hp      = (lvl - 1) * (avg_per_level + con_mod) if lvl > 1 else 0
        total_hp      = max(1, lv1_hp + extra_hp)
 
        result = {
            # Identity
            "name":      wiz["name"].get().strip(),
            "sex":       wiz["sex"].get().strip(),
            "alignment": wiz["alignment"].get(),
 
            # Race
            "race":    wiz["race"].get(),
            "subrace": wiz["subrace"].get(),
            "speed":   _clean(race_row, "Speed", "30"),
            "size":    _clean(race_row, "Size",  "M"),
            "race_languages": str(race_row.get("Language", "")) if race_row is not None else "",
            "racial_bonus":   str(race_row.get("Bonus", ""))    if race_row is not None else "",
 
            # Background
            "background":    wiz["background"].get(),
            "bg_feature":    str(bg_row.get("Feature", ""))     if bg_row is not None else "",
            "bg_description":str(bg_row.get("Description", "")) if bg_row is not None else "",
            "bg_skills":     wiz["bg_skills"],
            "bg_languages":  str(bg_row.get("Languages", ""))   if bg_row is not None else "",
            "bg_tools":      str(bg_row.get("Tools", ""))        if bg_row is not None else "",
            "bg_gold":       str(bg_row.get("Gold", ""))         if bg_row is not None else "",
            "bg_equipment":  str(bg_row.get("Equipment", ""))   if bg_row is not None else "",
 
            # Class
            "class_name": wiz["class_name"].get(),
            "level":      wiz["level"].get(),
            "subclass":   wiz["subclass"].get(),
            "armor_pro":  str(prof_row.get("Armor_Pro", ""))    if prof_row is not None else "",
            "weapon_pro": str(prof_row.get("Weapons_Pro", ""))  if prof_row is not None else "",
            "tool_pro":   str(prof_row.get("Tools_Pro", ""))    if prof_row is not None else "",
            "saving_throws": str(prof_row.get("Savingthrows","")) if prof_row is not None else "",
 
            # Scores
            "scores": final_scores,
            "max_hp": total_hp, 
            # Skills
            "all_skill_profs": wiz["bg_skills"] + wiz["class_skills"],
        }
 
        win.destroy()
        on_complete(result)
 
    show_page(0)

# ---------------------------------------------------------------------------
# JSON HELPERS

def is_choice_feature(feature):

    return (
        feature.get("type")
        == "choice"
    )

# BUILD0: Chracter Feats
# ---------------------------------------------------------------------------
def open_levelup_popup():
    """Small popup to set level and recalculate HP."""
    popup = tk.Toplevel()
    popup.title("⬆️ Level Up")
    popup.geometry("340x420")
    popup.resizable(False, False)
    popup.grab_set()

    tk.Label(popup, text="Level Up", font=("Arial", 14, "bold")).pack(pady=(14,2))
    tk.Label(popup, text="Set your new level and confirm HP.",
             fg="gray", font=("Arial", 9)).pack(pady=(0,10))

    # --- Class & Level ---
    form = tk.Frame(popup)
    form.pack(padx=20, fill="x")

    def row_widgets(label, var, values=None, width=8):
        r = tk.Frame(form)
        r.pack(fill="x", pady=3)
        tk.Label(r, text=label, width=16, anchor="w").pack(side="left")
        if values:
            w = ttk.Combobox(r, textvariable=var, values=values,
                             state="readonly", width=width)
        else:
            w = tk.Spinbox(r, textvariable=var, from_=1, to=20, width=width)
        w.pack(side="left", padx=4)
        return w

    new_level = tk.StringVar(value=class1_level_var.get())
    row_widgets("New Level:", new_level)

    # --- HP Preview ---
    ttk.Separator(popup, orient="horizontal").pack(fill="x", padx=20, pady=10)
    tk.Label(popup, text="HP Calculation",
             font=("Arial", 10, "bold")).pack(anchor="w", padx=20)

    preview_txt = tk.Text(popup, height=7, width=34,
                          font=("Courier", 9), state="disabled",
                          relief="flat", bg=popup.cget("bg"))
    preview_txt.pack(padx=20, pady=6)

    def calc_hp_preview(*_):
        try:
            lvl = int(new_level.get())
        except:
            return

        cls  = class1_var.get()
        info = CLASS_INFO.get(cls, {})
        hd   = str(info.get("hit_die", "d8")).replace("d","").replace("D","")
        try:
            hd_max = int(hd)
        except:
            hd_max = 8

        try:
            con_score = int(sb_vars["CON"].get())
        except:
            con_score = 10
        con_mod = (con_score - 10) // 2

        avg_per_level = (hd_max // 2) + 1

        lv1_hp    = hd_max + con_mod
        extra_hp  = (lvl - 1) * (avg_per_level + con_mod) if lvl > 1 else 0
        total_hp  = lv1_hp + extra_hp

        lines = [
            f"Class:      {cls or '—'}",
            f"Hit Die:    d{hd_max}",
            f"CON mod:    {'+' if con_mod >= 0 else ''}{con_mod}",
            f"",
            f"Lv 1:       {hd_max} + {con_mod} = {lv1_hp}",
        ]
        if lvl > 1:
            lines.append(
                f"Lv 2-{lvl}:    "
                f"{lvl-1} × ({avg_per_level}+{con_mod}) = {extra_hp}"
            )
        lines += [
            f"{'─'*28}",
            f"Total HP:   {total_hp}",
        ]

        preview_txt.config(state="normal")
        preview_txt.delete("1.0", tk.END)
        preview_txt.insert("1.0", "\n".join(lines))
        preview_txt.config(state="disabled")

        return total_hp

    new_level.trace_add("write", calc_hp_preview)
    calc_hp_preview()

    # --- Confirm ---
    def apply_levelup():
        try:
            lvl = int(new_level.get())
        except:
            messagebox.showwarning("Invalid", "Please enter a valid level.")
            return

        total_hp = calc_hp_preview()
        if total_hp is None:
            return

        if not messagebox.askyesno("Confirm Level Up",
                f"Set level to {lvl} and Max HP to {total_hp}?"):
            return

        # Apply level
        class1_level_var.set(str(lvl))

        # Apply HP
        if hp_vars:
            hp_vars["max"].set(str(total_hp))
            hp_vars["cur"].set(str(total_hp))

        # Refresh everything
        refresh_feats()
        update_all_skills()
        refresh_spells()

        popup.destroy()
        messagebox.showinfo("Leveled Up!",
            f"🎉 {class1_var.get()} is now level {lvl} with {total_hp} HP!")

    tk.Button(popup, text="⬆️ Apply Level Up",
              command=apply_levelup,
              bg="#27ae60", fg="white",
              font=("Arial", 11, "bold"),
              width=20).pack(pady=10)

def build_feats_tab(parent):
    global feats_listbox, feats_desc_text

    main = tk.Frame(parent)
    main.pack(fill="both", expand=True)

    def build_feats_tab(parent):
        global feats_listbox

    # --- Action bar ---
    action_bar = tk.Frame(parent)
    action_bar.pack(fill="x", padx=8, pady=(6,2))

    tk.Button(action_bar, text="⬆️ Level Up",
              command=open_levelup_popup,
              bg="#27ae60", fg="white",
              font=("Arial", 9, "bold")).pack(side="left", padx=4)
    tk.Button(action_bar, text="⛺ Rest",
                command=open_rest_popup,
                bg="#2c3e50", fg="white",
                font=("Arial", 9, "bold")).pack(side="left", padx=4)
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
    global JSON_FEATS_CACHE 
    sel = feats_listbox.curselection()
    if not sel:
        return
    index = sel[0]
    df = PROG_DF
    df["class_level"] = pd.to_numeric(df["class_level"], errors="coerce").fillna(0)
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

    if index < len(JSON_FEATS_CACHE):

        feat = JSON_FEATS_CACHE[index]

        feats_desc_text.delete("1.0", tk.END)

        text = (
            f"{feat['data']['name']}\n\n"
            f"Class: {feat['class'].title()}\n"
            f"Level: {feat['level']}\n"
            f"Type: {feat['type']}\n\n"
        )

        if "text" in feat["data"]:
            text += "\n".join(feat["data"]["text"])

        feats_desc_text.insert("1.0", text)

        return

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
    global JSON_FEATS_CACHE
    if feats_listbox is None:
        return
    feats_listbox.delete(0, tk.END)

    df = PROG_DF
    df["class_level"] = pd.to_numeric(df["class_level"], errors="coerce").fillna(0)
    JSON_FEATS_CACHE = []
    all_feats = pd.DataFrame()
    if df.empty:
        return
    # =========================
    # CLASS 1
    # =========================

    cls1 = class1_var.get()
    sub1 = subclass1_var.get()

    try:
        lvl1 = int(class1_level_var.get())
    except:
        lvl1 = 0
    print("=== DEBUG CLASS ===")
    print("Class 1:", cls1)
    print("Subclass 1:", sub1)
    print("Level 1:", lvl1)
    print("CLASS_JSON keys:", CLASS_JSON.keys())
    if cls1 and lvl1 > 0:
        if cls1.lower() in CLASS_JSON:
            print("JSON CLASS FOUND!")
            JSON_FEATS_CACHE.extend(
                get_features_for_character(
                    cls1,
                    sub1,
                    lvl1
                )
            )
            print("JSON FEATS FOUND:", len(JSON_FEATS_CACHE))
        else:
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
        if cls2.lower() in CLASS_JSON:

            JSON_FEATS_CACHE.extend(
                get_features_for_character(
                    cls2,
                    sub2,
                    lvl2
                )
            )

        else:
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
    if all_feats.empty and not JSON_FEATS_CACHE:
        return

    if not all_feats.empty:
        all_feats = all_feats.sort_values(by="class_level")

    # JSON features first
    for feat in JSON_FEATS_CACHE:
        print(feat["type"], feat["data"]["name"])
        feat_type = feat.get("type", "feature")

        prefix = ""

        if feat_type == "choice":
            prefix = "[CHOICE] "

        elif feat_type == "table":
            prefix = "[TABLE] "

        elif feat_type == "resource":
            prefix = "[RESOURCE] "

        name = (
            f"{feat['class'].title()} "
            f"Lv {feat['level']} "
            f"- {prefix}{feat['data']['name']}"
        )

        feats_listbox.insert(tk.END, name)

    # Excel features second
    if not all_feats.empty:

        for _, row in all_feats.iterrows():

            name = (
                f"{row['class_id']} "
                f"Lv {int(row['class_level'])} "
                f"- {row['name']}"
            )

            feats_listbox.insert(tk.END, name)
# ---------------------------------------------------------------------------
# BUILD000: CHARACTER IDENTITY
# ---------------------------------------------------------------------------

def get_spell_slots():

    slots = {
        1:0, 2:0, 3:0,
        4:0, 5:0, 6:0,
        7:0, 8:0, 9:0
    }

    class_data = [
        (class1_var.get(), int(class1_level_var.get())),
        (class2_var.get(), int(class2_level_var.get()))
    ]

    for cls, lvl in class_data:

        if cls not in CLASS_INFO:
            continue

        if lvl <= 0:
            continue

        caster_type = CLASS_INFO[cls].get("caster_type", "None")

        if caster_type in ("None", "KI", "—"):
            continue

        row_name = f"L{lvl}_{caster_type}"

        match = SLOTS_DF[
            SLOTS_DF["Caster_Level"] == row_name
        ]

        if match.empty:
            continue

        row = match.iloc[0]

        for spell_lvl in range(1, 10):

            col = f"Slot_Level_{spell_lvl}"

            if col in row:

                try:
                    slots[spell_lvl] += int(row[col])
                except:
                    pass

    return slots
def update_spell_slots():

    slots = get_spell_slots()

    for lvl in range(1, 10):

        value = slots.get(lvl, 0)

        if lvl in spell_slot_vars:
            spell_slot_vars[lvl].set(value)



def build_identity(parent):
    frame = ttk.LabelFrame(parent, text=" Character Identity ")
    frame.pack(fill="x", padx=10, pady=5)
    global race_var, background_var
    global name_entry, sex_entry
    global skills_lbl, languages_lbl, equipment_lbl
    global cantrip_label, spells_known_label
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
        refresh_spell_slots()   # ← add this

    def on_class2_selected(event=None):
        cls = class2_var.get()
        subs = SUBCLASS_MAP.get(cls, [])
        subclass2_box.config(values=subs)
        subclass2_var.set("")
        refresh_feats()
        refresh_spell_slots()   # ← add this

    def update_player_level(*args):
        try: lv1 = int(class1_level_var.get())
        except: lv1 = 0
        try: lv2 = int(class2_level_var.get())
        except: lv2 = 0
        player_level_var.set(str(lv1 + lv2))
        refresh_spell_slots()   # ← add this


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

    class1_var.trace_add("write",       lambda *_: refresh_spell_slots())
    class2_var.trace_add("write",       lambda *_: refresh_spell_slots())
    class1_level_var.trace_add("write", lambda *_: refresh_spell_slots())
    class2_level_var.trace_add("write", lambda *_: refresh_spell_slots())

def build_save_load(parent):
    global prof_text   
    frame = tk.Frame(parent)
    frame.pack(fill="x", padx=10, pady=5)
# ==================================================
# PROFICIENCIES & TRAINING
# ==================================================

    prof_frame = ttk.LabelFrame(parent, text=" Proficiency & Training ")
    prof_frame.pack(side="left", fill="y", padx=5, pady=5)
    prof_text = tk.Text(
        prof_frame,
        height=25,
        width=35,
        wrap="word",
        font=("Century Gothic", 8)
    )
    prof_text.pack(fill="both", expand=False, padx=6, pady=6)

    starter_text = """
    Armor:
    —
    Weapons:
    —
    Tools:
    —
    Languages:
    —
    Saving Throws:
    —
    Senses:
    —
    Other:
    —
    """
    prof_text.insert("1.0", starter_text)
    prof_text.config(state="disabled")

def build_combat_hud(parent):
    global ac_var, speed_var, passive_var, initiative_label
    global cantrip_label, spells_known_label
    frame = ttk.LabelFrame(parent, text=" Combat & Actions ")
    frame.pack(side="left", fill="both", expand=False, padx=5)

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

    init_b = tk.Frame(top, relief="groove", bd=1)
    init_b.pack(side="left", padx=8)
    tk.Label(init_b, text="Initiative", font=("Arial",8)).pack()
    initiative_label = tk.Label(init_b, text="+0",
                                 font=("Arial",13,"bold"), fg="blue", width=4)
    initiative_label.pack(padx=4, pady=2)
    
    ac_var      = editable_bubble(top, "AC", "10")
    speed_var   = editable_bubble(top, "Speed (ft)", "30")
    passive_var = editable_bubble(top, "Passive Perc.", "10")

    # Condition
    cond_b = tk.Frame(top, relief="groove", bd=1)
    cond_b.pack(side="left", padx=4)
    tk.Label(cond_b, text="Condition", font=("Arial",8)).pack()

    CONDITIONS = [
        "—",
        "Blinded", "Charmed", "Deafened",
        "Exhaustion 1", "Exhaustion 2", "Exhaustion 3",
        "Exhaustion 4", "Exhaustion 5",
        "Frightened", "Grappled", "Incapacitated",
        "Invisible", "Paralyzed", "Petrified",
        "Poisoned", "Prone", "Restrained",
        "Stunned", "Unconscious",
    ]

    condition_var = tk.StringVar(value="—")
    condition_box = ttk.Combobox(
        cond_b,
        textvariable=condition_var,
        values=CONDITIONS,
        state="readonly",
        width=10,
        font=("Arial",9)
    )
    condition_box.pack(padx=4, pady=2)

    def on_condition_change(event=None):
        cond = condition_var.get()
        if cond == "—":
            condition_box.config(foreground="black")
            return
        # Color code by severity
        danger = {"Paralyzed","Petrified","Stunned","Unconscious","Incapacitated"}
        caution = {"Blinded","Charmed","Deafened","Frightened",
                   "Grappled","Poisoned","Prone","Restrained","Invisible"}
        exhaust = {f"Exhaustion {i}" for i in range(1,6)}

        if cond in danger:
            condition_box.config(foreground="#c0392b")   # red
        elif cond in caution:
            condition_box.config(foreground="#e67e22")   # orange
        elif cond in exhaust:
            level = int(cond[-1])
            colors = ["#f1c40f","#e67e22","#e74c3c",
                      "#c0392b","#8e44ad"]
            condition_box.config(foreground=colors[level-1])
        else:
            condition_box.config(foreground="black")

    condition_box.bind("<<ComboboxSelected>>", on_condition_change)

    # HP Tracker
    hp_frame = ttk.LabelFrame(frame, text=" Hit Points ")
    hp_frame.pack(fill="x", padx=6, pady=6)
    global hp_vars
    global hitdice1_var, hitdice2_var

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
    # Death Saves — sits right next to Hit Dice
    death_cell = tk.Frame(hp_frame)
    death_cell.grid(row=0, column=5)

    tk.Label(death_cell, text="Death Sav",
             font=("Arial",8,"bold")).pack()

    death_save_var = tk.StringVar(value="")
    tk.Entry(death_cell, textvariable=death_save_var,
             width=6, justify="center",
             font=("Arial",10,"bold"),
             fg="darkred").pack(pady=2)

    tk.Label(death_cell, text="✓/✗",
             fg="gray", font=("Arial",8)).pack()


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
    tk.Label(btn_row, text="amt", justify="left").pack(side="bottom")
    tk.Button(btn_row, text="– Damage", bg="#c0392b", fg="white",
              command=lambda: adjust_hp(-1)).pack(side="left", padx=3)
    tk.Button(btn_row, text="+ Heal", bg="#27ae60", fg="white",
              command=lambda: adjust_hp(1)).pack(side="left", padx=3)
    tk.Entry(btn_row, textvariable=amt_var, width=5, justify="center").pack(side="left", padx=3)
    tk.Button(btn_row, text="Apply–", bg="#c0392b", fg="white",
              command=lambda: apply_amt(-1)).pack(side="left", padx=2)
    tk.Button(btn_row, text="Apply+", bg="#27ae60", fg="white",
              command=lambda: apply_amt(1)).pack(side="left", padx=2)

# Weapon slots
    wp_frame = ttk.LabelFrame(frame, text=" Weapon / Attack Slots ")
    wp_frame.pack(fill="x", padx=6, pady=6)

    headers = [("Weapon", 14), ("To Hit", 7), ("Damage", 8),
               ("Type", 10), ("Bonus", 5)]
    for col, (hdr, w) in enumerate(headers):
        tk.Label(wp_frame, text=hdr, font=("Arial", 8, "bold"),
                 width=w, anchor="center").grid(row=0, column=col, padx=3, pady=2)

    weapon_slot_vars.clear()
    for r in range(1, 4):
        slot = {
            "weapon":  tk.StringVar(value="—"),
            "to_hit":  tk.StringVar(value="—"),
            "damage":  tk.StringVar(value="—"),
            "type":    tk.StringVar(value="—"),
            "bonus":   tk.StringVar(value="0"),
        }
        weapon_slot_vars.append(slot)

        # Weapon dropdown
        cb = ttk.Combobox(wp_frame, textvariable=slot["weapon"],
                          values=["—"], state="readonly", width=13)
        cb.grid(row=r, column=0, padx=3, pady=2)
        slot["cb"] = cb
        # To Hit / Damage / Type — read only display
        for col_i, key in enumerate(["to_hit", "damage", "type"], start=1):
            widths = [7, 8, 10]
            tk.Entry(wp_frame, textvariable=slot[key],
                     width=widths[col_i - 1], justify="center",
                     state="readonly",
                     readonlybackground="#2c3e50",
                     fg="white",
                     font=("Arial", 9, "bold")).grid(row=r, column=col_i,
                                                      padx=3, pady=2)

        # Bonus — manually editable, triggers recalc
        bonus_entry = tk.Entry(wp_frame, textvariable=slot["bonus"],
                               width=5, justify="center")
        bonus_entry.grid(row=r, column=4, padx=3, pady=2)

        # Bind weapon selection and bonus change
        def on_weapon_select(event=None, s=slot):
            recalc_weapon_slot(s)

        def on_bonus_change(*_, s=slot):
            recalc_weapon_slot(s)

        cb.bind("<<ComboboxSelected>>", on_weapon_select)
        slot["bonus"].trace_add("write", on_bonus_change)

    # ---------------------------
    # SPELL SLOTS
    # ---------------------------

    spell_frame = ttk.LabelFrame(frame, text=" Spellcasting ")
    spell_frame.pack(fill="x", padx=6, pady=6)
    global cantrip_label, spells_known_label
    # Static info row
    info_row = tk.Frame(spell_frame)
    info_row.pack(fill="x", padx=8, pady=(4, 2))

    cantrip_label = tk.Label(info_row, text="Cantrips: —",
                             font=("Arial", 9), fg="cyan", anchor="w")
    cantrip_label.pack(side="left", padx=(0, 16))

    spells_known_label = tk.Label(info_row, text="Spells Known: —",
                                  font=("Arial", 9), fg="cyan", anchor="w")
    spells_known_label.pack(side="left")

    slots_container = tk.Frame(spell_frame)
    slots_container.pack()

    left_col = tk.Frame(slots_container)
    left_col.pack(side="left", padx=20)

    right_col = tk.Frame(slots_container)
    right_col.pack(side="left", padx=20)

    # LEFT SIDE (1–4)
    for level in range(1, 5):

        row = tk.Frame(left_col)
        row.pack(anchor="w", pady=2)

        tk.Label(
            row,
            text=str(level),
            width=2,
            font=("Arial", 10, "bold")
        ).pack(side="left")

        spell_slot_vars[level] = [True] * 4
        spell_slot_labels[level] = []

        for i in range(4):

            lbl = tk.Label(
                row,
                text="★",
                font=("Arial", 14),
                fg="cyan",
                cursor="hand2"
            )

            lbl.pack(side="left", padx=1)

            lbl.bind(
                "<Button-1>",
                lambda e, l=level, idx=i:
                    toggle_spell_slot(l, idx)
            )

            spell_slot_labels[level].append(lbl)

    # RIGHT SIDE (5–8)
    for level in range(5, 9):

        row = tk.Frame(right_col)
        row.pack(anchor="w", pady=2)

        tk.Label(
            row,
            text=str(level),
            width=2,
            font=("Arial", 10, "bold")
        ).pack(side="left")

        spell_slot_vars[level] = [True] * 4
        spell_slot_labels[level] = []

        for i in range(4):

            lbl = tk.Label(
                row,
                text="★",
                font=("Arial", 14),
                fg="cyan",
                cursor="hand2"
            )

            lbl.pack(side="left", padx=1)

            lbl.bind(
                "<Button-1>",
                lambda e, l=level, idx=i:
                    toggle_spell_slot(l, idx)
            )

            spell_slot_labels[level].append(lbl)

    # LEVEL 9 CENTERED
    row9 = tk.Frame(spell_frame)
    row9.pack(pady=(6, 2))

    tk.Label(
        row9,
        text="9",
        width=2,
        font=("Arial", 10, "bold")
    ).pack(side="left")

    spell_slot_vars[9] = [True] * 4
    spell_slot_labels[9] = []

    for i in range(4):

        lbl = tk.Label(
            row9,
            text="★",
            font=("Arial", 14),
            fg="cyan",
            cursor="hand2"
        )

        lbl.pack(side="left", padx=1)

        lbl.bind(
            "<Button-1>",
            lambda e, l=9, idx=i:
                toggle_spell_slot(l, idx)
        )

        spell_slot_labels[9].append(lbl)

def build_skills(parent):
    global prof_info_label, save_prof_vars, save_labels

    frame = ttk.LabelFrame(parent, text=" Core Skills ")
    frame.pack(side="left", fill="both", padx=5, pady=5)

    prof_info_label = tk.Label(frame, text="Prof: +2",
                                font=("Arial", 8), fg="gray")
    prof_info_label.pack(anchor="w", padx=4, pady=(2, 6))

    grouped_skills = {
        "STR": ["Athletics"],
        "DEX": ["Acrobatics", "Sleight of Hand", "Stealth"],
        "CON": [],
        "INT": ["Arcana", "History", "Investigation", "Nature", "Religion"],
        "WIS": ["Animal Handling", "Insight", "Medicine", "Perception", "Survival"],
        "CHA": ["Deception", "Intimidation", "Performance", "Persuasion"],
    }

    pairs = [("STR", "DEX"), ("CON", "CHA"), ("INT", "WIS")]

    def build_stat_card(container, stat):
        skills = grouped_skills.get(stat, [])
        card   = ttk.LabelFrame(container, text=f" {stat} ")
        card.pack(side="left", fill="both", expand=True, padx=3, pady=4)

        top = tk.Frame(card)
        top.pack(fill="x")

        score_frame = tk.Frame(top)
        score_frame.pack(side="left", padx=4)
        tk.Label(score_frame, textvariable=sb_vars[stat],
                 font=("Arial", 14, "bold"), width=3).pack()
        mod_lbl = tk.Label(score_frame, text="(+0)", fg="gray",
                            font=("Arial", 10, "bold"))
        mod_lbl.pack()
        mod_display_labels[stat] = mod_lbl

        save_frame = tk.Frame(top)
        save_frame.pack(side="left", padx=6)
        save_prof = tk.BooleanVar()
        save_prof_vars[stat] = save_prof
        save_cb = ttk.Checkbutton(
            save_frame,
            variable=save_prof,
            command=update_all_skills
        )

        save_cb.pack(side="left", padx=2)
        save_lbl = tk.Label(save_frame, text="Save +0",
                             fg="darkred", font=("Arial", 8, "bold"))
        save_lbl.pack(side="left")
        save_labels[stat] = save_lbl

        sb_vars[stat].trace_add("write",
                                 lambda *_, s=stat: on_stat_change(s))

        for skill in skills:
            row      = tk.Frame(card)
            row.pack(fill="x", padx=4, pady=1)
            prof_var = tk.BooleanVar()

            if not hasattr(tk, "_skill_name_map"):
                tk._skill_name_map = {}
            tk._skill_name_map[skill] = prof_var

            cb = ttk.Checkbutton(
                row,
                variable=prof_var,
                command=update_all_skills
            )
            cb.pack(side="left", padx=2)

            btn = tk.Button(row, text=skill, anchor="w",
                            relief="flat", font=("Arial", 8))
            btn.pack(side="left", fill="x", expand=True)

            lbl = tk.Label(row, text="+0", fg="blue",
                           font=("Arial", 10, "bold"), width=4)
            lbl.pack(side="right")

            btn.bind("<Button-1>",
                     lambda e, s=stat, v=prof_var: roll_skill(s, v, 0))
            btn.bind("<Shift-Button-1>",
                     lambda e, s=stat, v=prof_var: roll_skill(s, v, 1))
            btn.bind("<Button-3>",
                     lambda e, s=stat, v=prof_var: roll_skill(s, v, -1))

            skill_labels.append((lbl, stat, prof_var))

    for stat_a, stat_b in pairs:
        pair_row = tk.Frame(frame)
        pair_row.pack(fill="x", pady=2)
        build_stat_card(pair_row, stat_a)
        build_stat_card(pair_row, stat_b)

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


def toggle_spell_slot(level, idx):
    """Toggle a spell slot used/available — only if slot exists."""
    cls1 = class1_var.get()
    cls2 = class2_var.get()
    try: lvl1 = int(class1_level_var.get() or 0)
    except: lvl1 = 0
    try: lvl2 = int(class2_level_var.get() or 0)
    except: lvl2 = 0

    # Check slot actually exists before toggling
    if level not in spell_slot_vars:
        return
    if idx >= len(spell_slot_vars[level]):
        return
    # Don't toggle invisible slots
    lbl = spell_slot_labels[level][idx]
    if lbl.cget("fg") == "#1e1e2e":
        return

    # Toggle
    spell_slot_vars[level][idx] = not spell_slot_vars[level][idx]
    active = spell_slot_vars[level][idx]
    lbl.config(
        fg="cyan" if active else "gray",
        text="★"  if active else "☆"
    )
def refresh_spell_slots():
    if SLOTS_DF is None or SLOTS_DF.empty:
        return
    if not spell_slot_labels:
        return

    # --- Determine effective caster levels ---
    cls1 = class1_var.get()
    cls2 = class2_var.get()
    try: lvl1 = int(class1_level_var.get() or 0)
    except: lvl1 = 0
    try: lvl2 = int(class2_level_var.get() or 0)
    except: lvl2 = 0

    def get_caster_type(cls):
        return CLASS_INFO.get(cls, {}).get("caster_type", "none").strip()

    def effective_caster_level(cls, lvl):
        ct = get_caster_type(cls)
        if ct in ("Full",):          return lvl
        if ct in ("Half",):          return lvl // 2
        if ct in ("Quarter",):       return lvl // 4
        if ct == "Artificer":        return -lvl   # handled separately
        if ct == "Warlock":          return 0      # handled separately
        return 0

    ct1 = get_caster_type(cls1)
    ct2 = get_caster_type(cls2)

    # --- Warlock slots (always separate) ---
    warlock_key = None
    if ct1 == "Warlock" and lvl1 > 0:
        warlock_key = f"L{lvl1}_Warlock"
    elif ct2 == "Warlock" and lvl2 > 0:
        warlock_key = f"L{lvl2}_Warlock"

    # --- Artificer slots ---
    artificer_key = None
    if ct1 == "Artificer" and lvl1 > 0:
        artificer_key = f"L{lvl1}_Artificer"
    elif ct2 == "Artificer" and lvl2 > 0:
        artificer_key = f"L{lvl2}_Artificer"

    # --- Combined multiclass caster level ---
    ecl = 0
    for cls, lvl in [(cls1, lvl1), (cls2, lvl2)]:
        ct = get_caster_type(cls)
        if ct == "Full":     ecl += lvl
        elif ct == "Half":   ecl += lvl // 2
        elif ct == "Quarter": ecl += lvl // 4
        # Warlock and Artificer handled separately

# --- Determine which key to look up ---
    if warlock_key and ecl == 0:
        lookup_key = warlock_key
    elif artificer_key and ecl == 0:
        lookup_key = artificer_key
    elif ecl > 0:
        lookup_key = f"L{ecl}_FullCaster"
    # --- Monk ---
    elif ct1 == "Monk" and lvl1 > 0:
        lookup_key = f"L{lvl1}_Monk"
    elif ct2 == "Monk" and lvl2 > 0:
        lookup_key = f"L{lvl2}_Monk"
    # --- Barbarian ---
    elif ct1 == "Barbarian" and lvl1 > 0:
        lookup_key = f"L{lvl1}_Barbarian"
    elif ct2 == "Barbarian" and lvl2 > 0:
        lookup_key = f"L{lvl2}_Barbarian"
    else:
        for level in range(1, 10):
            if level in spell_slot_labels:
                for lbl in spell_slot_labels[level]:
                    lbl.config(fg="#1e1e2e", text="★")
        return
    # --- Look up slot row ---
    df  = SLOTS_DF
    col = "Caster_Level" if "Caster_Level" in df.columns else df.columns[0]
    row_match = df[df[col].astype(str).str.strip() == lookup_key]

    # Also check warlock separately if multiclassing
    warlock_row = None
    if warlock_key and ecl > 0:
        wm = df[df[col].astype(str).str.strip() == warlock_key]
        if not wm.empty:
            warlock_row = wm.iloc[0]

    if row_match.empty:
        return

    slot_row = row_match.iloc[0]

# --- Monk: show Ki Points, hide slots ---
    if lookup_key and "Monk" in lookup_key:
        for level in range(1, 10):
            if level in spell_slot_labels:
                for lbl in spell_slot_labels[level]:
                    lbl.config(fg="#1e1e2e", text="★")
        try:
            ki = slot_row.get("Ki_Points", 0)
            ki_count = int(ki) if pd.notna(ki) else 0
            if spells_known_label is not None:
                spells_known_label.config(text=f"Ki Points: {ki_count}")
            if cantrip_label is not None:
                cantrip_label.config(text="Cantrips: —")
        except:
            pass
        return

    # --- Barbarian: show Rage count + damage bonus, hide slots ---
    if lookup_key and "Barbarian" in lookup_key:
        for level in range(1, 10):
            if level in spell_slot_labels:
                for lbl in spell_slot_labels[level]:
                    lbl.config(fg="#1e1e2e", text="★")
        try:
            rage_count  = slot_row.get("Rage_Count", 0)
            rage_damage = slot_row.get("Rage_Damage", "+2")
            rc = int(rage_count) if pd.notna(rage_count) else 0
            rd = str(rage_damage).strip() if pd.notna(rage_damage) else "+2"
            if rc == 36:
                rc_display = "∞"
            else:
                rc_display = str(rc)
            if spells_known_label is not None:
                spells_known_label.config(
                    text=f"Rages: {rc_display} | Bonus: {rd}")
            if cantrip_label is not None:
                cantrip_label.config(text="Cantrips: —")
        except:
            pass
        return


    # --- Update star displays ---
    slot_col_map = {
        1: "Slot_Level_1", 2: "Slot_Level_2", 3: "Slot_Level_3",
        4: "Slot_Level_4", 5: "Slot_Level_5", 6: "Slot_Level_6",
        7: "Slot_Level_7", 8: "Slot_Level_8", 9: "Slot_Level_9",
    }

    for level in range(1, 10):
        if level not in spell_slot_labels:
            continue

        col_name = slot_col_map.get(level)
        count = 0

        try:
            val = slot_row.get(col_name, 0)
            count = int(val) if pd.notna(val) else 0
        except:
            count = 0

        # Warlock pact slots override levels 1-5 if multiclassing
        if warlock_row is not None and level <= 5:
            try:
                wval = warlock_row.get(col_name, 0)
                wcount = int(wval) if pd.notna(wval) else 0
                # Warlock slots are separate — add them
                count += wcount
            except:
                pass

        labels = spell_slot_labels[level]
        for i, lbl in enumerate(labels):
            if i < count:
                # Slot exists — show active or used based on current state
                if spell_slot_vars.get(level) and i < len(spell_slot_vars[level]):
                    active = spell_slot_vars[level][i]
                else:
                    active = True
                lbl.config(
                    fg="cyan"  if active else "gray",
                    text="★"   if active else "☆"
                )
            else:
                # Slot doesn't exist at this level — hide it
                lbl.config(fg="#1e1e2e", text="★")  # invisible

# --- Cantrips Known ---
    cantrip_count = 0
    df_stripped = SLOTS_DF.copy()
    df_stripped.columns = [c.strip() for c in df_stripped.columns]

    for cls, lvl in [(cls1, lvl1), (cls2, lvl2)]:
        if not cls or cls in ("Class", "") or lvl <= 0:
            continue

        # Step 1: Class → Caster_Type
        ct = CLASS_INFO.get(cls, {}).get("caster_type", "none")
        if ct == "none":
            continue

        # Step 2: Class → ClassName_Cantrips column
        col_name = CANTRIP_COL.get(cls, "").strip()
        if not col_name:
            continue
        if col_name not in df_stripped.columns:
            print(f"Column not found: {col_name}")
            continue

        # Step 3: Find row where Caster_Type AND class_lv both match
        try:
            cant_rows = df_stripped[
                (df_stripped["Caster_Type"].astype(str).str.strip() == ct) &
                (df_stripped["class_lv"].apply(
                    lambda x: int(float(x)) if pd.notna(x) else -1
                ) == lvl)
            ]
            if not cant_rows.empty:
                val = cant_rows.iloc[0][col_name]
                cantrip_count += int(val) if pd.notna(val) and str(val) != "" else 0
        except Exception as e:
            print(f"Cantrip lookup error: {type(e).__name__}: {e}")
    if cantrip_label is not None:
        cantrip_label.config(
            text=f"Cantrips: {cantrip_count if cantrip_count > 0 else '—'}"
        )
# --- Spells Known / Prepared ---
    spells_known_count = 0
    spells_known_label_text = "Known"
    artificer_infusions = 0
    artificer_infused   = 0
    show_artificer      = False

    sp_df = SLOTS_DF.copy()
    sp_df.columns = [c.strip() for c in sp_df.columns]

    # Stat mod helpers
    def get_mod(stat):
        try:
            score = int(sb_vars[stat].get())
            return (score - 10) // 2
        except:
            return 0

    PREPARED_CLASSES = {"Cleric", "Druid", "Wizard", "Paladin", "Artificer"}

    STATIC_SPELLS_COL = {
        "Bard":     "Bard_Spells",
        "Sorcerer": "Sorcerer_Spells",
        "Ranger":   "Ranger_Spells",
        "Fighter":  "Fighter_Spells",
        "Rogue":    "Rogue_Spells",
        "Warlock":  "Warlock_Spells",
    }

    for cls, lvl in [(cls1, lvl1), (cls2, lvl2)]:
        if not cls or cls in ("Class", "") or lvl <= 0:
            continue

        ct = CLASS_INFO.get(cls, {}).get("caster_type", "none")

        # --- Artificer infusions (separate display) ---
        if cls == "Artificer":
            show_artificer = True
            try:
                art_rows = sp_df[
                    (sp_df["Caster_Type"].astype(str).str.strip() == "Artificer") &
                    (sp_df["class_lv"].apply(
                        lambda x: int(float(x)) if pd.notna(x) else -1
                    ) == lvl)
                ]
                if not art_rows.empty:
                    inf_val = art_rows.iloc[0].get("Artificer_Infusions", 0)
                    ied_val = art_rows.iloc[0].get("Artificer_Infused", 0)
                    artificer_infusions = int(inf_val) if pd.notna(inf_val) else 0
                    artificer_infused   = int(ied_val) if pd.notna(ied_val) else 0
            except Exception as e:
                print(f"Artificer infusion error: {e}")

            # Artificer prepared spells = INT mod + half level rounded down
            prep = get_mod("INT") + (lvl // 2)
            spells_known_count += max(0, prep)
            spells_known_label_text = "Prepared"
            continue

        # --- Formula classes ---
        if cls == "Cleric":
            spells_known_count += max(0, get_mod("WIS") + lvl)
            spells_known_label_text = "Prepared"
            continue

        if cls == "Druid":
            spells_known_count += max(0, get_mod("WIS") + lvl)
            spells_known_label_text = "Prepared"
            continue

        if cls == "Wizard":
            spells_known_count += max(0, get_mod("INT") + lvl)
            spells_known_label_text = "Prepared"
            continue

        if cls == "Paladin":
            spells_known_count += max(0, get_mod("CHA") + (lvl // 2))
            spells_known_label_text = "Prepared"
            continue

        # --- Ki Points (Monk — in Full chart) ---
        if cls == "Monk":
            try:
                monk_rows = sp_df[
                    (sp_df["Caster_Type"].astype(str).str.strip() == "Full") &
                    (sp_df["class_lv"].apply(
                        lambda x: int(float(x)) if pd.notna(x) else -1
                    ) == lvl)
                ]
                if not monk_rows.empty:
                    ki_val = monk_rows.iloc[0].get("Ki_Points", 0)
                    spells_known_count += int(ki_val) if pd.notna(ki_val) else 0
                    spells_known_label_text = "Ki Points"
            except Exception as e:
                print(f"Ki points error: {e}")
            continue

        # --- Static lookup classes ---
        col_name = STATIC_SPELLS_COL.get(cls, "").strip()
        if not col_name:
            continue
        if col_name not in sp_df.columns:
            print(f"Spells col not found: {col_name}")
            continue

        try:
            sp_rows = sp_df[
                (sp_df["Caster_Type"].astype(str).str.strip() == ct) &
                (sp_df["class_lv"].apply(
                    lambda x: int(float(x)) if pd.notna(x) else -1
                ) == lvl)
            ]
            if not sp_rows.empty:
                val = sp_rows.iloc[0][col_name]
                spells_known_count += int(val) if pd.notna(val) else 0
                spells_known_label_text = "Known"
        except Exception as e:
            print(f"Spells known error: {e}")

    # --- Update labels ---
    if spells_known_label is not None:
        if show_artificer:
            spells_known_label.config(
                text=f"Prepared: {spells_known_count} | "
                     f"Infusions: {artificer_infusions} | "
                     f"Infused: {artificer_infused}"
            )
        else:
            spells_known_label.config(
                text=f"{spells_known_label_text}: "
                     f"{spells_known_count if spells_known_count > 0 else '—'}"
            )
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

    equip_listbox = tk.Listbox(equip_col, width=18, height=15, selectmode="single")
    equip_listbox.pack(fill="y")
    
    tk.Label(diagram_col, text="Spell Visual", font=("Arial", 10, "bold")).pack()

    diagram_canvas = tk.Canvas(diagram_col, bg="white", height=250)
    diagram_canvas.pack(fill="both", expand=True)


    bar = tk.Frame(main_row)
    bar.pack(fill="x", padx=6, pady=4)

    tk.Label(bar, text="").pack(side="left")
    spell_class_var = tk.StringVar(value="All")
    cb = ttk.Combobox(bar, textvariable=spell_class_var,
                      values=["All"] + sorted(CLASS_INFO.keys()),
                      width=3, state="readonly")
    cb.pack(side="left", padx=4)
    cb.bind("<<ComboboxSelected>>", refresh_spells)

    tk.Label(bar, text="Lv:").pack(side="left", padx=(8,0))
    spell_level_var = tk.StringVar(value="")
    lcb = ttk.Combobox(bar, textvariable=spell_level_var,
                       values=["All","0","1","2","3","4","5","6","7","8","9"],
                       width=1, state="readonly")
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
    global backpack_listbox, equipped_listbox, item_listbox, item_type_var, item_desc_text, equipment_backpack_listbox, global_refs, backpack_items, refresh_backpack_func
    backpack_items = []
    global backpack_items_global
    equipped_items = []
    backpack_items_global = backpack_items
    # Store the refresh function globally
    def refresh_backpack():
        backpack_listbox.delete(0, tk.END)
        for item in backpack_items:
            backpack_listbox.insert(tk.END, item)
    
    # Make refresh_backpack available globally
    refresh_backpack_func = refresh_backpack

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
    global_refs["backpack_listbox"] = backpack_listbox  # ← ADD THIS
    
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

        category = item_type_var.get()
        df = ITEM_SHEETS.get(category)

        if df is None or df.empty:
            return

        name_col = df.columns[0]

        match = df[df[name_col] == item_name]

        if match.empty:
            return

        row = match.iloc[0]

        # -------------------------
        # GET COST
        # -------------------------

        cost_text = row.get("Cost", "0 gp")

        item_cost_cp = parse_cost(cost_text)

        current_money_cp = wallet_to_cp()

        # -------------------------
        # CHECK FUNDS
        # -------------------------

        if current_money_cp < item_cost_cp:

            messagebox.showwarning(
                "Not Enough Money",
                f"You cannot afford {item_name}.\n\nCost: {cost_text}"
            )

            return

        # -------------------------
        # PURCHASE
        # -------------------------

        new_total = current_money_cp - item_cost_cp

        set_wallet_from_cp(new_total)

        backpack_items.append(item_name)

        refresh_backpack()

    def get_equipped_armor_style(name):
        return ARMOR_STYLE.get(name)

    def recalc_ac():
        if ac_var is not None:
            ac_var.set(str(calculate_ac(equipped_items)))

    def equip_item(event=None):
        sel = backpack_listbox.curselection()
        if not sel:
            return

        item = backpack_items[sel[0]]
        style = ARMOR_STYLE.get(item)

        # Auto-swap body armor
        if style in ("Light", "Medium", "Heavy"):
            current_body = [
                e for e in equipped_items
                if ARMOR_STYLE.get(e) in ("Light", "Medium", "Heavy")
            ]
            for old in current_body:
                equipped_items.remove(old)
                backpack_items.append(old)

        # Auto-swap off-hand
        elif style == "Off-Hand":
            current_offhand = [
                e for e in equipped_items
                if ARMOR_STYLE.get(e) == "Off-Hand"
            ]
            for old in current_offhand:
                equipped_items.remove(old)
                backpack_items.append(old)

        backpack_items.pop(sel[0])
        equipped_items.append(item)
        refresh_backpack()
        refresh_equipped()
        recalc_ac()
        refresh_weapon_dropdowns()
    def unequip_item(event=None):
        sel = equipped_listbox.curselection()
        if not sel:
            return

        item = equipped_items.pop(sel[0])
        backpack_items.append(item)
        refresh_backpack()
        refresh_equipped()
        recalc_ac()
        refresh_weapon_dropdowns()
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
    build_wallet(right_col)
    def add_to_backpack_from_anywhere(item_name):
        """Callback function for adding items from NPC shops."""
        backpack_items.append(item_name)
        refresh_backpack()
        print(f"🎒 Added '{item_name}' to backpack via callback")

    # Store this callback somewhere accessible
    global add_to_backpack_callback
    add_to_backpack_callback = add_to_backpack_from_anywhere

def build_wallet(parent):

    wallet_frame = ttk.LabelFrame(parent, text=" Wallet ")
    wallet_frame.pack(fill="x", padx=6, pady=6)

    # -------------------------
    # TOP ROW - CURRENT MONEY
    # -------------------------

    top = tk.Frame(wallet_frame)
    top.pack(fill="x", pady=4)

    for coin in ["PP", "GP", "EP", "SP", "CP"]:

        cell = tk.Frame(top)
        cell.pack(side="left", padx=6)

        tk.Label(
            cell,
            text=coin,
            font=("Arial", 8, "bold")
        ).pack()

        tk.Entry(
            cell,
            textvariable=wallet_vars[coin],
            width=6,
            justify="center",
            font=("Arial", 11, "bold")
        ).pack()

    # -------------------------
    # BOTTOM ROW - MODIFY MONEY
    # -------------------------

    controls = tk.Frame(wallet_frame)
    controls.pack(fill="x", pady=6)

    amount_var = tk.IntVar(value=0)
    coin_var = tk.StringVar(value="GP")

    tk.Entry(
        controls,
        textvariable=amount_var,
        width=8,
        justify="center"
    ).pack(side="left", padx=4)

    ttk.Combobox(
        controls,
        textvariable=coin_var,
        values=["PP", "GP", "EP", "SP", "CP"],
        width=4,
        state="readonly"
    ).pack(side="left", padx=4)

    def modify_money(delta):
        try:
            current = wallet_vars[coin_var.get()].get()
            amount = amount_var.get()

            new_total = max(0, current + (amount * delta))

            wallet_vars[coin_var.get()].set(new_total)

        except:
            pass

    tk.Button(
        controls,
        text="+",
        bg="#27ae60",
        fg="white",
        command=lambda: modify_money(1)
    ).pack(side="left", padx=4)

    tk.Button(
        controls,
        text="-",
        bg="#c0392b",
        fg="white",
        command=lambda: modify_money(-1)
    ).pack(side="left", padx=4)
def wallet_to_cp():

    total = 0

    for coin, var in wallet_vars.items():
        total += var.get() * COIN_VALUES[coin]

    return total
def set_wallet_from_cp(total_cp):

    total_cp = max(0, total_cp)

    pp = total_cp // 1000
    total_cp %= 1000

    gp = total_cp // 100
    total_cp %= 100

    ep = total_cp // 50
    total_cp %= 50

    sp = total_cp // 10
    total_cp %= 10

    cp = total_cp

    wallet_vars["PP"].set(pp)
    wallet_vars["GP"].set(gp)
    wallet_vars["EP"].set(ep)
    wallet_vars["SP"].set(sp)
    wallet_vars["CP"].set(cp)
def parse_cost(cost_text):

    if pd.isna(cost_text):
        return 0

    text = str(cost_text).strip().lower()

    if text in ["—", "-", ""]:
        return 0

    try:
        parts = text.split()

        amount = float(parts[0])
        coin = parts[1].upper()

        return int(amount * COIN_VALUES[coin])

    except:
        return 0

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
# BACKGROUND TAB
# ---------------------------------------------------------------------------
def build_background_tab(parent):
    global skills_lbl, languages_lbl, equipment_lbl
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True, padx=8, pady=8)

# ==================================================
# TOP — Background Feature
# ==================================================

    feature_frame = ttk.LabelFrame(frame, text=" Background Feature ")
    feature_frame.pack(fill="x", pady=(0,6))

    bg_feature_title = tk.Label(
        feature_frame,
        text="Feature Name",
        font=("Arial", 11, "bold"),
        anchor="w"
    )
    bg_feature_title.pack(fill="x", padx=6, pady=(4,0))

    bg_feature_text = tk.Text(feature_frame, height=6, wrap="word")
    bg_feature_text.pack(fill="x", padx=6, pady=6)

# ==================================================
# MIDDLE — Backstory + Personality Column
# ==================================================

    middle_frame = tk.Frame(frame)
    middle_frame.pack(fill="both", expand=True)
# --------------------------
# LEFT — Backstory
# --------------------------

    backstory_frame = ttk.LabelFrame(middle_frame, text=" Backstory ")
    backstory_frame.pack(side="left", fill="both", expand=True, padx=(0,6))

    backstory_text = tk.Text(
        backstory_frame,
        wrap="word"
    )
    backstory_text.pack(fill="both", expand=True, padx=6, pady=6)
# --------------------------
# RIGHT — Personality Blocks
# --------------------------

    right_col = tk.Frame(middle_frame)
    right_col.pack(side="left", fill="y")
    def small_box(parent, title, height=4):
        lf = ttk.LabelFrame(parent, text=f" {title} ")
        lf.pack(fill="x", pady=(0,6))

        txt = tk.Text(lf, height=height, wrap="word", width=28)
        txt.pack(fill="both", expand=True, padx=4, pady=4)

        return txt

    traits_text = small_box(right_col, "Traits")
    ideals_text = small_box(right_col, "Ideals")
    bonds_text  = small_box(right_col, "Bonds")
    flaws_text  = small_box(right_col, "Flaws")


# ==================================================
# BOTTOM — Background Mechanics
# ==================================================

    bottom_frame = ttk.LabelFrame(frame, text=" Background Details ")
    bottom_frame.pack(fill="x", pady=(6,0))
    skills_lbl = tk.Label(bottom_frame, text="Skills: —", anchor="s", justify="left")
    skills_lbl.grid(row=3, column=0, sticky="s", padx=8, pady=4)

    languages_lbl = tk.Label(bottom_frame, text="Languages: —", anchor="s", justify="left")
    languages_lbl.grid(row=3, column=1, sticky="s", padx=8, pady=4)

    equipment_lbl = tk.Label(bottom_frame, text="Equipment: —", anchor="s", justify="left")
    equipment_lbl.grid(row=3, column=2, sticky="s", padx=8, pady=4)
# ---------------------------------------------------------------------------
# MAIN WINDOW
# ---------------------------------------------------------------------------

def build_ui():
    global sheet_tab, spells_tab, vtt_tab, npc_tab, vtt_instance, player_vtt_built
    
    # Create notebook
    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True)
    
    # Build character tab
    sheet_tab = tk.Frame(notebook)
    notebook.add(sheet_tab, text="Character")
    build_identity(sheet_tab)
    
    # Build spells tab
    spells_tab = tk.Frame(notebook)
    notebook.add(spells_tab, text="Spells")
    build_spell_panel(spells_tab)
    
    # Build VTT tab (once)
    vtt_tab = tk.Frame(notebook)
    notebook.add(vtt_tab, text="VTT")
    vtt_instance, vtt_canvas = build_vtt_tab(vtt_tab, npc_mode)  # Pass npc_mode if needed
    player_vtt_built = True
    
    # Build NPC tab
    npc_tab = tk.Frame(notebook)
    notebook.add(npc_tab, text="NPC Mode")
    npc_mode = NPCMode(npc_tab, lambda data: vtt_instance.create_token_from_npc(data) if vtt_instance else None)
    
    # Store notebook reference
    root.notebook = notebook


root = tk.Tk()
global advantage_var
advantage_var = tk.IntVar(value=0)
root.title("JD&D Tracker")
mode_var = tk.StringVar(root, value="PLAYER")
root.geometry("1050x900")
#root.state("zoomed")
root.resizable(True, True)
#root.minsize(900, 700)

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

tk.Button(top_bar, text="💾 Save",
          command=save_character).pack(side="right", padx=5)

tk.Button(top_bar, text="📂 Load",
          command=load_character).pack(side="right", padx=5)
level_var = tk.StringVar(value="1")
sb_vars   = {s: tk.StringVar(value="10")
             for s in ["STR","DEX","CON","INT","WIS","CHA"]}
count_label = None
def on_wizard_complete(result):
    if not messagebox.askyesno("Apply Character",
            "This will overwrite the current character sheet.\nContinue?"):
        return

    # --- Identity ---
    name_entry.delete(0, tk.END)
    name_entry.insert(0, result["name"])
    sex_entry.delete(0, tk.END)
    sex_entry.insert(0, result["sex"])

    # --- Dropdowns ---
    race_var.set(result["race"])
    background_var.set(result["background"])
    class1_var.set(result["class_name"])
    class1_level_var.set(result["level"])
    subs = SUBCLASS_MAP.get(result["class_name"], [])
    subclass1_box.config(values=subs)
    subclass1_var.set(result["subclass"])

    # --- Ability scores ---
    for stat, val in result["scores"].items():
        if stat in sb_vars:
            sb_vars[stat].set(str(val))

    # --- Speed ---
    if speed_var is not None:
        speed_var.set(result.get("speed", "30"))

    # --- HP ---
    max_hp = result.get("max_hp", 10)
    try:
        hp_vars["max"].set(str(max_hp))
        hp_vars["cur"].set(str(max_hp))
        hp_vars["tmp"].set("0")
    except Exception as e:
        print(f"HP apply error: {e}")

    # --- Saving throw proficiencies ---
    st_map = {
        "strength":"STR","str":"STR",
        "dexterity":"DEX","dex":"DEX",
        "constitution":"CON","con":"CON",
        "intelligence":"INT","int":"INT",
        "wisdom":"WIS","wis":"WIS",
        "charisma":"CHA","cha":"CHA",
    }
    # Clear existing first
    for var in save_prof_vars.values():
        var.set(False)
    for token in result.get("saving_throws","").replace(","," ").split():
        stat = st_map.get(token.strip().lower())
        if stat and stat in save_prof_vars:
            save_prof_vars[stat].set(True)

    # --- Skill proficiencies ---
    if hasattr(tk, "_skill_name_map"):
        for skill in result.get("all_skill_profs", []):
            if skill in tk._skill_name_map:
                tk._skill_name_map[skill].set(True)

    # --- Proficiency & Training block ---
    try:
        prof_content = (
            f"Armor:\n{result.get('armor_pro','—') or '—'}\n\n"
            f"Weapons:\n{result.get('weapon_pro','—') or '—'}\n\n"
            f"Tools:\n{result.get('tool_pro','—') or '—'}\n\n"
            f"Languages:\n{result.get('race_languages','—') or '—'}\n\n"
            f"Saving Throws:\n{result.get('saving_throws','—') or '—'}\n\n"
            f"Senses:\n—\n\n"
            f"Other:\n{result.get('racial_bonus','—') or '—'}\n"
        )
        prof_text.config(state="normal")
        prof_text.delete("1.0", tk.END)
        prof_text.insert("1.0", prof_content)
        prof_text.config(state="disabled")
    except Exception as e:
        print(f"prof_text error: {e}")

    # --- Background tab ---
    if skills_lbl is not None:
        skills_lbl.config(
            text=f"Skills: {', '.join(result['bg_skills']) or '—'}"
        )
    if languages_lbl is not None:
        languages_lbl.config(
            text=f"Languages: {result.get('bg_languages','—')}"
        )
    if equipment_lbl is not None:
        equipment_lbl.config(
            text=f"Equipment: {result.get('bg_equipment','—')}"
        )

    # --- Refresh all UI ---
    for stat in sb_vars:
        on_stat_change(stat)
    refresh_feats()
    update_all_skills()
    refresh_spells()
    update_hit_dice()
    refresh_spell_slots()
    messagebox.showinfo("Character Created",
        f"✨ {result['name']} is ready for adventure!")
def launch_wizard():
    if messagebox.askyesno("New Character",
            "Starting a new character will clear the current sheet.\n"
            "Any unsaved progress will be lost.\n\nContinue?"):
        open_character_wizard(
            root,
            DATA_FILE,
            CLASS_INFO,
            SUBCLASS_MAP,
            on_wizard_complete
        )

tk.Button(top_bar, text="✨ New Character",
          command=launch_wizard,
          bg="#8e44ad", fg="white",
          font=("Arial", 9, "bold")).pack(side="left", padx=6)

wallet_vars = {
    "PP": tk.IntVar(value=0),
    "GP": tk.IntVar(value=0),
    "EP": tk.IntVar(value=0),
    "SP": tk.IntVar(value=0),
    "CP": tk.IntVar(value=0),
}

# FRAMES
sheet_outer = tk.Frame(notebook)
sheet_outer.pack_propagate(False)

spells_tab = tk.Frame(notebook)
inventory_tab = tk.Frame(notebook)
feats_tab = tk.Frame(notebook)
#items_tab = tk.Frame(notebook)
background_tab = tk.Frame(notebook)
notes_tab = tk.Frame(notebook)
pets_tab = tk.Frame(notebook)
npc_tab = ttk.Frame(notebook)
hb_tab = tk.Frame(notebook)
vtt_tab = ttk.Frame(notebook)
player_vtt_tab = ttk.Frame(notebook)

notebook.add(sheet_outer, text="Character")
# Canvas + Scrollbar
sheet_canvas = tk.Canvas(sheet_outer)
sheet_scroll = ttk.Scrollbar(
    sheet_outer,
    orient="vertical",
    command=sheet_canvas.yview
)
sheet_canvas.configure(
    yscrollcommand=sheet_scroll.set
)
sheet_scroll.pack(side="right", fill="y")
sheet_canvas.pack(side="left", fill="both", expand=True)

sheet_tab = tk.Frame(sheet_canvas)
sheet_window = sheet_canvas.create_window(
    (0, 0),
    window=sheet_tab,
    anchor="nw"
)
def update_scroll_region(event):
    sheet_canvas.configure(
        scrollregion=sheet_canvas.bbox("all")
    )
sheet_tab.bind("<Configure>", update_scroll_region)

def resize_canvas(event):
    sheet_canvas.itemconfig(
        sheet_window,
        width=event.width
    )
sheet_canvas.bind("<Configure>", resize_canvas)
def _on_mousewheel(event):
    sheet_canvas.yview_scroll(
        int(-1 * (event.delta / 120)),
        "units"
    )

sheet_canvas.bind_all("<MouseWheel>", _on_mousewheel)

def on_spawn_npc(npc_data):
    """Receive NPC data from NPC mode and create VTT token."""
    if vtt_instance and hasattr(vtt_instance, 'create_token_from_npc'):
        vtt_instance.create_token_from_npc(npc_data)
    else:
        print(f"VTT token creation not implemented yet. NPC data: {npc_data}")

notebook.add(spells_tab, text="Spells")
notebook.add(inventory_tab,  text="Equipment")
notebook.add(feats_tab,  text="Class Feats")
notebook.add(background_tab,  text="Background")
#notebook.add(items_tab,  text="Items")
notebook.add(notes_tab, text="Notes")
notebook.add(pets_tab, text="Companions")
notebook.add(hb_tab, text="Homebrew")
notebook.add(player_vtt_tab, text="Battle Map")
notebook.add(npc_tab, text="NPC Mode")
notebook.add(vtt_tab, text="DMT")



simtower = SimTowerApp(hb_tab)

def build_spell_slot_panel(parent):

    global spell_slot_vars
build_spell_panel(spells_tab)
def get_player_gold_cp():
    """Return player's total gold in copper pieces."""
    return wallet_to_cp()
def deduct_player_gold_cp(amount_cp):
    """Deduct amount in copper pieces from wallet."""
    current_cp = wallet_to_cp()
    new_cp = max(0, current_cp - amount_cp)
    set_wallet_from_cp(new_cp)
    return new_cp
def add_player_gold_cp(amount_cp):
    """Add amount in copper pieces to wallet."""
    current_cp = wallet_to_cp()
    new_cp = current_cp + amount_cp
    set_wallet_from_cp(new_cp)
    return new_cp

build_inventory_tab(inventory_tab)

def temp_callback(data):
    print("VTT not ready yet, NPC data:", data)

vtt_instance, vtt_canvas = build_vtt_tab(vtt_tab, None)
if add_to_backpack_callback is not None:
    vtt_instance.set_add_to_backpack_callback(add_to_backpack_callback)
    print("✅ Backpack callback connected")
else:
    print("❌ add_to_backpack_callback is None — Equipment tab may not have been built yet")
vtt_instance.set_wallet_functions(get_player_gold_cp, deduct_player_gold_cp, add_player_gold_cp)
npc_mode = NPCMode(npc_tab, lambda data: vtt_instance.create_token_from_npc(data))
vtt_instance.npc_mode = npc_mode
vtt_instance.npc_ai_tick()
print("✅ VTT and NPC Mode connected, AI tick started")

def get_current_character_name():
    return name_entry.get()  # or whatever variable stores character name
build_player_vtt_tab(player_vtt_tab, get_current_character_name)


build_background_tab(background_tab)
build_notes_tab(notes_tab, lambda: name_entry.get())
build_companions_tab(pets_tab)

##CHARACTER
#
build_feats_tab(feats_tab)
build_identity(sheet_tab)
update_spell_slots()
build_save_load(sheet_tab)

mid = tk.Frame(sheet_tab)
mid.pack(fill="x", padx=10, pady=5)
#build_utility(mid)
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

#----------------------------------
root.mainloop()
