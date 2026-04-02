"""
log_window.py — Fenêtre de log toggleable (Toplevel tkinter).

- Affiche les LogRecords déposés dans src.logger.log_queue
- Couleurs par niveau : DEBUG (gris), INFO (blanc), WARNING (orange), ERROR (rouge)
- Toggle via LogWindow.toggle() ou le bouton "Logs" de la fenêtre principale
- Mémorise visibilité + géométrie dans les préférences
"""

import logging
import tkinter as tk
from tkinter import ttk, font as tkfont

from src import logger as app_logger
from src import preferences as prefs_mod

# Mapping niveau → tag couleur
_LEVEL_TAGS = {
    logging.DEBUG:    ("DEBUG",   "#888888"),
    logging.INFO:     ("INFO",    "#d4d4d4"),
    logging.WARNING:  ("WARNING", "#ce9178"),
    logging.ERROR:    ("ERROR",   "#f44747"),
    logging.CRITICAL: ("CRITICAL","#f44747"),
}

_MAX_LINES = 2000  # Nombre max de lignes conservées dans le widget


class LogWindow:
    def __init__(self, parent: tk.Tk, prefs: dict) -> None:
        self._parent = parent
        self._prefs = prefs
        self._win: tk.Toplevel | None = None
        self._text: tk.Text | None = None
        self._autoscroll_var: tk.BooleanVar | None = None
        self._on_visibility_change: "callable | None" = None

        # Démarrer la boucle de lecture de la queue
        self._poll()

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def set_on_visibility_change(self, callback: "callable") -> None:
        """Enregistre un callback(is_visible: bool) appelé à chaque show/hide."""
        self._on_visibility_change = callback

    def toggle(self) -> None:
        if self._win and self._win.winfo_exists():
            self._hide()
        else:
            self._show()

    def is_visible(self) -> bool:
        return bool(self._win and self._win.winfo_exists())

    def restore_from_prefs(self) -> None:
        """Appelé au démarrage : ouvre la fenêtre si elle était visible."""
        if prefs_mod.get(self._prefs, "log_window", "visible", default=False):
            self._show()

    # ------------------------------------------------------------------
    # Affichage / masquage
    # ------------------------------------------------------------------

    def _show(self) -> None:
        if self._win and self._win.winfo_exists():
            self._win.lift()
            return

        self._win = tk.Toplevel(self._parent)
        self._win.title("Logs — assu_genfli")
        self._win.protocol("WM_DELETE_WINDOW", self._hide)

        geometry = prefs_mod.get(self._prefs, "log_window", "geometry", default="700x350+120+120")
        self._win.geometry(geometry)

        self._build_ui()
        prefs_mod.set_(self._prefs, "log_window", "visible", value=True)
        if self._on_visibility_change:
            self._on_visibility_change(True)

    def _hide(self) -> None:
        if self._win and self._win.winfo_exists():
            self._save_geometry()
            self._win.destroy()
        self._win = None
        self._text = None
        prefs_mod.set_(self._prefs, "log_window", "visible", value=False)
        if self._on_visibility_change:
            self._on_visibility_change(False)

    # ------------------------------------------------------------------
    # Construction du widget
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        win = self._win

        win.columnconfigure(0, weight=1)
        win.rowconfigure(0, weight=1)

        # --- Zone texte + scrollbar ---
        frame = ttk.Frame(win)
        frame.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        mono = tkfont.Font(family="Consolas", size=9)
        self._text = tk.Text(
            frame,
            state="disabled",
            wrap="none",
            background="#1e1e1e",
            foreground="#d4d4d4",
            insertbackground="#d4d4d4",
            font=mono,
            relief="flat",
        )
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self._text.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=self._text.xview)
        self._text.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self._text.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        # Définir les tags de couleur
        for level, (tag, color) in _LEVEL_TAGS.items():
            self._text.tag_configure(tag, foreground=color)

        # --- Barre de contrôle en bas ---
        bar = ttk.Frame(win)
        bar.grid(row=1, column=0, sticky="ew", padx=4, pady=(0, 4))

        self._autoscroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Auto-scroll", variable=self._autoscroll_var).pack(side="left")
        ttk.Button(bar, text="Effacer", command=self._clear).pack(side="left", padx=6)
        ttk.Button(bar, text="Fermer", command=self._hide).pack(side="right")

    # ------------------------------------------------------------------
    # Lecture de la queue et affichage
    # ------------------------------------------------------------------

    def _poll(self) -> None:
        """Lit la queue de logs toutes les 100 ms depuis le thread principal."""
        try:
            while True:
                record = app_logger.log_queue.get_nowait()
                self._append(record)
        except Exception:
            pass
        # Replanifier dans la boucle tkinter principale
        self._parent.after(100, self._poll)

    def _append(self, record: logging.LogRecord) -> None:
        if not (self._text and self._win and self._win.winfo_exists()):
            return

        tag, _ = _LEVEL_TAGS.get(record.levelno, ("INFO", "#d4d4d4"))
        msg = record.getMessage()
        line = f"{self._format_time(record)}  {record.levelname:<8}  {msg}\n"

        self._text.configure(state="normal")

        # Limiter le nombre de lignes
        current_lines = int(self._text.index("end-1c").split(".")[0])
        if current_lines > _MAX_LINES:
            self._text.delete("1.0", f"{current_lines - _MAX_LINES}.0")

        self._text.insert("end", line, tag)
        self._text.configure(state="disabled")

        if self._autoscroll_var and self._autoscroll_var.get():
            self._text.see("end")

    @staticmethod
    def _format_time(record: logging.LogRecord) -> str:
        import time
        return time.strftime("%H:%M:%S", time.localtime(record.created))

    def _clear(self) -> None:
        if self._text:
            self._text.configure(state="normal")
            self._text.delete("1.0", "end")
            self._text.configure(state="disabled")

    # ------------------------------------------------------------------
    # Sauvegarde géométrie
    # ------------------------------------------------------------------

    def _save_geometry(self) -> None:
        if self._win and self._win.winfo_exists():
            prefs_mod.set_(self._prefs, "log_window", "geometry", value=self._win.geometry())
