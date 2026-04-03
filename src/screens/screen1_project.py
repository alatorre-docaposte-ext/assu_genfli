"""
screen1_project.py — Écran 1 du wizard : sélection du projet Git.

Affiche les projets configurés sous forme de tuiles cliquables.
Le bouton Suivant n'est activé qu'après sélection d'un projet.
"""

import tkinter as tk
from tkinter import ttk

from src import preferences as prefs_mod
from src.logger import get_logger

log = get_logger()

# Couleurs des tuiles
_COLOR_BG        = "#f0f0f0"
_COLOR_BG_HOVER  = "#e0e8f5"
_COLOR_BG_SEL    = "#0078d4"
_COLOR_FG_SEL    = "#ffffff"
_COLOR_FG        = "#1a1a1a"
_COLOR_FG_SUB    = "#555555"
_COLOR_BORDER    = "#c0c0c0"
_COLOR_BORDER_SEL= "#005fa3"


class Screen1Project:
    title = "Sélectionner le projet à livrer"

    def __init__(self, parent: ttk.Frame, wizard) -> None:
        self._wizard = wizard
        self._prefs  = wizard.get_prefs()
        self._selected_key: str | None = None   # clé unique = index stringifié
        self._cards: dict[str, dict]  = {}      # key → {frame, labels, data}

        self.frame = ttk.Frame(parent)
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(0, weight=1)

        self._build()

    # ------------------------------------------------------------------

    def _build(self) -> None:
        projects: list = prefs_mod.get(self._prefs, "projects", default=[])

        if not projects:
            self._build_empty()
        else:
            self._build_cards(projects)

    def _build_empty(self) -> None:
        f = ttk.Frame(self.frame)
        f.grid(row=0, column=0)

        ttk.Label(
            f,
            text="Aucun projet configuré.",
            font=("Segoe UI", 11),
        ).pack(pady=(40, 8))

        ttk.Label(
            f,
            text="Ajoutez un projet via  Fichier → Préférences → Projets.",
            foreground="gray",
        ).pack()

    def _build_cards(self, projects: list) -> None:
        # Conteneur scrollable
        container = ttk.Frame(self.frame)
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        canvas = tk.Canvas(container, highlightthickness=0, background="#ffffff")
        vsb    = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        inner = tk.Frame(canvas, background="#ffffff")
        inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.columnconfigure(0, weight=1)

        def _on_resize(event):
            canvas.itemconfig(inner_id, width=event.width)
        canvas.bind("<Configure>", _on_resize)

        def _on_scroll(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_scroll)

        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        for idx, project in enumerate(projects):
            key = str(idx)
            self._make_card(inner, key, project, row=idx)
            # _make_card remplit self._cards[key] avec le dict complet

    def _make_card(self, parent: tk.Frame, key: str, project: dict, row: int) -> tk.Frame:
        card = tk.Frame(
            parent,
            background=_COLOR_BG,
            highlightbackground=_COLOR_BORDER,
            highlightthickness=1,
            cursor="hand2",
        )
        card.grid(row=row, column=0, sticky="ew", padx=12, pady=6)
        card.columnconfigure(1, weight=1)

        # Indicateur de sélection (barre gauche colorée)
        indicator = tk.Frame(card, width=6, background=_COLOR_BG)
        indicator.grid(row=0, column=0, rowspan=3, sticky="ns", padx=(0, 10))

        # Nom du projet
        lbl_name = tk.Label(
            card, text=project.get("name", "—"),
            font=("Segoe UI", 11, "bold"),
            background=_COLOR_BG, foreground=_COLOR_FG,
            anchor="w",
        )
        lbl_name.grid(row=0, column=1, sticky="w", padx=(0, 12), pady=(10, 2))

        # Code
        code_text = f"Code : {project.get('code', '—')}"
        lbl_code = tk.Label(
            card, text=code_text,
            font=("Segoe UI", 9),
            background=_COLOR_BG, foreground=_COLOR_FG_SUB,
            anchor="w",
        )
        lbl_code.grid(row=1, column=1, sticky="w", padx=(0, 12))

        # Dépôts
        depots = "  |  ".join(filter(None, [
            project.get("depot_wfd_distant") or project.get("depot_wfd_local", ""),
            project.get("depot_ress_distant") or project.get("depot_ress_local", ""),
        ]))
        lbl_depot = tk.Label(
            card, text=depots or "—",
            font=("Segoe UI", 8),
            background=_COLOR_BG, foreground=_COLOR_FG_SUB,
            anchor="w",
        )
        lbl_depot.grid(row=2, column=1, sticky="w", padx=(0, 12), pady=(2, 10))

        # Connexion badge
        conn = project.get("conn_method", "SSH")
        lbl_conn = tk.Label(
            card, text=conn,
            font=("Segoe UI", 8, "bold"),
            background="#ddeeff", foreground="#004499",
            padx=6, pady=2,
        )
        lbl_conn.grid(row=0, column=2, padx=(0, 12), pady=(10, 2), sticky="ne")

        widgets = [card, indicator, lbl_name, lbl_code, lbl_depot, lbl_conn]

        def _select(e=None):
            self._select_card(key)

        def _hover_in(e=None):
            if key != self._selected_key:
                self._set_card_style(key, hovered=True)

        def _hover_out(e=None):
            if key != self._selected_key:
                self._set_card_style(key, hovered=False)

        for w in widgets:
            w.bind("<Button-1>",    _select)
            w.bind("<Enter>",       _hover_in)
            w.bind("<Leave>",       _hover_out)

        self._cards[key] = {
            "frame": card,
            "indicator": indicator,
            "labels": [lbl_name, lbl_code, lbl_depot],
            "data": project,
        }
        return card

    # ------------------------------------------------------------------

    def _select_card(self, key: str) -> None:
        # Désélectionner l'ancien
        if self._selected_key and self._selected_key in self._cards:
            self._set_card_style(self._selected_key, selected=False)

        self._selected_key = key
        self._set_card_style(key, selected=True)

        project = self._cards[key]["data"]
        log.info(f"Projet sélectionné : {project.get('name')} [{project.get('code')}]")

        # Stocker dans les prefs de session pour les écrans suivants
        prefs_mod.set_(self._prefs, "session", "selected_project", value=project)

        self._wizard.set_next_enabled(True)

    def _set_card_style(self, key: str, selected: bool = False, hovered: bool = False) -> None:
        card_info = self._cards.get(key)
        if not card_info:
            return
        card      = card_info["frame"]
        indicator = card_info["indicator"]
        labels    = card_info["labels"]

        if selected:
            bg         = _COLOR_BG_SEL
            fg         = _COLOR_FG_SEL
            ind_color  = _COLOR_BORDER_SEL
            border     = _COLOR_BORDER_SEL
        elif hovered:
            bg         = _COLOR_BG_HOVER
            fg         = _COLOR_FG
            ind_color  = "#0078d4"
            border     = "#0078d4"
        else:
            bg         = _COLOR_BG
            fg         = _COLOR_FG
            ind_color  = _COLOR_BG
            border     = _COLOR_BORDER

        card.config(background=bg, highlightbackground=border)
        indicator.config(background=ind_color)
        for lbl in labels:
            lbl.config(background=bg, foreground=fg if lbl == labels[0] else (fg if selected else _COLOR_FG_SUB))

    # ------------------------------------------------------------------
    # Hooks wizard
    # ------------------------------------------------------------------

    def on_shown(self) -> None:
        """Appelé quand l'écran devient visible. Pré-sélectionner si déjà choisi."""
        existing = prefs_mod.get(self._prefs, "session", "selected_project")
        if existing:
            # Retrouver la carte correspondante
            for key, card_info in self._cards.items():
                if card_info["data"].get("name") == existing.get("name"):
                    self._select_card(key)
                    return
        self._wizard.set_next_enabled(False)

    def on_next(self) -> bool:
        """Retourne True si la navigation peut continuer."""
        if not self._selected_key:
            return False
        return True
