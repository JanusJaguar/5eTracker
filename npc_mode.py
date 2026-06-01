import tkinter as tk
from tkinter import ttk
import random
# Globals
npc_state = {
    "hp": 40,
    "max_hp": 100,
    "enemy_adjacent": True,
    "enemy_visible": True,
    "ally_downed": False,
}
GAMBIT_LIBRARY = [
    "wander",
    "pause",
    "attack_if_adjacent",
    "flee_if_low_hp",
    "patrol"
]


# Start
class NPCMode:

    def load_selected_npc(self, event=None):
        sel = self.npc_listbox.curselection()
        if not sel:
            return

        name = self.npc_listbox.get(sel[0])
        self.selected_npc = name

        npc = self.npcs[name]

        self.name_var.set(name)
        self.hp_var.set(npc["hp"])
        self.ac_var.set(npc["ac"])
        self.speed_var.set(npc["speed"])

        self.refresh_gambits()

    def __init__(self, parent, vtt):

        self.parent = parent
        self.vtt = vtt
        self.npcs = {}
        self.selected_npc = None
        self.build_ui()
        self.gambits = []
    # -------------------------------------------------
    # UI
    # -------------------------------------------------

    def build_ui(self):

        main = tk.Frame(self.parent)
        main.pack(fill="both", expand=True)

        # =============================================
        # LEFT PANEL
        # =============================================

        left = tk.Frame(main)
        left.pack(side="left", fill="y", padx=5, pady=5)

        tk.Label(
            left,
            text="NPCs",
            font=("Arial", 11, "bold")
        ).pack()

        self.npc_listbox = tk.Listbox(
            left,
            width=24,
            height=25
        )

        self.npc_listbox.pack(fill="y", expand=True)

        self.npc_listbox.bind(
            "<<ListboxSelect>>",
            self.load_selected_npc
        )

        tk.Button(
            left,
            text="+ Add NPC",
            command=self.add_npc
        ).pack(fill="x", pady=2)

        tk.Button(
            left,
            text="- Remove NPC",
            command=self.remove_npc
        ).pack(fill="x")

        # =============================================
        # CENTER PANEL
        # =============================================

        center = tk.Frame(main)
        center.pack(side="left", fill="both", expand=True, padx=5)

        stats_frame = ttk.LabelFrame(
            center,
            text=" NPC Sheet "
        )

        stats_frame.pack(fill="x", pady=4)

        self.name_var = tk.StringVar()
        self.hp_var = tk.IntVar(value=10)
        self.ac_var = tk.IntVar(value=10)
        self.speed_var = tk.IntVar(value=300)

        self.make_stat_row(stats_frame, "Name", self.name_var)
        self.make_stat_row(stats_frame, "HP", self.hp_var)
        self.make_stat_row(stats_frame, "AC", self.ac_var)
        self.make_stat_row(stats_frame, "Speed", self.speed_var)

        # =============================================
        # RIGHT PANEL
        # =============================================

        right = tk.Frame(main)
        right.pack(side="left", fill="both", padx=5, pady=5)

        gambit_frame = ttk.LabelFrame(
            right,
            text=" Gambits "
        )

        gambit_frame.pack(fill="both", expand=True)

        self.gambit_listbox = tk.Listbox(
            gambit_frame,
            width=40,
            height=20
        )

        self.gambit_listbox.pack(fill="both", expand=True, pady=4)

        tk.Button(
            gambit_frame,
            text="+ Add Gambit",
            command=self.add_gambit
        ).pack(fill="x", pady=2)

        tk.Button(
            gambit_frame,
            text="- Remove Gambit",
            command=self.remove_gambit
        ).pack(fill="x")

        self.gambit_entry = tk.Entry(gambit_frame)
        self.gambit_entry.pack(fill="x")

    # -------------------------------------------------
    # HELPERS
    # -------------------------------------------------

    def make_stat_row(self, parent, label, variable):

        row = tk.Frame(parent)
        row.pack(fill="x", pady=2)

        tk.Label(
            row,
            text=label,
            width=10,
            anchor="w"
        ).pack(side="left")

        tk.Entry(
            row,
            textvariable=variable
        ).pack(side="left", fill="x", expand=True)
    def evaluate_condition(gambit):

        condition = gambit["condition"]

        if condition == "Enemy Adjacent":
            return npc_state["enemy_adjacent"]

        elif condition == "Enemy Visible":
            return npc_state["enemy_visible"]

        elif condition == "HP Below 50%":
            return (
                npc_state["hp"]
                < npc_state["max_hp"] * 0.5
            )

        elif condition == "Ally Downed":
            return npc_state["ally_downed"]

        return False

    # -------------------------------------------------
    # NPC FUNCTIONS
    # -------------------------------------------------
    def get_npcs(self):
        return self.npcs
    def add_npc(self):
        name = f"NPC {len(self.npcs)+1}"
        self.npcs[name] = {
            "hp": 10,
            "ac": 10,
            "speed": 30,
            "gambits": []
        }

        self.refresh_npc_list()
        self.vtt.create_token(name)
    def remove_npc(self):

        sel = self.npc_listbox.curselection()

        if not sel:
            return

        index = sel[0]

        npc_id = self.listbox_index_to_id.get(index)

        if not npc_id:
            return

        del self.npcs[npc_id]

        self.refresh_npc_list()

    def refresh_npc_list(self):

        self.npc_listbox.delete(0, tk.END)

        for name in self.npcs:
            self.npc_listbox.insert(tk.END, name)



    # -------------------------------------------------
    # GAMBITS
    # -------------------------------------------------
    def add_gambit(self):

        if not self.selected_npc:
            return

        gambit = random.choice([
            "wander",
            "pause"
        ])

        self.npcs[self.selected_npc]["gambits"].append(gambit)

        self.refresh_gambits()
    def remove_gambit(self):

        sel = self.gambit_listbox.curselection()

        if not sel or not self.selected_npc:
            return

        idx = sel[0]

        del self.npcs[self.selected_npc]["gambits"][idx]

        self.refresh_gambits()

    def refresh_gambits(self):

        self.gambit_listbox.delete(0, tk.END)

        if not self.selected_npc:
            return

        for g in self.npcs[self.selected_npc]["gambits"]:
            self.gambit_listbox.insert(tk.END, g)

