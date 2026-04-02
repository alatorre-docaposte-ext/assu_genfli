"""
project_dialog.py — Boîte de dialogue création/modification d'un projet.

Champs : Nom, Code, Dépôt WFD, Dépôt RESS, Dépôt DEV, Répertoire, Dépôt distant.
Retourne le dict projet dans self.result (None si Annuler).
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Définition des champs : (clé, libellé, placeholder, browse_dir?)
_FIELDS = [
    ("name",          "Nom :",           "Alias du projet",                 False),
    ("code",          "Code :",          "Code du projet (ex: SGK)",         False),
    ("depot_wfd",     "Dépôt WFD :",     "/chemin/du/dépôt/WFD",            True),
    ("depot_ress",    "Dépôt RESS :",    "/chemin/du/dépôt/RESS",           True),
    ("depot_dev",     "Dépôt DEV :",     "/chemin/du/dépôt/DEV",            True),
    ("repertoire",    "Répertoire :",    "/chemin/local/du/dépôt",           True),
    ("depot_distant", "Dépôt distant :", "https://github.com/org/repo.git",  False),
]


class ProjectDialog:
    """
    Usage :
        dlg = ProjectDialog(parent, title="Nouveau projet")
        if dlg.result:
            ...  # dict avec les champs du projet
    """

    def __init__(self, parent: tk.Toplevel, title: str = "Projet", data: dict | None = None) -> None:
        self.result: dict | None = None
        self._data = data or {}
        self._entries: dict[str, ttk.Entry] = {}

        self._win = tk.Toplevel(parent)
        self._win.title(title)
        self._win.resizable(False, False)
        self._win.grab_set()
        self._win.transient(parent)

        self._build()
        self._win.wait_window()

    # ------------------------------------------------------------------

    def _build(self) -> None:
        win = self._win
        win.columnconfigure(1, weight=1)

        for row, (key, label, placeholder, has_browse) in enumerate(_FIELDS):
            ttk.Label(win, text=label, width=15, anchor="e").grid(
                row=row, column=0, sticky="e", padx=(10, 4), pady=5
            )

            entry = ttk.Entry(win, width=46)
            entry.grid(
                row=row, column=1,
                sticky="ew",
                padx=(0, 4 if has_browse else 10),
                pady=5,
            )
            self._entries[key] = entry

            # Placeholder visuel
            saved_val = self._data.get(key, "")
            if saved_val:
                entry.insert(0, saved_val)
                entry.config(foreground="")
            else:
                entry.insert(0, placeholder)
                entry.config(foreground="gray")
                entry.bind("<FocusIn>",  lambda e, ent=entry, ph=placeholder: self._on_focus_in(ent, ph))
                entry.bind("<FocusOut>", lambda e, ent=entry, ph=placeholder: self._on_focus_out(ent, ph))

            if has_browse:
                ttk.Button(
                    win, text="Browse...",
                    command=lambda ent=entry: self._browse_dir(ent),
                ).grid(row=row, column=2, padx=(0, 10), pady=5)

        # Boutons
        btn_frame = ttk.Frame(win)
        btn_frame.grid(
            row=len(_FIELDS), column=0, columnspan=3,
            sticky="e", padx=10, pady=(8, 10),
        )
        ttk.Button(btn_frame, text="OK",      width=10, command=self._ok).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Annuler", width=10, command=self._win.destroy).pack(side="left", padx=4)

    # ------------------------------------------------------------------

    @staticmethod
    def _on_focus_in(entry: ttk.Entry, placeholder: str) -> None:
        if entry.get() == placeholder:
            entry.delete(0, "end")
            entry.config(foreground="")

    @staticmethod
    def _on_focus_out(entry: ttk.Entry, placeholder: str) -> None:
        if not entry.get():
            entry.insert(0, placeholder)
            entry.config(foreground="gray")

    def _browse_dir(self, entry: ttk.Entry) -> None:
        current = entry.get()
        initial = current if os.path.isdir(current) else os.path.expanduser("~")
        path = filedialog.askdirectory(parent=self._win, initialdir=initial)
        if path:
            entry.delete(0, "end")
            entry.insert(0, path)
            entry.config(foreground="")

    # ------------------------------------------------------------------

    def _ok(self) -> None:
        placeholders = {key: ph for key, _, ph, _ in _FIELDS}
        result = {}
        for key, entry in self._entries.items():
            val = entry.get()
            result[key] = "" if val == placeholders.get(key) else val

        if not result.get("name"):
            messagebox.showwarning("Champ requis", "Le nom du projet est obligatoire.", parent=self._win)
            return

        self.result = result
        self._win.destroy()
