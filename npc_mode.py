import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import random
import json
import os

# Gambit condition library
GAMBIT_LIBRARY = [
    {"name": "Wander", "condition": "always", "action": "move_random"},
    {"name": "Pause", "condition": "always", "action": "wait"},
    {"name": "Attack if Adjacent", "condition": "enemy_adjacent", "action": "attack"},
    {"name": "Flee if Low HP", "condition": "hp_below_30", "action": "flee"},
    {"name": "Patrol", "condition": "always", "action": "patrol"},
    {"name": "Defend Ally", "condition": "ally_attacked", "action": "guard"},
    {"name": "Heal if Low", "condition": "hp_below_50", "action": "heal_self"},

    {"name": "Shop", "condition": "player_interact", "action": "open_shop"},
]


class NPCMode:
    def __init__(self, parent, vtt_callback):
        """
        parent: tkinter parent widget (the NPC tab)
        vtt_callback: function to call when spawning token (receives npc_data dict)
        """
        self.parent = parent
        self.vtt_callback = vtt_callback
        self.npcs = {}  # name -> npc_data dict
        self.selected_npc = None
        self.gambits = []
        
        # Track listbox index to NPC name mapping
        self.listbox_index_to_name = {}
        self.build_ui()
        self.load_npcs()

    # -------------------------------------------------
    # UI BUILD
    # -------------------------------------------------
    def build_ui(self):
        main = tk.Frame(self.parent)
        main.pack(fill="both", expand=True)

        # ========== LEFT PANEL ==========
        left = tk.Frame(main)
        left.pack(side="left", fill="y", padx=5, pady=5)

        tk.Label(left, text="NPCs", font=("Arial", 11, "bold")).pack()

        self.npc_listbox = tk.Listbox(left, width=24, height=25)
        self.npc_listbox.pack(fill="y", expand=True)
        self.npc_listbox.bind("<<ListboxSelect>>", self.load_selected_npc)

        tk.Button(left, text="+ Add NPC", command=self.add_npc).pack(fill="x", pady=2)
        tk.Button(left, text="- Remove NPC", command=self.remove_npc).pack(fill="x")

        # ========== CENTER PANEL ==========
        center = tk.Frame(main)
        center.pack(side="left", fill="both", expand=True, padx=5)

        stats_frame = ttk.LabelFrame(center, text=" NPC Sheet ")
        stats_frame.pack(fill="x", pady=4)

        self.name_var = tk.StringVar()
        self.hp_var = tk.IntVar(value=10)
        self.hp_max_var = tk.IntVar(value=10)
        self.ac_var = tk.IntVar(value=10)
        self.speed_var = tk.IntVar(value=300)

        self.make_stat_row(stats_frame, "Name", self.name_var)
        self.make_stat_row(stats_frame, "HP", self.hp_var)
        self.make_stat_row(stats_frame, "Max HP", self.hp_max_var)
        self.make_stat_row(stats_frame, "AC", self.ac_var)
        self.make_stat_row(stats_frame, "Speed (ft)", self.speed_var)

        # Stats grid (STR, DEX, CON, INT, WIS, CHA)
        ability_frame = ttk.LabelFrame(center, text=" Ability Scores ")
        ability_frame.pack(fill="x", pady=4)

        self.stat_vars = {}
        stats = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
        for i, stat in enumerate(stats):
            row = tk.Frame(ability_frame)
            row.grid(row=i // 3, column=(i % 3) * 2, padx=5, pady=2, sticky="w")
            tk.Label(row, text=stat, width=5).pack(side="left")
            var = tk.IntVar(value=10)
            self.stat_vars[stat] = var
            tk.Entry(row, textvariable=var, width=4).pack(side="left", padx=2)

        # ========== RIGHT PANEL ==========
        right = tk.Frame(main)
        right.pack(side="left", fill="both", padx=5, pady=5)

        gambit_frame = ttk.LabelFrame(right, text=" Gambits ")
        gambit_frame.pack(fill="both", expand=True)

        self.gambit_listbox = tk.Listbox(gambit_frame, width=40, height=15)
        self.gambit_listbox.pack(fill="both", expand=True, pady=4)

        # Gambit picker (dropdown)
        pick_frame = tk.Frame(gambit_frame)
        pick_frame.pack(fill="x", pady=2)

        self.gambit_var = tk.StringVar()
        gambit_names = [g["name"] for g in GAMBIT_LIBRARY]
        gambit_dropdown = ttk.Combobox(pick_frame, textvariable=self.gambit_var, 
                                        values=gambit_names, state="readonly", width=25)
        gambit_dropdown.pack(side="left", padx=2)
        gambit_dropdown.set("Select Gambit")

        tk.Button(pick_frame, text="+ Add", command=self.add_gambit).pack(side="left", padx=2)
        tk.Button(pick_frame, text="- Remove", command=self.remove_gambit).pack(side="left", padx=2)

        # ========== SHOP SECTION ==========
        shop_frame = ttk.LabelFrame(right, text=" 🛒 Shop Settings (Merchants) ")
        shop_frame.pack(fill="x", pady=5)

        # Shop inventory dropdown
        tk.Label(shop_frame, text="Shop Inventory:").pack(anchor="w", padx=5, pady=(5,0))
        self.shop_inventory_var = tk.StringVar(value="")
        shop_combo = ttk.Combobox(shop_frame, textvariable=self.shop_inventory_var,
                                values=["", "shop_blacksmith", "shop_apothecary", 
                                        "shop_general", "shop_town1", "shop_armorer"],
                                state="readonly", width=25)
        shop_combo.pack(fill="x", padx=5, pady=2)

        # Shop greeting (optional)
        tk.Label(shop_frame, text="Shop Greeting:").pack(anchor="w", padx=5, pady=(5,0))
        self.shop_greeting_var = tk.StringVar(value="Welcome! Take a look at my wares.")
        tk.Entry(shop_frame, textvariable=self.shop_greeting_var, width=30).pack(fill="x", padx=5, pady=2)

        # Spawn button
        tk.Button(right, text="🎲 Spawn Token on VTT", command=self.spawn_token,
                  bg="#27ae60", fg="white", font=("Arial", 10, "bold")).pack(fill="x", pady=10)

        # Save/Load buttons
        btn_frame = tk.Frame(right)
        btn_frame.pack(fill="x", pady=5)
        tk.Button(btn_frame, text="💾 Save NPCs", command=self.save_npcs).pack(side="left", padx=2)
        tk.Button(btn_frame, text="📂 Load NPCs", command=self.load_npcs).pack(side="left", padx=2)

    def make_stat_row(self, parent, label, variable):
        row = tk.Frame(parent)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, width=10, anchor="w").pack(side="left")
        tk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)

    # -------------------------------------------------
    # NPC DATA MANAGEMENT
    # -------------------------------------------------
    def get_current_npc_data(self):
        """Build NPC dict from current UI values."""
        return {
            "name": self.name_var.get(),
            "hp": self.hp_var.get(),
            "max_hp": self.hp_max_var.get(),
            "ac": self.ac_var.get(),
            "speed": self.speed_var.get(),
            "stats": {stat: var.get() for stat, var in self.stat_vars.items()},
            "gambits": self.gambits[:],
            "shop_inventory": self.shop_inventory_var.get(),
            "shop_greeting": self.shop_greeting_var.get(),
        }

    def load_npc_to_ui(self, npc):
        """Populate UI from NPC dict."""
        self.name_var.set(npc.get("name", ""))
        self.hp_var.set(npc.get("hp", 10))
        self.hp_max_var.set(npc.get("max_hp", 10))
        self.ac_var.set(npc.get("ac", 10))
        self.speed_var.set(npc.get("speed", 300))
        
        self.shop_inventory_var.set(npc.get("shop_inventory", ""))
        self.shop_greeting_var.set(npc.get("shop_greeting", "Welcome! Take a look at my wares."))

        stats = npc.get("stats", {})
        for stat in self.stat_vars:
            self.stat_vars[stat].set(stats.get(stat, 10))

        self.gambits = npc.get("gambits", [])
        self.refresh_gambits()


    def refresh_npc_list(self):
        """Update listbox with all NPC names."""
        self.npc_listbox.delete(0, tk.END)
        self.listbox_index_to_name = {}
        for idx, name in enumerate(sorted(self.npcs.keys())):
            self.npc_listbox.insert(tk.END, name)
            self.listbox_index_to_name[idx] = name

    def refresh_gambits(self):
        """Update gambit listbox."""
        self.gambit_listbox.delete(0, tk.END)
        for g in self.gambits:
            self.gambit_listbox.insert(tk.END, g)

    # -------------------------------------------------
    # NPC CRUD
    # -------------------------------------------------
    def add_npc(self):
        """Create new NPC."""
        name = simpledialog.askstring("New NPC", "Enter NPC name:")
        if not name:
            return
        if name in self.npcs:
            messagebox.showerror("Error", f"NPC '{name}' already exists.")
            return

        self.npcs[name] = {
            "name": name,
            "hp": 10,
            "max_hp": 10,
            "ac": 10,
            "speed": 300,
            "stats": {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
            "gambits": ["Wander"],
            "shop_inventory": "",
            "shop_greeting": "Khajiit has wares, if you have coin",
        }
        self.refresh_npc_list()
        self.save_npcs()

    def remove_npc(self):
        """Delete selected NPC."""
        sel = self.npc_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        name = self.listbox_index_to_name.get(idx)
        if not name:
            return

        if messagebox.askyesno("Confirm Delete", f"Delete NPC '{name}'?"):
            del self.npcs[name]
            self.refresh_npc_list()
            self.save_npcs()
            self.name_var.set("")
            self.gambits = []
            self.refresh_gambits()

    def load_selected_npc(self, event=None):
        """Load selected NPC into UI."""
        sel = self.npc_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        name = self.listbox_index_to_name.get(idx)
        if not name or name not in self.npcs:
            return

        self.selected_npc = name
        self.load_npc_to_ui(self.npcs[name])

    # -------------------------------------------------
    # GAMBIT MANAGEMENT
    # -------------------------------------------------
    def add_gambit(self):
        """Add selected gambit to current NPC."""
        gambit_name = self.gambit_var.get()
        if not gambit_name or gambit_name == "Select Gambit":
            messagebox.showwarning("Warning", "Select a gambit from the dropdown.")
            return

        if self.selected_npc is None:
            messagebox.showwarning("Warning", "Select an NPC first.")
            return

        # Verify gambit exists
        gambit = next((g for g in GAMBIT_LIBRARY if g["name"] == gambit_name), None)
        if gambit:
            self.gambits.append(gambit_name)
            self.npcs[self.selected_npc]["gambits"] = self.gambits
            self.refresh_gambits()
            self.save_npcs()

    def remove_gambit(self):
        """Remove selected gambit from current NPC."""
        sel = self.gambit_listbox.curselection()
        if not sel or self.selected_npc is None:
            return

        idx = sel[0]
        del self.gambits[idx]
        self.npcs[self.selected_npc]["gambits"] = self.gambits
        self.refresh_gambits()
        self.save_npcs()

    # -------------------------------------------------
    # PERSISTENCE
    # -------------------------------------------------
    def save_npcs(self):
        """Save NPCs to JSON file."""
        try:
            with open("npcs.json", "w") as f:
                json.dump(self.npcs, f, indent=4)
            print("NPCs saved.")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    def load_npcs(self):
        """Load NPCs from JSON file."""
        try:
            if os.path.exists("npcs.json"):
                with open("npcs.json", "r") as f:
                    self.npcs = json.load(f)
            else:
                self.create_sample_npcs()
            self.refresh_npc_list()
            print(f"Loaded {len(self.npcs)} NPCs.")
        except Exception as e:
            messagebox.showerror("Load Error", str(e))
            self.npcs = {}
            self.create_sample_npcs()
            self.refresh_npc_list()

    def create_sample_npcs(self):
        """Create example NPCs for testing."""
        self.npcs = {
            "Goblin": {
                "name": "Goblin",
                "hp": 7,
                "max_hp": 7,
                "ac": 15,
                "speed": 30,  # Fixed from 300
                "stats": {"STR": 8, "DEX": 14, "CON": 10, "INT": 10, "WIS": 8, "CHA": 8},
                "gambits": ["Attack if Adjacent", "Flee if Low HP"],
                "shop_inventory": "",
                "shop_greeting": ""
            },
            "Wolf": {
                "name": "Wolf",
                "hp": 11,
                "max_hp": 11,
                "ac": 13,
                "speed": 40,  # Fixed from 400
                "stats": {"STR": 12, "DEX": 15, "CON": 12, "INT": 3, "WIS": 12, "CHA": 6},
                "gambits": ["Attack if Adjacent", "Wander"],
                "shop_inventory": "",
                "shop_greeting": ""
            },
            "Bandit Captain": {
                "name": "Bandit Captain",
                "hp": 65,
                "max_hp": 65,
                "ac": 15,
                "speed": 30,
                "stats": {"STR": 15, "DEX": 16, "CON": 14, "INT": 14, "WIS": 11, "CHA": 14},
                "gambits": ["Attack if Adjacent", "Defend Ally", "Patrol"],
                "shop_inventory": "",
                "shop_greeting": ""
            },
            "Grom the Blacksmith": {
                "name": "Grom the Blacksmith",
                "hp": 30,
                "max_hp": 30,
                "ac": 15,
                "speed": 30,
                "stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 10, "CHA": 12},
                "gambits": ["Shop"],
                "shop_inventory": "shop_blacksmith",
                "shop_greeting": "Welcome to my forge! Need any weapons or armor?"
            }
        }
    def get_npcs(self):
        """Return all NPCs dictionary for VTT AI access."""
        return self.npcs

    # ========== ADD THIS METHOD HERE ==========
    def spawn_token(self):
        """Spawn the selected NPC as a token on the VTT."""
        if self.selected_npc is None:
            messagebox.showwarning("Warning", "Select an NPC first.")
            return
        
        npc_data = self.npcs[self.selected_npc].copy()
        
        if self.vtt_callback:
            self.vtt_callback(npc_data)
            messagebox.showinfo("Spawned", f"'{npc_data['name']}' added to VTT!")
        else:
            messagebox.showwarning("No VTT", "VTT callback not set.")
