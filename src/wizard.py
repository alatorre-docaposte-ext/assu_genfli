"""
wizard.py — Infrastructure du wizard multi-étapes.

La fenêtre principale contient :
  ┌──────────────────────────────────────────┐
  │  En-tête : titre de l'étape + numéro     │
  ├──────────────────────────────────────────┤
  │                                          │
  │   Zone contenu (frame swappable)         │
  │                                          │
  ├──────────────────────────────────────────┤
  │  [ Précédent ]          [ Suivant / OK ] │
  └──────────────────────────────────────────┘

Utilisation :
    wizard = Wizard(parent, prefs)
    wizard.register(ScreenClass)   # dans l'ordre
    wizard.start()
"""

import tkinter as tk
from tkinter import ttk


class Wizard:
    def __init__(self, parent: tk.Tk, prefs: dict) -> None:
        self._parent = parent
        self._prefs = prefs
        self._steps: list = []          # liste de classes d'écran
        self._current: int = 0
        self._active_screen = None      # instance de l'écran courant

        self._build()

    # ------------------------------------------------------------------
    # Construction du squelette
    # ------------------------------------------------------------------

    def _build(self) -> None:
        parent = self._parent
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # --- En-tête ---
        self._header_frame = ttk.Frame(parent, relief="flat")
        self._header_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        self._header_frame.columnconfigure(0, weight=1)

        self._title_var = tk.StringVar()
        self._step_var  = tk.StringVar()

        ttk.Label(
            self._header_frame,
            textvariable=self._title_var,
            font=("Segoe UI", 13, "bold"),
            padding=(16, 10, 16, 2),
        ).grid(row=0, column=0, sticky="w")

        ttk.Label(
            self._header_frame,
            textvariable=self._step_var,
            foreground="gray",
            padding=(16, 0, 16, 8),
        ).grid(row=1, column=0, sticky="w")

        ttk.Separator(parent, orient="horizontal").grid(row=0, column=0, sticky="sew", padx=0)

        # --- Zone contenu ---
        self._content = ttk.Frame(parent)
        self._content.grid(row=1, column=0, sticky="nsew", padx=16, pady=10)
        self._content.columnconfigure(0, weight=1)
        self._content.rowconfigure(0, weight=1)

        # --- Pied de page ---
        ttk.Separator(parent, orient="horizontal").grid(row=2, column=0, sticky="new")
        footer = ttk.Frame(parent)
        footer.grid(row=3, column=0, sticky="ew", padx=16, pady=8)

        self._btn_prev = ttk.Button(footer, text="◀  Précédent", command=self._go_prev, state="disabled")
        self._btn_prev.pack(side="left")

        self._btn_next = ttk.Button(footer, text="Suivant  ▶", command=self._go_next, state="disabled")
        self._btn_next.pack(side="right")

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def register(self, screen_class) -> None:
        """Enregistre un écran (classe). L'ordre d'appel définit l'ordre du wizard."""
        self._steps.append(screen_class)

    def start(self) -> None:
        """Affiche le premier écran."""
        self._show(0)

    def get_prefs(self) -> dict:
        return self._prefs

    def set_next_enabled(self, enabled: bool) -> None:
        """Appelé par l'écran courant pour activer/désactiver le bouton Suivant."""
        self._btn_next.config(state="normal" if enabled else "disabled")

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _go_prev(self) -> None:
        if self._current > 0:
            self._show(self._current - 1)

    def _go_next(self) -> None:
        if self._active_screen and hasattr(self._active_screen, "on_next"):
            if not self._active_screen.on_next():
                return  # L'écran bloque la navigation
        if self._current < len(self._steps) - 1:
            self._show(self._current + 1)

    def _show(self, index: int) -> None:
        # Détruire l'écran courant
        for widget in self._content.winfo_children():
            widget.destroy()
        self._active_screen = None

        self._current = index
        screen_class = self._steps[index]

        # Instancier le nouvel écran dans la zone contenu
        self._active_screen = screen_class(self._content, self)
        self._active_screen.frame.grid(row=0, column=0, sticky="nsew")

        # Mettre à jour l'en-tête
        self._title_var.set(self._active_screen.title)
        self._step_var.set(f"Étape {index + 1} sur {len(self._steps)}")

        # Boutons de navigation
        self._btn_prev.config(state="normal" if index > 0 else "disabled")
        # Suivant : désactivé par défaut, l'écran appelle set_next_enabled()
        last = (index == len(self._steps) - 1)
        self._btn_next.config(
            text="Terminer" if last else "Suivant  ▶",
            state="disabled",
        )
        # Laisser l'écran décider de l'état initial du bouton Suivant
        if hasattr(self._active_screen, "on_shown"):
            self._active_screen.on_shown()
