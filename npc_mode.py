import tkinter as tk
from tkinter import ttk




# Globals
npc_state = {
    "hp": 40,
    "max_hp": 100,
    "enemy_adjacent": True,
    "enemy_visible": True,
    "ally_downed": False,
}

# Start
class NPCMode:

    def __init__(self, parent):

        self.parent = parent

        self.npcs = {}

        self.selected_npc = None

        self.build_ui()

    # -------------------------------------------------
    # UI
    # -------------------------------------------------

    def build_ui(self):

        main = tk.Frame(self.parent)
        main.pack(fill="both", expand=True)

    # -------------------------
    # AI LOG
    # -------------------------

        global action_log

        log_frame = ttk.LabelFrame(root, text=" AI Log ")
        log_frame.pack(fill="both", expand=True, padx=6, pady=6)

        action_log = tk.Text(
            log_frame,
            height=8,
            bg="#101010",
            fg="#00ff99",
            font=("Courier", 10)
        )

        action_log.pack(fill="both", expand=True)

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
        self.speed_var = tk.IntVar(value=30)

        self.make_stat_row(stats_frame, "Name", self.name_var)
        self.make_stat_row(stats_frame, "HP", self.hp_var)
        self.make_stat_row(stats_frame, "AC", self.ac_var)
        self.make_stat_row(stats_frame, "Speed", self.speed_var)

        # =============================================
        # RIGHT PANEL
        # =============================================

        gambit_frame = ttk.LabelFrame(root, text=" Gambits ")
        gambit_frame.pack(fill="both", expand=True, padx=6, pady=6)

        gambit_listbox = tk.Listbox(
            gambit_frame,
            height=10,
            width=50
        )

        gambit_listbox.pack(fill="both", expand=True, padx=4, pady=4)

        button_row = tk.Frame(gambit_frame)
        button_row.pack(fill="x")

        tk.Button(
            button_row,
            text="+ Add Gambit",
            command=open_gambit_editor
        ).pack(side="left", padx=4)

        tk.Button(
            button_row,
            text="- Remove",
            command=remove_gambit
        ).pack(side="left", padx=4)
        tk.Button(
            button_row,
            text="▶ Run Gambits",
            command=run_gambits
        ).pack(side="left", padx=4)
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
    def perform_action(gambit):

        global action_log

        action = gambit["action"]
        target = gambit["target"]

        result = f"{action} -> {target}"

        action_log.insert(
            tk.END,
            result + "\n"
        )

        action_log.see(tk.END)
    def run_gambits():

        for gambit in npc_gambits:

            if evaluate_condition(gambit):

                perform_action(gambit)

                break
    # -------------------------------------------------
    # NPC FUNCTIONS
    # -------------------------------------------------

    def add_npc(self):

        name = f"NPC {len(self.npcs)+1}"

        self.npcs[name] = {
            "hp": 10,
            "ac": 10,
            "speed": 30,
            "gambits": []
        }

        self.refresh_npc_list()

    def remove_npc(self):

        sel = self.npc_listbox.curselection()

        if not sel:
            return

        name = self.npc_listbox.get(sel[0])

        del self.npcs[name]

        self.refresh_npc_list()

    def refresh_npc_list(self):

        self.npc_listbox.delete(0, tk.END)

        for npc in self.npcs:
            self.npc_listbox.insert(tk.END, npc)

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

    # -------------------------------------------------
    # GAMBITS
    # -------------------------------------------------

    def add_gambit(self):

        if not self.selected_npc:
            return

        gambit = "IF Enemy Adjacent → Attack"

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

def open_gambit_editor():

    popup = tk.Toplevel()

    popup.title("Add Gambit")
    popup.geometry("300x220")

    # -------------------------
    # DROPDOWN DATA
    # -------------------------

    conditions = [
        "Enemy Adjacent",
        "Enemy Visible",
        "HP Below 50%",
        "Ally Downed",
    ]

    actions = [
        "Attack",
        "Move Toward",
        "Retreat",
        "Defend",
    ]

    targets = [
        "Nearest",
        "Lowest HP",
        "Self",
        "Random",
    ]

    # -------------------------
    # VARIABLES
    # -------------------------

    condition_var = tk.StringVar(value=conditions[0])
    action_var = tk.StringVar(value=actions[0])
    target_var = tk.StringVar(value=targets[0])

    # -------------------------
    # UI
    # -------------------------

    tk.Label(popup, text="Condition").pack(pady=(8,0))

    ttk.Combobox(
        popup,
        textvariable=condition_var,
        values=conditions,
        state="readonly"
    ).pack()

    tk.Label(popup, text="Action").pack(pady=(8,0))

    ttk.Combobox(
        popup,
        textvariable=action_var,
        values=actions,
        state="readonly"
    ).pack()

    tk.Label(popup, text="Target").pack(pady=(8,0))

    ttk.Combobox(
        popup,
        textvariable=target_var,
        values=targets,
        state="readonly"
    ).pack()