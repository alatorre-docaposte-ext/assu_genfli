"""
screen3_files.py — Écran 3 : sélection des livrables.

Pipeline :
  1. À l'arrivée, calcule le diff Git dans un thread :
       tag courant WFD (screen 2)  vs.  tag n-1 WFD  (trouvé automatiquement)
       tag courant RESS             vs.  tag n-1 RESS
  2. Affiche la liste (Treeview) avec cases à cocher
  3. Permet l'ajout manuel de fichiers
  4. on_next() → sauvegarde la liste sélectionnée dans session["files"]
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk, simpledialog

from src import git_ops
from src import preferences as prefs_mod
from src.logger import get_logger

log = get_logger()

_CHECKED   = "☑"
_UNCHECKED = "☐"

_STATUS_TEXT = {
    "A": "Ajouté",
    "M": "Modifié",
    "D": "Supprimé",
    "R": "Renommé",
    "T": "Type",
    "-": "Manuel",
}


class Screen3Files:
    title = "Sélection des livrables"

    def __init__(self, parent: ttk.Frame, wizard) -> None:
        self._wizard = wizard
        self._prefs  = wizard.get_prefs()
        self._files: list[dict] = []      # {checked, status, path, source}
        self._queue: queue.Queue = queue.Queue()

        self.frame = ttk.Frame(parent)
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(1, weight=1)

        self._build()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        # --- Toolbar ---
        tb = ttk.Frame(self.frame)
        tb.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        ttk.Button(tb, text="☑ Tout cocher",    command=self._check_all).pack(side="left", padx=(0, 4))
        ttk.Button(tb, text="☐ Tout décocher",  command=self._uncheck_all).pack(side="left", padx=(0, 4))
        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(tb, text="+ Ajouter",        command=self._add_manual).pack(side="left", padx=(0, 4))
        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(tb, text="⟳ Recalculer",     command=self._start_diff).pack(side="left")

        self._diff_status_var = tk.StringVar(value="")
        ttk.Label(tb, textvariable=self._diff_status_var, foreground="gray").pack(side="right", padx=4)

        # --- Treeview + scrollbars ---
        tree_frame = ttk.Frame(self.frame)
        tree_frame.grid(row=1, column=0, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        self._tree = ttk.Treeview(
            tree_frame,
            columns=("check", "status", "path", "source"),
            show="headings",
            selectmode="browse",
        )
        self._tree.heading("check",  text="")
        self._tree.heading("status", text="Statut",  anchor="center")
        self._tree.heading("path",   text="Fichier",  anchor="w")
        self._tree.heading("source", text="Dépôt",   anchor="center")

        self._tree.column("check",  width=30,  minwidth=30,  stretch=False, anchor="center")
        self._tree.column("status", width=95,  minwidth=70,  stretch=False, anchor="center")
        self._tree.column("path",   width=480, minwidth=200, stretch=True,  anchor="w")
        self._tree.column("source", width=70,  minwidth=60,  stretch=False, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",   command=self._tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self._tree.bind("<Button-1>", self._on_click)

        # Couleurs par statut
        self._tree.tag_configure("added",    foreground="#007700")
        self._tree.tag_configure("modified", foreground="#0055cc")
        self._tree.tag_configure("deleted",  foreground="#cc0000")
        self._tree.tag_configure("manual",   foreground="#886600")
        self._tree.tag_configure("unchecked",foreground="#aaaaaa")

        # --- Résumé bas de page ---
        self._summary_var = tk.StringVar(value="Aucun fichier")
        ttk.Label(self.frame, textvariable=self._summary_var, foreground="gray").grid(
            row=2, column=0, sticky="w", pady=(4, 0)
        )

        self._wizard.set_next_enabled(False)

    # ------------------------------------------------------------------
    # Hook wizard
    # ------------------------------------------------------------------

    def on_shown(self) -> None:
        session_files = prefs_mod.get(self._prefs, "session", "files", default=None)
        if session_files is not None:
            # Restaurer la liste de session (revenir en arrière)
            self._files = session_files
            self._refresh_tree()
            self._update_summary()
        else:
            self._start_diff()

    # ------------------------------------------------------------------
    # Diff Git (thread)
    # ------------------------------------------------------------------

    def _start_diff(self) -> None:
        self._diff_status_var.set("Calcul en cours…")
        self._wizard.set_next_enabled(False)

        # On garde les fichiers ajoutés manuellement
        self._files = [f for f in self._files if f.get("source") == "Manuel"]
        self._refresh_tree()

        delivery = prefs_mod.get(self._prefs, "session", "delivery", default={})
        project  = prefs_mod.get(self._prefs, "session", "selected_project", default={})

        tag_wfd  = delivery.get("tag_wfd", "")
        tag_ress = delivery.get("tag_ressources", "") or delivery.get("tag_ress", "")

        tasks: list[tuple[str, str, str]] = []
        if tag_wfd  and project.get("depot_wfd_local"):
            tasks.append(("WFD",  project["depot_wfd_local"],  tag_wfd))
        if tag_ress and project.get("depot_ress_local"):
            tasks.append(("RESS", project["depot_ress_local"], tag_ress))

        if not tasks:
            self._diff_status_var.set("⚠ Aucun dépôt / tag configuré (vérifiez l'étape 2)")
            self._wizard.set_next_enabled(True)
            return

        def run() -> None:
            for source, repo_path, current_tag in tasks:
                # 1. Calcul du diff (fichiers à cocher)
                self._queue.put(("status", f"[{source}] Recherche du tag précédent…"))
                prev_tag = git_ops.find_previous_tag(repo_path, current_tag)
                diff_paths: set[tuple[str, str]] = set()   # {(change_type, path)}
                if prev_tag:
                    self._queue.put(("status", f"[{source}] Diff {prev_tag} → {current_tag}…"))
                    try:
                        for change_type, path in git_ops.get_diff_files(repo_path, prev_tag, current_tag):
                            diff_paths.add((change_type, path))
                    except Exception as exc:
                        self._queue.put(("warning", f"[{source}] Diff impossible : {exc}"))
                else:
                    self._queue.put(("warning", f"[{source}] Pas de tag précédent, tous les fichiers décochés"))

                # 2. Tous les fichiers du dépôt au tag courant
                self._queue.put(("status", f"[{source}] Lecture de tous les fichiers au tag {current_tag}…"))
                try:
                    all_paths = git_ops.get_all_files_at_tag(repo_path, current_tag)
                    diff_path_set = {p for _, p in diff_paths}
                    diff_type_map = {p: ct for ct, p in diff_paths}
                    for path in all_paths:
                        in_diff   = path in diff_path_set
                        ct        = diff_type_map.get(path, "M")
                        self._queue.put(("file", (source, ct, path, in_diff)))
                    # Fichiers supprimés (dans le diff mais absents du tree = 'D')
                    for ct, path in diff_paths:
                        if ct == "D":
                            self._queue.put(("file", (source, "D", path, True)))
                except Exception as exc:
                    self._queue.put(("warning", f"[{source}] Lecture impossible : {exc}"))

            self._queue.put(("done", None))

        threading.Thread(target=run, daemon=True).start()
        self._poll()

    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "status":
                    self._diff_status_var.set(payload)
                elif kind == "warning":
                    self._diff_status_var.set(payload)
                    log.warning(payload)
                elif kind == "file":
                    source, change_type, path, checked = payload
                    existing = {f["path"] for f in self._files}
                    if path not in existing:
                        self._files.append({
                            "checked": checked,
                            "status":  change_type,
                            "path":    path,
                            "source":  source,
                        })
                    self._refresh_tree()
                elif kind == "done":
                    total = len(self._files)
                    self._diff_status_var.set(f"Diff terminé — {total} fichier(s) trouvé(s)")
                    self._update_summary()
                    return
        except queue.Empty:
            pass
        self.frame.after(50, self._poll)

    # ------------------------------------------------------------------
    # Treeview
    # ------------------------------------------------------------------

    def _refresh_tree(self) -> None:
        self._tree.delete(*self._tree.get_children())
        for i, f in enumerate(self._files):
            chk    = _CHECKED if f["checked"] else _UNCHECKED
            label  = _STATUS_TEXT.get(f["status"], f["status"])
            source = f.get("source", "?")

            if not f["checked"]:
                tag = "unchecked"
            elif source == "Manuel":
                tag = "manual"
            else:
                tag = {"A": "added", "M": "modified", "D": "deleted"}.get(f["status"], "modified")

            self._tree.insert("", "end", iid=str(i),
                              values=(chk, label, f["path"], source),
                              tags=(tag,))

    def _on_click(self, event: tk.Event) -> None:
        if self._tree.identify_region(event.x, event.y) != "cell":
            return
        if self._tree.identify_column(event.x) != "#1":
            return
        iid = self._tree.identify_row(event.y)
        if not iid:
            return
        idx = int(iid)
        self._files[idx]["checked"] = not self._files[idx]["checked"]
        self._refresh_tree()
        self._update_summary()

    def _update_summary(self) -> None:
        total    = len(self._files)
        selected = sum(1 for f in self._files if f["checked"])
        self._summary_var.set(f"{selected} fichier(s) sélectionné(s) sur {total}")
        self._wizard.set_next_enabled(selected > 0)

    # ------------------------------------------------------------------
    # Toolbar
    # ------------------------------------------------------------------

    def _check_all(self) -> None:
        for f in self._files:
            f["checked"] = True
        self._refresh_tree()
        self._update_summary()

    def _uncheck_all(self) -> None:
        for f in self._files:
            f["checked"] = False
        self._refresh_tree()
        self._update_summary()

    def _add_manual(self) -> None:
        path = simpledialog.askstring(
            "Ajouter un fichier",
            "Chemin du fichier (relatif ou absolu) :",
            parent=self.frame,
        )
        if not path:
            return
        path = path.strip()
        if path in {f["path"] for f in self._files}:
            return
        self._files.append({"checked": True, "status": "-", "path": path, "source": "Manuel"})
        self._refresh_tree()
        self._update_summary()

    # ------------------------------------------------------------------
    # Hook on_next
    # ------------------------------------------------------------------

    def on_next(self) -> bool:
        selected = [f for f in self._files if f["checked"]]
        if not selected:
            return False
        prefs_mod.set_(self._prefs, "session", "files", value=selected)
        log.info(f"Livrables : {len(selected)} fichier(s) sélectionné(s)")
        return True
