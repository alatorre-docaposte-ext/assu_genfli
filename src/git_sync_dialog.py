"""
git_sync_dialog.py — Fenêtre modale de synchronisation Git.

Affiche :
  - Le nom du projet et les dépôts à synchroniser
  - Un champ passphrase SSH (optionnel, si méthode SSH + clé configurée)
  - Boutons "Synchroniser" / "Fermer"
  - Barre de progression + statuts par dépôt pendant l'opération
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk

from src import git_ops, preferences as prefs_mod
from src.logger import get_logger

log = get_logger()


class GitSyncDialog:
    """
    Usage :
        GitSyncDialog(parent, project, prefs)

    Se bloque via wait_window jusqu'à la fermeture.
    """

    def __init__(self, parent: tk.Misc, project: dict, prefs: dict) -> None:
        self._project = project
        self._prefs   = prefs
        self._queue: queue.Queue = queue.Queue()
        self._running = False

        self._win = tk.Toplevel(parent)
        self._win.title("Synchronisation Git")
        self._win.grab_set()
        self._win.transient(parent)
        self._win.resizable(False, False)
        self._win.protocol("WM_DELETE_WINDOW", self._on_close)

        self._repos = self._list_repos()

        if not self._repos:
            self._win.destroy()
            return

        self._build()
        self._win.wait_window()

    # ------------------------------------------------------------------
    # Repos à synchroniser
    # ------------------------------------------------------------------

    def _list_repos(self) -> list[tuple[str, str, str]]:
        """Retourne [(label, local_path, remote_url)] pour les dépôts configurés."""
        p = self._project
        repos = []
        if p.get("depot_wfd_local") and p.get("depot_wfd_distant"):
            repos.append(("WFD",  p["depot_wfd_local"],  p["depot_wfd_distant"]))
        if p.get("depot_ress_local") and p.get("depot_ress_distant"):
            repos.append(("RESS", p["depot_ress_local"], p["depot_ress_distant"]))
        if p.get("depot_dev") and p.get("depot_dev_distant"):
            repos.append(("DEV",  p["depot_dev"],        p["depot_dev_distant"]))
        return repos

    # ------------------------------------------------------------------
    # Construction de la fenêtre
    # ------------------------------------------------------------------

    def _build(self) -> None:
        win = self._win
        win.columnconfigure(0, weight=1)

        # Titre + projet
        ttk.Label(
            win,
            text="Synchronisation des dépôts Git",
            font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=0, padx=16, pady=(12, 2), sticky="w")

        ttk.Label(
            win,
            text=f"Projet : {self._project.get('name', '?')}",
            foreground="gray",
        ).grid(row=1, column=0, padx=16, pady=(0, 10), sticky="w")

        # Zone statuts
        status_frame = ttk.Frame(win)
        status_frame.grid(row=2, column=0, padx=16, sticky="ew")
        status_frame.columnconfigure(1, weight=1)

        self._status_vars: dict[str, tk.StringVar] = {}
        for i, (label, _, _) in enumerate(self._repos):
            ttk.Label(status_frame, text=f"{label} :", anchor="e", width=8).grid(
                row=i, column=0, sticky="e", padx=(0, 8), pady=3,
            )
            var = tk.StringVar(value="—")
            self._status_vars[label] = var
            ttk.Label(status_frame, textvariable=var, anchor="w", width=50).grid(
                row=i, column=1, sticky="w", pady=3,
            )

        # Passphrase SSH (visible seulement si SSH + clé configurée)
        self._passphrase_var: tk.StringVar | None = None
        conn_method = self._project.get("conn_method", "SSH")
        ssh_key     = prefs_mod.get(self._prefs, "git", "ssh_key", default="").strip()

        if conn_method == "SSH" and ssh_key:
            sep = ttk.Separator(win, orient="horizontal")
            sep.grid(row=3, column=0, padx=16, pady=(10, 6), sticky="ew")

            pass_frame = ttk.Frame(win)
            pass_frame.grid(row=4, column=0, padx=16, sticky="ew")
            pass_frame.columnconfigure(1, weight=1)

            ttk.Label(pass_frame, text="Passphrase SSH :").grid(row=0, column=0, sticky="e", padx=(0, 8))
            self._passphrase_var = tk.StringVar()
            ttk.Entry(pass_frame, textvariable=self._passphrase_var, show="●", width=30).grid(
                row=0, column=1, sticky="w",
            )
            ttk.Label(pass_frame, text="(laissez vide si la clé n'en a pas)", foreground="gray").grid(
                row=1, column=0, columnspan=2, sticky="w", pady=(2, 0),
            )
            next_row = 5
        else:
            next_row = 3

        # Barre de progression (cachée au départ)
        self._progress = ttk.Progressbar(win, mode="indeterminate", length=380)
        self._progress.grid(row=next_row, column=0, padx=16, pady=(10, 4), sticky="ew")
        self._progress.grid_remove()   # masquée jusqu'au démarrage

        # Boutons
        btn_frame = ttk.Frame(win)
        btn_frame.grid(row=next_row + 1, column=0, padx=16, pady=(4, 12), sticky="e")

        self._btn_sync  = ttk.Button(btn_frame, text="Synchroniser", command=self._start)
        self._btn_sync.pack(side="left", padx=(0, 6))
        self._btn_close = ttk.Button(btn_frame, text="Fermer", command=self._on_close)
        self._btn_close.pack(side="left")

        win.update_idletasks()

    # ------------------------------------------------------------------
    # Lancement du thread
    # ------------------------------------------------------------------

    def _start(self) -> None:
        if self._running:
            return
        self._running = True
        self._btn_sync.config(state="disabled")
        self._btn_close.config(state="disabled")
        self._win.protocol("WM_DELETE_WINDOW", lambda: None)   # bloquer fermeture

        for var in self._status_vars.values():
            var.set("En attente…")

        self._progress.grid()
        self._progress.start(15)

        passphrase = self._passphrase_var.get() if self._passphrase_var else ""

        def run() -> None:
            conn_method = self._project.get("conn_method", "SSH")
            for label, local_path, remote_url in self._repos:
                git_ops.sync_repo(
                    label=label,
                    local_path=local_path,
                    remote_url=remote_url,
                    conn_method=conn_method,
                    prefs=self._prefs,
                    on_progress=lambda lbl, msg: self._queue.put(("progress", lbl, msg)),
                    passphrase=passphrase,
                )
            self._queue.put(("done", None, None))

        threading.Thread(target=run, daemon=True).start()
        self._poll()

    def _poll(self) -> None:
        try:
            while True:
                kind, label, msg = self._queue.get_nowait()
                if kind == "progress":
                    if label in self._status_vars:
                        self._status_vars[label].set(msg)
                    log.info(f"Git [{label}] : {msg}")
                elif kind == "done":
                    self._on_done()
                    return
        except queue.Empty:
            pass
        self._win.after(50, self._poll)

    # ------------------------------------------------------------------
    # Fin de synchronisation
    # ------------------------------------------------------------------

    def _on_done(self) -> None:
        self._running = False
        self._progress.stop()
        self._progress.config(mode="determinate", value=100)
        self._btn_close.config(state="normal")
        self._win.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self) -> None:
        if not self._running:
            self._win.destroy()
